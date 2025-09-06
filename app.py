import os
import re
import tempfile
import urllib.request
import urllib.parse
import json
import time
import logging
import sqlite3
import uuid
import random
import subprocess
import shutil
import smtplib
import ssl
from datetime import datetime, time as dtime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, send_file, make_response, session, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv, dotenv_values

# Ensure both names available for existing code
_shutil = shutil

# Load .env first
load_dotenv()

def _apply_r2_env_overrides():
    """Best-effort: load r2.env and apply safe overrides so R2 works in prod shells.
    Only sets env vars if they're not already set.
    """
    try:
        env_path = os.path.join(os.path.dirname(__file__), 'r2.env')
        if os.path.exists(env_path):
            vals = dotenv_values(env_path) or {}
            for k in ('R2_BUCKET_NAME','R2_ENDPOINT_URL','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','MEDIA_BASE_URL'):
                v = vals.get(k)
                if v is not None and not os.environ.get(k):
                    os.environ[k] = v
    except Exception:
        # Non-fatal; app can continue without R2
        pass

_apply_r2_env_overrides()

# Optional boto3 for R2 (S3-compatible)
try:
    import boto3
    from botocore.config import Config as BotoConfig
except Exception:
    boto3 = None

# Global in-memory cache for library listings
_LIB_CACHE: dict = {}

# --- SQLite user database helpers ---
def _db_path() -> str:
    # Allow relocating the DB out of the repo so deploys don't overwrite it
    p = os.environ.get('USERS_DB_PATH') or 'users.sqlite'
    try:
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return p

def get_db():
    db = sqlite3.connect(_db_path())
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)')
    # Add columns/indexes best-effort
    try:
        cols = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
        if 'full_name' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
            except Exception:
                pass
        if 'link_code' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN link_code TEXT')
                try:
                    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_link_code ON users(link_code)')
                except Exception:
                    pass
            except Exception:
                pass
        if 'email_verified' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0')
            except Exception:
                pass
        if 'verify_token' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN verify_token TEXT')
            except Exception:
                pass
        if 'verify_sent_at' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN verify_sent_at INTEGER')
            except Exception:
                pass
        if 'avatar' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN avatar TEXT')
            except Exception:
                pass
    except Exception:
        pass
    db.commit()

init_db()

# -------- Early logging to file for startup diagnostics (captures silent exits) --------
LOG_FILE = 'startup_log.txt'
try:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.debug('Logging initialized. Writing to %s', LOG_FILE)
except Exception as _log_e:
    # Fallback simple print if logging fails
    print(f'Logging setup failed: {_log_e}')

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Honor X-Forwarded-* from Cloudflare/NGINX and prefer HTTPS for URL generation
# Safe for local dev; only affects how Flask infers scheme/host/port
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config.update(
    PREFERRED_URL_SCHEME='https',
    SESSION_COOKIE_SECURE=False if os.environ.get('FLASK_ENV') == 'development' else True,
    SESSION_COOKIE_SAMESITE='Lax',
    # Set this in production to share login across subdomains: ".everydayadvertise.com"
    SESSION_COOKIE_DOMAIN=os.environ.get('SESSION_COOKIE_DOMAIN') or None,
)
print('DEBUG: app.py initialization start', flush=True)
logging.debug('App module import start')

# Build/version metadata (helps verify production is updated)
def _compute_build_stamp():
    try:
        # Prefer explicit environment value if provided by CI/deploy
        env = os.environ.get('APP_BUILD')
        if env:
            return str(env)
        # Fall back to mtime of this file for a stable, cache-busting stamp
        return str(int(os.path.getmtime(__file__)))
    except Exception:
        try:
            import time as _t
            return str(int(_t.time()))
        except Exception:
            return 'unknown'

BUILD_STAMP = _compute_build_stamp()

def _git_short_commit():
    try:
        # Try git if available in runtime; ignore failures silently
        out = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL)
        return out.decode('utf-8').strip()
    except Exception:
        return None
GIT_COMMIT = _git_short_commit()

# ---------------------- Auth setup (username/password + Google OAuth) ----------------------
from functools import wraps
try:
    from authlib.integrations.flask_client import OAuth
except Exception:
    OAuth = None

# Lightweight in-memory diagnostics buffers (safe, non-secret)
try:
    from collections import deque
    _ASSIGN_DENIES = deque(maxlen=50)
    _PRESIGNS = deque(maxlen=50)
except Exception:
    _ASSIGN_DENIES = []
    _PRESIGNS = []

    # ---------------------- Email sending helpers ----------------------
    def _mail_configured():
        return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_PORT') and os.environ.get('SMTP_USERNAME') and os.environ.get('SMTP_PASSWORD'))

    def send_email(to_addr: str, subject: str, body: str) -> bool:
        try:
            host = os.environ.get('SMTP_HOST')
            port = int(os.environ.get('SMTP_PORT') or '0')
            user = os.environ.get('SMTP_USERNAME')
            pwd = os.environ.get('SMTP_PASSWORD')
            use_tls = str(os.environ.get('SMTP_USE_TLS') or 'true').lower() != 'false'
            from_addr = os.environ.get('SMTP_FROM') or (user if user and '@' in user else f"no-reply@{(request.host or 'everydayadvertise.com').split(':')[0] if has_request_context() else 'everydayadvertise.com'}")
            if not (host and port and user and pwd and to_addr):
                raise RuntimeError('SMTP not fully configured')
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = from_addr
            msg['To'] = to_addr
            msg.set_content(body)
            if use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(host, port, timeout=15) as server:
                    server.starttls(context=context)
                    server.login(user, pwd)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=15) as server:
                    server.login(user, pwd)
                    server.send_message(msg)
            logging.info('send_email success to=%s via=%s:%s from=%s', to_addr, host, port, from_addr)
            return True
        except Exception as e:
            logging.warning('send_email failed: %s', e)
            return False

# Unconditional email helpers (override definitions above if they were in an exception path)
def _mail_configured():
    return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_PORT') and os.environ.get('SMTP_USERNAME') and os.environ.get('SMTP_PASSWORD'))

def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Send a plain-text email using SMTP settings from env.

    Env vars:
      - SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS
      - SMTP_TIMEOUT (optional, seconds; default 12)
    """
    phase = 'init'
    try:
        host = os.environ.get('SMTP_HOST')
        port = int(os.environ.get('SMTP_PORT') or '0')
        user = os.environ.get('SMTP_USERNAME')
        pwd = os.environ.get('SMTP_PASSWORD')
        use_tls = str(os.environ.get('SMTP_USE_TLS') or 'true').lower() != 'false'
        timeout = float(os.environ.get('SMTP_TIMEOUT') or 12)
        from_addr = os.environ.get('SMTP_FROM') or (user if user and '@' in user else f"no-reply@{(request.host or 'everydayadvertise.com').split(':')[0] if has_request_context() else 'everydayadvertise.com'}")
        if not (host and port and user and pwd and to_addr):
            raise RuntimeError('SMTP not fully configured')
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg.set_content(body)

        t0 = time.time()
        if use_tls:
            context = ssl.create_default_context()
            phase = 'connect'
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                try:
                    server.ehlo()
                except Exception:
                    pass
                phase = 'starttls'
                server.starttls(context=context)
                try:
                    server.ehlo()
                except Exception:
                    pass
                phase = 'login'
                server.login(user, pwd)
                phase = 'send'
                server.send_message(msg)
        else:
            phase = 'connect'
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                phase = 'login'
                server.login(user, pwd)
                phase = 'send'
                server.send_message(msg)
        dt = (time.time() - t0) * 1000.0
        logging.info('send_email success to=%s via=%s:%s tls=%s from=%s in %.0fms', to_addr, host, port, bool(use_tls), from_addr, dt)
        return True
    except smtplib.SMTPAuthenticationError as e:
        logging.warning('send_email auth failed at phase=%s: %s', phase, e)
        return False
    except (smtplib.SMTPException, TimeoutError, OSError) as e:
        logging.warning('send_email smtp error at phase=%s: %s', phase, e)
        return False
    except Exception as e:
        logging.warning('send_email failed at phase=%s: %s', phase, e)
        return False

    def _issue_verification_token(username: str) -> str:
        token = uuid.uuid4().hex + uuid.uuid4().hex
        try:
            db = get_db()
            db.execute('UPDATE users SET verify_token = ?, verify_sent_at = ? WHERE username = ?', (token, int(time.time()), (username or '').strip().lower()))
            db.commit()
        except Exception as e:
            logging.warning('Failed to persist verify token for %s: %s', username, e)
        return token

    def _send_verification_email(username: str):
        try:
            email = (username or '').strip().lower()
            token = _issue_verification_token(email)
            try:
                verify_url = url_for('verify_email', token=token, _external=True, _scheme='https')
            except Exception:
                host = 'https://api.everydayadvertise.com'
                verify_url = f"{host}/verify/{token}"
            subject = 'Verify your EverydayAdvertise account'
            body = f"Welcome! Please verify your email by clicking this link:\n\n{verify_url}\n\nThis link will confirm your account. If you did not sign up, please ignore this email."
            if _mail_configured():
                ok = send_email(email, subject, body)
                if ok:
                    logging.info('Verification email sent to %s', email)
                else:
                    logging.warning('SMTP send failed; printing verification URL: %s', verify_url)
            else:
                logging.warning('SMTP not configured; printing verification URL: %s', verify_url)
            return True
        except Exception as e:
            logging.warning('send_verification_email failed: %s', e)
            return False

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        # During tests, bypass auth requirements to keep unit tests simple
        try:
            if app.config.get('TESTING'):
                return view(*args, **kwargs)
        except Exception:
            pass
        if not session.get('user'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped

def _effective_admin_creds():
    exp_u = os.environ.get('ADMIN_USERNAME') or 'admin'
    exp_p = os.environ.get('ADMIN_PASSWORD')
    if not exp_p:
        # Dev fallback to avoid lockout if password not set; override via DEV_DEFAULT_PASSWORD
        dev_pwd = os.environ.get('DEV_DEFAULT_PASSWORD') or ('admin' if os.environ.get('FLASK_ENV') == 'development' else None)
        exp_p = dev_pwd
    return exp_u, exp_p

def _check_basic_auth(u: str|None, p: str|None) -> bool:
    exp_u, exp_p = _effective_admin_creds()
    if not exp_p:
        # No password set and not in development fallback -> always fail securely
        return False
    return (u or '') == exp_u and (p or '') == exp_p

oauth = None
if OAuth is not None:
    try:
        oauth = OAuth(app)
        google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        if google_client_id and google_client_secret:
            oauth.register(
                name='google',
                client_id=google_client_id,
                client_secret=google_client_secret,
                server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                client_kwargs={'scope': 'openid email profile'},
            )
            try:
                logging.debug('OAuth: Google provider registered')
            except Exception:
                pass
        ms_client_id = os.environ.get('MICROSOFT_CLIENT_ID')
        ms_client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
        ms_tenant = os.environ.get('MICROSOFT_TENANT_ID') or 'common'
        if ms_client_id and ms_client_secret:
            oauth.register(
                name='microsoft',
                client_id=ms_client_id,
                client_secret=ms_client_secret,
                server_metadata_url=f'https://login.microsoftonline.com/{ms_tenant}/v2.0/.well-known/openid-configuration',
                client_kwargs={'scope': 'openid email profile offline_access'},
            )
            try:
                logging.debug('OAuth: Microsoft provider registered')
            except Exception:
                pass
    except Exception as _e:
        logging.warning('OAuth init failed: %s', _e)

@app.route('/login', methods=['GET','POST'])
def login():
    """Sign-in form with three auth paths:
    1) Admin/basic via env vars
    2) Local SQLite users
    3) OAuth buttons (Google/Microsoft) rendered when configured
    """
    if request.method == 'POST':
        u = (request.form.get('username') or '').strip().lower()
        p = request.form.get('password') or ''

        # 1) Admin/basic auth via env vars
        try:
            if _check_basic_auth(u, p):
                session['user'] = {'name': u, 'method': 'password'}
                nxt = request.args.get('next')
                if not nxt:
                    # Prefer api subdomain for the dashboard after login
                    try:
                        host = request.host or ''
                        if not host.startswith('api.') and 'everydayadvertise.com' in host:
                            return redirect('https://api.everydayadvertise.com/dashboard')
                    except Exception:
                        pass
                    nxt = url_for('dashboard')
                return redirect(nxt)
        except Exception:
            # Fall through to local user check
            pass

        # 2) Local users (SQLite)
        try:
            db = get_db()
            row = db.execute(
                'SELECT username, password_hash FROM users WHERE username = ?',
                (u,)
            ).fetchone()
            if row and check_password_hash(row['password_hash'], p or ''):
                session['user'] = {'name': row['username'], 'method': 'local'}
                # Ensure this user has a pairing code
                try:
                    _ensure_user_link_code(row['username'])
                except Exception:
                    pass
                nxt = request.args.get('next')
                if not nxt:
                    try:
                        host = request.host or ''
                        if not host.startswith('api.') and 'everydayadvertise.com' in host:
                            return redirect('https://api.everydayadvertise.com/dashboard')
                    except Exception:
                        pass
                    nxt = url_for('dashboard')
                return redirect(nxt)
        except Exception as _e:
            logging.warning('Local user login failed: %s', _e)

        flash('Invalid username or password', 'error')

    # GET or failed POST -> render login page
    try:
        google_env = bool(os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET'))
        ms_env = bool(os.environ.get('MICROSOFT_CLIENT_ID') and os.environ.get('MICROSOFT_CLIENT_SECRET'))
        google_enabled = bool(oauth and getattr(oauth, 'google', None)) or google_env
        microsoft_enabled = bool(oauth and getattr(oauth, 'microsoft', None)) or ms_env
    except Exception:
        google_enabled = False
        microsoft_enabled = False

    resp = make_response(render_template('login.html', google_enabled=google_enabled, microsoft_enabled=microsoft_enabled, build_stamp=BUILD_STAMP))
    try:
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    except Exception:
        pass
    return resp

# ---------------------- Password reset (request + confirm) ----------------------
def _issue_password_reset_token(username: str) -> Optional[str]:
    try:
        token = uuid.uuid4().hex + uuid.uuid4().hex
        db = get_db()
        # Reuse verify_token column to avoid schema change; store a time prefix to distinguish
        stamped = f"reset:{int(time.time())}:{token}"
        db.execute('UPDATE users SET verify_token = ?, verify_sent_at = ? WHERE username = ?', (stamped, int(time.time()), (username or '').strip().lower()))
        db.commit()
        return token
    except Exception as e:
        logging.warning('issue_password_reset_token failed: %s', e)
        return None

def _parse_reset_token_row(row) -> bool:
    try:
        vt = row['verify_token'] or ''
        if not vt.startswith('reset:'): return False
        parts = vt.split(':', 2)
        if len(parts) != 3: return False
        ts = int(parts[1] or '0')
        # Valid for 1 hour
        return (time.time() - ts) < 3600
    except Exception:
        return False

@app.route('/forgot', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash('Please enter your email', 'error')
            # Include an error flag in the redirect so the message shows even if cookies are scoped
            return redirect(url_for('forgot_password', err=1))
        try:
            logging.info('forgot_password requested for %s', email)
            db = get_db()
            row = db.execute('SELECT username FROM users WHERE username = ?', (email,)).fetchone()
            if not row:
                # Do not reveal existence; show generic message
                flash('If that email exists, we sent a reset link.', 'success')
                return redirect(url_for('forgot_password', ok=1))
            token = _issue_password_reset_token(email)
            if not token:
                flash('Could not start password reset. Try again later.', 'error')
                return redirect(url_for('forgot_password', err=1))
            try:
                reset_url = url_for('reset_password', token=token, _external=True, _scheme='https')
            except Exception:
                host = 'https://api.everydayadvertise.com'
                reset_url = f"{host}/reset/{token}"
            body = f"We received a request to reset your password.\n\nClick this link to set a new password:\n{reset_url}\n\nIf you didn't request this, you can ignore this email. The link expires in 1 hour."
            subject = 'Reset your EverydayAdvertise password'
            if _mail_configured():
                logging.info('Attempting SMTP send to %s (host=%s)', email, os.environ.get('SMTP_HOST'))
                ok = send_email(email, subject, body)
                if ok:
                    flash('If that email exists, we sent a reset link.', 'success')
                    return redirect(url_for('forgot_password', ok=1))
                else:
                    flash('Failed to send email. Try again later.', 'error')
                    return redirect(url_for('forgot_password', err=1))
            else:
                logging.warning('SMTP not configured; password reset URL: %s', reset_url)
                flash('If that email exists, we sent a reset link.', 'success')
                return redirect(url_for('forgot_password', ok=1))
        except Exception as e:
            logging.warning('forgot_password error: %s', e)
            flash('Could not process request.', 'error')
            return redirect(url_for('forgot_password', err=1))
    # GET
    return render_template('forgot.html')

@app.route('/reset/<token>', methods=['GET','POST'])
def reset_password(token: str):
    tok = (token or '').strip()
    if not tok:
        flash('Invalid reset link', 'error')
        return redirect(url_for('login'))
    try:
        db = get_db()
        row = db.execute('SELECT username, verify_token FROM users WHERE verify_token LIKE ?', (f'reset:%:{tok}',)).fetchone()
        if not row or not _parse_reset_token_row(row):
            flash('Reset link is invalid or expired', 'error')
            return redirect(url_for('login'))
        if request.method == 'POST':
            pwd = request.form.get('password') or ''
            if len(pwd) < 6:
                flash('Password must be at least 6 characters', 'error')
                return render_template('reset.html', token=tok)
            try:
                db.execute('UPDATE users SET password_hash = ?, verify_token = NULL WHERE username = ?', (generate_password_hash(pwd), row['username']))
                db.commit()
                flash('Password updated. You can now sign in.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                logging.warning('reset_password update failed: %s', e)
                flash('Could not update password', 'error')
                return render_template('reset.html', token=tok)
        # GET -> show form
        return render_template('reset.html', token=tok)
    except Exception as e:
        logging.warning('reset_password error: %s', e)
        flash('Reset link not valid', 'error')
        return redirect(url_for('login'))

# ---- Import media from third-party share links (Dropbox / Google Drive / OneDrive) ----
@app.route('/import_from_url', methods=['POST'])
@login_required
def import_from_url():
    try:
        data = request.get_json(force=True) or {}
        raw_url = (data.get('url') or '').strip()
        raw_prefix = data.get('prefix')
        if not raw_url:
            return jsonify({'success': False, 'error': 'url required'}), 400

        # Only allow specific providers to reduce SSRF surface
        # Normalize common share URLs to direct-download endpoints when possible
        def normalize_provider_link(u: str) -> tuple[str, str|None]:
            try:
                parsed = urllib.parse.urlparse(u)
                host = (parsed.hostname or '').lower()
                # Dropbox: www.dropbox.com/s/<id>/file?dl=0 -> dl=1; also support dl.dropboxusercontent.com
                if host.endswith('dropbox.com') or host.endswith('dropboxusercontent.com'):
                    q = urllib.parse.parse_qs(parsed.query)
                    q['dl'] = ['1']
                    new_q = urllib.parse.urlencode({k: v[-1] if isinstance(v, list) else v for k, v in q.items()})
                    return ('dropbox', urllib.parse.urlunparse(parsed._replace(query=new_q)))
                # Google Drive: https://drive.google.com/file/d/<id>/view -> https://drive.google.com/uc?export=download&id=<id>
                if host.endswith('drive.google.com'):
                    m = re.search(r"/file/d/([^/]+)/", parsed.path or '')
                    if m:
                        fid = m.group(1)
                        return ('gdrive', f'https://drive.google.com/uc?export=download&id={fid}')
                    # Already uc endpoint – keep
                    if (parsed.path or '').startswith('/uc'):
                        return ('gdrive', u)
                # OneDrive: onedrive.live.com or 1drv.ms -> append download=1
                if host.endswith('onedrive.live.com') or host.endswith('1drv.ms'):
                    q = urllib.parse.parse_qs(parsed.query)
                    q['download'] = ['1']
                    new_q = urllib.parse.urlencode({k: v[-1] if isinstance(v, list) else v for k, v in q.items()})
                    return ('onedrive', urllib.parse.urlunparse(parsed._replace(query=new_q)))
                return ('unknown', None)
            except Exception:
                return ('unknown', None)

        provider, norm = normalize_provider_link(raw_url)
        if provider == 'unknown' or not norm:
            return jsonify({'success': False, 'error': 'Only Dropbox, Google Drive, and OneDrive links are supported'}), 400

        # Validate hostname again after normalization
        host = (urllib.parse.urlparse(norm).hostname or '').lower()
        allowed_hosts = (
            'dropbox.com', 'dropboxusercontent.com',
            'drive.google.com',
            'onedrive.live.com', '1drv.ms'
        )
        if not any(host == h or host.endswith('.'+h) for h in allowed_hosts):
            return jsonify({'success': False, 'error': 'Host not allowed'}), 400

        # Fetch with tight limits
        MAX_BYTES = int(os.environ.get('IMPORT_MAX_BYTES', '104857600'))  # 100 MiB default
        timeout = float(os.environ.get('IMPORT_TIMEOUT', '25'))
        req = urllib.request.Request(norm, headers={'User-Agent': 'PHTV/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, 'status', 200)
            if status < 200 or status >= 300:
                return jsonify({'success': False, 'error': f'Provider returned HTTP {status}'}), 502
            clen = resp.getheader('Content-Length')
            if clen:
                try:
                    if int(clen) > MAX_BYTES:
                        return jsonify({'success': False, 'error': 'File too large'}), 413
                except Exception:
                    pass

            # Determine a filename and extension
            disp = resp.getheader('Content-Disposition') or ''
            filename = None
            # RFC 5987 style: filename*=UTF-8''<url-encoded-filename>
            m = re.search(r"filename\*=UTF-8''([^\";]+)", disp)
            if m:
                filename = urllib.parse.unquote(m.group(1))
            if not filename:
                m2 = re.search(r'filename="?([^";]+)"?', disp)
                if m2:
                    filename = m2.group(1)
            if not filename:
                # Fallback to URL path basename
                filename = os.path.basename(urllib.parse.urlparse(norm).path) or 'imported'

            # Guess extension from filename or content-type
            ext = ''
            if '.' in filename:
                ext = filename.rsplit('.', 1)[1].lower()
            if not ext:
                try:
                    import mimetypes
                    mt = resp.getheader('Content-Type') or 'application/octet-stream'
                    exts = mimetypes.guess_all_extensions(mt) or []
                    for e in exts:
                        e2 = e.lstrip('.').lower()
                        if e2 in ALLOWED_EXTENSIONS:
                            ext = e2
                            break
                except Exception:
                    pass
            if ext not in ALLOWED_EXTENSIONS:
                return jsonify({'success': False, 'error': f'File type not allowed ({ext or "unknown"})'}), 415

            # Stream to temp file with size guard
            tmpf = tempfile.NamedTemporaryFile(prefix='import_', suffix='.'+ext, delete=False)
            tmp_path = tmpf.name
            written = 0
            try:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_BYTES:
                        tmpf.close()
                        os.unlink(tmp_path)
                        return jsonify({'success': False, 'error': 'File too large'}), 413
                    tmpf.write(chunk)
                tmpf.flush()
            finally:
                try:
                    tmpf.close()
                except Exception:
                    pass

        # Persist into user library under requested prefix
        user_root = _user_content_prefix()
        if not user_root:
            try: os.unlink(tmp_path)
            except Exception: pass
            return jsonify({'success': False, 'error': 'auth required'}), 403
        ui_prefix = _sanitize_prefix(raw_prefix)
        req_prefix = _join_prefix_key(user_root, ui_prefix)
        # Generate a uuid-based destination name to avoid collisions
        safe_name = f"{uuid.uuid4()}.{ext}"
        local_dir = os.path.join(app.config['UPLOAD_FOLDER'], req_prefix)
        os.makedirs(local_dir, exist_ok=True)
        dest = os.path.join(local_dir, safe_name)
        # Move tmp to destination
        try:
            os.replace(tmp_path, dest)
        except Exception:
            shutil.copyfile(tmp_path, dest)
            try: os.unlink(tmp_path)
            except Exception: pass

        # Bust library cache for this user/prefix and root
        try:
            for k in (f"{user_root}|{ui_prefix or '__root__'}", f"{user_root}|__root__"):
                _LIB_CACHE.pop(k, None)
        except Exception:
            pass

        # Push to R2 if configured
        try:
            if r2_enabled():
                with open(dest, 'rb') as fh:
                    data_bytes = fh.read()
                key = _join_prefix_key(req_prefix, safe_name)
                r2_put_bytes(key, data_bytes, content_type=_guess_mime(safe_name))
        except Exception:
            pass

        return jsonify({'success': True, 'filename': safe_name, 'url': build_public_url(_join_prefix_key(req_prefix, safe_name)), 'media_type': ext, 'provider': provider})
    except Exception as e:
        logging.exception('import_from_url error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if not username or not password:
            flash('Email and password required', 'error')
        elif '@' not in username or '.' not in username.split('@')[-1]:
            flash('Please use a valid email address', 'error')
        elif password != password2:
            flash('Passwords do not match', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
        else:
            db = get_db()
            try:
                # Try inserting with full_name if column exists
                try:
                    db.execute('INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)', (
                        username, generate_password_hash(password), full_name
                    ))
                except sqlite3.OperationalError:
                    # Fallback for older DB without full_name
                    db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, generate_password_hash(password)))
                db.commit()
                # Generate a pairing code for this new user
                try:
                    _ensure_user_link_code(username)
                except Exception:
                    pass
                flash('Account created! Please sign in.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Username already exists', 'error')
    # Mirror login page behavior: expose whether Google OAuth is enabled
    try:
        google_env = bool(os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET'))
        ms_env = bool(os.environ.get('MICROSOFT_CLIENT_ID') and os.environ.get('MICROSOFT_CLIENT_SECRET'))
        google_enabled = bool(oauth and getattr(oauth, 'google', None)) or google_env
        microsoft_enabled = bool(oauth and getattr(oauth, 'microsoft', None)) or ms_env
    except Exception:
        google_enabled = False
        microsoft_enabled = False
    resp = make_response(render_template('signup.html', google_enabled=google_enabled, microsoft_enabled=microsoft_enabled))
    try:
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    except Exception:
        pass
    return resp

@app.route('/logout')
def logout():
    session.pop('user', None)
    # Redirect to the main public homepage after logout
    try:
        host = request.host or ''
        if 'everydayadvertise.com' in host:
            return redirect('https://everydayadvertise.com/')
    except Exception:
        pass
    return redirect(url_for('home'))

# ---------------------- Public homepage ----------------------
@app.route('/')
def home():
    try:
        # Provide cache-busting for logo and build info
        import os, time as _t
        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'ea-logo.svg')
        asset_bust = int(os.path.getmtime(logo_path)) if os.path.exists(logo_path) else int(_t.time())
    except Exception:
        asset_bust = 0
    resp = make_response(render_template('home.html', build_stamp=BUILD_STAMP, git_commit=GIT_COMMIT, asset_bust=asset_bust))
    try:
        resp.headers['Cache-Control'] = 'public, max-age=300'
    except Exception:
        pass
    return resp

# ---------------------- Email verification routes ----------------------
@app.route('/verify/<token>')
def verify_email(token: str):
    token = (token or '').strip()
    if not token:
        flash('Invalid verification link', 'error')
        return redirect(url_for('login'))
    try:
        db = get_db()
        row = db.execute('SELECT username FROM users WHERE verify_token = ?', (token,)).fetchone()
        if not row:
            flash('Verification link is invalid or already used', 'error')
            return redirect(url_for('login'))
        uname = (row['username'] or '').strip().lower()
        db.execute('UPDATE users SET email_verified = 1, verify_token = NULL WHERE username = ?', (uname,))
        db.commit()
        flash('Email verified! You can now sign in.', 'success')
    except Exception as e:
        logging.warning('verify_email failed: %s', e)
        flash('Could not verify email. Please try again.', 'error')
    return redirect(url_for('login'))

@app.route('/auth/google')
def auth_google():
    # Ensure the Google client exists; lazily register if env vars are present
    try:
        client = None
        if oauth:
            if not getattr(oauth, 'google', None):
                gid = os.environ.get('GOOGLE_CLIENT_ID')
                gsecret = os.environ.get('GOOGLE_CLIENT_SECRET')
                if gid and gsecret:
                    try:
                        oauth.register(
                            name='google',
                            client_id=gid,
                            client_secret=gsecret,
                            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                            client_kwargs={'scope': 'openid email profile'},
                        )
                        logging.info('OAuth: Google provider lazily registered in route')
                    except Exception as _e:
                        logging.warning('OAuth: google (re)register failed: %s', _e)
            try:
                client = oauth.create_client('google')
            except Exception:
                client = None

        if not client:
            flash('Google Sign-In not configured', 'error')
            return redirect(url_for('login'))

        try:
            redirect_uri = url_for('auth_google_callback', _external=True)
            # If a proxy ever yields http, prefer https externally
            if redirect_uri.startswith('http://'):
                redirect_uri = redirect_uri.replace('http://', 'https://', 1)
        except Exception:
            redirect_uri = 'https://api.everydayadvertise.com/auth/google/callback'

        return client.authorize_redirect(redirect_uri)
    except Exception as e:
        logging.warning('Google auth init failed: %s', e)
        flash('Google Sign-In not available', 'error')
        return redirect(url_for('login'))

@app.route('/auth/google/callback')
def auth_google_callback():
    # Ensure google client exists in case of lazy registration need
    try:
        if oauth and not getattr(oauth, 'google', None):
            gid = os.environ.get('GOOGLE_CLIENT_ID')
            gsecret = os.environ.get('GOOGLE_CLIENT_SECRET')
            if gid and gsecret:
                try:
                    oauth.register(
                        name='google',
                        client_id=gid,
                        client_secret=gsecret,
                        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                        client_kwargs={'scope': 'openid email profile'},
                    )
                    logging.info('OAuth: Google provider lazily registered in callback')
                except Exception as _e:
                    logging.warning('OAuth: google lazy register failed in callback: %s', _e)
        client = oauth.create_client('google') if oauth else None
        if not client:
            flash('Google Sign-In not configured', 'error')
            return redirect(url_for('login'))
    except Exception as _e:
        logging.warning('Google client prep failed: %s', _e)
        flash('Google Sign-In not configured', 'error')
        return redirect(url_for('login'))
    try:
        token = client.authorize_access_token()
        userinfo = token.get('userinfo') or {}
        # Some providers put userinfo under separate call; fallback
        if not userinfo:
            resp = client.get('userinfo')
            userinfo = resp.json() if resp else {}
        email = userinfo.get('email')
        if not email:
            flash('Google login failed: no email scope', 'error')
            return redirect(url_for('login'))
        # Optional domain restriction
        allowed_domain = os.environ.get('GOOGLE_ALLOWED_DOMAIN')
        if allowed_domain and not str(email).lower().endswith('@'+allowed_domain.lower()):
            flash('Email domain not allowed', 'error')
            return redirect(url_for('login'))
        session['user'] = {'name': userinfo.get('name') or email, 'email': email, 'method': 'google'}
        # Upsert a local user record so we can store a pairing code
        try:
            db = get_db()
            uname = (email or '').strip().lower()
            if uname:
                try:
                    # Try inserting with full_name if column exists
                    db.execute('INSERT OR IGNORE INTO users (username, full_name) VALUES (?, ?)', (uname, userinfo.get('name') or uname))
                except Exception:
                    try:
                        db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (uname,))
                    except Exception:
                        pass
                db.commit()
                # Mark verified for OAuth sources
                try:
                    db.execute('UPDATE users SET email_verified = 1 WHERE username = ?', (uname,))
                    db.commit()
                except Exception:
                    pass
                _ensure_user_link_code(uname)
        except Exception:
            pass
        nxt = request.args.get('next')
        if not nxt:
            try:
                host = request.host or ''
                if not host.startswith('api.') and 'everydayadvertise.com' in host:
                    return redirect('https://api.everydayadvertise.com/dashboard')
            except Exception:
                pass
            nxt = url_for('dashboard')
        return redirect(nxt)
    except Exception as e:
        logging.exception('Google auth failed: %s', e)
        flash('Google login failed', 'error')
        return redirect(url_for('login'))

@app.route('/auth/microsoft')
def auth_microsoft():
    # Ensure OAuth exists
    global oauth
    if oauth is None and OAuth is not None:
        try:
            oauth = OAuth(app)
            logging.info('OAuth: instantiated in route')
        except Exception as _e:
            logging.warning('OAuth: instantiate failed: %s', _e)
    # Attempt (re)registration based on env
    ms_client_id = os.environ.get('MICROSOFT_CLIENT_ID')
    ms_client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
    # Resolve tenant locally to avoid relying on module init state
    ms_tenant = os.environ.get('MICROSOFT_TENANT_ID') or 'common'
    try:
        if oauth and ms_client_id and ms_client_secret:
            try:
                # Register if not present
                client = None
                try:
                    client = oauth.create_client('microsoft')
                except Exception:
                    client = None
                if client is None:
                    oauth.register(
                        name='microsoft',
                        client_id=ms_client_id,
                        client_secret=ms_client_secret,
                        server_metadata_url=f'https://login.microsoftonline.com/{ms_tenant}/v2.0/.well-known/openid-configuration',
                        client_kwargs={'scope': 'openid email profile offline_access'},
                    )
                    logging.info('OAuth: Microsoft provider (re)registered in route')
            except Exception as _e:
                logging.warning('OAuth: microsoft (re)register failed: %s', _e)
    except Exception:
        pass
    # Acquire client and proceed
    try:
        client = oauth.create_client('microsoft') if oauth else None
    except Exception:
        client = None
    if not client:
        # Fallback: construct authorize URL manually if env present
        if ms_client_id:
            try:
                redirect_uri = url_for('auth_microsoft_callback', _external=True)
                if redirect_uri.startswith('http://'):
                    redirect_uri = redirect_uri.replace('http://', 'https://', 1)
            except Exception:
                redirect_uri = 'https://api.everydayadvertise.com/auth/microsoft/callback'
            params = {
                'client_id': ms_client_id,
                'response_type': 'code',
                'redirect_uri': redirect_uri,
                'response_mode': 'query',
                'scope': 'openid email profile offline_access',
            }
            try:
                import urllib.parse as _up
                tenant_for_auth = os.environ.get('MICROSOFT_TENANT_ID') or 'common'
                auth_url = f'https://login.microsoftonline.com/{tenant_for_auth}/oauth2/v2.0/authorize?' + _up.urlencode(params)
                logging.warning('OAuth: redirecting via manual Microsoft authorize URL (no client)')
                return redirect(auth_url)
            except Exception as _e:
                logging.warning('OAuth: manual authorize URL build failed: %s', _e)
        flash('Microsoft Sign-In not configured', 'error')
        return redirect(url_for('login'))
    # Build a https-safe redirect URI (proxy may yield http)
    try:
        redirect_uri = url_for('auth_microsoft_callback', _external=True)
        if redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://', 1)
    except Exception:
        redirect_uri = 'https://api.everydayadvertise.com/auth/microsoft/callback'
    return client.authorize_redirect(redirect_uri)

@app.route('/auth/microsoft/callback')
def auth_microsoft_callback():
    # Ensure client exists (lazy register if needed)
    global oauth
    try:
        if (oauth is None) and (OAuth is not None):
            oauth = OAuth(app)
            logging.warning('OAuth: instantiated in callback')
        if oauth and not getattr(oauth, 'microsoft', None):
            ms_client_id = os.environ.get('MICROSOFT_CLIENT_ID')
            ms_client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
            if ms_client_id and ms_client_secret:
                try:
                    ms_tenant = os.environ.get('MICROSOFT_TENANT_ID') or 'common'
                    oauth.register(
                        name='microsoft',
                        client_id=ms_client_id,
                        client_secret=ms_client_secret,
                        server_metadata_url=f'https://login.microsoftonline.com/{ms_tenant}/v2.0/.well-known/openid-configuration',
                        client_kwargs={'scope': 'openid email profile offline_access'},
                    )
                    logging.warning('OAuth: Microsoft provider lazily registered in callback')
                except Exception as _e:
                    logging.error('OAuth: lazy register in callback failed: %s', _e)
    except Exception as _e:
        logging.error('OAuth: callback init failed: %s', _e)
    # Prefer a client from registry rather than attribute access
    client = None
    try:
        client = oauth.create_client('microsoft') if oauth else None
    except Exception:
        client = None

    # Helper: manual token exchange + userinfo when client is missing or ID token validation fails
    def _manual_token_and_userinfo():
        try:
            import requests as _rq
            code = request.args.get('code')
            ms_client_id = os.environ.get('MICROSOFT_CLIENT_ID')
            ms_client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
            ms_tenant = os.environ.get('MICROSOFT_TENANT_ID') or 'common'
            if not (code and ms_client_id and ms_client_secret):
                return None, None
            try:
                redirect_uri = url_for('auth_microsoft_callback', _external=True)
            except Exception:
                redirect_uri = 'https://api.everydayadvertise.com/auth/microsoft/callback'
            data = {
                'client_id': ms_client_id,
                'client_secret': ms_client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
            }
            tresp = _rq.post(f'https://login.microsoftonline.com/{ms_tenant}/oauth2/v2.0/token', data=data, timeout=12)
            try:
                tj = tresp.json() or {}
            except Exception:
                tj = {}
            access_token = tj.get('access_token')
            if not access_token:
                logging.error('Microsoft fallback token exchange failed: status=%s body=%s', tresp.status_code, tresp.text[:500])
                return None, None
            # Fetch OIDC userinfo
            userinfo = {}
            try:
                uresp = _rq.get('https://graph.microsoft.com/oidc/userinfo', headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
                if 200 <= uresp.status_code < 300:
                    userinfo = uresp.json() or {}
            except Exception as _e:
                logging.warning('Microsoft fallback userinfo error: %s', _e)
            if not userinfo:
                return None, None
            return tj, userinfo
        except Exception as _e:
            logging.error('Microsoft manual flow exception: %s', _e)
            return None, None

    # Acquire token and userinfo
    token = None
    userinfo = {}
    # Prefer manual token exchange first to avoid issuer validation issues on /common
    token, userinfo = _manual_token_and_userinfo()
    if token is None:
        # Fallback to Authlib's standard flow only if manual exchange failed
        if not client:
            flash('Microsoft login failed', 'error')
            return redirect(url_for('login'))
        try:
            token = client.authorize_access_token()
        except Exception as e:
            logging.error('Microsoft authorize_access_token failed: %s', e)
            flash('Microsoft login failed', 'error')
            return redirect(url_for('login'))
        # If we got here via Authlib, try to fetch userinfo via the provider
        try:
            if not userinfo and client:
                resp = client.get('userinfo')
                if resp is not None:
                    userinfo = resp.json() or {}
        except Exception:
            userinfo = {}
        # Fallback to id_token claims (Authlib path only)
        if not userinfo:
            userinfo = token.get('userinfo') or token.get('id_token_claims') or {}
        email = userinfo.get('email') or userinfo.get('preferred_username')
        name = userinfo.get('name') or (email.split('@')[0] if email else None)
        if not email:
            flash('Microsoft login failed: no email', 'error')
            return redirect(url_for('login'))
        session['user'] = {'name': name or email, 'email': email, 'method': 'microsoft'}
        # Upsert a local user record so we can store a pairing code
        try:
            db = get_db()
            uname = (email or '').strip().lower()
            if uname:
                try:
                    db.execute('INSERT OR IGNORE INTO users (username, full_name) VALUES (?, ?)', (uname, name or uname))
                except Exception:
                    try:
                        db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (uname,))
                    except Exception:
                        pass
                db.commit()
                # Mark verified for OAuth sources
                try:
                    db.execute('UPDATE users SET email_verified = 1 WHERE username = ?', (uname,))
                    db.commit()
                except Exception:
                    pass
                _ensure_user_link_code(uname)
        except Exception:
            pass
        nxt = request.args.get('next')
        if not nxt:
            try:
                host = request.host or ''
                if not host.startswith('api.') and 'everydayadvertise.com' in host:
                    return redirect('https://api.everydayadvertise.com/dashboard')
            except Exception:
                pass
            nxt = url_for('dashboard')
        return redirect(nxt)
    else:
        # Manual-first path succeeded: set session, upsert user, and redirect
        try:
            email = (userinfo.get('email') or userinfo.get('preferred_username') or '').strip().lower()
            name = userinfo.get('name') or (email.split('@')[0] if email else None)
        except Exception:
            email = None
            name = None
        if not email:
            logging.error('Microsoft manual flow: missing email in userinfo: %s', userinfo)
            flash('Microsoft login failed: no email', 'error')
            return redirect(url_for('login'))
        session['user'] = {'name': name or email, 'email': email, 'method': 'microsoft'}
        try:
            db = get_db()
            uname = email
            if uname:
                try:
                    db.execute('INSERT OR IGNORE INTO users (username, full_name) VALUES (?, ?)', (uname, name or uname))
                except Exception:
                    try:
                        db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (uname,))
                    except Exception:
                        pass
                db.commit()
                try:
                    db.execute('UPDATE users SET email_verified = 1 WHERE username = ?', (uname,))
                    db.commit()
                except Exception:
                    pass
                _ensure_user_link_code(uname)
        except Exception as _e:
            logging.warning('Microsoft manual flow user upsert failed: %s', _e)
        nxt = request.args.get('next')
        if not nxt:
            try:
                host = request.host or ''
                if not host.startswith('api.') and 'everydayadvertise.com' in host:
                    return redirect('https://api.everydayadvertise.com/dashboard')
            except Exception:
                pass
            nxt = url_for('dashboard')
        return redirect(nxt)

@app.route('/healthz')
def _healthz():
    return jsonify({
        'ok': True,
        'build': BUILD_STAMP,
        'commit': GIT_COMMIT,
        'r2_enabled': r2_enabled(),
        'media_base_url': os.environ.get('MEDIA_BASE_URL')
    })

@app.route('/diag/auth')
def _diag_auth():
    try:
        google_env = bool(os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET'))
    except Exception:
        google_env = False
    try:
        ms_env = bool(os.environ.get('MICROSOFT_CLIENT_ID') and os.environ.get('MICROSOFT_CLIENT_SECRET'))
    except Exception:
        ms_env = False
    try:
        google_client = False
        if oauth:
            try:
                google_client = bool(oauth.create_client('google'))
            except Exception:
                google_client = False
    except Exception:
        google_client = False
    try:
        ms_client = False
        if oauth:
            try:
                ms_client = bool(oauth.create_client('microsoft'))
            except Exception:
                ms_client = False
    except Exception:
        ms_client = False
    return jsonify({
        'google_env': google_env,
        'microsoft_env': ms_env,
        'google_client': google_client,
        'microsoft_client': ms_client,
        'build': BUILD_STAMP,
        'commit': GIT_COMMIT,
    })

# ---- Simple slow-request logging and ETag helpers ----
from functools import wraps
import hashlib
from werkzeug.http import http_date

def slowlog(threshold_ms=500):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.time()
            resp = fn(*args, **kwargs)
            dt = (time.time() - t0) * 1000.0
            if dt >= threshold_ms:
                logging.warning('SLOW %s %.1fms %s', request.path, dt, request.args or request.get_json(silent=True))
            return resp
        return wrapper
    return deco

def with_etag_json(fn):
    @wraps(fn)
    def w(*args, **kwargs):
        r = fn(*args, **kwargs)

        def _parse_inm(raw: str | None) -> set[str]:
            if not raw:
                return set()
            # Accept formats: W/"abc", "def", abc
            tokens = []
            for part in raw.split(','):
                p = part.strip()
                if p.startswith('W/'):  # weak tag prefix
                    p = p[2:].strip()
                if p.startswith('"') and p.endswith('"') and len(p) >= 2:
                    p = p[1:-1]
                tokens.append(p)
            return set(t for t in tokens if t)

        def _make_resp_from_payload(payload: str, rest: list):
            # Build a Response and attach a properly quoted ETag
            resp = jsonify(json.loads(payload))
            et = hashlib.md5(payload.encode('utf-8')).hexdigest()
            # Conditional GET handling
            inm = _parse_inm(request.headers.get('If-None-Match'))
            if et in inm:
                return Response(status=304)
            try:
                resp.set_etag(et, weak=False)
            except Exception:
                resp.headers['ETag'] = f'"{et}"'
            resp.headers.setdefault('Cache-Control', 'public, max-age=30')
            # Preserve status/headers tuple parts if provided
            if rest:
                return (resp, *rest)
            return resp

        # Tuple: (dict/list, [status], [headers])
        if isinstance(r, tuple):
            body, *rest = r
            if isinstance(body, (dict, list)):
                payload = json.dumps(body, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
                return _make_resp_from_payload(payload, rest)
            return r

        # Dict/list: convert and attach ETag
        if isinstance(r, (dict, list)):
            payload = json.dumps(r, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
            return _make_resp_from_payload(payload, [])

        # Already a Response or other type
        return r
    return w
@app.after_request
def _add_cache_headers(resp):
    try:
        p = request.path or ''
        if p.startswith('/static/uploads/') or p.startswith('/thumb/') or p.startswith('/vthumb/'):
            # Only long-cache successful media responses; never cache errors to avoid sticky 404s at CDN
            if 200 <= resp.status_code < 300:
                resp.headers['Cache-Control'] = 'public, max-age=2592000, immutable'
            elif resp.status_code == 206:  # partial content
                resp.headers['Cache-Control'] = 'public, max-age=3600'
            else:
                resp.headers['Cache-Control'] = 'no-store, max-age=0'
        elif p.startswith('/api/'):
            # small API responses get short caching to smooth bursts
            if 200 <= resp.status_code < 300:
                resp.headers.setdefault('Cache-Control', 'public, max-age=15')
            else:
                resp.headers['Cache-Control'] = 'no-store, max-age=0'
        # Attach build metadata for easy troubleshooting across all responses
        resp.headers['X-App-Build'] = BUILD_STAMP
        if GIT_COMMIT:
            resp.headers['X-App-Commit'] = GIT_COMMIT
    except Exception:
        pass
    return resp


# Enable gzip compression if available
try:
    from flask_compress import Compress
    # Configure a conservative set of MIME types to compress
    app.config.setdefault('COMPRESS_MIMETYPES', [
        'text/html', 'text/css', 'application/json', 'application/javascript', 'text/javascript'
    ])
    app.config.setdefault('COMPRESS_LEVEL', 6)
    app.config.setdefault('COMPRESS_MIN_SIZE', 1024)
    Compress(app)
    logging.debug('Flask-Compress enabled')
except Exception as _compress_e:
    logging.warning('Flask-Compress not enabled: %s', _compress_e)

# --- Media base URL (for external/CDN like Cloudflare R2) ---
def get_media_base_url():
    """Return the base URL for serving media files.
    - If R2 is not configured, force local '/static/uploads/'.
    - If R2 is configured, use MEDIA_BASE_URL when provided; otherwise fallback to local.
    Ensures trailing slash.
    """
    if not r2_enabled():
        base = '/static/uploads/'
    else:
        base = os.environ.get('MEDIA_BASE_URL') or '/static/uploads/'
    if not base.endswith('/'):
        base += '/'
    return base

def _is_abs(u: str) -> bool:
    try:
        return isinstance(u, str) and (u.startswith('http://') or u.startswith('https://'))
    except Exception:
        return False

def build_public_url(filename: str) -> str | None:
    if not filename:
        return None
    if _is_abs(filename):
        return filename
    # Already rooted path coming from our app? return as-is
    try:
        if isinstance(filename, str) and (filename.startswith('/static/') or filename.startswith('/media/')):
            return filename
    except Exception:
        pass
    return get_media_base_url() + filename

def _cdn_thumb_url(kind: str, width: int, rel_path: str) -> Optional[str]:
    """Return CDN URL for a generated asset if R2 is enabled.
    kind: 'thumbs' (webp), 'vthumbs' (jpg), or 'vpreviews' (mp4);
    rel_path: original relative path (may include folders).
    """
    try:
        if not r2_enabled():
            return None
        base = get_media_base_url()  # ensures trailing slash
        # Map original extension to the generated one
        stem = os.path.splitext(rel_path)[0]
        if kind == 'thumbs':
            out = stem + '.webp'
        elif kind == 'vthumbs':
            out = stem + '.jpg'
        elif kind == 'vpreviews':
            out = stem + '.mp4'
        else:
            return None
        return f"{base}{kind}/{width}/{out}"
    except Exception:
        return None

# ---- Safe folder/prefix utilities for library organization ----
def _sanitize_prefix(prefix: str | None) -> str:
    """Sanitize a folder prefix like '2025-08' or '2025-08/campaign-a'.
    - Strips leading/trailing slashes
    - Converts backslashes to slashes
    - Only allow [A-Za-z0-9_-]/ separators
    - Returns '' for root on any invalid input
    """
    try:
        p = (prefix or '').strip().replace('\\','/').strip('/')
        if not p:
            return ''
        for part in p.split('/'):
            # Allow dots and spaces to support user namespaces and readable folder names
            # Disallow leading/trailing spaces within a part by trimming check
            if part != part.strip():
                return ''
            if not part or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- " for c in part):
                return ''
        return p
    except Exception:
        return ''

def _join_prefix_key(prefix: str, name: str) -> str:
    p = _sanitize_prefix(prefix)
    if not p:
        return name
    name = name.lstrip('/').replace('\\','/')
    return f"{p}/{name}"

# --- R2 (S3-compatible) integration ---
def r2_enabled() -> bool:
    return bool(
        os.environ.get('R2_BUCKET_NAME')
        and os.environ.get('R2_ENDPOINT_URL')
        and os.environ.get('R2_ACCESS_KEY_ID')
        and os.environ.get('R2_SECRET_ACCESS_KEY')
        and boto3 is not None
    )

def r2_diag() -> dict:
    """Return non-secret diagnostics for R2 configuration.
    Never include keys or secrets; only booleans and brief notes.
    """
    try:
        d = {
            'env_present': {
                'R2_BUCKET_NAME': bool(os.environ.get('R2_BUCKET_NAME')),
                'R2_ENDPOINT_URL': bool(os.environ.get('R2_ENDPOINT_URL')),
                'R2_ACCESS_KEY_ID': bool(os.environ.get('R2_ACCESS_KEY_ID')),
                'R2_SECRET_ACCESS_KEY': bool(os.environ.get('R2_SECRET_ACCESS_KEY')),
            },
            'boto3_available': boto3 is not None,
            'enabled': False,
        }
        d['enabled'] = bool(d['boto3_available'] and all(d['env_present'].values()))
        if d['enabled']:
            try:
                s3 = get_s3_client()
                _ = s3.generate_presigned_url(
                    'put_object',
                    Params={
                        'Bucket': os.environ['R2_BUCKET_NAME'],
                        'Key': f"diag-{uuid.uuid4()}.bin",
                        'ContentType': 'application/octet-stream'
                    },
                    ExpiresIn=60
                )
                d['presign_construct_ok'] = True
            except Exception as _e:
                d['presign_construct_ok'] = False
                d['note'] = f"presign error: {_e.__class__.__name__}"
        return d
    except Exception as _e2:
        return {'enabled': False, 'error': f'diag_failed: {_e2.__class__.__name__}'}

_s3_client = None
def get_s3_client():
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not r2_enabled():
        return None
    # Use aggressive timeouts and minimal retries so uploads don't hang when R2 is unreachable
    try:
        cfg = BotoConfig(
            signature_version='s3v4',
            retries={'max_attempts': 1, 'mode': 'standard'},
            connect_timeout=2,
            read_timeout=5,
        )
    except TypeError:
        # Fallback for older botocore without explicit timeout kwargs
        cfg = BotoConfig(signature_version='s3v4', retries={'max_attempts': 1, 'mode': 'standard'})
    _s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        endpoint_url=os.environ['R2_ENDPOINT_URL'],
        config=cfg
    )
    return _s3_client

def r2_put_bytes(key: str, data: bytes, content_type: Optional[str] = None):
    s3 = get_s3_client()
    if not s3:
        raise RuntimeError('R2 not configured')
    extra = {}
    if content_type:
        extra['ContentType'] = content_type
    s3.put_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=key, Body=data, **extra)

def r2_delete_object(key: str):
    s3 = get_s3_client()
    if not s3:
        raise RuntimeError('R2 not configured')
    s3.delete_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=key)

def r2_list_objects(prefix: str = ''):
    s3 = get_s3_client()
    if not s3:
        raise RuntimeError('R2 not configured')
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=os.environ['R2_BUCKET_NAME'], Prefix=prefix):
        for obj in page.get('Contents', []) or []:
            yield obj

def r2_object_exists(key: str) -> bool:
    try:
        s3 = get_s3_client()
        if not s3:
            return False
        s3.head_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=key)
        return True
    except Exception:
        return False

# ---- Helpers to normalize store/screen ids across legacy/prefixed forms ----
def _normalize_screen_ref(cfg, store_id: str, screen_id: str) -> tuple[str | None, str | None]:
    """Return normalized (store_id, screen_id) present in cfg or (None, None).
    Accepts either short or store-prefixed screen ids and legacy store mapping for '1881'.
    """
    try:
        screens_all = cfg.get('screens', {}) or {}
        if store_id not in screens_all and str(store_id) == '1881':
            m = cfg.get('master_store_id')
            if m and m in screens_all:
                store_id = m
        screens = screens_all.get(store_id) or {}
        if screen_id in screens:
            return store_id, screen_id
        # Try add prefix
        cand = f"{store_id}_{screen_id}" if '_' not in screen_id else None
        if cand and cand in screens:
            return store_id, cand
        # Try strip prefix to short form
        if '_' in screen_id:
            short = screen_id.split('_', 1)[1]
            if short in screens:
                return store_id, short
        return None, None
    except Exception:
        return None, None

# --- Screen heartbeat + status (placed after app initialization) ---
HEARTBEAT_TIMEOUT = 60  # seconds

@app.route('/api/screen_heartbeat', methods=['POST', 'GET'])
def screen_heartbeat():
    """Android TV app should POST here every ~30s with store_id and screen_id.
    Also accepts GET with query params for quick manual testing: ?store_id=...&screen_id=...
    """
    if request.method == 'GET':
        data = {'store_id': request.args.get('store_id'), 'screen_id': request.args.get('screen_id')}
    else:
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            data = {}
    store_id = data.get('store_id')
    screen_id = data.get('screen_id')
    logging.debug('HB recv store_id=%s screen_id=%s raw_body=%s', store_id, screen_id, data)
    if not store_id or not screen_id:
        return jsonify({'success': False, 'error': 'Missing store_id or screen_id'}), 400
    # If a device provides X-User-Code, scope to that user's config
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    # Require a pairing code when no dashboard session is present
    if not user_key and not _safe_user_key():
        return jsonify({'success': False, 'error': 'pair code required'}), 403
    cfg = load_store_config_for_user_safe_key(user_key) if user_key else load_store_config()
    # Legacy mapping: if store_id changed (e.g., old '1881' -> current master), alias automatically
    try:
        master = cfg.get('master_store_id')
        if master and store_id not in (cfg.get('screens') or {}) and str(store_id) == '1881':
            logging.debug('HB legacy store_id %s mapped to master %s', store_id, master)
            store_id = master
    except Exception:
        pass
    store_screens = cfg.get('screens', {}).get(store_id)
    if not isinstance(store_screens, dict):
        logging.debug('HB store not found: %s', store_id)
        return jsonify({'success': False, 'error': 'Store not found'}), 404
    # Accept either full key (e.g., "1112_screen1") or plain ("screen1")
    if screen_id not in store_screens:
        candidate = None
        if '_' not in screen_id:
            candidate = f"{store_id}_{screen_id}"
        else:
            # Handle cross-store prefixed IDs like "1881_screen1" -> map suffix to current store
            try:
                suffix = screen_id.split('_', 1)[1]
                candidate = f"{store_id}_{suffix}"
            except Exception:
                candidate = None
        if candidate and candidate in store_screens:
            screen_id = candidate
        else:
            logging.debug('HB screen not found: store=%s screen=%s candidate=%s keys=%s', store_id, screen_id, candidate, list(store_screens.keys()))
            return jsonify({'success': False, 'error': 'Screen not found'}), 404
    # record last_seen epoch seconds
    store_screens[screen_id]['last_seen'] = int(time.time())
    logging.debug('HB set last_seen for %s/%s', store_id, screen_id)
    if user_key:
        save_store_config_for_user_safe_key(user_key, cfg)
    else:
        save_store_config(cfg)
    return jsonify({'success': True})

# -------- Client event reporting (per-item load success/failure) --------
@app.route('/api/client_event', methods=['POST'])
def client_event():
    """Android TV clients can report item-level events here.
    Body JSON: {store_id, screen_id, event, file?, item_id?, error?}
    Stores recent events and last status per item in config for dashboard visibility.
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    store_id = str(data.get('store_id') or '')
    screen_id = str(data.get('screen_id') or '')
    event = (data.get('event') or '').strip().lower()  # e.g., 'load_ok' | 'load_fail' | 'playlist_reload'
    file = data.get('file')
    item_id = data.get('item_id')
    error = data.get('error')
    if not store_id or not screen_id or not event:
        return jsonify({'success': False, 'error': 'store_id, screen_id and event required'}), 400
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    # Require a pairing code when no dashboard session is present
    if not user_key and not _safe_user_key():
        return jsonify({'success': False, 'error': 'pair code required'}), 403
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(user_key) if user_key else load_store_config())
    ns, nid = _normalize_screen_ref(cfg, store_id, screen_id)
    if not ns or not nid:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    scr = cfg['screens'][ns][nid]
    ev = {
        'ts': int(time.time()),
        'event': event,
        'file': file,
        'item_id': item_id,
        'error': (str(error)[:500] if error else None)
    }
    # Append to bounded events list
    events = scr.setdefault('events', [])
    events.append(ev)
    if len(events) > 100:
        del events[:-100]
    # Update last_item_status map using item_id when available, else by file key
    key = None
    if item_id:
        key = f"id:{item_id}"
    elif file:
        # normalize file to key (strip absolute URL)
        v = str(file)
        try:
            if v.startswith('http://') or v.startswith('https://'):
                v = v.rstrip('/').split('/')[-1]
        except Exception:
            pass
        key = f"file:{v}"
    if key:
        last = scr.setdefault('last_item_status', {})
        state = 'ok' if event in ('ok', 'load_ok', 'loaded') else ('fail' if 'fail' in event else event)
        last[key] = {'state': state, 'ts': ev['ts'], 'error': ev['error'], 'file': file, 'item_id': item_id}
        try:
            app.logger.debug('client_event mapped key=%s state=%s file=%s item_id=%s', key, state, file, item_id)
        except Exception:
            pass
    if user_key:
        save_store_config_for_user_safe_key(user_key, cfg)
    else:
        save_store_config(cfg)
    return jsonify({'success': True})

@app.route('/api/screen_events/<store_id>/<screen_id>', methods=['GET'])
def screen_events(store_id, screen_id):
    # Require session or device pairing code
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key and not _safe_user_key():
        return jsonify({'success': False, 'error': 'pair code required'}), 403
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(user_key) if user_key else load_store_config())
    ns, nid = _normalize_screen_ref(cfg, store_id, screen_id)
    if not ns or not nid:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    scr = cfg['screens'][ns][nid]
    return jsonify({'success': True, 'events': scr.get('events', []), 'last_item_status': scr.get('last_item_status', {})})

# -------- Debug: expose playlist-to-status mapping for troubleshooting --------
@app.route('/api/debug_item_status/<store_id>/<screen_id>', methods=['GET'])
def debug_item_status(store_id, screen_id):
    # Require session or device pairing code
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key and not _safe_user_key():
        return jsonify({'success': False, 'error': 'pair code required'}), 403
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(user_key) if user_key else load_store_config())
    ns, nid = _normalize_screen_ref(cfg, store_id, screen_id)
    if not ns or not nid:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    scr = cfg['screens'][ns][nid]
    pl = scr.get('playlist', []) or []
    last = scr.get('last_item_status', {}) or {}
    out = []
    for it in pl:
        try:
            fid = it.get('id')
            f = str(it.get('file') or '')
            base = ''
            if f:
                try:
                    base = f.split('?')[0].split('/')[-1]
                except Exception:
                    base = f
            keys = []
            if fid:
                keys.append(f'id:{fid}')
            if f:
                keys.append(f'file:{f}')
            if base and base != f:
                keys.append(f'file:{base}')
            matched_key = None
            matched_status = None
            for k in keys:
                if k in last:
                    matched_key = k
                    matched_status = last.get(k)
                    break
            out.append({'id': fid, 'file': f, 'file_base': base, 'try_keys': keys, 'matched_key': matched_key, 'last_status': matched_status})
        except Exception:
            out.append({'id': it.get('id'), 'file': it.get('file'), 'error': 'inspect-failed'})
    return jsonify({'success': True, 'keys_present': list(last.keys()), 'items': out})

# -------- Lightweight command channel (dashboard -> client) --------
@app.route('/api/push_command', methods=['POST'])
@login_required
def push_command():
    """Queue a command for a screen. Body: {store_id, screen_id, type, item_id?, file?}
    Types: 'reload', 'retry_item', 'flush_cache'. Clients should poll /api/commands.
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    store_id = str(data.get('store_id') or '')
    screen_id = str(data.get('screen_id') or '')
    ctype = (data.get('type') or '').strip().lower()
    item_id = data.get('item_id')
    file = data.get('file')
    if not store_id or not screen_id or ctype not in {'reload','retry_item','flush_cache'}:
        return jsonify({'success': False, 'error': 'invalid parameters'}), 400
    # Dashboard-only: commands are queued under the admin's tenant config
    cfg = ensure_playlists_structure(load_store_config())
    ns, nid = _normalize_screen_ref(cfg, store_id, screen_id)
    if not ns or not nid:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    cmd = {
        'id': str(uuid.uuid4()),
        'ts': int(time.time()),
        'type': ctype,
        'item_id': item_id,
        'file': file
    }
    q = cfg['screens'][ns][nid].setdefault('cmd_queue', [])
    q.append(cmd)
    # Trim to last 50
    if len(q) > 50:
        del q[:-50]
    save_store_config(cfg)
    return jsonify({'success': True, 'command': cmd})

@app.route('/api/commands', methods=['GET'])
def pop_commands():
    """Client polls for pending commands. Query: store_id, screen_id, limit? pop=1|0
    Returns and optionally clears the queue.
    """
    store_id = request.args.get('store_id') or ''
    screen_id = request.args.get('screen_id') or ''
    pop = (request.args.get('pop', '1') not in ('0', 'false', 'no'))
    try:
        limit = int(request.args.get('limit') or '10')
    except Exception:
        limit = 10
    # Allow either device with pairing code or dashboard session
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key and not _safe_user_key():
        return jsonify({'success': False, 'error': 'pair code required'}), 403
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(user_key) if user_key else load_store_config())
    ns, nid = _normalize_screen_ref(cfg, store_id, screen_id)
    if not ns or not nid:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    scr = cfg['screens'][ns][nid]
    q = list(scr.get('cmd_queue', []))
    out = q[:max(0, limit)]
    if pop and out:
        # remove returned commands
        scr['cmd_queue'] = q[len(out):]
        if user_key:
            save_store_config_for_user_safe_key(user_key, cfg)
        else:
            save_store_config(cfg)
    return jsonify({'success': True, 'commands': out, 'remaining': len(scr.get('cmd_queue', []))})

# Internal helper: enqueue a command into the config object for a given screen
def _enqueue_command_in_cfg(cfg, store_id, screen_id, ctype='reload', item_id=None, file=None):
    try:
        ns, nid = _normalize_screen_ref(cfg, str(store_id), str(screen_id))
        if not ns or not nid:
            return None
        cmd = {
            'id': str(uuid.uuid4()),
            'ts': int(time.time()),
            'type': ctype,
            'item_id': item_id,
            'file': file,
        }
        q = cfg.setdefault('screens', {}).setdefault(ns, {}).setdefault(nid, {}).setdefault('cmd_queue', [])
        q.append(cmd)
        if len(q) > 50:
            del q[:-50]
        return cmd
    except Exception:
        return None

# -------- One-off migration: local static/uploads -> R2 bucket --------
@app.route('/admin/migrate_to_r2', methods=['POST'])
def migrate_to_r2():
    if not r2_enabled():
        return jsonify({'success': False, 'error': 'R2 not configured'}), 400
    # Simple secret guard to avoid exposing in prod; set MIGRATE_SECRET env var
    secret = os.environ.get('MIGRATE_SECRET')
    provided = request.headers.get('X-Admin-Secret') or request.args.get('secret')
    if not secret or provided != secret:
        return jsonify({'success': False, 'error': 'unauthorized'}), 401
    folder = app.config['UPLOAD_FOLDER']
    migrated = []
    skipped = []
    failed = []
    try:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            if not allowed_file(name):
                continue
            # Skip if already present in R2
            if r2_object_exists(name):
                skipped.append(name)
                continue
            try:
                with open(path, 'rb') as fh:
                    data = fh.read()
                r2_put_bytes(name, data, content_type=_guess_mime(name))
                migrated.append(name)
            except Exception as e:
                failed.append({'name': name, 'error': str(e)})
        return jsonify({'success': True, 'migrated': migrated, 'skipped': skipped, 'failed': failed})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/screen_status', methods=['GET'])
@slowlog(300)
@with_etag_json
def screen_status():
    """Return online/offline status for all screens across all stores."""
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    # Allow dashboard session without code; otherwise require code
    if not user_key and not _safe_user_key():
        return {'success': False, 'error': 'pair code required'}, 403
    cfg = load_store_config_for_user_safe_key(user_key) if user_key else load_store_config()
    now = int(time.time())
    result = {}
    for store_id, screens in cfg.get('screens', {}).items():
        for sid, sdata in (screens or {}).items():
            last_seen = int(sdata.get('last_seen', 0) or 0)
            online = (now - last_seen) < HEARTBEAT_TIMEOUT
            result.setdefault(store_id, {})[sid] = 'online' if online else 'offline'
    # Return plain dict to allow decorator to attach ETag
    return {'success': True, 'status': result}

@app.route('/api/screen_status/<store_id>', methods=['GET'])
@slowlog(300)
@with_etag_json
def screen_status_by_store(store_id):
    """Return status mapping for a specific store (lighter payload for dashboard)."""
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key and not _safe_user_key():
        return {'success': False, 'error': 'pair code required'}, 403
    cfg = load_store_config_for_user_safe_key(user_key) if user_key else load_store_config()
    now = int(time.time())
    screens = cfg.get('screens', {}).get(store_id, {}) or {}
    result = {}
    for sid, sdata in screens.items():
        last_seen = int(sdata.get('last_seen', 0) or 0)
        online = (now - last_seen) < HEARTBEAT_TIMEOUT
        result[sid] = 'online' if online else 'offline'
    logging.debug('STATUS store=%s result=%s', store_id, result)
    # Return plain dict to allow decorator to attach ETag
    return {'success': True, 'status': result}

# -------------------- Core Configuration & Media Type Definitions --------------------
CONFIG_FILE = 'store_config.json'

# --- Multi-tenant config selection (per-logged-in user) ---
def _safe_user_key() -> Optional[str]:
    """Return a safe identifier for the current logged-in user based on session.
    Prefers email; falls back to username/name. Returns None if no session user.
    The key is sanitized to [a-z0-9._-] and '@' becomes '_at_'.
    """
    try:
        # Avoid touching session outside a request context (e.g., app startup / workers preload)
        if not has_request_context():
            return None
        # Flask's session is a dict-like object; access directly
        u = session.get('user')
        if not isinstance(u, dict):
            return None
        # Accept multiple common identity keys: email, name, username, login
        raw = (u.get('email') or u.get('name') or u.get('username') or u.get('login') or '').strip().lower()
        if not raw:
            return None
        # replace '@' to keep email uniqueness without special char
        raw = raw.replace('@', '_at_')
        safe = ''.join(c for c in raw if (c.isalnum() or c in '._-'))
        return safe or None
    except Exception:
        return None

def _effective_config_path() -> str:
    """Return the path to the active store config file.
    - If a user is logged in (dashboard/browser requests), use a per-user file.
    - Otherwise (TV clients without session), use the legacy global CONFIG_FILE.
    """
    try:
        k = _safe_user_key()
        if k:
            return f"store_config__{k}.json"
    except Exception:
        pass
    return CONFIG_FILE

# Per-user content prefix util
def _user_content_prefix() -> Optional[str]:
    """Return a bucket/local prefix root for the current user, e.g. 'users/john_at_gmail.com'.
    Returns None if no user (devices and public routes shouldn't access user media APIs).
    In TESTING mode, return a stable fake user root for isolation.
    """
    k = _safe_user_key()
    if not k:
        try:
            if app.config.get('TESTING'):
                return 'users/testuser'
        except Exception:
            pass
        return None
    return f"users/{k}"
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, 'avatars')
os.makedirs(AVATAR_FOLDER, exist_ok=True)

# Cache folder for generated thumbnails
THUMB_FOLDER = os.path.join('static', 'thumbs')
VTHUMB_FOLDER = os.path.join('static', 'vthumbs')
VPREVIEW_FOLDER = os.path.join('static', 'vpreviews')
os.makedirs(THUMB_FOLDER, exist_ok=True)
os.makedirs(VTHUMB_FOLDER, exist_ok=True)
os.makedirs(VPREVIEW_FOLDER, exist_ok=True)

# Categorized extension sets (keep lowercase)
IMAGE_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'bmp', 'webp', 'svg', 'avif', 'heic', 'heif', 'tif', 'tiff'
}
ANIMATED_EXTENSIONS = {
    'gif', 'webp'
}
VIDEO_EXTENSIONS = {
    'mp4', 'webm', 'ogg', 'mov', 'avi', 'mkv', 'm4v'
}

ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | ANIMATED_EXTENSIONS | VIDEO_EXTENSIONS

# Flask config values
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Optional: size limit (e.g., 500MB) - adjust as needed
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

def classify_media(filename: str) -> str:
    """Classify media by extension into image / animated / video.
    Falls back to 'image' if unknown but allowed (future-proofing)."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    if ext in ANIMATED_EXTENSIONS:
        return 'animated'
    return 'image'

def load_store_config():
    """Load JSON config; create default if missing; backfill structural keys.
    Uses a per-user config file when a session user exists; otherwise global.
    """
    cfg_path = _effective_config_path()
    is_user_scoped = (cfg_path != CONFIG_FILE)
    if not os.path.exists(cfg_path):
        # For user-scoped configs, start EMPTY (no stores/screens).
        # For the global/legacy config, keep the legacy single master store.
        cfg = get_default_config(user_scoped=is_user_scoped)
        if cfg.get('stores') and 'master_store_id' not in cfg:
            try:
                cfg['master_store_id'] = cfg['stores'][0]['id']
            except Exception:
                pass
        save_store_config(cfg)
        return cfg
    try:
        with open(cfg_path, 'r') as f:
            cfg = json.load(f)
    except Exception:
        # Backup corrupt file and reset to default
        backup_path = cfg_path + '.corrupt.bak'
        try:
            shutil.copyfile(cfg_path, backup_path)
            print(f"Backed up corrupt config to {backup_path}")
        except Exception:
            pass
        # On corrupt user-scoped config, reset to EMPTY; for global, use legacy default
        if is_user_scoped:
            cfg = get_default_config(user_scoped=True)
        else:
            cfg = get_default_config(user_scoped=False)
    # For user-scoped configs, keep them empty until the user creates stores/screens.
    # Backfill master_store_id if missing
    if 'master_store_id' not in cfg and cfg.get('stores'):
        cfg['master_store_id'] = cfg['stores'][0]['id']
        save_store_config(cfg)
    return cfg

@app.route('/supported_extensions')
@with_etag_json
def supported_extensions():
    """Expose supported extensions categorized for front-end dynamic usage."""
    payload = {
        'success': True,
        'images': sorted(list(IMAGE_EXTENSIONS - ANIMATED_EXTENSIONS)),  # pure still images
        'animated': sorted(list(ANIMATED_EXTENSIONS)),
        'videos': sorted(list(VIDEO_EXTENSIONS)),
        'all': sorted(list(ALLOWED_EXTENSIONS))
    }
    # Return tuple to preserve stronger cache header via decorator
    return payload, 200, {'Cache-Control': 'public, max-age=3600'}

# (duplicate /healthz removed; using earlier _healthz route)

# Simple version endpoint for human/debug consumption
@app.route('/version')
def version():
    return jsonify({
        'build': BUILD_STAMP,
        'commit': GIT_COMMIT,
    'time': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    })

@app.route('/whoami')
def whoami():
    """Lightweight diagnostics for session/user scoping.
    Returns current session username variants, safe key, and active config path.
    """
    try:
        u = session.get('user')
        key = _safe_user_key()
        return jsonify({
            'success': True,
            'session_user': u if isinstance(u, dict) else None,
            'resolved_safe_key': key,
            'config_path': _effective_config_path(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# -------------------- Video Streaming with HTTP Range Support --------------------
# More accurate MIME types improve playback compatibility for formats like MOV/MKV/AVI
VIDEO_MIME = {
    'mp4': 'video/mp4',
    'm4v': 'video/mp4',
    'webm': 'video/webm',
    'ogg': 'video/ogg',
    'mov': 'video/quicktime',
    'avi': 'video/x-msvideo',
    'mkv': 'video/x-matroska',
}

def _video_mime(ext: str) -> str:
    ext = (ext or '').lower()
    return VIDEO_MIME.get(ext, f'video/{ext or "mp4"}')
@app.route('/media/<path:filename>', methods=['GET','HEAD'])
def stream_media(filename):
    """Stream large video files with HTTP Range (partial content) support so clients can
    start playback without downloading the entire file first."""
    # Basic security / validation
    if not allowed_file(filename):
        return jsonify({'error': 'file not allowed'}), 400
    ext = filename.rsplit('.',1)[-1].lower()
    if ext not in VIDEO_EXTENSIONS:  # Only stream videos here; others go through static
        return redirect(url_for('static', filename=f'uploads/{filename}'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'not found'}), 404

    file_size = os.path.getsize(file_path)
    mtime = os.path.getmtime(file_path)
    lm_http = http_date(mtime)
    # Simple, fast ETag derived from mtime and size (no content hashing)
    etag = f'{int(mtime):x}-{file_size:x}'

    def _parse_inm(raw: str | None) -> set[str]:
        if not raw:
            return set()
        tokens = []
        for part in raw.split(','):
            p = part.strip()
            if p.startswith('W/'):
                p = p[2:].strip()
            if p.startswith('"') and p.endswith('"') and len(p) >= 2:
                p = p[1:-1]
            tokens.append(p)
        return set(t for t in tokens if t)
    range_header = request.headers.get('Range')
    logging.debug(f"/media request filename=%s method=%s range=%s", filename, request.method, range_header)
    if request.method == 'HEAD':
        # Fast metadata response
        resp = Response(status=200, mimetype=_video_mime(ext))
        resp.headers.add('Accept-Ranges', 'bytes')
        resp.headers.add('Content-Length', str(file_size))
        resp.headers.add('Last-Modified', lm_http)
        try:
            resp.set_etag(etag)
        except Exception:
            resp.headers['ETag'] = f'"{etag}"'
        resp.headers.setdefault('Cache-Control', 'public, max-age=3600')
        return resp
    # Conditional GET for full representation
    inm = _parse_inm(request.headers.get('If-None-Match'))
    if not range_header and etag in inm:
        return Response(status=304)
    if range_header:
        # Example: Range: bytes=START-END
        try:
            units, rng = range_header.split('=')
            if units != 'bytes':
                raise ValueError('Only bytes supported')
            start_str, end_str = (rng.split('-') + [''])[:2]
            start = int(start_str) if start_str else 0
            # If no end specified, serve only an initial chunk so clients (ExoPlayer) can begin quickly
            CHUNK_MAX = 1024 * 1024  # 1MB initial chunk when open-ended
            if end_str.strip() == '':
                end = min(start + CHUNK_MAX - 1, file_size - 1)
            else:
                end = int(end_str)
            end = min(end, file_size - 1)
            if start > end or start >= file_size:
                return Response(status=416, headers={'Content-Range': f'bytes */{file_size}'})

            def partial_gen(s, e):
                with open(file_path, 'rb') as f:
                    f.seek(s)
                    remaining = e - s + 1
                    chunk = 1024 * 256  # 256KB sub-chunks
                    while remaining > 0:
                        read_len = min(chunk, remaining)
                        data = f.read(read_len)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            length = end - start + 1
            resp = Response(partial_gen(start, end), 206, mimetype=_video_mime(ext))
            resp.headers.add('Accept-Ranges', 'bytes')
            resp.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            resp.headers.add('Content-Length', str(length))
            resp.headers.add('Last-Modified', lm_http)
            try:
                resp.set_etag(etag)
            except Exception:
                resp.headers['ETag'] = f'"{etag}"'
            # Encourage client reuse; range responses can be cached by many clients
            resp.headers.add('Cache-Control', 'public, max-age=3600')
            return resp
        except Exception as e:
            print(f"Range parse error: {e}")
            # Fallback to full file below
    # No Range header: send small iterable response to avoid loading full file in memory
    def generate():
        chunk_size = 1024 * 512  # 512KB
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    resp = Response(generate(), 200, mimetype=_video_mime(ext))
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(file_size))
    resp.headers.add('Last-Modified', lm_http)
    try:
        resp.set_etag(etag)
    except Exception:
        resp.headers['ETag'] = f'"{etag}"'
    resp.headers.setdefault('Cache-Control', 'public, max-age=3600')
    return resp

def ensure_playlists_structure(config):
    changed = False
    for store_id, screens in config.get('screens', {}).items():
        for sid, sdata in screens.items():
            if 'playlist' not in sdata or not isinstance(sdata.get('playlist'), list):
                pl = []
                if sdata.get('file'):
                    pl.append({
                        'id': str(uuid.uuid4()),
                        'file': sdata['file'],
                        'enabled': True,
                        'start': None,
                        'end': None,
                        'schedule': [],  # NEW multi-window support
                        'duration': 10,
                        'repeat': True,
                        'link_next': False,
                        'media_type': classify_media(sdata['file'])
                    })
                sdata['playlist'] = pl
                changed = True
            # Initialize runtime rotation metadata if not present
            if 'rotation_meta' not in sdata:
                sdata['rotation_meta'] = {'last_index': 0, 'last_ts': 0}
                changed = True
            else:
                for item in sdata['playlist']:
                    item.setdefault('id', str(uuid.uuid4()))
                    item.setdefault('enabled', True)
                    item.setdefault('start', None)
                    item.setdefault('end', None)
                    item.setdefault('schedule', [])  # backfill schedule list
                    item.setdefault('duration', 10)
                    item.setdefault('repeat', True)
                    item.setdefault('link_next', False)
                    # Backfill media_type for older entries
                    if 'media_type' not in item and item.get('file'):
                        item['media_type'] = classify_media(item['file'])
                if 'rotation_meta' not in sdata:
                    sdata['rotation_meta'] = {'last_index': 0, 'last_ts': 0}
                    changed = True
    if changed:
        save_store_config(config)
    return config

def get_default_config(user_scoped: bool = False):
    """Get default store configuration.
    - For new users (user_scoped=True): start empty (no stores/screens).
    - For global legacy config: keep the existing single-store default.
    """
    if user_scoped:
        # Seed a single master store with NO screens; the UI will show add placeholders.
        master_id = '1000'
        return {
            'stores': [
                {'id': master_id, 'name': 'My First Store'}
            ],
            'master_store_id': master_id,
            'screens': {
                master_id: {}
            }
        }
    return {
        'stores': [
            {'id': '1881', 'name': 'Canley Vale'}
        ],
        'screens': {
            '1881': {
                'screen1': {'file': None, 'vertical': True, 'horizontal': True, 'rotation': 0, 'playlist': []},
                'screen2': {'file': None, 'vertical': True, 'horizontal': True, 'rotation': 0, 'playlist': []},
                'screen3': {'file': None, 'vertical': True, 'horizontal': True, 'rotation': 0, 'playlist': []},
                'promo1': {'file': None, 'vertical': True, 'horizontal': False, 'rotation': 0, 'playlist': []},
                'promo2': {'file': None, 'vertical': True, 'horizontal': False, 'rotation': 0, 'playlist': []},
                'promo3': {'file': None, 'vertical': True, 'horizontal': False, 'rotation': 0, 'playlist': []}
            }
        }
    }

# -------------------- User pairing code utilities --------------------
def _safe_key_from_username(username: str | None) -> Optional[str]:
    if not username:
        return None
    try:
        raw = str(username).strip().lower().replace('@', '_at_')
        safe = ''.join(c for c in raw if (c.isalnum() or c in '._-'))
        return safe or None
    except Exception:
        return None

def _gen_unique_4digit_code(db) -> str:
    # Try up to 50 attempts to avoid rare collisions
    for _ in range(50):
        code = str(random.randint(1000, 9999))
        row = db.execute('SELECT 1 FROM users WHERE link_code = ?', (code,)).fetchone()
        if not row:
            return code
    # As a fallback, return a time-based suffix to maintain 4 digits
    return str(int(time.time()))[-4:]

def _ensure_user_link_code(username: str) -> str:
    db = get_db()
    uname = (username or '').strip().lower()
    r = db.execute('SELECT link_code FROM users WHERE username = ?', (uname,)).fetchone()
    if r and r['link_code']:
        return str(r['link_code'])
    code = _gen_unique_4digit_code(db)
    try:
        db.execute('UPDATE users SET link_code = ? WHERE username = ?', (code, uname))
        db.commit()
    except Exception:
        # If UPDATE failed (row might not exist), try insert minimal row
        try:
            db.execute('INSERT OR IGNORE INTO users (username, link_code) VALUES (?, ?)', (uname, code))
            db.commit()
        except Exception:
            pass
    return code

def _resolve_user_key_by_code(raw_code: Optional[str]) -> Optional[str]:
    """Map a 4-digit pairing code to the user's safe key for per-user configs.
    Returns None if code is invalid or not found.
    """
    try:
        code = (raw_code or '').strip()
        if not (len(code) == 4 and code.isdigit()):
            return None
        db = get_db()
        row = db.execute('SELECT username FROM users WHERE link_code = ?', (code,)).fetchone()
        if not row:
            return None
        uname = (row['username'] or '').strip().lower()
        return _safe_key_from_username(uname)
    except Exception:
        return None

def _get_current_username_from_session() -> Optional[str]:
    try:
        # Avoid using session outside a request context
        if not has_request_context():
            return None
        u = session.get('user')
        if not isinstance(u, dict):
            return None
        # Prefer email when present (OAuth), else name/username/login
        return (u.get('email') or u.get('name') or u.get('username') or u.get('login') or '').strip().lower() or None
    except Exception:
        return None

def _config_path_for_user_safe_key(safe_key: str) -> str:
    return f"store_config__{safe_key}.json"

def load_store_config_for_user_safe_key(safe_key: str):
    """Load another user's config by safe key (used for code-based listing).
    Seeds from global master if missing, mirroring load_store_config behavior.
    """
    path = _config_path_for_user_safe_key(safe_key)
    is_user_scoped = True
    if not os.path.exists(path):
        # New per-user config: seed from current global config if available,
        # so existing stores/screens layout is visible to the newly paired user.
        try:
            global_cfg = None
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    global_cfg = json.load(f)
            if isinstance(global_cfg, dict) and global_cfg.get('stores') and global_cfg.get('screens'):
                # Shallow copy to avoid accidental mutation; per-user edits will diverge afterwards
                cfg = {
                    'stores': list(global_cfg.get('stores', [])),
                    'screens': dict(global_cfg.get('screens', {})),
                    'master_store_id': global_cfg.get('master_store_id') or (global_cfg.get('stores',[{}])[0].get('id') if global_cfg.get('stores') else None),
                }
            else:
                cfg = get_default_config(user_scoped=True)
        except Exception:
            cfg = get_default_config(user_scoped=True)
        if cfg.get('stores') and 'master_store_id' not in cfg:
            try:
                cfg['master_store_id'] = cfg['stores'][0]['id']
            except Exception:
                pass
        # Save to user-scoped file
        try:
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            pass
        return cfg
    try:
        with open(path, 'r') as f:
            cfg = json.load(f)
    except Exception:
        # Corrupt -> back up and reset to per-user default (single master store)
        try:
            shutil.copyfile(path, path + '.corrupt.bak')
        except Exception:
            pass
        cfg = get_default_config(user_scoped=True)
        try:
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            pass
        return cfg
    # backfill master_store_id
    if 'master_store_id' not in cfg and cfg.get('stores'):
        cfg['master_store_id'] = cfg['stores'][0]['id']
        try:
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            pass
    return cfg

def save_store_config_for_user_safe_key(safe_key: str, config):
    """Save the given config to the per-user JSON path atomically."""
    try:
        path = _config_path_for_user_safe_key(safe_key)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        print(f"Configuration atomically saved to {path}")
    except Exception as e:
        print(f"Error saving per-user configuration: {e}")
        raise

@app.route('/api/stores_by_code/<code>', methods=['GET'])
@with_etag_json
def stores_by_code(code):
    """Return stores and screens for the user identified by a 4-digit code.
    Response: {success, user:{username}, stores:[{id,name}], screens:{store_id:{screen_id:{...}}}}
    """
    try:
        raw = (code or '').strip()
        if not (len(raw) == 4 and raw.isdigit()):
            return {'success': False, 'error': 'invalid code'}, 400
        db = get_db()
        row = db.execute('SELECT username FROM users WHERE link_code = ?', (raw,)).fetchone()
        if not row:
            return {'success': False, 'error': 'code not found'}, 404
        uname = (row['username'] or '').strip().lower()
        safe_key = _safe_key_from_username(uname)
        if not safe_key:
            return {'success': False, 'error': 'invalid user'}, 404
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(safe_key))
        # Return minimal listing to the TV app
        return {
            'success': True,
            'user': {'username': uname},
            'stores': cfg.get('stores', []),
            'screens': cfg.get('screens', {})
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

@app.route('/profile', methods=['GET'])
@login_required
def profile():
    uname = _get_current_username_from_session()
    code = None
    full_name = None
    try:
        if uname:
            code = _ensure_user_link_code(uname)
            row = get_db().execute('SELECT full_name FROM users WHERE username = ?', (uname,)).fetchone()
            full_name = (row['full_name'] if row and 'full_name' in row.keys() else None)
    except Exception:
        pass
    # Basic cache control to avoid exposing stale codes
    resp = make_response(render_template('profile.html', username=uname, full_name=full_name, link_code=code, build_stamp=BUILD_STAMP))
    try:
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    except Exception:
        pass
    return resp

@app.route('/profile/regenerate_code', methods=['POST'])
@login_required
def regenerate_code():
    uname = _get_current_username_from_session()
    if not uname:
        return jsonify({'success': False, 'error': 'auth required'}), 403
    db = get_db()
    try:
        code = _gen_unique_4digit_code(db)
        db.execute('UPDATE users SET link_code = ? WHERE username = ?', (code, uname))
        db.commit()
        return jsonify({'success': True, 'link_code': code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ----- Profile management APIs for in-drawer profile panel -----
@app.route('/api/me', methods=['GET'])
@login_required
def api_me():
    try:
        uname = _get_current_username_from_session()
        if not uname:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        db = get_db()
        row = db.execute('SELECT username, full_name, avatar FROM users WHERE username = ?', (uname,)).fetchone()
        full_name = (row['full_name'] if row and 'full_name' in row.keys() else None)
        avatar_rel = (row['avatar'] if row and 'avatar' in row.keys() else None)
        avatar_url = None
        try:
            if avatar_rel:
                avatar_url = url_for('static', filename=avatar_rel)
        except Exception:
            avatar_url = None
        code = _ensure_user_link_code(uname)
        return jsonify({'success': True, 'username': uname, 'full_name': full_name, 'avatar_url': avatar_url, 'link_code': code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/profile/name', methods=['POST'])
@login_required
def api_profile_update_name():
    try:
        data = request.get_json() or {}
        full_name = (data.get('full_name') or '').strip()
        if len(full_name) < 2:
            return jsonify({'success': False, 'error': 'name too short'}), 400
        uname = _get_current_username_from_session()
        db = get_db()
        db.execute('UPDATE users SET full_name = ? WHERE username = ?', (full_name, uname))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/profile/password', methods=['POST'])
@login_required
def api_profile_change_password():
    try:
        data = request.get_json() or {}
        current = data.get('current_password') or ''
        new = data.get('new_password') or ''
        if len(new) < 6:
            return jsonify({'success': False, 'error': 'password too short'}), 400
        uname = _get_current_username_from_session()
        db = get_db()
        row = db.execute('SELECT password_hash FROM users WHERE username = ?', (uname,)).fetchone()
        ph = row['password_hash'] if row else None
        if not ph or not check_password_hash(ph, current):
            return jsonify({'success': False, 'error': 'current password incorrect'}), 400
        db.execute('UPDATE users SET password_hash = ? WHERE username = ?', (generate_password_hash(new), uname))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/profile/delete', methods=['POST'])
@login_required
def api_profile_delete_account():
    try:
        data = request.get_json() or {}
        current = data.get('current_password') or ''
        uname = _get_current_username_from_session()
        db = get_db()
        row = db.execute('SELECT password_hash FROM users WHERE username = ?', (uname,)).fetchone()
        ph = row['password_hash'] if row else None
        if not ph or not check_password_hash(ph, current):
            return jsonify({'success': False, 'error': 'current password incorrect'}), 400
        # Remove per-user config file and any local uploads under users/<k>/
        try:
            safe_key = _safe_key_from_username(uname)
            if safe_key:
                cfg_file = f"store_config__{safe_key}.json"
                if os.path.exists(cfg_file):
                    try:
                        os.remove(cfg_file)
                    except Exception:
                        pass
                # Remove local uploads prefix folders if present
                uploads_root = os.path.join('static', 'uploads')
                prefix = os.path.join(uploads_root, 'users', safe_key)
                if os.path.exists(prefix):
                    import shutil
                    try:
                        shutil.rmtree(prefix, ignore_errors=True)
                    except Exception:
                        pass
                # Remove avatar file
                try:
                    avatar_path = os.path.join('static', 'uploads', 'avatars', f'{safe_key}.png')
                    if os.path.exists(avatar_path):
                        os.remove(avatar_path)
                except Exception:
                    pass
        except Exception:
            pass
        db.execute('DELETE FROM users WHERE username = ?', (uname,))
        db.commit()
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/profile/avatar', methods=['POST'])
@login_required
def api_profile_upload_avatar():
    try:
        if 'avatar' not in request.files:
            return jsonify({'success': False, 'error': 'no file'}), 400
        f = request.files['avatar']
        if not f or f.filename == '':
            return jsonify({'success': False, 'error': 'no file'}), 400
        # Process image to square 256x256 PNG
        from PIL import Image, ImageOps  # type: ignore
        im = Image.open(f.stream)
        im = ImageOps.exif_transpose(im)
        im = ImageOps.fit(im, (256, 256), Image.Resampling.LANCZOS)
        uname = _get_current_username_from_session()
        safe_key = _safe_key_from_username(uname or '') or 'user'
        save_path = os.path.join(AVATAR_FOLDER, f'{safe_key}.png')
        im.save(save_path, format='PNG')
        # Store relative path for static url building
        rel = os.path.join('uploads', 'avatars', f'{safe_key}.png')
        db = get_db()
        db.execute('UPDATE users SET avatar = ? WHERE username = ?', (rel, uname))
        db.commit()
        url = url_for('static', filename=rel)
        # Add cache-buster so the fresh avatar shows immediately
        try:
            ts = int(os.path.getmtime(save_path))
            sep = '&' if ('?' in url) else '?'
            url = f"{url}{sep}t={ts}"
        except Exception:
            pass
        return jsonify({'success': True, 'avatar_url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def save_store_config(config):
    """Save store configuration to the active JSON file (per-user or global)."""
    try:
        cfg_path = _effective_config_path()
        # Atomic write: write to temp file then replace
        tmp_file = cfg_path + '.tmp'
        with open(tmp_file, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, cfg_path)
        print(f"Configuration atomically saved to {cfg_path}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Minimal content-type helper for uploads to R2
def _guess_mime(filename: str) -> Optional[str]:
    try:
        import mimetypes
        mt, _ = mimetypes.guess_type(filename)
        return mt or None
    except Exception:
        return None

# ---- Thumbnail helpers and endpoint ----
def _image_ext(filename: str) -> str:
    return (filename.rsplit('.', 1)[-1].lower() if '.' in filename else '')

def _is_image(filename: str) -> bool:
    return _image_ext(filename) in IMAGE_EXTENSIONS

def _safe_upload_path(name: str) -> str:
    """Resolve to an absolute path under UPLOAD_FOLDER; prevent path traversal."""
    abs_upload = os.path.abspath(UPLOAD_FOLDER)
    target = os.path.abspath(os.path.join(UPLOAD_FOLDER, name))
    if not (target == abs_upload or target.startswith(abs_upload + os.sep)):
        raise ValueError('invalid filename')
    return target

try:
    from PIL import Image, ImageOps  # type: ignore
except Exception:
    Image = None  # Pillow optional; we'll fallback to original
    ImageOps = None

@app.route('/thumb/<int:width>/<path:filename>')
def thumbnail(width: int, filename: str):
    """Return a cached thumbnail for an uploaded image.
    - Supports nested folders (e.g., 2025-08/banner.jpg)
    - Caches to static/thumbs/{width}_{path_no_ext}.webp (slashes -> '__')
    - If local source doesn't exist and R2 is enabled, fetch from R2 to build the thumb.
    - If Pillow missing, redirect to original.
    """
    try:
        rel_path = str(filename).lstrip('/').replace('\\','/')
        # If CDN has the object, redirect to it immediately
        if r2_enabled():
            try:
                s3 = get_s3_client()
                if s3:
                    r2_key_try_webp = f"thumbs/{width}/" + os.path.splitext(rel_path)[0] + '.webp'
                    r2_key_try_jpg  = f"thumbs/{width}/" + os.path.splitext(rel_path)[0] + '.jpg'
                    try:
                        s3.head_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=r2_key_try_webp)
                        cdn = _cdn_thumb_url('thumbs', width, rel_path)
                        if cdn: return redirect(cdn, code=302)
                    except Exception:
                        try:
                            s3.head_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=r2_key_try_jpg)
                            cdn = _cdn_thumb_url('thumbs', width, rel_path)
                            if cdn: return redirect(cdn, code=302)
                        except Exception:
                            pass
            except Exception:
                pass
        if not _is_image(rel_path):
            return redirect(url_for('static', filename=f'uploads/{rel_path}'))
        local_src = _safe_upload_path(rel_path)
        have_local = os.path.exists(local_src)

        # Build a cache key that includes folders to avoid collisions
        name_no_ext = os.path.splitext(rel_path)[0].replace('/', '__')
        cached_name = f"{width}_{name_no_ext}.webp"
        cached_path = os.path.abspath(os.path.join(THUMB_FOLDER, cached_name))

        # Source mtime for rebuild decision
        src_mtime = None
        if have_local:
            try:
                src_mtime = os.path.getmtime(local_src)
            except Exception:
                src_mtime = None
        elif r2_enabled():
            try:
                s3 = get_s3_client()
                if s3:
                    head = s3.head_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=rel_path)
                    lm = head.get('LastModified')
                    if lm:
                        src_mtime = int(lm.timestamp())
            except Exception:
                src_mtime = None

        # Decide if we need to rebuild
        rebuild = True
        if os.path.exists(cached_path):
            if src_mtime is None:
                # If we cannot determine source time, keep existing
                rebuild = False
            else:
                try:
                    rebuild = os.path.getmtime(cached_path) < src_mtime
                except Exception:
                    rebuild = False

        if rebuild:
            if Image is None:
                return redirect(url_for('static', filename=f'uploads/{rel_path}'))
            try:
                os.makedirs(THUMB_FOLDER, exist_ok=True)
                # Open source image from local or R2
                if have_local:
                    im_ctx = Image.open(local_src)
                else:
                    s3 = get_s3_client()
                    if not s3:
                        return redirect(url_for('static', filename=f'uploads/{rel_path}'))
                    obj = s3.get_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=rel_path)
                    from io import BytesIO
                    im_ctx = Image.open(BytesIO(obj['Body'].read()))
                with im_ctx as im:
                    if im.mode in ('P', 'RGBA', 'LA'):
                        im = im.convert('RGB')
                    im_copy = im.copy()
                    target_w = int(width) if width>0 else 300
                    im_copy.thumbnail((target_w, 10000), Image.LANCZOS)
                    q = 60 if target_w <= 220 else 78
                    out_ext = 'webp'
                    try:
                        im_copy.save(cached_path, 'WEBP', quality=q, method=6)
                    except Exception:
                        fallback_path = cached_path[:-5] + '.jpg'
                        jq = 75 if target_w <= 220 else 85
                        im_copy.save(fallback_path, 'JPEG', quality=jq, optimize=True)
                        cached_path = fallback_path
                        cached_name = os.path.basename(cached_path)
                        out_ext = 'jpg'

                    # Push the generated thumbnail to R2 so CDN can serve it first
                    try:
                        if r2_enabled():
                            s3 = get_s3_client()
                            if s3:
                                # Use original path but swap extension to output format, keep nested folders
                                r2_key = f"thumbs/{width}/" + os.path.splitext(rel_path)[0] + ('.webp' if out_ext=='webp' else '.jpg')
                                with open(cached_path, 'rb') as fh:
                                    body = fh.read()
                                ct = 'image/webp' if out_ext=='webp' else 'image/jpeg'
                                s3.put_object(
                                    Bucket=os.environ['R2_BUCKET_NAME'],
                                    Key=r2_key,
                                    Body=body,
                                    ContentType=ct,
                                    CacheControl='public, max-age=2592000'
                                )
                    except Exception as _upl_err:
                        logging.debug('R2 upload (thumb) skipped/failed for %s: %s', rel_path, _upl_err)
            except Exception as e:
                logging.error('Thumbnail build failed for %s: %s', rel_path, e)
                return redirect(url_for('static', filename=f'uploads/{rel_path}'))

        resp = send_file(cached_path)
        try:
            resp.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
        except Exception:
            pass
        return resp
    except Exception as e:
        logging.error('Thumbnail error: %s', e)
        return jsonify({'error': 'bad request'}), 400

# ---- Video thumbnail endpoint using ffmpeg (if available) ----
def _ffmpeg_bin() -> Optional[str]:
    """Resolve ffmpeg executable path.
    Order: FFMPEG_BIN env -> shutil.which -> common absolute paths.
    """
    try:
        # 1) Explicit env override
        env_bin = os.environ.get('FFMPEG_BIN')
        if env_bin and os.path.exists(env_bin) and os.access(env_bin, os.X_OK):
            return env_bin
        # 2) PATH search
        found = _shutil.which('ffmpeg')
        if found:
            return found
        # 3) Common system locations (systemd may have a reduced PATH)
        for p in ('/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/bin/ffmpeg'):
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
    except Exception:
        pass
    return None

def _has_ffmpeg() -> bool:
    try:
        return _ffmpeg_bin() is not None
    except Exception:
        return False

def _safe_video_path(name: str) -> str:
    abs_upload = os.path.abspath(UPLOAD_FOLDER)
    target = os.path.abspath(os.path.join(UPLOAD_FOLDER, name))
    if not (target == abs_upload or target.startswith(abs_upload + os.sep)):
        raise ValueError('invalid filename')
    ext = (name.rsplit('.', 1)[-1].lower() if '.' in name else '')
    if ext not in VIDEO_EXTENSIONS:
        raise ValueError('not a video')
    return target

@app.route('/vthumb/<int:width>/<path:filename>')
def vthumbnail(width: int, filename: str):
    try:
        rel_path = str(filename).lstrip('/').replace('\\','/')
        # If CDN has the object, redirect to it immediately
        if r2_enabled():
            try:
                s3 = get_s3_client()
                if s3:
                    r2_key = f"vthumbs/{width}/" + os.path.splitext(rel_path)[0] + '.jpg'
                    try:
                        s3.head_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=r2_key)
                        cdn = _cdn_thumb_url('vthumbs', width, rel_path)
                        if cdn: return redirect(cdn, code=302)
                    except Exception:
                        pass
            except Exception:
                pass
        src_path = _safe_video_path(rel_path)
        # Include folders in cache key to avoid collisions
        name_no_ext = os.path.splitext(rel_path)[0].replace('/', '__')
        cached_name = f"{width}_{name_no_ext}.jpg"
        cached_path = os.path.abspath(os.path.join(VTHUMB_FOLDER, cached_name))
        rebuild = True
        if os.path.exists(cached_path):
            try:
                rebuild = os.path.getmtime(cached_path) < os.path.getmtime(src_path)
            except Exception:
                rebuild = True
        if rebuild:
            ffmpeg = _ffmpeg_bin()
            if not ffmpeg:
                return jsonify({'error': 'ffmpeg not available'}), 404
            os.makedirs(VTHUMB_FOLDER, exist_ok=True)
            try:
                # If local video source is missing but R2 is enabled, fetch to a temp file first
                tmp_src = None
                if not os.path.exists(src_path) and r2_enabled():
                    try:
                        s3 = get_s3_client()
                        if s3:
                            data = s3.get_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=rel_path)['Body'].read()
                            os.makedirs(os.path.dirname(src_path), exist_ok=True)
                            tmp_src = os.path.join(VTHUMB_FOLDER, f"_src_{name_no_ext}")
                            with open(tmp_src, 'wb') as fh:
                                fh.write(data)
                            src_use = tmp_src
                        else:
                            src_use = src_path
                    except Exception:
                        src_use = src_path
                else:
                    src_use = src_path

                cmd = [
                    ffmpeg, '-y', '-ss', '0.2', '-i', src_use,
                    '-vframes', '1', '-vf', f'scale={int(width) if width>0 else 300}:-1',
                    cached_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Push the generated vthumb to R2 for CDN delivery
                try:
                    if r2_enabled():
                        s3 = get_s3_client()
                        if s3 and os.path.exists(cached_path):
                            r2_key = f"vthumbs/{width}/" + os.path.splitext(rel_path)[0] + '.jpg'
                            with open(cached_path, 'rb') as fh:
                                body = fh.read()
                            s3.put_object(
                                Bucket=os.environ['R2_BUCKET_NAME'],
                                Key=r2_key,
                                Body=body,
                                ContentType='image/jpeg',
                                CacheControl='public, max-age=2592000'
                            )
                except Exception as _upl_err:
                    logging.debug('R2 upload (vthumb) skipped/failed for %s: %s', rel_path, _upl_err)
                if tmp_src and os.path.exists(tmp_src):
                    try: os.remove(tmp_src)
                    except Exception: pass
            except Exception as e:
                logging.error('ffmpeg thumbnail failed for %s: %s', rel_path, e)
                return jsonify({'error': 'thumb failed'}), 500
        resp = send_file(cached_path)
        try:
            resp.headers['Cache-Control'] = 'public, max-age=2592000'
        except Exception:
            pass
        return resp
    except Exception as e:
        logging.error('vthumbnail error: %s', e)
        return jsonify({'error': 'bad request'}), 400

# ---- Low-res video preview clip (first few seconds) ----
@app.route('/vpreview/<int:width>/<path:filename>')
def vpreview(width: int, filename: str):
    try:
        # Support files in nested folders (e.g., 2025-08/campaign/clip.mp4)
        rel_path = str(filename).lstrip('/').replace('\\','/')
        # If CDN has the preview, redirect to it immediately
        if r2_enabled():
            try:
                s3 = get_s3_client()
                if s3:
                    r2_key = f"vpreviews/{width}/" + os.path.splitext(rel_path)[0] + '.mp4'
                    try:
                        s3.head_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=r2_key)
                        cdn = _cdn_thumb_url('vpreviews', width, rel_path)
                        if cdn: return redirect(cdn, code=302)
                    except Exception:
                        pass
            except Exception:
                pass
        src_path = _safe_video_path(rel_path)
        # Store mp4 previews for broad compatibility; include folders in key to avoid collisions
        name_no_ext = os.path.splitext(rel_path)[0].replace('/', '__')
        cached_name = f"{width}_{name_no_ext}.mp4"
        cached_path = os.path.abspath(os.path.join(VPREVIEW_FOLDER, cached_name))
        rebuild = True
        if os.path.exists(cached_path):
            try:
                rebuild = os.path.getmtime(cached_path) < os.path.getmtime(src_path)
            except Exception:
                rebuild = True
        if rebuild:
            ffmpeg = _ffmpeg_bin()
            if not ffmpeg:
                return jsonify({'error': 'ffmpeg not available'}), 404
            os.makedirs(VPREVIEW_FOLDER, exist_ok=True)
            try:
                # If local video source is missing but R2 is enabled, fetch to a temp file first
                tmp_src = None
                if not os.path.exists(src_path) and r2_enabled():
                    try:
                        s3 = get_s3_client()
                        if s3:
                            data = s3.get_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=rel_path)['Body'].read()
                            os.makedirs(os.path.dirname(src_path), exist_ok=True)
                            tmp_src = os.path.join(VPREVIEW_FOLDER, f"_src_{name_no_ext}")
                            with open(tmp_src, 'wb') as fh:
                                fh.write(data)
                            src_use = tmp_src
                        else:
                            src_use = src_path
                    except Exception:
                        src_use = src_path
                else:
                    src_use = src_path
                # 6s low-bitrate H.264 baseline clip, scaled to width, no audio, faststart
                target_w = int(width) if width>0 else 360
                cmd = [
                    ffmpeg, '-y', '-ss', '0', '-t', '6', '-i', src_use,
                    '-an', '-vf', f'scale={target_w}:-2',
                    '-c:v', 'libx264', '-profile:v', 'baseline', '-preset', 'veryfast', '-b:v', '600k',
                    '-movflags', '+faststart', cached_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Push the generated preview to R2 for CDN delivery
                try:
                    if r2_enabled():
                        s3 = get_s3_client()
                        if s3 and os.path.exists(cached_path):
                            r2_key = f"vpreviews/{width}/" + os.path.splitext(rel_path)[0] + '.mp4'
                            with open(cached_path, 'rb') as fh:
                                body = fh.read()
                            s3.put_object(
                                Bucket=os.environ['R2_BUCKET_NAME'],
                                Key=r2_key,
                                Body=body,
                                ContentType='video/mp4',
                                CacheControl='public, max-age=2592000'
                            )
                except Exception as _upl_err:
                    logging.debug('R2 upload (vpreview) skipped/failed for %s: %s', rel_path, _upl_err)
                if tmp_src and os.path.exists(tmp_src):
                    try: os.remove(tmp_src)
                    except Exception: pass
            except Exception as e:
                logging.error('ffmpeg vpreview failed for %s: %s', rel_path, e)
                return jsonify({'error': 'preview failed'}), 500
        resp = send_file(cached_path, mimetype='video/mp4')
        try:
            resp.headers['Cache-Control'] = 'public, max-age=2592000'
        except Exception:
            pass
        return resp
    except Exception as e:
        logging.error('vpreview error: %s', e)
        return jsonify({'error': 'bad request'}), 400

def parse_time_string(val, now):
    if not val:
        return None
    try:
        if len(val) <= 8 and all(c.isdigit() or c==':' for c in val):
            parts = [int(p) for p in val.split(':')]
            while len(parts) < 3:
                parts.append(0)
            return datetime.combine(now.date(), dtime(parts[0], parts[1], parts[2]))
        return datetime.fromisoformat(val)
    except Exception:
        return None

def pick_active_playlist_item(screen, parent_config=None, store_id=None, screen_id=None):
    pl = screen.get('playlist', [])
    # If this screen is part of a sync group but doesn't yet have a concrete playlist item,
    # synthesize a read-only placeholder item so dashboard and players can show the synced media.
    try:
        groups = (cfg.get('sync_groups') or {}) if isinstance(cfg.get('sync_groups'), dict) else {}
        # Track which sync groups already have a real item on this screen
        have_groups = set()
        for _it in (pl or []):
            try:
                _sr = _it.get('sync_ref') if isinstance(_it, dict) else None
                if isinstance(_sr, dict) and _sr.get('group'):
                    have_groups.add(_sr.get('group'))
            except Exception:
                continue
        # Append placeholders for memberships missing a concrete item
        for gid, grp in (groups.items() if isinstance(groups, dict) else []):
            try:
                members = grp.get('members') or []
                mem = next((m for m in members if m.get('screen_id') == screen_id), None)
                if not mem:
                    continue
                if gid in have_groups:
                    continue
                fname = grp.get('filename') or None
                if not fname:
                    continue
                placeholder = {
                    'id': f"virtual:{gid}:{screen_id}",
                    'file': fname,
                    'enabled': True,
                    'start': None,
                    'end': None,
                    'schedule': [],
                    'duration': 10,
                    'repeat': True,
                    'link_next': False,
                    'media_type': classify_media(fname),
                    'sync_ref': {
                        'group': gid,
                        'role': mem.get('role') or 'follower',
                        'order': mem.get('order', 0)
                    }
                }
                # Do not mutate stored config; return a view list including the placeholder
                pl = list(pl) + [placeholder]
            except Exception:
                continue
    except Exception:
        pass
    if not pl:
        return screen.get('file')
    # Use local server time (was UTC) so user-entered wall-clock times align with expectations
    now = datetime.now()
    # Base enabled list (user toggle). Windows will not force-on disabled items.
    enabled = [i for i in pl if i.get('enabled', True)]
    scheduled = []
    fallback = []
    def interval_active(raw_s, raw_e, now, days=None):
        """Return True if now is inside the interval defined by raw_s/raw_e.
        Accepts:
          - time-only 'HH:MM[:SS]'
          - ISO 'YYYY-MM-DDTHH:MM:SS'
          - date-only 'YYYY-MM-DD'
        Rules:
          - If either side contains a date (absolute), weekday gating is ignored.
          - Date-only normalization:
              * start=date with no end -> active for that calendar day (00:00..23:59:59)
              * end=date with no start -> active for that calendar day (00:00..23:59:59)
          - Overnight:
              * time-only end < start wraps midnight
              * same-date absolute end < start -> treat as end + 1 day continuous
        """
        def is_time_only(v):
            return bool(v) and (len(v) <= 8) and (':' in v) and ('-' not in v)
        def is_date_only(v):
            return bool(v) and (len(v) == 10) and (v[4] == '-' and v[7] == '-')
        def is_absolute(v):
            return bool(v) and (('T' in v) or is_date_only(v))

        # If either boundary is absolute (has a date), ignore weekday gating
        if not (is_absolute(raw_s) or is_absolute(raw_e)):
            if days:
                wd = ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]
                if wd not in days:
                    return False

        if not (raw_s or raw_e):
            return False
        ws = parse_time_string(raw_s, now) if raw_s else None
        we = parse_time_string(raw_e, now) if raw_e else None
        # Normalize date-only single-sided inputs to same-day window
        if raw_e and is_date_only(raw_e) and we:
            we = we.replace(hour=23, minute=59, second=59, microsecond=999999)
        if (raw_s and is_date_only(raw_s)) and not raw_e and ws:
            # start is date-only, no end -> clamp end to end-of-day
            we = ws.replace(hour=23, minute=59, second=59, microsecond=999999)
        if (raw_e and is_date_only(raw_e)) and not raw_s and we:
            # end is date-only, no start -> clamp start to start-of-day
            ws = we.replace(hour=0, minute=0, second=0, microsecond=0)

        time_only = (is_time_only(raw_s) or is_time_only(raw_e))
        if ws and we:
            if we < ws:
                if not time_only and ws.date() == we.date():
                    we_plus = we + timedelta(days=1)
                    return ws <= now <= we_plus
                return (now >= ws) or (now <= we)
            return ws <= now <= we
        if ws and now < ws:
            return False
        if we and now > we:
            return False
        return True

    for item in enabled:
        st_raw = item.get('start')
        en_raw = item.get('end')
        schedule_windows = item.get('schedule') or []  # list of {'start':..., 'end':...}
        in_any_window = False
        # Evaluate multi windows first; if any valid, treat as scheduled
        if schedule_windows:
            for win in schedule_windows:
                if interval_active(win.get('start'), win.get('end'), now, win.get('days')):
                    in_any_window = True
                    break
        if in_any_window:
            scheduled.append(item)
            continue
        if st_raw or en_raw:
            if interval_active(st_raw, en_raw, now, item.get('days')):
                scheduled.append(item)
            else:
                fallback.append(item)
        elif item.get('enabled', True):
            fallback.append(item)
        else:
            fallback.append(item)
    # If no explicit scheduled windows right now, use enabled fallback respecting repeat
    active_set = scheduled if scheduled else [i for i in fallback if i.get('repeat', True)]
    if not active_set:
        return None
    # Duration-based sequential rotation tracking last change to avoid time modulo drift
    seq = scheduled if scheduled else active_set
    if not seq:
        return None
    meta = screen.setdefault('rotation_meta', {'last_index': 0, 'last_ts': int(now.timestamp())})
    idx = meta.get('last_index', 0)
    last_ts = meta.get('last_ts', int(now.timestamp()))
    # Clamp idx
    if idx >= len(seq):
        idx = 0
    current_item = seq[idx]
    dur = max(1, int(current_item.get('duration', 10)))
    elapsed = int(now.timestamp()) - int(last_ts)
    if elapsed >= dur:
        # advance
        idx = (idx + 1) % len(seq)
        meta['last_index'] = idx
        meta['last_ts'] = int(now.timestamp())
        if parent_config and store_id and screen_id:
            try:
                save_store_config(parent_config)
            except Exception as e:
                print(f"Rotation meta save failed: {e}")
        current_item = seq[idx]
        # persist change lazily (avoid too-frequent writes: only when index advances)
        try:
            # lightweight load/save pattern avoided; caller handles persistence
            pass
        except Exception:
            pass
    return current_item.get('file')

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    print("DEBUG: Dashboard route called")
    try:
        print("DEBUG: Loading store config...")
        # load_store_config respects the logged-in session via _effective_config_path
        config = ensure_playlists_structure(load_store_config())
        # Guard: ensure stores/screens keys exist even for new users
        if 'stores' not in config or not isinstance(config.get('stores'), list):
            config['stores'] = []
        if 'screens' not in config or not isinstance(config.get('screens'), dict):
            config['screens'] = {}
        # Expose media_base_url in config for front-end JS helpers
        try:
            mbu = get_media_base_url()
            config['media_base_url'] = mbu
            # Also provide under settings for backward compatibility
            settings = config.get('settings') or {}
            settings['media_base_url'] = mbu
            config['settings'] = settings
        except Exception as _e:
            print(f"DEBUG: Failed to set media_base_url in config: {_e}")
        print("DEBUG: Config loaded successfully")
        print(f"DEBUG: Config has {len(config.get('stores', []))} stores")
        print("DEBUG: Rendering template...")
        # Provide a cache-busting token for static assets (logo)
        try:
            import os, time
            logo_path = os.path.join(os.path.dirname(__file__), 'static', 'ea-logo.svg')
            asset_bust = int(os.path.getmtime(logo_path)) if os.path.exists(logo_path) else int(time.time())
        except Exception:
            asset_bust = 0
        # Compute user info for header menu (email + pairing code)
        try:
            u = session.get('user') or {}
            uname = (u.get('email') or u.get('name') or u.get('username') or '').strip()
            link_code = _ensure_user_link_code(uname) if uname else ''
        except Exception:
            uname = ''
            link_code = ''
        # After computing asset_bust, render the template
        resp = make_response(render_template(
            'dashboard.html',
            config=config,
            media_base_url=get_media_base_url(),
            asset_bust=asset_bust,
            build_stamp=BUILD_STAMP,
            git_commit=GIT_COMMIT,
            user_email=uname,
            link_code=link_code
        ))
        # Avoid CDN/browser caching the admin dashboard HTML
        try:
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        except Exception:
            pass
        return resp
    except Exception as e:
        print(f"DEBUG: Error in dashboard route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {e}", 500

@app.route('/upload_to_screen', methods=['POST'])
@login_required
def upload_to_screen():
    """Upload file to specific screen"""
    store_id = request.form.get('store_id')
    screen_id = request.form.get('screen_id')
    apply_to_all = request.form.get('apply_to_all', '').lower() == 'true'

    # Normalize screen_id: accept legacy short form (e.g. 'screen1') by expanding to '<store_id>_screen1' if needed
    try:
        if store_id and screen_id and store_id in load_store_config().get('screens', {}):
            cfg = load_store_config()
            if screen_id not in cfg['screens'][store_id]:
                candidate = f"{store_id}_{screen_id}"
                if candidate in cfg['screens'][store_id]:
                    print(f"[upload_to_screen] Mapped legacy screen_id '{screen_id}' -> '{candidate}' for store {store_id}")
                    screen_id = candidate
    except Exception as e:
        print(f"[upload_to_screen] Legacy mapping check failed: {e}")
    
    if 'file' not in request.files:
        print(f"[upload_to_screen] Missing file field store={store_id} screen={screen_id}")
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print(f"[upload_to_screen] Empty filename store={store_id} screen={screen_id}")
        return jsonify({'error': 'No file selected'}), 400
    
    print(f"[upload_to_screen] Incoming upload store={store_id} screen={screen_id} apply_all={apply_to_all} original_name={file.filename}")
    if file and allowed_file(file.filename):
        # Generate unique filename
        randname = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        # Put user content under users/<user>/<YYYY-MM>/
        month_prefix = datetime.now(timezone.utc).strftime('%Y-%m')
        user_root = _user_content_prefix() or 'public'
        key = _join_prefix_key(_join_prefix_key(user_root, month_prefix), randname)
        # Detect content-type
        content_type = file.mimetype or 'application/octet-stream'
        if r2_enabled():
            try:
                data = file.read()
                r2_put_bytes(key, data, content_type)
                print(f"[upload_to_screen] Uploaded to R2 as {key}")
            except Exception as _e_r2_up:
                logging.warning('R2 direct upload failed, falling back to local: %s', _e_r2_up)
                # Reset stream and fall back to local save
                try:
                    file.stream.seek(0)
                except Exception:
                    pass
                # Ensure local directory exists for user namespace
                local_dir = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(key))
                os.makedirs(local_dir, exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], key)
                try:
                    ext = randname.rsplit('.',1)[-1].lower()
                except Exception:
                    ext = ''
                if ext in IMAGE_EXTENSIONS and Image is not None and ImageOps is not None:
                    try:
                        img = Image.open(file.stream)
                        img = ImageOps.exif_transpose(img)
                        save_kwargs = {}
                        if ext in ('jpg','jpeg'): save_kwargs = {'quality': 90, 'optimize': True}
                        img.save(filepath, **save_kwargs)
                    except Exception:
                        try:
                            file.stream.seek(0)
                        except Exception:
                            pass
                        file.save(filepath)
                else:
                    file.save(filepath)
                print(f"[upload_to_screen] Saved locally as fallback {key} -> {filepath}")
        else:
            # Local-only: save under user namespace
            local_dir = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(key))
            os.makedirs(local_dir, exist_ok=True)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], key)
            # Normalize EXIF orientation for images to avoid client-side rotation surprises
            try:
                ext = randname.rsplit('.',1)[-1].lower()
            except Exception:
                ext = ''
            if ext in IMAGE_EXTENSIONS and Image is not None and ImageOps is not None:
                try:
                    img = Image.open(file.stream)
                    img = ImageOps.exif_transpose(img)
                    save_kwargs = {}
                    if ext in ('jpg','jpeg'): save_kwargs = {'quality': 90, 'optimize': True}
                    img.save(filepath, **save_kwargs)
                except Exception:
                    try:
                        file.stream.seek(0)
                    except Exception:
                        pass
                    file.save(filepath)
            else:
                file.save(filepath)
            print(f"[upload_to_screen] Saved as {key} -> {filepath}")

        # Update configuration
        config = ensure_playlists_structure(load_store_config())
    else:
        print(f"[upload_to_screen] Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type'}), 400

    # If apply_to_all was requested but this isn't the master store, downgrade to single-store
    if apply_to_all:
        master_store_id = config.get('master_store_id')
        if store_id != master_store_id:
            print(f"[upload_to_screen] apply_to_all requested by non-master store {store_id}. Downgrading to single-store upload.")
            apply_to_all = False

    if apply_to_all:
        # Apply the file to the same screen type across all stores
        screen_type = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id
        updated_stores: list[str] = []
        skipped_stores: list[str] = []
        created_screens: list[str] = []

        for current_store_id in config['screens']:
            target_screen_id = f"{current_store_id}_{screen_type}"
            legacy_id = screen_type
            if target_screen_id in config['screens'][current_store_id]:
                actual_screen_id = target_screen_id
            elif legacy_id in config['screens'][current_store_id]:
                actual_screen_id = legacy_id
            else:
                is_promo = screen_type.startswith('promo')
                config['screens'][current_store_id][target_screen_id] = {
                    'file': None,
                    'vertical': is_promo,
                    'horizontal': not is_promo,
                    'rotation': 0,
                    'protected': False,
                    'playlist': []
                }
                created_screens.append(f"{current_store_id}:{target_screen_id}")
                actual_screen_id = target_screen_id

            is_protected = config['screens'][current_store_id][actual_screen_id].get('protected', False)
            if is_protected:
                skipped_stores.append(current_store_id)
            else:
                scr = config['screens'][current_store_id][actual_screen_id]
                scr['file'] = key
                pl = scr.setdefault('playlist', [])
                if not any(i.get('file') == key for i in pl):
                    pl.append({'id': str(uuid.uuid4()), 'file': key, 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(key)})
                # Auto-push a reload for this screen so TVs update fast
                _enqueue_command_in_cfg(config, current_store_id, actual_screen_id, 'reload')
                updated_stores.append(current_store_id)

        save_store_config(config)
        print(f"[upload_to_screen] Apply-to-all updated stores={updated_stores} skipped={skipped_stores} created={created_screens}")
        message = f"File applied to {screen_type} in {len(updated_stores)} stores"
        if created_screens:
            message += f". Created {len(created_screens)} missing screens"
        if skipped_stores:
            message += f". Skipped {len(skipped_stores)} protected stores"

        return jsonify({
            'success': True,
            'filename': key,
            'url': build_public_url(key),
            'media_type': classify_media(key),
            'store_id': store_id,
            'screen_id': screen_id,
            'applied_to_all': True,
            'updated_stores': updated_stores,
            'skipped_stores': skipped_stores,
            'created_screens': created_screens,
            'message': message
        })

    # Single-store path
    if store_id in config.get('screens', {}) and screen_id in config['screens'].get(store_id, {}):
        screen_obj = config['screens'][store_id][screen_id]
        screen_obj['file'] = key
        pl = screen_obj.setdefault('playlist', [])
        if not any(i.get('file') == key for i in pl):
            pl.append({'id': str(uuid.uuid4()), 'file': key, 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(key)})
        # Auto-push a reload for this single screen
        _enqueue_command_in_cfg(config, store_id, screen_id, 'reload')
        save_store_config(config)
        print(f"[upload_to_screen] Single-store success store={store_id} screen={screen_id} file={key} playlist_len={len(pl)}")
        return jsonify({
            'success': True,
            'filename': key,
            'url': build_public_url(key),
            'media_type': classify_media(key),
            'store_id': store_id,
            'screen_id': screen_id,
            'applied_to_all': False
        })

    # If we reach here, the target screen does not exist
    return jsonify({'success': False, 'error': 'screen not found'}), 404

@app.route('/update_rotation', methods=['POST'])
@login_required
def update_rotation():
    """Update rotation setting for a screen"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        rotation = data.get('rotation', 0)

        if not store_id or not screen_id:
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400

        config = load_store_config()
        if store_id not in config['screens'] or screen_id not in config['screens'][store_id]:
            return jsonify({'error': 'Screen not found'}), 404

        if rotation not in [0, 90, 180, 270]:
            return jsonify({'error': 'Invalid rotation value'}), 400

        config['screens'][store_id][screen_id]['rotation'] = rotation
        save_store_config(config)
        return jsonify({'success': True, 'rotation': rotation})
    except Exception as e:
        print(f"Error updating rotation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_orientation', methods=['POST'])
@login_required
def update_orientation():
    """Update screen orientation settings"""
    data = request.get_json()
    store_id = data.get('store_id')
    screen_id = data.get('screen_id')
    orientation = data.get('orientation')
    value = data.get('value')
    
    config = load_store_config()
    if store_id in config['screens'] and screen_id in config['screens'][store_id]:
        config['screens'][store_id][screen_id][orientation] = value
        save_store_config(config)
        return jsonify({'success': True})
    
    return jsonify({'error': 'Invalid screen'}), 400

@app.route('/set_orientation_mode', methods=['POST'])
@login_required
def set_orientation_mode():
    """Set orientation mode in one call: vertical, horizontal, or default (none)."""
    try:
        data = request.get_json() or {}
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        mode = (data.get('mode') or '').lower()
        if not store_id or not screen_id or mode not in ['vertical','horizontal','default']:
            return jsonify({'error': 'store_id, screen_id and valid mode required'}), 400
        config = load_store_config()
        if store_id not in config['screens'] or screen_id not in config['screens'][store_id]:
            return jsonify({'error': 'Screen not found'}), 404
        if mode == 'vertical':
            config['screens'][store_id][screen_id]['vertical'] = True
            config['screens'][store_id][screen_id]['horizontal'] = False
        elif mode == 'horizontal':
            config['screens'][store_id][screen_id]['vertical'] = False
            config['screens'][store_id][screen_id]['horizontal'] = True
        else:  # default
            config['screens'][store_id][screen_id]['vertical'] = False
            config['screens'][store_id][screen_id]['horizontal'] = False
        save_store_config(config)
        return jsonify({'success': True, 'mode': mode})
    except Exception as e:
        print(f"Error setting orientation mode: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_protection', methods=['POST'])
@login_required
def update_protection():
    """Update screen protection status"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        protected = data.get('protected', False)
        
        if not store_id or not screen_id:
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400
            
        config = load_store_config()
        if store_id in config['screens'] and screen_id in config['screens'][store_id]:
            config['screens'][store_id][screen_id]['protected'] = protected
            save_store_config(config)
            return jsonify({'success': True, 'protected': protected})
        
        return jsonify({'error': 'Store or screen not found'}), 404
        
    except Exception as e:
        print(f"Error updating protection: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_screen_name', methods=['POST'])
@login_required
def update_screen_name():
    """Set or clear a human-friendly name for a screen.
    Body JSON: {store_id, screen_id, name}
    - name: trimmed; if empty, the custom name is removed and UI falls back to derived label.
    """
    try:
        data = request.get_json() or {}
        store_id = str(data.get('store_id') or '').strip()
        screen_id = str(data.get('screen_id') or '').strip()
        name = str(data.get('name') or '').strip()
        if not store_id or not screen_id:
            return jsonify({'success': False, 'error': 'store_id and screen_id required'}), 400

        cfg = ensure_playlists_structure(load_store_config())
        ns, nid = _normalize_screen_ref(cfg, store_id, screen_id)
        if not ns or not nid:
            return jsonify({'success': False, 'error': 'screen not found'}), 404

        # Sanitize length
        if len(name) > 100:
            name = name[:100]

        scr = cfg.get('screens', {}).get(ns, {}).get(nid)
        if scr is None:
            return jsonify({'success': False, 'error': 'screen not found'}), 404
        if name:
            scr['name'] = name
        else:
            # Clear custom name to fall back to derived label
            scr.pop('name', None)

        save_store_config(cfg)
        return jsonify({'success': True, 'name': scr.get('name', '')})
    except Exception as e:
        app.logger.exception('update_screen_name failed')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/tv_view/<store_id>/<screen_id>')
def tv_view(store_id, screen_id):
    """TV display view for specific screen.
    Note: Original implementation picked a single active file once per load.
    To support per-item custom duration switching without full page reload,
    client-side JS now fetches the playlist and cycles items using their
    'duration' (seconds) when any item has link_next=True.
    """
    config = load_store_config()
    screen_config = ensure_playlists_structure(config)['screens'].get(store_id, {}).get(screen_id, {})
    active_file = pick_active_playlist_item(screen_config, config, store_id, screen_id)
    return render_template('tv_view.html', screen_config=screen_config, screen_id=screen_id, store_id=store_id, active_file=active_file, media_base_url=get_media_base_url())

# ---------------------- Web Player (browser-based TV) ----------------------
@app.route('/webplayer')
@app.route('/webplayer/')
def webplayer_index():
    """Landing page to launch the browser-based TV player.
    Step 1: Enter the 4-digit TV link (pairing) code.
    """
    try:
        return render_template('webplayer/index.html')
    except Exception as e:
        return make_response(f"Webplayer index unavailable: {e}", 500)


@app.route('/webplayer/browse')
@app.route('/webplayer/browse/')
def webplayer_browse():
    """Step 2: After entering TV code and store code, show screens for that store.
    Query: ?code=NNNN&store_id=STORE
    The page fetches /api/stores_by_code/<code> then lists screens of store_id.
    """
    code = (request.args.get('code') or '').strip()
    store_id = (request.args.get('store_id') or '').strip()
    if not (len(code) == 4 and code.isdigit()) or not store_id:
        return redirect(url_for('webplayer_index'))
    try:
        return render_template('webplayer/browse.html', code=code, store_id=store_id)
    except Exception as e:
        return make_response(f"Webplayer browse unavailable: {e}", 500)

@app.route('/webplayer/store')
@app.route('/webplayer/store/')
def webplayer_store():
    """Intermediate step to enter store code after a valid TV code.
    Query: ?code=NNNN
    """
    code = (request.args.get('code') or '').strip()
    if not (len(code) == 4 and code.isdigit()):
        return redirect(url_for('webplayer_index'))
    try:
        return render_template('webplayer/store.html', code=code)
    except Exception as e:
        return make_response(f"Webplayer store step unavailable: {e}", 500)


@app.route('/webplayer/play')
@app.route('/webplayer/play/')
def webplayer_play():
    """Launch the full-screen web player for a given store/screen.
    Query params: store_id, screen_id, code (optional pairing code)
    """
    store_id = (request.args.get('store_id') or '').strip()
    screen_id = (request.args.get('screen_id') or '').strip()
    code = (request.args.get('code') or '').strip()
    if not store_id or not screen_id:
        return redirect(url_for('webplayer_index'))
    try:
        config = load_store_config()
        screen_config = ensure_playlists_structure(config).get('screens', {}).get(store_id, {}).get(screen_id, {})
    except Exception:
        screen_config = {}
    try:
        active_file = pick_active_playlist_item(screen_config, load_store_config(), store_id, screen_id)
    except Exception:
        active_file = None
    # Use legacy template for older Samsung Tizen browsers for maximum compatibility
    try:
        ua = (request.user_agent.string or '')
    except Exception:
        ua = ''
    legacy = (request.args.get('legacy') == '1') or (('Tizen' in ua) or ('TizenBrowser' in ua) or ('SMART-TV' in ua) or ('SmartTV' in ua) or ('Maple' in ua))
    template_name = 'webplayer/player_legacy.html' if legacy else 'webplayer/player.html'
    return render_template(template_name, store_id=store_id, screen_id=screen_id, active_file=active_file, media_base_url=get_media_base_url(), code=code)

@app.route('/delete_from_screen', methods=['POST'])
@login_required
def delete_from_screen():
    """Delete file from specific screen or force delete from gallery"""
    # Declare once at function start to avoid SyntaxError
    global _LIB_CACHE
    try:
        data = request.get_json()
        print(f"Delete request received: {data}")

        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        filename = data.get('filename')
        force_delete = data.get('force_delete', False)

        config = load_store_config()
        print(f"Current config loaded successfully")

        # Basic validation
        if not force_delete and (not store_id or not screen_id):
            return jsonify({'error': 'store_id and screen_id are required'}), 400

        # Normalize screen_id to match what's stored in config for this store.
        # Accept both prefixed (e.g., 1112_screen1) and unprefixed (screen1) forms.
        if not force_delete and store_id in config.get('screens', {}):
            store_screens = config['screens'][store_id]
            if screen_id not in store_screens:
                # Try adding prefix
                candidate_add = f"{store_id}_{screen_id}"
                if candidate_add in store_screens:
                    print(f"Mapped screen_id '{screen_id}' -> '{candidate_add}' (added prefix)")
                    screen_id = candidate_add
                else:
                    # Try removing prefix if already present
                    pref = f"{store_id}_"
                    if screen_id.startswith(pref):
                        candidate_strip = screen_id[len(pref):]
                        if candidate_strip in store_screens:
                            print(f"Mapped screen_id '{screen_id}' -> '{candidate_strip}' (stripped prefix)")
                            screen_id = candidate_strip

        # Handle force delete from gallery (delete file completely)
        if force_delete and filename:
            print(f"Processing force delete for filename: {filename}")
            try:
                # Enforce per-user ownership for force delete
                user_root = _user_content_prefix()
                if not user_root:
                    return jsonify({'error': 'auth required'}), 403
                # Map absolute URL to key and verify it resides under current user's namespace
                fn_key = filename
                try:
                    if isinstance(fn_key, str) and (fn_key.startswith('http://') or fn_key.startswith('https://')):
                        fn_key = fn_key.rstrip('/').split('/')[-1]
                except Exception:
                    pass
                if not isinstance(fn_key, str) or not fn_key.startswith(user_root + '/'):
                    return jsonify({'error': 'cross-tenant delete denied'}), 403
                # Remove file from storage
                removed_physical = False
                if r2_enabled():
                    try:
                        r2_delete_object(fn_key)
                        removed_physical = True
                        print(f"Force deleted R2 object: {fn_key}")
                    except Exception as e:
                        print(f"R2 force delete failed (continuing): {e}")
                else:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], fn_key)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        removed_physical = True
                        print(f"Force deleted file: {filepath}")

                # Remove file from all screens that use it
                for sid, screens in config['screens'].items():
                    for scr_id, screen_data in screens.items():
                        if screen_data.get('file') == fn_key:
                            config['screens'][sid][scr_id]['file'] = None
                            print(f"Removed {fn_key} from store {sid}, screen {scr_id}")

                save_store_config(config)
                try:
                    # Bust media library cache so UI refresh sees removal immediately
                    _LIB_CACHE = {}
                except Exception:
                    pass
                return jsonify({'success': True, 'message': 'File deleted successfully from all screens'})

            except Exception as e:
                print(f"Error force deleting file: {e}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500

        # Handle regular delete from specific screen
        print(f"Processing screen delete for store_id: {store_id}, screen_id: {screen_id}")
        if (not force_delete and store_id in config.get('screens', {}) and
                screen_id in config['screens'][store_id]):
            current_filename = config['screens'][store_id][screen_id].get('file')
            print(f"Current filename for {store_id}/{screen_id}: {current_filename}")

            if not current_filename:
                print(f"No file attached to {store_id}/{screen_id}")
                return jsonify({'error': 'No file to delete', 'screen_id': screen_id}), 400

            try:
                # Helper to map absolute URLs (e.g., R2 public URLs) to their object key
                def _key_of(val: Optional[str]) -> Optional[str]:
                    if not val:
                        return val
                    v = str(val)
                    try:
                        if v.startswith('http://') or v.startswith('https://'):
                            return v.rstrip('/').split('/')[-1]
                    except Exception:
                        pass
                    return v

                key_current = _key_of(current_filename)
                # Determine if other screens still reference this file
                still_in_use = False
                for other_store_id, screens in config.get('screens', {}).items():
                    for other_screen_id, sdata in screens.items():
                        other_file = sdata.get('file')
                        if (other_store_id, other_screen_id) != (store_id, screen_id) and _key_of(other_file) == key_current:
                            still_in_use = True
                            break
                    if still_in_use:
                        break
                print(f"Reference check - file '{current_filename}' still_in_use={still_in_use}")

                # Only remove the physical file if no other screen uses it AND it belongs to current user's namespace
                user_root = _user_content_prefix()
                allowed_delete = bool(user_root and isinstance(key_current, str) and key_current.startswith(user_root + '/'))
                if not allowed_delete:
                    print("Skipping physical delete; file not in current user's namespace")
                    # Treat as still in use for response semantics to avoid implying deletion
                    still_in_use = True

                if not still_in_use:
                    if r2_enabled():
                        try:
                            if key_current:
                                r2_delete_object(key_current)
                            print(f"Deleted R2 object: {current_filename}")
                        except Exception as de:
                            print(f"R2 delete failed: {de}")
                    else:
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], key_current or current_filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            print(f"Deleted physical file: {filepath}")
                        else:
                            print(f"Physical file already missing: {filepath}")
                else:
                    print(f"Skipping physical delete; file shared by other screens")

                # Update configuration for this screen
                config['screens'][store_id][screen_id]['file'] = None
                # remove from playlist entries referencing file
                pl = config['screens'][store_id][screen_id].get('playlist', [])
                config['screens'][store_id][screen_id]['playlist'] = [i for i in pl if _key_of(i.get('file')) != key_current]
                save_store_config(config)

                try:
                    # Bust media library cache if the physical file was deleted
                    if not still_in_use:
                        _LIB_CACHE = {}
                except Exception:
                    pass
                resp = jsonify({
                    'success': True,
                    'message': 'File removed from screen',
                    'file_was_shared': still_in_use,
                    'file_deleted': not still_in_use,
                    'removed_filename': current_filename,
                    'removed_key': key_current
                })
                try:
                    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                except Exception:
                    pass
                return resp
            except Exception as e:
                print(f"Error during delete operation: {e}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500

        print(f"Invalid parameters - store_id: {store_id}, screen_id: {screen_id}")
        try:
            print(f"Available stores: {list(config.get('screens', {}).keys())}")
            if store_id in config.get('screens', {}):
                print(f"Available screens for {store_id}: {list(config['screens'][store_id].keys())}")
        except Exception:
            pass
        return jsonify({'error': 'Invalid parameters or screen not found', 'store_id': store_id, 'screen_id': screen_id}), 400

    except Exception as e:
        print(f"Unexpected error in delete_from_screen: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/apply_to_all', methods=['POST'])
@login_required
def apply_to_all():
    """Apply settings to all stores"""
    # This would implement the "Apply to all Stores" functionality
    return jsonify({'success': True, 'message': 'Settings applied to all stores'})

@app.route('/replicate_screen', methods=['POST'])
@login_required
def replicate_screen():
    """Replicate a master store screen file to all other stores.

    Behavior controlled by 'mode' in JSON body:
    - 'override' (default): replace target screen's file and reset playlist to only the source file (or upsert selected items by file).
    - 'addon': keep existing items and append the source file to the playlist if not present.
    - 'mirror': fully replace the target playlist to exactly match the master's current playlist (requires all items selected).

    Always skips screens marked protected in target stores.
    """
    try:
        data = request.get_json() or {}
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        mode = (data.get('mode') or 'override').lower()
        selected_item_ids = data.get('selected_item_ids') or []
        target_store_ids = data.get('target_store_ids') or []
        if not isinstance(selected_item_ids, list):
            selected_item_ids = []
        if not isinstance(target_store_ids, list):
            target_store_ids = []
        if not store_id or not screen_id:
            return jsonify({'error': 'store_id and screen_id required'}), 400

        config = ensure_playlists_structure(load_store_config())
        master_store_id = config.get('master_store_id')
        if store_id != master_store_id:
            return jsonify({'error': 'Only master store can replicate'}), 403

        master_screens = config['screens'].get(store_id, {})
        if screen_id not in master_screens:
            if '_' in screen_id:
                candidate = screen_id.split('_', 1)[1]
                if candidate in master_screens:
                    screen_id = candidate
            else:
                prefixed = f"{store_id}_{screen_id}"
                if prefixed in master_screens:
                    screen_id = prefixed

        if screen_id not in master_screens:
            return jsonify({'error': 'Screen not found in master store'}), 404

        source_screen = master_screens[screen_id]
        source_file = source_screen.get('file')
        source_playlist = source_screen.get('playlist', [])

        # Build list of source items if specific selection requested
        source_items = []
        if selected_item_ids:
            by_id = {str(it.get('id')): it for it in source_playlist if isinstance(it, dict)}
            for iid in selected_item_ids:
                it = by_id.get(str(iid))
                if it:
                    # Shallow copy fields we care about; generate new id per target later
                    copied = {
                        'file': it.get('file'),
                        'enabled': bool(it.get('enabled', True)),
                        'start': it.get('start'),
                        'end': it.get('end'),
                        'schedule': it.get('schedule', []),
                        'duration': it.get('duration', 10),
                        'repeat': bool(it.get('repeat', True)),
                        'link_next': bool(it.get('link_next', False)),
                        'media_type': it.get('media_type') or classify_media(it.get('file') or '')
                    }
                    source_items.append(copied)
            # If selection empty after filtering, clear the selection flag
            if not source_items:
                selected_item_ids = []

        # Validation for mirror mode: must select all items from master
        if mode == 'mirror':
            master_ids = [str(it.get('id')) for it in source_playlist if isinstance(it, dict) and it.get('id') is not None]
            if not master_ids:
                return jsonify({'error': 'Master screen has no playlist items to mirror'}), 400
            sel_set = set(str(x) for x in (selected_item_ids or []))
            if set(master_ids) != sel_set:
                return jsonify({'error': 'Please tick all playlist items to mirror/replace exactly'}), 400
            # Ensure source_items reflects all items in order
            source_items = []
            for it in source_playlist:
                if isinstance(it, dict):
                    source_items.append({
                        'file': it.get('file'),
                        'enabled': bool(it.get('enabled', True)),
                        'start': it.get('start'),
                        'end': it.get('end'),
                        'schedule': it.get('schedule', []),
                        'duration': it.get('duration', 10),
                        'repeat': bool(it.get('repeat', True)),
                        'link_next': bool(it.get('link_next', False)),
                        'media_type': it.get('media_type') or classify_media(it.get('file') or '')
                    })
            selected_item_ids = master_ids

        # If no selection (non-mirror), require a single source file as before
        if not selected_item_ids and mode != 'mirror':
            if not source_file:
                return jsonify({'error': 'No file on this screen to replicate'}), 400

        # Logical screen type for cross-store mapping
        screen_type = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id

        updated_stores = []
        skipped_stores = []
        created_screens = []

        # Optional filter: only apply to these stores if provided
        target_filter = set(str(sid) for sid in target_store_ids) if target_store_ids else None

        for sid, screens in config.get('screens', {}).items():
            if sid == master_store_id:
                continue
            if target_filter is not None and sid not in target_filter:
                continue
            target_id = f"{sid}_{screen_type}"
            legacy_id = screen_type

            if target_id in screens:
                actual_id = target_id
            elif legacy_id in screens:
                actual_id = legacy_id
            else:
                # Create new screen with sensible defaults
                is_promo = screen_type.startswith('promo')
                screens[target_id] = {
                    'file': None,
                    'vertical': is_promo,
                    'horizontal': not is_promo,
                    'rotation': 0,
                    'protected': False
                }
                created_screens.append(f"{sid}:{target_id}")
                actual_id = target_id

            if screens[actual_id].get('protected'):
                skipped_stores.append(sid)
                continue

            # Apply action based on mode and whether specific items were selected
            if selected_item_ids:
                # Using selected playlist items as the replication source
                tgt_pl = screens[actual_id].setdefault('playlist', [])
                if mode == 'addon':
                    # Append any of the selected files that are not in target playlist (by file)
                    existing_files = {i.get('file') for i in tgt_pl if isinstance(i, dict)}
                    for src in source_items:
                        f = src.get('file')
                        if f and f not in existing_files:
                            item = dict(src)
                            item['id'] = str(uuid.uuid4())
                            tgt_pl.append(item)
                    # If target has no primary file, set to first selected
                    if not screens[actual_id].get('file') and source_items:
                        screens[actual_id]['file'] = source_items[0].get('file')
                elif mode == 'mirror':
                    # Replace the entire playlist with exactly the master's items (order preserved)
                    new_pl = []
                    for src in source_items:
                        item = dict(src)
                        item['id'] = str(uuid.uuid4())
                        new_pl.append(item)
                    screens[actual_id]['playlist'] = new_pl
                    screens[actual_id]['file'] = new_pl[0].get('file') if new_pl else None
                else:
                    # override: upsert each selected item by file (replace settings if exists; add if missing)
                    # Keep other existing items intact
                    file_index = {}
                    for idx, it in enumerate(list(tgt_pl)):
                        f = isinstance(it, dict) and it.get('file')
                        if f: file_index[f] = idx
                    for src in source_items:
                        f = src.get('file')
                        if not f:
                            continue
                        if f in file_index:
                            # Replace payload but preserve item id
                            idx = file_index[f]
                            existing = tgt_pl[idx] if 0 <= idx < len(tgt_pl) else None
                            keep_id = (existing or {}).get('id') or str(uuid.uuid4())
                            new_item = dict(src)
                            new_item['id'] = keep_id
                            tgt_pl[idx] = new_item
                        else:
                            new_item = dict(src)
                            new_item['id'] = str(uuid.uuid4())
                            tgt_pl.append(new_item)
                    # Set primary file if empty
                    if not screens[actual_id].get('file') and source_items:
                        screens[actual_id]['file'] = source_items[0].get('file')
            else:
                # Legacy single-file replicate path
                if mode == 'addon':
                    # Keep existing items, append if missing
                    pl = screens[actual_id].setdefault('playlist', [])
                    if not any(i.get('file') == source_file for i in pl):
                        pl.append({'id': str(uuid.uuid4()), 'file': source_file, 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(source_file)})
                    if not screens[actual_id].get('file'):
                        screens[actual_id]['file'] = source_file
                else:
                    # override: set file and replace playlist with only this item
                    screens[actual_id]['file'] = source_file
                    screens[actual_id]['playlist'] = [{
                        'id': str(uuid.uuid4()),
                        'file': source_file,
                        'enabled': True,
                        'start': None,
                        'end': None,
                        'schedule': [],
                        'duration': 10,
                        'repeat': True,
                        'link_next': False,
                        'media_type': classify_media(source_file)
                    }]
            updated_stores.append(sid)
            # Enqueue reload for each affected screen
            try:
                _enqueue_command_in_cfg(config, sid, actual_id, 'reload')
            except Exception:
                pass

        save_store_config(config)

        action = 'Added to' if mode == 'addon' else 'Replaced in'
        extra = ''
        if selected_item_ids:
            extra = f" using {len(source_items)} selected item(s)"
        message = f"{action} {len(updated_stores)} stores ({screen_type}){extra}"
        if created_screens:
            message += f". Created {len(created_screens)} screens"
        if skipped_stores:
            message += f". Skipped {len(skipped_stores)} protected"

        return jsonify({
            'success': True,
            'filename': source_file,
            'updated_stores': updated_stores,
            'skipped_stores': skipped_stores,
            'created_screens': created_screens,
            'message': message,
            'screen_type': screen_type
        })
    except Exception as e:
        print(f"Error in replicate_screen: {e}")
        return jsonify({'error': str(e)}), 500


# Legacy routes for backward compatibility
@app.route('/upload')
def upload():
    return redirect(url_for('dashboard'))

@app.route('/gallery')
def gallery():
    """Enhanced gallery with file usage information"""
    images = []
    config = load_store_config()
    
    # Get all files in upload directory
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename):
                # Find which screens use this file
                used_by = []
                for store_id, screens in config['screens'].items():
                    for screen_id, screen_data in screens.items():
                        if screen_data.get('file') == filename or any(i.get('file') == filename for i in screen_data.get('playlist', [])):
                            store_name = next((s['name'] for s in config['stores'] if s['id'] == store_id), store_id)
                            used_by.append(f"{store_name} - {screen_id}")
                
                images.append({
                    'filename': filename,
                    'used_by': used_by,
                    'unused': len(used_by) == 0
                })
    
    return render_template('gallery.html', images=images)

@app.route('/delete_unused_files', methods=['POST'])
@login_required
def delete_unused_files():
    """Delete all unused files for the current user namespace (local and R2)."""
    try:
        # Helper to normalize keys from possible absolute URLs
        def _key_of(val: str) -> str:
            v = str(val or '')
            try:
                if v.startswith('http://') or v.startswith('https://'):
                    return v.rstrip('/').split('/')[-1]
            except Exception:
                pass
            return v

        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403

        config = load_store_config()
        used_files = set()

        # Collect used files from this user's config only
        for _sid, screens in (config.get('screens') or {}).items():
            for _scr_id, screen_data in (screens or {}).items():
                f = _key_of(screen_data.get('file'))
                if f:
                    used_files.add(f)
                for item in screen_data.get('playlist', []) or []:
                    fi = _key_of(item.get('file'))
                    if fi:
                        used_files.add(fi)

        # Restrict used set to current namespace only
        used_user = {k for k in used_files if isinstance(k, str) and k.startswith(user_root + '/')}

        deleted_count = 0
        if r2_enabled():
            # Scan current user's prefix in R2
            prefix = user_root + '/'
            for obj in r2_list_objects(prefix):
                key = obj.get('Key')
                if not key or key.endswith('/'):
                    continue
                # Only delete allowed media types that are not referenced
                if allowed_file(key) and key not in used_user:
                    try:
                        r2_delete_object(key)
                        deleted_count += 1
                        print(f"Deleted unused R2 object: {key}")
                    except Exception as de:
                        print(f"Failed to delete R2 object {key}: {de}")
        else:
            # Local filesystem: walk under user namespace folder
            base = app.config['UPLOAD_FOLDER']
            root_path = os.path.join(base, user_root)
            if os.path.isdir(root_path):
                for dirpath, _dirnames, filenames in os.walk(root_path):
                    for name in filenames:
                        if not allowed_file(name):
                            continue
                        abs_path = os.path.join(dirpath, name)
                        # Compute object key: user_root + relative path using forward slashes
                        rel_path = os.path.relpath(abs_path, base).replace('\\', '/')
                        key = rel_path
                        if key not in used_user:
                            try:
                                os.remove(abs_path)
                                deleted_count += 1
                                print(f"Deleted unused file: {key}")
                            except Exception as le:
                                print(f"Failed to delete file {key}: {le}")

        return jsonify({'success': True, 'deleted_count': deleted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_delete')
def test_delete():
    """Test page for debugging delete functionality"""
    return render_template('test_delete.html')

@app.route('/add_screen', methods=['POST'])
@login_required
def add_screen():
    """Add a new screen to a store"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_type = data.get('screen_type', 'screen')  # 'screen' or 'promo'
        if screen_type not in ('screen','promo'):
            screen_type = 'screen'
        
        if not store_id:
            return jsonify({'error': 'Store ID is required'}), 400

        # Respect per-user segmented config if present
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        if store_id not in config['screens']:
            config['screens'][store_id] = {}

        # If this is a brand-new store namespace and an old stray promo seed like f"{store_id}_promo1" exists, remove it unless user explicitly requested promo
        if screen_type == 'screen':
            stray_promo = f"{store_id}_promo1"
            if stray_promo in config['screens'][store_id] and not config['screens'][store_id][stray_promo].get('file') and not config['screens'][store_id][stray_promo].get('playlist'):
                try:
                    del config['screens'][store_id][stray_promo]
                except Exception:
                    pass

        # Purge any sync groups whose base screen no longer exists (prevents resurrecting old sync state when reusing ids)
        try:
            groups = config.get('sync_groups') or {}
            to_del = []
            for gid, grp in list(groups.items()):
                if grp.get('store_id') != store_id:
                    continue
                base = grp.get('base')
                if base and base not in config['screens'][store_id]:
                    to_del.append(gid)
            if to_del:
                for gid in to_del:
                    groups.pop(gid, None)
                if groups:
                    config['sync_groups'] = groups
                else:
                    config.pop('sync_groups', None)
        except Exception:
            pass
        
        # Find next available screen number for store-specific screen IDs
        store_prefix = f"{store_id}_"
        existing_screens = []
        
        for screen_id in config['screens'][store_id].keys():
            # Check if this screen belongs to current store and is of the requested type
            if screen_id.startswith(store_prefix):
                # Extract the part after store prefix (e.g., "screen1" from "1931_screen1")
                screen_part = screen_id[len(store_prefix):]
                if screen_part.startswith(screen_type):
                    existing_screens.append(screen_part)
        
        if existing_screens:
            # Extract numbers and find the highest
            numbers = []
            for screen in existing_screens:
                try:
                    # Remove the screen_type prefix to get just the number
                    num_str = screen.replace(screen_type, '')
                    if num_str:  # Make sure there's a number part
                        num = int(num_str)
                        numbers.append(num)
                except ValueError:
                    continue
            next_num = max(numbers) + 1 if numbers else 1
        else:
            next_num = 1

        # Create store-specific screen ID; fill gaps (e.g. if screen1 deleted, reuse 1)
        used = set()
        for s in existing_screens:
            try:
                num_str = s.replace(screen_type, '')
                if num_str:
                    used.add(int(num_str))
            except Exception:
                pass
        gap = 1
        while gap in used:
            gap += 1
        new_screen_id = f"{store_id}_{screen_type}{gap}"
        
        # Set default orientation based on screen type
        is_promo = screen_type.startswith('promo')
        
        # Add new screen with default settings
        config['screens'][store_id][new_screen_id] = {
            'file': None,
            'vertical': is_promo,  # Promos default to vertical
            'horizontal': not is_promo,  # Regular screens default to horizontal
            'rotation': 0,
            'protected': False,
            'playlist': [],
            'fresh': True  # Hint for UI to treat as new, not part of any prior sync
        }
        
        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
        else:
            save_store_config(config)
        
        return jsonify({
            'success': True,
            'screen_id': new_screen_id,
            'screen': config['screens'][store_id][new_screen_id],
            'message': f'Added {new_screen_id} successfully'
        })
        
    except Exception as e:
        print(f"Error adding screen: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_screen', methods=['POST'])
@login_required
def delete_screen():
    """Delete a screen and its associated file"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        
        print(f"DEBUG: Delete screen request - store_id: {store_id}, screen_id: {screen_id}")
        
        if not store_id or not screen_id:
            print("DEBUG: Missing store_id or screen_id")
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400

        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        print(f"DEBUG: Available stores: {list(config['screens'].keys())}")
        
        if store_id not in config['screens']:
            print(f"DEBUG: Store {store_id} not found in config")
            return jsonify({'error': 'Store not found'}), 404
        # Normalize provided id: accept both prefixed (e.g., "1881_screen1") and unprefixed ("screen1")
        actual_id = screen_id
        store_screens = config['screens'].get(store_id, {})
        if actual_id not in store_screens:
            print(f"DEBUG: Screen {actual_id} not directly in store {store_id}, attempting mapping")
            # If given id is prefixed but for a different store, remap suffix to this store
            if '_' in screen_id:
                short = screen_id.split('_', 1)[1]
                candidate = f"{store_id}_{short}"
                if candidate in store_screens:
                    actual_id = candidate
                elif short in store_screens:
                    actual_id = short
            else:
                # Unprefixed -> try store-prefixed variant
                candidate = f"{store_id}_{screen_id}"
                if candidate in store_screens:
                    actual_id = candidate
        if actual_id not in store_screens:
            print(f"DEBUG: Screen {screen_id} not found (mapped={actual_id}) in store {store_id}")
            print(f"DEBUG: Available screens in store {store_id}: {list(store_screens.keys())}")
            return jsonify({'error': 'Screen not found'}), 404
        
        print(f"DEBUG: Found screen {actual_id} in store {store_id}")
        
        # Delete associated file if exists
        screen_data = config['screens'][store_id][actual_id]
        if screen_data.get('file'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], screen_data['file'])
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"DEBUG: Deleted file: {filepath}")
        
        # Remove screen from configuration
        del config['screens'][store_id][actual_id]
        print(f"DEBUG: Removed screen {actual_id} from config")

        # Clean up any sync groups referencing this screen
        try:
            groups = config.get('sync_groups') or {}
            changed = False
            for gid, grp in list(groups.items()):
                if grp.get('store_id') != store_id:
                    continue
                members = grp.get('members') or []
                if grp.get('base') == actual_id:
                    # Remove entire group; scrub sync_ref items from all member screens
                    for m in members:
                        msid = m.get('screen_id')
                        scr = config['screens'][store_id].get(msid) if store_id in config['screens'] else None
                        if isinstance(scr, dict):
                            pl = scr.get('playlist') or []
                            scr['playlist'] = [it for it in pl if not (isinstance(it, dict) and (it.get('sync_ref') or {}).get('group') == gid)]
                    groups.pop(gid, None)
                    changed = True
                else:
                    # Remove member referencing this screen
                    new_members = [m for m in members if m.get('screen_id') != actual_id]
                    if len(new_members) != len(members):
                        # Scrub playlist items on that screen (already removed) from other screens just in case
                        for m in members:
                            msid = m.get('screen_id')
                            scr = config['screens'][store_id].get(msid) if store_id in config['screens'] else None
                            if isinstance(scr, dict):
                                pl = scr.get('playlist') or []
                                scr['playlist'] = [it for it in pl if not (isinstance(it, dict) and (it.get('sync_ref') or {}).get('group') == gid and it.get('sync_ref', {}).get('role') == 'follower' and it.get('screen_id') == actual_id)]
                        grp['members'] = new_members
                        grp['count'] = len(new_members)
                        # If less than 2 members remain, remove group entirely
                        if grp['count'] < 2:
                            groups.pop(gid, None)
                        changed = True
            if changed:
                if groups:
                    config['sync_groups'] = groups
                else:
                    config.pop('sync_groups', None)
        except Exception as _sg_clean_err:
            print('WARN: sync group cleanup failed', _sg_clean_err)
        
        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
        else:
            save_store_config(config)
        print(f"DEBUG: Configuration saved successfully")
        
        return jsonify({
            'success': True,
            'message': f'Screen {actual_id} deleted successfully'
        })
        
    except Exception as e:
        print(f"ERROR: Error deleting screen: {e}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_store', methods=['POST'])
@login_required
def add_store():
    """Add a new store starting with no screens"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        store_name = data.get('store_name')
        
        if not store_id or not store_name:
            return jsonify({'error': 'Store ID and Store Name are required'}), 400
            
        config = load_store_config()
        
        # Check if store already exists
        for store in config['stores']:
            if store['id'] == store_id:
                return jsonify({'error': f'Store {store_id} already exists'}), 400
        
        # Add new store to stores list
        config['stores'].append({
            'id': store_id,
            'name': store_name
        })
        # Start with no screens; UI will show add placeholders for Screen and Promo
        if 'screens' not in config:
            config['screens'] = {}
        if store_id not in config['screens']:
            config['screens'][store_id] = {}
        
        save_store_config(config)
        
        return jsonify({
            'success': True,
            'store_id': store_id,
            'store_name': store_name,
            'message': f'Store {store_id} - {store_name} added successfully'
        })
        
    except Exception as e:
        print(f"Error adding store: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_stores', methods=['POST'])
@login_required
def add_stores_bulk():
    """Add multiple stores in one request.
    Body JSON: { stores: [ {store_id, store_name}, ... ] }
    Returns: {success, added:[{id,name}], skipped:[{id,reason}], message}
    """
    try:
        data = request.get_json() or {}
        stores_in = data.get('stores') or []
        if not isinstance(stores_in, list) or not stores_in:
            return jsonify({'error': 'stores list required'}), 400

        config = load_store_config()
        # Build a fast lookup of existing ids
        existing_ids = {str(s.get('id')) for s in (config.get('stores') or []) if s and s.get('id')}

        added = []
        skipped = []
        seen_new = set()
        for entry in stores_in:
            try:
                sid = str((entry.get('store_id') or '').strip())
                sname = (entry.get('store_name') or '').strip()
            except Exception:
                sid = ''
                sname = ''
            if not sid or not sname:
                skipped.append({'id': sid or '(blank)', 'reason': 'missing id or name'})
                continue
            if not sid.isdigit():
                skipped.append({'id': sid, 'reason': 'id must be numeric'})
                continue
            if sid in existing_ids:
                skipped.append({'id': sid, 'reason': 'already exists'})
                continue
            if sid in seen_new:
                skipped.append({'id': sid, 'reason': 'duplicate in input'})
                continue
            # Append to config
            config.setdefault('stores', []).append({'id': sid, 'name': sname})
            config.setdefault('screens', {}).setdefault(sid, {})
            seen_new.add(sid)
            added.append({'id': sid, 'name': sname})

        if added:
            save_store_config(config)

        msg = f"Added {len(added)} store(s)"
        if skipped:
            msg += f"; skipped {len(skipped)}"

        return jsonify({'success': True, 'added': added, 'skipped': skipped, 'message': msg})
    except Exception as e:
        print(f"Error adding stores bulk: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_store', methods=['POST'])
@login_required
def delete_store():
    """Delete a store and all its associated screens and files"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        
        if not store_id:
            return jsonify({'error': 'Store ID is required'}), 400
            
        config = load_store_config()
        
        # Protect master store from deletion
        master_store_id = config.get('master_store_id')
        if store_id == master_store_id:
            return jsonify({'error': 'Master Store cannot be deleted'}), 403
        
        # Check if store exists
        store_found = False
        for i, store in enumerate(config['stores']):
            if store['id'] == store_id:
                store_found = True
                store_name = store['name']
                # Remove store from stores list
                del config['stores'][i]
                break
        
        if not store_found:
            return jsonify({'error': 'Store not found'}), 404
        
        # Delete all files associated with this store's screens
        if store_id in config['screens']:
            for screen_id, screen_data in config['screens'][store_id].items():
                if screen_data.get('file'):
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], screen_data['file'])
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"Deleted file: {filepath}")
                # also ignore playlist cleanup here (files may be shared)
            
            # Remove all screens for this store
            del config['screens'][store_id]
        
        save_store_config(config)
        
        return jsonify({
            'success': True,
            'message': f'Store {store_id} - {store_name} and all its screens deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting store: {e}")
        return jsonify({'error': str(e)}), 500

# ---------------- Playlist API Endpoints (moved above app.run) ----------------
@app.route('/playlist/<store_id>/<screen_id>')
@slowlog(300)
@with_etag_json
def get_playlist(store_id, screen_id):
    print(f"DEBUG: GET /playlist {store_id} {screen_id}")
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    # Prefer per-user config when either a pair code OR a logged-in session user exists
    if not user_key and not _safe_user_key():
        return {'success': False, 'error': 'pair code required'}, 403
    ukey = user_key or _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    # Legacy mapping: if old store_id like '1881' no longer exists, map to current master store
    try:
        if store_id not in (cfg.get('screens') or {}) and str(store_id) == '1881':
            m = cfg.get('master_store_id')
            if m and m in (cfg.get('screens') or {}):
                print(f"DEBUG: Legacy store_id {store_id} -> master {m}")
                store_id = m
    except Exception:
        pass
    screens = cfg.get('screens', {}).get(store_id, {})
    screen = screens.get(screen_id)
    if not screen:
        # Try mapping between legacy short and store-prefixed IDs
        alt = None
        if '_' in screen_id:
            # If screen_id includes a store prefix, normalize to current store
            short = screen_id.split('_', 1)[1]
            # Prefer current-store-prefixed id first
            prefixed_current = f"{store_id}_{short}"
            alt = screens.get(prefixed_current) or screens.get(short)
            if alt is not None:
                screen_id = prefixed_current if prefixed_current in screens else short
        else:
            prefixed = f"{store_id}_{screen_id}"
            alt = screens.get(prefixed)
            if alt is not None:
                screen_id = prefixed
        screen = alt
    if not screen:
        # Auto-create a default screen entry so dashboard and players can proceed
        try:
            part = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id
            is_promo = str(part).startswith('promo')
            sdata = {
                'file': None,
                'vertical': True if is_promo else False,
                'horizontal': False if is_promo else True,
                'rotation': 0,
                'protected': False,
                'playlist': []
            }
            screens[screen_id] = sdata
            # Persist in whichever config space we're using
            try:
                if user_key:
                    save_store_config_for_user_safe_key(user_key, cfg)
                else:
                    save_store_config(cfg)
            except Exception:
                pass
            screen = sdata
            print(f"DEBUG: Auto-created screen entry {store_id}/{screen_id}")
        except Exception:
            print("DEBUG: Screen not found for playlist (after mapping)")
            return jsonify({'success': False, 'error': 'screen not found'}), 404
    # Auto-clean missing-file items (local disk only)
    if not r2_enabled():
        original = screen.get('playlist', [])
        cleaned = []
        removed = 0
        for item in original:
            f = item.get('file')
            if f:
                path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                if not os.path.exists(path):
                    removed += 1
                    continue
            cleaned.append(item)
        if removed:
            screen['playlist'] = cleaned
            if user_key:
                save_store_config_for_user_safe_key(user_key, cfg)
            else:
                save_store_config(cfg)
            print(f"DEBUG: Auto-removed {removed} missing file playlist items")
    pl = screen.get('playlist', [])
    # Decorate with public URL and last known status for clients/dashboard
    last_status = screen.get('last_item_status') or {}
    out = []
    for item in pl:
        try:
            it = dict(item)
            it['url'] = build_public_url(it.get('file'))
            # Ensure the effect is serialized explicitly for clients
            if 'effect' in item and isinstance(item.get('effect'), str):
                it['effect'] = item.get('effect')
            # If part of a sync group, attach group timing info
            try:
                sref = item.get('sync_ref') if isinstance(item, dict) else None
                gid = None
                if isinstance(sref, dict):
                    gid = sref.get('group')
                # If no sync_ref on item, try to infer group membership from config (screen in group)
                if not gid:
                    try:
                        for ggid, g in (cfg.get('sync_groups') or {}).items():
                            for mem in (g.get('members') or []):
                                if mem.get('screen_id') == screen_id:
                                    gid = ggid; sref = {'group': ggid, 'order': mem.get('order'), 'role': mem.get('role','follower')}
                                    break
                            if gid: break
                    except Exception:
                        gid = None
                if gid:
                    grp = (cfg.get('sync_groups') or {}).get(gid) or {}
                    se = grp.get('start_epoch') or grp.get('start') or grp.get('created_at')
                    it.setdefault('sync_ref', dict(sref or {}))
                    if se:
                        it['sync_ref']['start_epoch'] = int(se)
                    try:
                        cnt = int(grp.get('count') or 0)
                        if cnt > 1:
                            it['sync_ref']['count'] = cnt
                    except Exception:
                        pass
                    it['sync_ref']['mode'] = grp.get('mode') or 'split-h'
            except Exception:
                pass
            # Prefer id mapping; if missing, fall back to file key.
            # Robustness: handle absolute URLs and relative paths by also checking basename-only key.
            ls = None
            try:
                if it.get('id'):
                    k_id = f"id:{it.get('id')}"
                    ls = last_status.get(k_id)
                if (ls is None) and it.get('file'):
                    f = str(it.get('file'))
                    # absolute URL -> basename
                    if f.startswith('http://') or f.startswith('https://'):
                        try:
                            f = f.rstrip('/').split('/')[-1]
                        except Exception:
                            pass
                    # try exact path first
                    k_file = f"file:{f}"
                    ls = last_status.get(k_file)
                    if ls is None:
                        # also try basename of relative path (e.g., uploads/foo.jpg -> foo.jpg)
                        try:
                            base1 = f.split('/')[-1]
                        except Exception:
                            base1 = f
                        k_base = f"file:{base1}"
                        if k_base != k_file:
                            ls = last_status.get(k_base)
            except Exception:
                ls = None
            if ls is not None:
                it['last_status'] = ls
            out.append(it)
        except Exception:
            out.append(item)
    # If no synced item is visible but this screen belongs to a sync group, synthesize a virtual follower item
    try:
        def synthesize_for(gid, grp, mem):
            fname = grp.get('filename')
            if not fname:
                return None
            return {
                'id': f"virtual:{gid}:{screen_id}",
                'file': fname,
                'url': build_public_url(fname),
                'enabled': True,
                'start': None,
                'end': None,
                'schedule': grp.get('schedule') or [],
                'duration': 10,
                'repeat': True,
                'link_next': False,
                'media_type': classify_media(fname),
                'sync_ref': {
                    'group': gid,
                    'role': mem.get('role') or 'follower',
                    'order': mem.get('order') or 0,
                    'virtual': True,
                    'start_epoch': int(grp.get('start_epoch') or grp.get('start') or grp.get('created_at') or 0),
                    'count': int(grp.get('count') or 0),
                    'mode': grp.get('mode') or 'split-h'
                }
            }

        # If there is already a synced item, skip synthesis
        has_sync = False
        for it in out:
            try:
                sref = it.get('sync_ref') if isinstance(it, dict) else None
                if isinstance(sref, dict) and sref.get('group'):
                    has_sync = True
                    break
            except Exception:
                pass
        if not has_sync:
            sync_groups = (cfg.get('sync_groups') or {})
            # Consider both prefixed and short ids for matching
            alt_ids = {screen_id}
            try:
                if '_' in screen_id:
                    short = screen_id.split('_', 1)[1]
                    alt_ids.add(short)
                else:
                    alt_ids.add(f"{store_id}_{screen_id}")
            except Exception:
                pass
            for gid, grp in sync_groups.items():
                try:
                    for mem in (grp.get('members') or []):
                        sid = mem.get('screen_id')
                        if sid and sid in alt_ids:
                            vit = synthesize_for(gid, grp, mem)
                            if vit:
                                out.append(vit)
                            raise StopIteration
                except StopIteration:
                    break
                except Exception:
                    continue
    except Exception:
        pass
    # Implicit multi-screen mirror: if this screen has no items and appears to be a numbered
    # sibling (e.g., screen2/3) while the base sibling (screen1) in the same store has a file,
    # synthesize a virtual follower item using that base file. This makes follower screens show
    # something even when a formal sync group hasn't been created yet.
    try:
        if not out:
            # NEW: Skip implicit mirror for a brand-new empty screen (no file, no playlist) so it appears truly empty.
            # This prevents a freshly added screen from auto-inheriting base screen media and looking "sync controlled" unintentionally.
            if screen.get('file') is None and not screen.get('playlist'):
                pass  # Leave it empty; user can explicitly sync or add media later.
            else:
                import re
                short = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id
                m = re.match(r'^(.*?)(\d+)$', short)
                if m:
                    prefix, num = m.group(1), int(m.group(2) or 0)
                    if num >= 2:
                        base_short = f"{prefix}1"
                        # Prefer current-store-prefixed id first, then short id
                        base_ids = [f"{store_id}_{base_short}", base_short]
                        base_scr = None
                        for bid in base_ids:
                            base_scr = (screens or {}).get(bid)
                            if base_scr:
                                break
                        if isinstance(base_scr, dict):
                            fname = base_scr.get('file')
                            if not fname:
                                try:
                                    plb = base_scr.get('playlist') or []
                                    if plb:
                                        fname = plb[0].get('file')
                                except Exception:
                                    fname = None
                            if fname:
                                se = ((int(time.time()) // 5) + 2) * 5
                                out.append({
                                    'id': f"virtual:implicit:{store_id}:{screen_id}",
                                    'file': fname,
                                    'url': build_public_url(fname),
                                    'enabled': True,
                                    'start': None,
                                    'end': None,
                                    'schedule': [],
                                    'duration': 10,
                                    'repeat': True,
                                    'link_next': False,
                                    'media_type': classify_media(fname),
                                    'sync_ref': {
                                        'group': f"implicit:{store_id}:{prefix}",
                                        'role': 'follower',
                                        'order': max(0, num-1),
                                        'virtual': True,
                                        'start_epoch': se,
                                        'count': 0,
                                        'mode': 'split-h'
                                    }
                                })
    except Exception:
        pass
    print(f"DEBUG: Returning playlist items: {len(out)}")
    # Orientation mode for clients: vertical, horizontal, or default (none)
    try:
        v = bool(screen.get('vertical'))
        h = bool(screen.get('horizontal'))
        orientation_mode = 'vertical' if (v and not h) else ('horizontal' if (h and not v) else 'default')
    except Exception:
        orientation_mode = 'default'
    # Dashboard needs immediate consistency after changes; disable caching here.
    # Include display rotation (0/90/180/270) so clients can honor it.
    try:
        rotation = int(screen.get('rotation') or 0)
        if rotation not in (0,90,180,270):
            rotation = 0
    except Exception:
        rotation = 0
    return (
    {'success': True, 'playlist': out, 'queue_len': len(screen.get('cmd_queue', [])), 'events_recent': len(screen.get('events', [])), 'orientation': orientation_mode, 'rotation': rotation},
        200,
        {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}
    )

# ---- Media library listing (for choosing existing uploads) ----
@app.route('/library')
@login_required
@slowlog(500)
@with_etag_json
def list_library():
    """List media library with optional prefix scoping and directory discovery.
    Query: prefix=foo/bar (optional)
    Returns: {success, prefix, dirs:[{name,prefix}], files:[...]} where file names are keys relative to root.
    """
    try:
        global _LIB_CACHE
        now_ts = time.time()
        prefix = _sanitize_prefix(request.args.get('prefix'))
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        cache_key = f"{user_root}|{prefix or '__root__'}"
        try:
            if isinstance(_LIB_CACHE, dict):
                entry = _LIB_CACHE.get(cache_key)
                if entry and (now_ts - entry.get('ts', 0) < 10):
                    return (
                        {'success': True, 'prefix': prefix, 'dirs': entry.get('dirs', []), 'files': entry.get('files', [])},
                        200,
                        {'Cache-Control': 'public, max-age=60'}
                    )
        except Exception:
            _LIB_CACHE = {}

        files = []
        dirs: list[dict] = []
        if r2_enabled():
            seen = set()
            # Real storage prefix is under user namespace; UI prefix is relative to it
            real_prefix = _join_prefix_key(user_root, prefix) if prefix else user_root
            pfx = real_prefix + '/'
            for obj in r2_list_objects(pfx):
                name = obj.get('Key')
                if not name:
                    continue
                # Gather subfolder names
                if pfx and name.startswith(pfx):
                    remainder = name[len(pfx):]
                else:
                    remainder = name
                if '/' in remainder:
                    d = remainder.split('/', 1)[0]
                    if d and d not in seen:
                        seen.add(d)
                # Only include files that are directly under prefix (no further '/')
                if remainder and '/' not in remainder and allowed_file(name):
                    size = int(obj.get('Size') or 0)
                    mtime = int(obj.get('LastModified').timestamp()) if obj.get('LastModified') else 0
                    relkey = name  # full key (includes user namespace)
                    files.append({
                        'name': relkey,
                        'media_type': classify_media(relkey),
                        'size': size,
                        'mtime': mtime,
                        'url': build_public_url(relkey)
                    })
            for d in sorted(seen):
                # Return UI prefix relative to user root, not including user namespace
                new_ui_prefix = _join_prefix_key(prefix, d) if prefix else d
                dirs.append({'name': d, 'prefix': new_ui_prefix})
        else:
            base = app.config['UPLOAD_FOLDER']
            # Local path under user namespace
            folder = os.path.join(base, _join_prefix_key(user_root, prefix) if prefix else user_root)
            if os.path.isdir(folder):
                for name in os.listdir(folder):
                    path = os.path.join(folder, name)
                    if os.path.isdir(path):
                        dirs.append({'name': name, 'prefix': _join_prefix_key(prefix, name)})
                        continue
                    if not os.path.isfile(path) or not allowed_file(name):
                        continue
                    stat = os.stat(path)
                    # Files: return full key including user namespace
                    relname = _join_prefix_key(_join_prefix_key(user_root, prefix), name) if prefix else _join_prefix_key(user_root, name)
                    files.append({
                        'name': relname,
                        'media_type': classify_media(name),
                        'size': stat.st_size,
                        'mtime': int(stat.st_mtime),
                        'url': build_public_url(relname)
                    })
        files.sort(key=lambda x: x['mtime'], reverse=True)
        payload = {'success': True, 'prefix': prefix, 'dirs': dirs, 'files': files}
        try:
            _LIB_CACHE[cache_key] = {'ts': now_ts, 'dirs': dirs, 'files': files}
        except Exception:
            pass
        return payload, 200, {'Cache-Control': 'public, max-age=60'}
    except Exception as e:
        logging.exception('list_library error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- Folder management (create / rename / delete) ----
@app.route('/library/folder/create', methods=['POST'])
@login_required
def lib_folder_create():
    try:
        data = request.get_json(force=True) or {}
        parent = _sanitize_prefix(data.get('prefix'))
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        name = _sanitize_prefix(data.get('name'))
        if not name:
            return jsonify({'success': False, 'error': 'invalid folder name'}), 400
        new_prefix_ui = _join_prefix_key(parent, name) if parent else name
        new_prefix = _join_prefix_key(user_root, new_prefix_ui)
        if r2_enabled():
            # Create a marker to make empty folder visible
            key = f"{new_prefix}/.keep"
            try:
                r2_put_bytes(key, b'', content_type='application/octet-stream')
            except Exception:
                pass
        else:
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], new_prefix), exist_ok=True)
        # bust cache for affected prefixes (parent and new)
        try:
            for k in (f"{user_root}|{parent or '__root__'}", f"{user_root}|{new_prefix_ui}"):
                _LIB_CACHE.pop(k, None)
        except Exception:
            pass
        return jsonify({'success': True, 'prefix': new_prefix_ui})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/library/folder/delete', methods=['POST'])
@login_required
def lib_folder_delete():
    try:
        data = request.get_json(force=True) or {}
        prefix_ui = _sanitize_prefix(data.get('prefix'))
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        prefix = _join_prefix_key(user_root, prefix_ui) if prefix_ui else user_root
        if not prefix:
            return jsonify({'success': False, 'error': 'prefix required'}), 400
        if r2_enabled():
            s3 = get_s3_client()
            if not s3:
                return jsonify({'success': False, 'error': 'R2 not configured'}), 400
            pfx = prefix + '/'
            # Delete all keys under prefix
            keys = [obj.get('Key') for obj in r2_list_objects(pfx)]
            for k in keys:
                try:
                    r2_delete_object(k)
                except Exception:
                    pass
        else:
            path = os.path.join(app.config['UPLOAD_FOLDER'], prefix)
            if os.path.isdir(path):
                shutil.rmtree(path)
        # bust caches for this prefix and its parent
        try:
            _LIB_CACHE.pop(f"{user_root}|{prefix_ui}", None)
            parent = prefix_ui.rsplit('/', 1)[0] if '/' in prefix_ui else ''
            _LIB_CACHE.pop(f"{user_root}|{parent or '__root__'}", None)
        except Exception:
            pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/library/folder/rename', methods=['POST'])
@login_required
def lib_folder_rename():
    try:
        data = request.get_json(force=True) or {}
        prefix_ui = _sanitize_prefix(data.get('prefix'))
        new_name = _sanitize_prefix(data.get('new_name'))
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        # Bugfix: referenced undefined variable `prefix`; use `prefix_ui`
        if not prefix_ui or not new_name:
            return jsonify({'success': False, 'error': 'prefix and new_name required'}), 400
        parent = prefix_ui.rsplit('/', 1)[0] if '/' in prefix_ui else ''
        new_prefix_ui = _join_prefix_key(parent, new_name) if parent else new_name
        old = _join_prefix_key(user_root, prefix_ui)
        new_prefix = _join_prefix_key(user_root, new_prefix_ui)
        if r2_enabled():
            s3 = get_s3_client()
            if not s3:
                return jsonify({'success': False, 'error': 'R2 not configured'}), 400
            oldp = old + '/'
            keys = [obj.get('Key') for obj in r2_list_objects(oldp)]
            bucket = os.environ['R2_BUCKET_NAME']
            for k in keys:
                rel = k[len(oldp):]
                new_k = f"{new_prefix}/{rel}"
                try:
                    s3.copy_object(Bucket=bucket, CopySource={'Bucket': bucket, 'Key': k}, Key=new_k)
                    r2_delete_object(k)
                except Exception:
                    pass
            # Preserve empty folders: if there were no keys (or all were filtered), ensure a marker exists at new prefix
            try:
                if not keys:
                    marker_key = f"{new_prefix}/.keep"
                    r2_put_bytes(marker_key, b'', content_type='application/octet-stream')
                # Best-effort: remove any old marker if present
                old_marker = f"{old}/.keep"
                try:
                    r2_delete_object(old_marker)
                except Exception:
                    pass
            except Exception:
                pass
        else:
            src = os.path.join(app.config['UPLOAD_FOLDER'], old)
            dst = os.path.join(app.config['UPLOAD_FOLDER'], new_prefix)
            os.makedirs(os.path.dirname(dst) or app.config['UPLOAD_FOLDER'], exist_ok=True)
            if os.path.exists(src):
                os.rename(src, dst)
        # bust caches for old/parent/new
        try:
            for k in (f"{user_root}|{prefix_ui}", f"{user_root}|{new_prefix_ui}", f"{user_root}|{parent or '__root__'}"):
                _LIB_CACHE.pop(k, None)
        except Exception:
            pass
        return jsonify({'success': True, 'prefix': new_prefix_ui})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- Upload media only (no playlist/config modification) ----
@app.route('/upload_media', methods=['POST'])
@login_required
def upload_media():
    t0 = time.time()
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        f = request.files['file']
        meta_len = request.content_length
        print(f"[upload_media] start name={f.filename!r} content_length={meta_len} mimetype={getattr(f, 'mimetype', None)}")
        if f.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        if not allowed_file(f.filename):
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400

        ext = f.filename.rsplit('.', 1)[1].lower()
        # Per-user root plus optional UI prefix (current month default)
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        # Respect explicitly provided empty prefix (root). Only default when not provided at all.
        vals = request.values or {}
        prefix_provided = ('prefix' in vals)
        raw_prefix = vals.get('prefix') if prefix_provided else None
        ui_prefix = _sanitize_prefix(raw_prefix)
        if ui_prefix == '' and not prefix_provided:
            ui_prefix = datetime.now(timezone.utc).strftime('%Y-%m')
        req_prefix = _join_prefix_key(user_root, ui_prefix)
        filename = f"{uuid.uuid4()}.{ext}"
        # Bust library cache for this user/prefix and root so new files show up immediately
        try:
            for k in (f"{user_root}|{ui_prefix or '__root__'}", f"{user_root}|__root__"):
                _LIB_CACHE.pop(k, None)
        except Exception:
            pass
        # Ensure local subdirectory exists (under user namespace)
        local_dir = os.path.join(app.config['UPLOAD_FOLDER'], req_prefix)
        try:
            os.makedirs(local_dir, exist_ok=True)
        except Exception:
            pass
        dest = os.path.join(local_dir, filename)

        # Normalize EXIF orientation for JPEGs only (PNG/WebP/etc. typically lack EXIF orientation)
        if ext in ('jpg', 'jpeg') and Image is not None and ImageOps is not None:
            try:
                img = Image.open(f.stream)
                img = ImageOps.exif_transpose(img)
                # Save with a reasonable quality and strip metadata by default
                save_kwargs = {'quality': 90, 'optimize': True}
                img.save(dest, **save_kwargs)
                print(f"[upload_media] PIL save ok -> {dest}")
            except Exception as pil_e:
                # Fallback to raw save
                try:
                    f.stream.seek(0)
                except Exception:
                    pass
                print(f"[upload_media] PIL path failed ({pil_e}); falling back to raw save")
                f.save(dest)
        else:
            f.save(dest)
            print(f"[upload_media] raw save -> {dest}")

        # File stats
        try:
            st = os.stat(dest)
            print(f"[upload_media] saved bytes={st.st_size}")
        except Exception:
            pass

        # If R2 is configured, upload the saved file to the bucket using the prefixed key
        try:
            if r2_enabled():
                with open(dest, 'rb') as fh:
                    data = fh.read()
                key = _join_prefix_key(req_prefix, filename)
                r2_put_bytes(key, data, content_type=_guess_mime(filename))
                print(f"[upload_media] R2 put ok key={key}")
        except Exception as _r2e:
            # Log but do not fail the upload if R2 copy fails; local copy still exists
            logging.warning('R2 upload failed for %s: %s', filename, _r2e)
        dt = int((time.time()-t0)*1000)
        key = _join_prefix_key(req_prefix, filename)
        print(f"[upload_media] done file={key} ms={dt}")
        return jsonify({'success': True, 'filename': key, 'media_type': classify_media(filename), 'url': build_public_url(key)})
    except Exception as e:
        print(f"upload_media error: {e}")
        import traceback as _tb
        _tb.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- R2 Presigned direct-upload endpoint (bypasses origin/proxy limits) ----
@app.route('/r2/presign_upload', methods=['POST', 'GET'])
@login_required
def r2_presign_upload():
    try:
        if not r2_enabled():
            # Return non-secret diagnostics to help ops fix quickly
            return jsonify({'success': False, 'error': 'R2 not configured on server', 'diag': r2_diag()}), 400
        # Accept JSON, form-encoded, or query parameters (more tolerant for various clients)
        data = request.get_json(silent=True) or {}
        # request.values merges args and form
        vals = request.values or {}
        # Fallback: try parsing raw body if JSON wasn't parsed
        if not data:
            try:
                raw = request.get_data(cache=True, as_text=True) or ''
                if raw and raw.strip().startswith('{'):
                    import json as _json
                    data = _json.loads(raw)
            except Exception:
                data = {}
        original = (
            (data.get('filename') or data.get('name') or vals.get('filename') or vals.get('name') or '')
        ).strip()
        content_type = (
            (data.get('content_type') or vals.get('content_type') or request.headers.get('X-Upload-Content-Type') or '')
        ).strip() or None
        if not original and not content_type:
            # Minimal diagnostics to aid debugging without leaking secrets
            try:
                print(f"[presign] missing params; method={request.method} args={dict(request.args)} form_keys={list(getattr(request,'form',{}).keys())} headers_ct={request.headers.get('Content-Type')}")
            except Exception:
                pass
            return jsonify({'success': False, 'error': 'filename or content_type required'}), 400
        # Derive extension from filename when possible; fallback from content-type
        ext = ''
        if original and '.' in original:
            ext = original.rsplit('.', 1)[-1].lower()
        if not ext and content_type:
            try:
                import mimetypes
                # Reverse map common types
                exts = mimetypes.guess_all_extensions(content_type) or []
                if exts:
                    ext = exts[0].lstrip('.').lower()
            except Exception:
                pass
        if not ext:
            # Default to bin to avoid leaking original name
            ext = 'bin'
        # Validate extension against allowed set to avoid junk uploads
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({'success': False, 'error': f'Unsupported file extension: .{ext}'}), 400
        # Per-user root + optional UI prefix; default month folder.
        # Respect explicitly provided empty prefix (root). Only default when not provided at all.
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        prefix_in_data = isinstance(data, dict) and ('prefix' in data)
        prefix_in_vals = isinstance(vals, dict) and ('prefix' in vals)
        prefix_provided = bool(prefix_in_data or prefix_in_vals)
        raw_prefix = (data.get('prefix') if prefix_in_data else (vals.get('prefix') if prefix_in_vals else None))
        ui_prefix = _sanitize_prefix(raw_prefix)
        if ui_prefix == '' and not prefix_provided:
            ui_prefix = datetime.now(timezone.utc).strftime('%Y-%m')
        req_prefix = _join_prefix_key(user_root, ui_prefix)
        key = _join_prefix_key(req_prefix, f"{uuid.uuid4()}.{ext}")
        # Proactively bust library cache for this user/prefix so the new file appears right away
        try:
            for k in (f"{user_root}|{ui_prefix or '__root__'}", f"{user_root}|__root__"):
                _LIB_CACHE.pop(k, None)
        except Exception:
            pass
        s3 = get_s3_client()
        # Ensure content-type is set for correct serving via CDN
        if not content_type:
            content_type = _guess_mime(key) or 'application/octet-stream'
        try:
            url = s3.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': os.environ['R2_BUCKET_NAME'],
                    'Key': key,
                    'ContentType': content_type,
                },
                ExpiresIn=3600
            )
        except Exception as e:
            logging.exception('Failed to presign R2 URL: %s', e)
            return jsonify({'success': False, 'error': 'presign failed'}), 500
        # Record minimal presign diag
        try:
            evt = {
                'user': _safe_user_key(),
                'key': key,
                'ct': content_type,
                'ts': int(time.time())
            }
            if isinstance(_PRESIGNS, list):
                _PRESIGNS.append(evt)
            else:
                _PRESIGNS.append(evt)  # deque
        except Exception:
            pass
        return jsonify({
            'success': True,
            'filename': key,
            'upload_url': url,
            'content_type': content_type,
            'public_url': build_public_url(key),
            'expires_in': 3600
        })
    except Exception as e:
        logging.exception('r2_presign_upload error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- R2 status diagnostics (safe, no secrets) ----
@app.route('/r2/status', methods=['GET'])
def r2_status():
    try:
        d = r2_diag()
        # Include MEDIA_BASE_URL snapshot for quick frontend sanity checks
        return jsonify({'success': True, 'r2': d, 'media_base_url': get_media_base_url(), 'env_media_base_url': os.environ.get('MEDIA_BASE_URL')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- Assign existing media to a screen (no file upload) ----
@app.route('/assign_to_screen', methods=['POST'])
@login_required
def assign_to_screen():
    try:
        data = request.get_json() or {}
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        apply_to_all = bool(data.get('apply_to_all', False))
        incoming = data.get('filename') or data.get('file') or ''

        if not store_id or not screen_id or not incoming:
            return jsonify({'success': False, 'error': 'store_id, screen_id, and filename are required'}), 400

        # Early best-effort normalization (will be revalidated against loaded config below)
        try:
            cfg_probe = load_store_config()
            if store_id in cfg_probe.get('screens', {}) and screen_id not in cfg_probe['screens'][store_id]:
                candidate = f"{store_id}_{screen_id}"
                if candidate in cfg_probe['screens'][store_id]:
                    screen_id = candidate
        except Exception:
            pass

        # Normalize incoming into an object key
        key = str(incoming or '').strip()
        # Enforce per-user ownership: key must be within user's namespace unless absolute URL to foreign CDN/origin is allowed
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        # Allow absolute http(s) only if domain is our media base or origin; otherwise require namespaced key
        raw_key = key
        if key.startswith('http://') or key.startswith('https://'):
            try:
                from urllib.parse import urlparse
                u = urlparse(key)
                base = (get_media_base_url() or '').strip('/')
                # Extract path relative to host
                path = (u.path or '').lstrip('/')
                # If MEDIA_BASE_URL has a path prefix, accept both with/without it
                # Also accept our origin paths under /static/uploads or /media
                # Strip common origin prefixes to yield raw object key
                if path.startswith('static/uploads/'):
                    path = path[len('static/uploads/'):]
                elif path.startswith('media/'):
                    # Videos sometimes flow through /media/<key>; normalize to key
                    path = path[len('media/'):]
                # If MEDIA_BASE_URL points to a subpath (rare), remove that as well
                try:
                    if base:
                        from urllib.parse import urlparse as _p
                        b = _p(base if base.startswith('http') else ('http://' + base))
                        bpath = (b.path or '').lstrip('/')
                        if bpath and path.startswith(bpath + '/'):
                            path = path[len(bpath)+1:]
                except Exception:
                    pass
                # Decode any percent-encoded segments
                try:
                    from urllib.parse import unquote
                    rel = unquote(path)
                except Exception:
                    rel = path
                key = rel
            except Exception:
                return jsonify({'success': False, 'error': 'invalid media URL'}), 400
        # Final check: key must begin with user_root/
        if not key.startswith(user_root + '/'):
            # Soft-allow if this exact key was presigned by this user recently (same session user)
            try:
                me = _safe_user_key()
                recent = list(_PRESIGNS)[-50:] if not isinstance(_PRESIGNS, list) else _PRESIGNS[-50:]
                if any((evt.get('user') == me and evt.get('key') == key) for evt in recent):
                    logging.info('assign_to_screen: allowing key via recent presign match for user=%s', me)
                else:
                    # Extra diagnostics to aid production triage (non-secret)
                    info = {
                        'user': me,
                        'user_root': user_root,
                        'incoming': str(incoming)[:500],
                        'raw_key': str(raw_key)[:500],
                        'normalized_key': str(key)[:500],
                        'media_base': get_media_base_url(),
                        'ts': int(time.time())
                    }
                    print(f"[assign_to_screen][DENY] {info}")
                    if isinstance(_ASSIGN_DENIES, list):
                        _ASSIGN_DENIES.append(info)
                    else:
                        _ASSIGN_DENIES.append(info)
                    return jsonify({'success': False, 'error': 'cross-tenant media access denied'}), 403
            except Exception:
                # If diagnostics fail, fall back to deny safely
                return jsonify({'success': False, 'error': 'cross-tenant media access denied'}), 403
        if not allowed_file(key):
            return jsonify({'success': False, 'error': 'Invalid or unsupported file type'}), 400

        config = ensure_playlists_structure(load_store_config())

        # Normalize screen_id against the actual config snapshot we will modify
        try:
            if store_id in config.get('screens', {}) and screen_id not in config['screens'][store_id]:
                candidate = f"{store_id}_{screen_id}"
                if candidate in config['screens'][store_id]:
                    screen_id = candidate
        except Exception:
            pass

        # If apply_to_all requested from non-master, downgrade to single-store
        if apply_to_all:
            master_store_id = config.get('master_store_id')
            if store_id != master_store_id:
                apply_to_all = False

        def _assign_to(store: str, scr_id: str):
            scr = config['screens'][store][scr_id]
            scr['file'] = key
            pl = scr.setdefault('playlist', [])
            if not any((i.get('file') == key) for i in pl):
                pl.append({
                    'id': str(uuid.uuid4()),
                    'file': key,
                    'enabled': True,
                    'start': None,
                    'end': None,
                    'schedule': [],
                    'duration': 10,
                    'repeat': True,
                    'link_next': False,
                    'media_type': classify_media(key)
                })

        if apply_to_all:
            screen_type = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id
            updated_stores = []
            skipped_stores = []
            created_screens = []
            for sid in config.get('screens', {}).keys():
                target = f"{sid}_{screen_type}"
                legacy = screen_type
                if target in config['screens'][sid]:
                    actual = target
                elif legacy in config['screens'][sid]:
                    actual = legacy
                else:
                    is_promo = screen_type.startswith('promo')
                    config['screens'][sid][target] = {
                        'file': None,
                        'vertical': is_promo,
                        'horizontal': not is_promo,
                        'rotation': 0,
                        'protected': False,
                        'playlist': []
                    }
                    created_screens.append(f"{sid}:{target}")
                    actual = target

                if config['screens'][sid][actual].get('protected'):
                    skipped_stores.append(sid)
                else:
                    _assign_to(sid, actual)
                    updated_stores.append(sid)

            save_store_config(config)
            return jsonify({
                'success': True,
                'filename': key,
                'url': build_public_url(key),
                'media_type': classify_media(key),
                'store_id': store_id,
                'screen_id': screen_id,
                'applied_to_all': True,
                'updated_stores': updated_stores,
                'skipped_stores': skipped_stores,
                'created_screens': created_screens
            })

        # Single-store path
        if store_id in config.get('screens', {}) and screen_id in config['screens'].get(store_id, {}):
            _assign_to(store_id, screen_id)
            save_store_config(config)
            return jsonify({
                'success': True,
                'filename': key,
                'url': build_public_url(key),
                'media_type': classify_media(key),
                'store_id': store_id,
                'screen_id': screen_id,
                'applied_to_all': False
            })

        return jsonify({'success': False, 'error': 'screen not found'}), 404
    except Exception as e:
        print(f"assign_to_screen error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Safe diagnostics for current session user
@app.route('/debug/assign_recent')
@login_required
def debug_assign_recent():
    try:
        key = _safe_user_key()
        # Filter to current user, newest first
        denies = [d for d in list(_ASSIGN_DENIES)[-50:] if not key or d.get('user') == key]
        pres = [p for p in list(_PRESIGNS)[-50:] if not key or p.get('user') == key]
        return jsonify({'success': True, 'denies': denies[-20:], 'presigns': pres[-20:]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -------- Store & Screen discovery API (for device first-run setup) --------
@app.route('/stores')
@with_etag_json
def list_stores():
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key and not _safe_user_key():
        return {'success': False, 'error': 'pair code required'}, 403
    ukey = user_key or _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    return {'success': True, 'stores': cfg.get('stores', [])}

@app.route('/screens_list/<store_id>')
@with_etag_json
def list_screens_legacy_array(store_id):
    """Legacy endpoint returning an array of {'id': screen_id} objects.

    NOTE: The dashboard now uses /screens/<store_id> which returns a mapping
    of screen_id -> screen_object. This endpoint retained for older TV clients.
    """
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key and not _safe_user_key():
        return {'success': False, 'error': 'pair code required'}, 403
    ukey = user_key or _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    if store_id not in (cfg.get('screens') or {}):
        return {'success': False, 'error': 'store not found'}, 404
    screens = cfg.get('screens', {}).get(store_id, {})
    arr = [{'id': sid} for sid in screens.keys()]
    return {'success': True, 'screens': arr, 'legacy': True}

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>', methods=['PATCH'])
@login_required
def update_playlist_item(store_id, screen_id, item_id):
    print(f"DEBUG: PATCH playlist item {store_id} {screen_id} {item_id}")
    # Persist in the same per-user config the dashboard is using
    ukey = _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    updated = False
    allowed_effects = {'fade','slide-l','slide-r','zoom-in','zoom-out','rotate'}
    for item in screen.get('playlist', []):
        if item['id'] == item_id:
            payload = request.get_json() or {}
            # Allow replacing the media file by referencing an existing upload
            if 'file' in payload:
                new_file = payload.get('file')
                if new_file:
                    # For R2-backed storage, skip local existence check
                    if not allowed_file(new_file):
                        return jsonify({'success': False, 'error': 'invalid file type'}), 400
                    if not r2_enabled():
                        path = os.path.join(app.config['UPLOAD_FOLDER'], new_file)
                        if not os.path.exists(path):
                            return jsonify({'success': False, 'error': 'file not found in uploads'}), 400
                    item['file'] = new_file
                    item['media_type'] = classify_media(new_file)
                    updated = True
            # Basic fields
            for k in ['enabled','start','end','duration','repeat','link_next']:
                if k in payload:
                    if k == 'duration':
                        try:
                            dval = int(str(payload[k]).strip())
                            if dval < 1:
                                dval = 1
                            item[k] = dval
                        except Exception:
                            pass
                    else:
                        item[k] = payload[k]
                    updated = True
            # Transition effect for item playback
            if 'effect' in payload:
                val = str(payload.get('effect') or '').strip().lower()
                if val in allowed_effects:
                    item['effect'] = val
                elif val == '' or val == 'default' or val == 'none':
                    item.pop('effect', None)
                else:
                    # ignore invalid values
                    pass
                updated = True
            # Days-of-week for primary interval
            if 'days' in payload:
                if isinstance(payload['days'], list):
                    # normalize to lower 3-letter codes
                    item['days'] = [str(d).lower()[:3] for d in payload['days'] if d]
                    updated = True
                elif payload['days'] is None:
                    item.pop('days', None)
                    updated = True
            # Schedule management: replace whole schedule array if provided
            if 'schedule' in payload and isinstance(payload['schedule'], list):
                # Sanitize entries to dicts with start/end only
                new_sched = []
                for win in payload['schedule']:
                    if isinstance(win, dict):
                        w = {'start': win.get('start'), 'end': win.get('end')}
                        if 'days' in win and isinstance(win.get('days'), list):
                            w['days'] = [str(d).lower()[:3] for d in win.get('days') if d]
                        new_sched.append(w)
                item['schedule'] = new_sched
                updated = True
            # Propagate to sync group members if this item is part of a sync group
            try:
                sref = item.get('sync_ref') if isinstance(item, dict) else None
                if updated and isinstance(sref, dict) and sref.get('group'):
                    gid = sref.get('group')
                    group = (cfg.get('sync_groups') or {}).get(gid)
                    if isinstance(group, dict):
                        members = group.get('members') or []
                        # Keep group filename in sync when 'file' changes on master
                        if 'file' in (payload or {}) and payload.get('file'):
                            try:
                                group['filename'] = payload.get('file')
                            except Exception:
                                pass
                        # Fields that are safe to propagate
                        prop_keys = set()
                        for k in ['file','enabled','start','end','duration','repeat','link_next','effect','days','schedule']:
                            if k in (payload or {}):
                                prop_keys.add(k)
                        for m in members:
                            msid = m.get('screen_id')
                            mid = m.get('item_id')
                            if not msid or not mid:
                                continue
                            if msid == screen_id and mid == item_id:
                                continue  # already applied
                            try:
                                tgt = cfg.get('screens', {}).get(store_id, {}).get(msid)
                                if not tgt:
                                    continue
                                for it2 in (tgt.get('playlist') or []):
                                    if it2.get('id') == mid:
                                        # Apply only provided keys; reuse sanitized schedule handling
                                        if 'file' in prop_keys and 'file' in payload:
                                            nf = payload.get('file')
                                            if nf and allowed_file(nf):
                                                it2['file'] = nf
                                                it2['media_type'] = classify_media(nf)
                                        for k in ['enabled','start','end','duration','repeat','link_next']:
                                            if k in prop_keys:
                                                if k == 'duration':
                                                    try:
                                                        dval = int(str(payload[k]).strip())
                                                        if dval < 1:
                                                            dval = 1
                                                        it2[k] = dval
                                                    except Exception:
                                                        pass
                                                else:
                                                    it2[k] = payload.get(k)
                                        if 'effect' in prop_keys:
                                            val = str(payload.get('effect') or '').strip().lower()
                                            allowed_effects = {'fade','slide-l','slide-r','zoom-in','zoom-out','rotate'}
                                            if val in allowed_effects:
                                                it2['effect'] = val
                                            elif val in ('', 'default', 'none'):
                                                it2.pop('effect', None)
                                        if 'days' in prop_keys:
                                            dv = payload.get('days')
                                            if isinstance(dv, list):
                                                it2['days'] = [str(d).lower()[:3] for d in dv if d]
                                            elif dv is None:
                                                it2.pop('days', None)
                                        if 'schedule' in prop_keys and isinstance(payload.get('schedule'), list):
                                            new_sched = []
                                            for win in payload.get('schedule'):
                                                if isinstance(win, dict):
                                                    w = {'start': win.get('start'), 'end': win.get('end')}
                                                    if 'days' in win and isinstance(win.get('days'), list):
                                                        w['days'] = [str(d).lower()[:3] for d in win.get('days') if d]
                                                    new_sched.append(w)
                                            it2['schedule'] = new_sched
                                        # Enqueue reload for that screen
                                        _enqueue_command_in_cfg(cfg, store_id, msid, 'reload')
                                        break
                            except Exception:
                                continue
            except Exception:
                pass
            break
    if updated:
        # Push a reload so connected TVs pick up changes quickly
        _enqueue_command_in_cfg(cfg, store_id, screen_id, 'reload')
        if ukey:
            save_store_config_for_user_safe_key(ukey, cfg)
        else:
            save_store_config(cfg)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'item not found'}), 404

@app.route('/screens/<store_id>', methods=['GET'])
@login_required
def get_screens_for_store(store_id: str):
    """Return authoritative screen map for a single store (used by dashboard to purge phantom client entries)."""
    try:
        ukey = _safe_user_key()
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
        screens_all = cfg.get('screens') or {}
        if store_id not in screens_all:
            return jsonify({'success': False, 'error': 'store not found'}), 404
        store_map = screens_all.get(store_id) or {}
        # Filter out any screens whose prefixed store segment doesn't match (phantom leakage from other stores / prior sync operations)
        cleaned = {}
        removed = []
        for sid, sval in list(store_map.items()):
            if '_' in sid:
                pref = sid.split('_', 1)[0]
                if pref != store_id:
                    removed.append(sid)
                    continue
            # Allow legacy unprefixed ids like 'screen1', 'promo1'
            cleaned[sid] = sval
        if removed:
            # Persist cleanup so future calls don't re-send phantoms
            screens_all[store_id] = cleaned
            cfg['screens'] = screens_all
            if ukey:
                save_store_config_for_user_safe_key(ukey, cfg)
            else:
                save_store_config(cfg)
            app.logger.warning('Purged %d cross-store screen ids from %s: %s', len(removed), store_id, removed)
        return jsonify({'success': True, 'store_id': store_id, 'screens': cleaned})
    except Exception as e:
        app.logger.exception('get_screens_for_store failed')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>', methods=['DELETE'])
@login_required
def delete_playlist_item(store_id, screen_id, item_id):
    print(f"DEBUG: DELETE playlist item {store_id} {screen_id} {item_id}")
    ukey = _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    # Find the item and determine if it's part of a sync group
    target_item = None
    for it in (screen.get('playlist') or []):
        if it.get('id') == item_id:
            target_item = it
            break
    if not target_item:
        return jsonify({'success': False, 'error': 'item not found'}), 404
    sref = target_item.get('sync_ref') if isinstance(target_item, dict) else None
    if isinstance(sref, dict) and sref.get('group'):
        # When deleting a synced item: if master, remove entire group; if follower, remove only this member
        gid = sref.get('group')
        group = (cfg.get('sync_groups') or {}).get(gid)
        # Remove this item from its screen
        screen['playlist'] = [i for i in screen.get('playlist', []) if i.get('id') != item_id]
        _enqueue_command_in_cfg(cfg, store_id, screen_id, 'reload')
        if isinstance(group, dict):
            role = sref.get('role')
            members = group.get('members') or []
            if role == 'master':
                # Delete all members' items and remove the group entirely
                for m in members:
                    msid = m.get('screen_id')
                    mid = m.get('item_id')
                    if not msid or not mid:
                        continue
                    try:
                        tgt = cfg.get('screens', {}).get(store_id, {}).get(msid)
                        if not tgt:
                            continue
                        before_len = len(tgt.get('playlist') or [])
                        tgt['playlist'] = [i for i in (tgt.get('playlist') or []) if i.get('id') != mid]
                        if len(tgt['playlist']) != before_len:
                            _enqueue_command_in_cfg(cfg, store_id, msid, 'reload')
                    except Exception:
                        continue
                try:
                    cfg.get('sync_groups', {}).pop(gid, None)
                except Exception:
                    pass
            else:
                # Follower removed: drop from group members; if no members left, remove group
                try:
                    new_members = [m for m in members if m.get('item_id') != item_id]
                    group['members'] = new_members
                    if not new_members:
                        cfg.get('sync_groups', {}).pop(gid, None)
                except Exception:
                    pass
        if ukey:
            save_store_config_for_user_safe_key(ukey, cfg)
        else:
            save_store_config(cfg)
        return jsonify({'success': True})
    else:
        before = len(screen.get('playlist', []))
        screen['playlist'] = [i for i in screen.get('playlist', []) if i.get('id') != item_id]
        if len(screen['playlist']) != before:
            _enqueue_command_in_cfg(cfg, store_id, screen_id, 'reload')
            if ukey:
                save_store_config_for_user_safe_key(ukey, cfg)
            else:
                save_store_config(cfg)
            return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'item not found'}), 404

# ---- Schedule window management endpoints ----
@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>/schedule', methods=['POST'])
@login_required
def add_schedule_window(store_id, screen_id, item_id):
    ukey = _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    payload = request.get_json() or {}
    # Accept optional days array; default to [] (meaning all days)
    valid_days = {'mon','tue','wed','thu','fri','sat','sun'}
    days = payload.get('days') or []
    if isinstance(days, list):
        days = [d for d in days if isinstance(d, str) and d.lower() in valid_days]
    else:
        days = []
    # Enabled defaults to True if not provided
    enabled = payload.get('enabled')
    if isinstance(enabled, bool):
        win_enabled = enabled
    else:
        win_enabled = True
    win = {'start': payload.get('start'), 'end': payload.get('end'), 'days': days, 'enabled': win_enabled}
    for it in screen.get('playlist', []):
        if it.get('id') == item_id:
            sched = it.setdefault('schedule', [])
            sched.append(win)
            # If part of a sync group, mirror to all members
            try:
                sref = it.get('sync_ref') if isinstance(it, dict) else None
                if isinstance(sref, dict) and sref.get('group'):
                    gid = sref.get('group')
                    group = (cfg.get('sync_groups') or {}).get(gid)
                    members = (group.get('members') or []) if isinstance(group, dict) else []
                    for m in members:
                        msid = m.get('screen_id')
                        mid = m.get('item_id')
                        if not msid or not mid:
                            continue
                        if msid == screen_id and mid == item_id:
                            continue
                        try:
                            tgt = cfg.get('screens', {}).get(store_id, {}).get(msid)
                            if not tgt:
                                continue
                            for it2 in (tgt.get('playlist') or []):
                                if it2.get('id') == mid:
                                    sch2 = it2.setdefault('schedule', [])
                                    sch2.append(dict(win))
                                    _enqueue_command_in_cfg(cfg, store_id, msid, 'reload')
                                    break
                        except Exception:
                            continue
            except Exception:
                pass
            _enqueue_command_in_cfg(cfg, store_id, screen_id, 'reload')
            if ukey:
                save_store_config_for_user_safe_key(ukey, cfg)
            else:
                save_store_config(cfg)
            return jsonify({'success': True, 'index': len(sched)-1, 'window': win})
    return jsonify({'success': False, 'error': 'item not found'}), 404

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>/schedule/<int:index>', methods=['PATCH'])
@login_required
def update_schedule_window(store_id, screen_id, item_id, index):
    ukey = _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    payload = request.get_json() or {}
    for it in screen.get('playlist', []):
        if it.get('id') == item_id:
            sched = it.setdefault('schedule', [])
            if 0 <= index < len(sched):
                if 'start' in payload: sched[index]['start'] = payload.get('start')
                if 'end' in payload: sched[index]['end'] = payload.get('end')
                if 'days' in payload:
                    valid_days = {'mon','tue','wed','thu','fri','sat','sun'}
                    days = payload.get('days') or []
                    if isinstance(days, list):
                        sched[index]['days'] = [d for d in days if isinstance(d, str) and d.lower() in valid_days]
                    else:
                        sched[index]['days'] = []
                if 'enabled' in payload:
                    en = payload.get('enabled')
                    sched[index]['enabled'] = bool(en) if isinstance(en, bool) else False
                # Propagate to sync group members at same index if present
                try:
                    sref = it.get('sync_ref') if isinstance(it, dict) else None
                    if isinstance(sref, dict) and sref.get('group'):
                        gid = sref.get('group')
                        group = (cfg.get('sync_groups') or {}).get(gid)
                        members = (group.get('members') or []) if isinstance(group, dict) else []
                        for m in members:
                            msid = m.get('screen_id')
                            mid = m.get('item_id')
                            if not msid or not mid:
                                continue
                            if msid == screen_id and mid == item_id:
                                continue
                            try:
                                tgt = cfg.get('screens', {}).get(store_id, {}).get(msid)
                                if not tgt:
                                    continue
                                for it2 in (tgt.get('playlist') or []):
                                    if it2.get('id') == mid:
                                        sch2 = it2.setdefault('schedule', [])
                                        if 0 <= index < len(sch2):
                                            if 'start' in payload: sch2[index]['start'] = payload.get('start')
                                            if 'end' in payload: sch2[index]['end'] = payload.get('end')
                                            if 'days' in payload:
                                                valid_days = {'mon','tue','wed','thu','fri','sat','sun'}
                                                days = payload.get('days') or []
                                                if isinstance(days, list):
                                                    sch2[index]['days'] = [d for d in days if isinstance(d, str) and d.lower() in valid_days]
                                                else:
                                                    sch2[index]['days'] = []
                                            if 'enabled' in payload:
                                                en = payload.get('enabled')
                                                sch2[index]['enabled'] = bool(en) if isinstance(en, bool) else False
                                            _enqueue_command_in_cfg(cfg, store_id, msid, 'reload')
                                        break
                            except Exception:
                                continue
                except Exception:
                    pass
                _enqueue_command_in_cfg(cfg, store_id, screen_id, 'reload')
                if ukey:
                    save_store_config_for_user_safe_key(ukey, cfg)
                else:
                    save_store_config(cfg)
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'index out of range'}), 400
    return jsonify({'success': False, 'error': 'item not found'}), 404

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>/schedule/<int:index>', methods=['DELETE'])
@login_required
def delete_schedule_window(store_id, screen_id, item_id, index):
    ukey = _safe_user_key()
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    for it in screen.get('playlist', []):
        if it.get('id') == item_id:
            sched = it.setdefault('schedule', [])
            if 0 <= index < len(sched):
                removed = sched.pop(index)
                # Mirror deletion to sync group members
                try:
                    sref = it.get('sync_ref') if isinstance(it, dict) else None
                    if isinstance(sref, dict) and sref.get('group'):
                        gid = sref.get('group')
                        group = (cfg.get('sync_groups') or {}).get(gid)
                        members = (group.get('members') or []) if isinstance(group, dict) else []
                        for m in members:
                            msid = m.get('screen_id')
                            mid = m.get('item_id')
                            if not msid or not mid:
                                continue
                            if msid == screen_id and mid == item_id:
                                continue
                            try:
                                tgt = cfg.get('screens', {}).get(store_id, {}).get(msid)
                                if not tgt:
                                    continue
                                for it2 in (tgt.get('playlist') or []):
                                    if it2.get('id') == mid:
                                        sch2 = it2.setdefault('schedule', [])
                                        if 0 <= index < len(sch2):
                                            sch2.pop(index)
                                            _enqueue_command_in_cfg(cfg, store_id, msid, 'reload')
                                        break
                            except Exception:
                                continue
                except Exception:
                    pass
                _enqueue_command_in_cfg(cfg, store_id, screen_id, 'reload')
                if ukey:
                    save_store_config_for_user_safe_key(ukey, cfg)
                else:
                    save_store_config(cfg)
                return jsonify({'success': True, 'removed': removed})
            return jsonify({'success': False, 'error': 'index out of range'}), 400
    return jsonify({'success': False, 'error': 'item not found'}), 404

# ---- Legacy fixed-path alias: redirect /playlist/1881/... to current master store id ----
@app.route('/playlist/1881/<screen_id>')
def get_playlist_legacy_1881(screen_id):
    cfg = ensure_playlists_structure(load_store_config())
    master = cfg.get('master_store_id')
    if master:
        # Call into the primary handler logic by passing mapped ids
        return get_playlist(master, screen_id)
    return jsonify({'success': False, 'error': 'legacy mapping unavailable'}), 404

# ---------------- Multi-screen Sync (create groups and mark items) ----------------
@app.route('/sync/create', methods=['POST'])
@login_required
def create_sync_group():
    """Create a synchronized playlist item across multiple screens within a store.
    Body JSON: { store_id, base_screen_id, count, filename }
    - base_screen_id: the first screen (e.g., 'screen1', 'promo1'). We'll attempt to add subsequent
      numeric siblings (screen2, screen3, ...) up to count screens if present in the store.
    - count: 2..5; we only include existing screens and skip missing ones.
    - filename: existing media key within the current user's namespace (or absolute URL that normalizes to it).
    Returns: { success, group_id, used_screens:[...], members:[{screen_id,item_id,role,order}], skipped:[...] }
    """
    try:
        data = request.get_json(force=True) or {}
        store_id = str(data.get('store_id') or '').strip()
        base_screen_id = str(data.get('base_screen_id') or '').strip()
        try:
            count = int(data.get('count') or 0)
        except Exception:
            count = 0
        incoming = str(data.get('filename') or data.get('file') or '').strip()

        if not store_id or not base_screen_id or count < 2 or count > 5 or not incoming:
            return jsonify({'success': False, 'error': 'store_id, base_screen_id, count (2-5), and filename are required'}), 400

        # Normalize/validate media key ownership (similar to assign_to_screen)
        key = incoming
        user_root = _user_content_prefix()
        if not user_root:
            return jsonify({'success': False, 'error': 'auth required'}), 403
        if key.startswith('http://') or key.startswith('https://'):
            try:
                from urllib.parse import urlparse, unquote
                u = urlparse(key)
                path = (u.path or '').lstrip('/')
                if path.startswith('static/uploads/'):
                    path = path[len('static/uploads/'):]
                elif path.startswith('media/'):
                    path = path[len('media/'):]
                # Remove MEDIA_BASE_URL path prefix if present
                try:
                    base = (get_media_base_url() or '').strip('/')
                    if base:
                        b = urlparse(base if base.startswith('http') else ('http://' + base))
                        bpath = (b.path or '').lstrip('/')
                        if bpath and path.startswith(bpath + '/'):
                            path = path[len(bpath)+1:]
                except Exception:
                    pass
                key = unquote(path)
            except Exception:
                return jsonify({'success': False, 'error': 'invalid media URL'}), 400
        if not key.startswith(user_root + '/'):
            return jsonify({'success': False, 'error': 'cross-tenant media access denied'}), 403
        if not allowed_file(key):
            return jsonify({'success': False, 'error': 'invalid or unsupported file type'}), 400

        ukey = _safe_user_key()
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
        if store_id not in (cfg.get('screens') or {}):
            return jsonify({'success': False, 'error': 'store not found'}), 404

        screens_map = cfg['screens'][store_id]
        # Normalize base_screen_id to an actual key present in this store (handles legacy short vs store-prefixed ids)
        if base_screen_id not in screens_map:
            candidate = f"{store_id}_{base_screen_id}"
            if candidate in screens_map:
                base_screen_id = candidate
        # Build the list of sibling screens from base + sequential index if any, preserving any prefix
        import re
        m = re.match(r'^(.*?)(\d+)$', base_screen_id)
        candidates: list[str] = []
        if m:
            prefix, num = m.group(1), int(m.group(2))
            for i in range(count):
                candidates.append(f"{prefix}{num + i}")
        else:
            # No trailing number; just use base_screen_id only (count ignored beyond 1)
            candidates = [base_screen_id]

        used = []
        skipped = []
        members = []
        group_id = str(uuid.uuid4())
        # Choose a common start timestamp a bit in the future to allow devices to fetch and align
        now = int(time.time())
        # Align to next 5-second boundary, at least +5s from now
        start_epoch = ((now // 5) + 2) * 5
        # Ensure top-level sync_groups container
        try:
            if not isinstance(cfg.get('sync_groups'), dict):
                cfg['sync_groups'] = {}
        except Exception:
            cfg['sync_groups'] = {}

        for idx, sid in enumerate(candidates):
            scr = screens_map.get(sid)
            if not scr:
                # Auto-create missing screen with defaults based on type (promo = vertical)
                try:
                    store_prefix = f"{store_id}_"
                    part = sid[len(store_prefix):] if sid.startswith(store_prefix) else sid
                    is_promo = str(part).startswith('promo')
                    scr = {
                        'file': None,
                        'vertical': True if is_promo else False,
                        'horizontal': False if is_promo else True,
                        'rotation': 0,
                        'protected': False
                    }
                    screens_map[sid] = scr
                except Exception:
                    skipped.append(sid)
                    continue
            # Ensure playlist exists
            pl = scr.setdefault('playlist', [])
            # Create a new item for this sync group (avoid duplicate exact same key+group)
            existing = next((it for it in pl if it.get('file') == key and isinstance(it.get('sync_ref'), dict) and it['sync_ref'].get('group') == group_id), None)
            if existing:
                item = existing
            else:
                item = {
                    'id': str(uuid.uuid4()),
                    'file': key,
                    'enabled': True,
                    'start': None,
                    'end': None,
                    'schedule': [],
                    'duration': 10,
                    'repeat': True,
                    'link_next': False,
                    'media_type': classify_media(key)
                }
                pl.append(item)
            role = 'master' if idx == 0 else 'follower'
            item['sync_ref'] = {'group': group_id, 'role': role, 'order': idx}
            scr['file'] = key  # show as current for screen preview
            used.append(sid)
            members.append({'screen_id': sid, 'item_id': item['id'], 'role': role, 'order': idx})
            _enqueue_command_in_cfg(cfg, store_id, sid, 'reload')

        # Persist group metadata
        cfg['sync_groups'][group_id] = {
            'store_id': store_id,
            'base': base_screen_id,
            'count': count,
            'filename': key,
            'members': members,
            'created_at': now,
            'start_epoch': start_epoch,
            # default segmentation mode: split horizontally across N screens
            'mode': 'split-h'
        }

        if ukey:
            save_store_config_for_user_safe_key(ukey, cfg)
        else:
            save_store_config(cfg)
        return jsonify({'success': True, 'group_id': group_id, 'used_screens': used, 'members': members, 'skipped': skipped, 'start_epoch': start_epoch})
    except Exception as e:
        app.logger.exception('create_sync_group failed')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/sync/expand', methods=['POST'])
@login_required
def expand_sync_group():
    """Expand an existing sync group to a higher screen count.
    Body JSON: { store_id, group_id, new_count }
    Constraints:
      - new_count must be > current member count and <= 5
      - Auto-create missing sequential screens if needed
    Returns: { success, group_id, added: [...], members:[...], count }
    """
    try:
        data = request.get_json(force=True) or {}
        store_id = str(data.get('store_id') or '').strip()
        group_id = str(data.get('group_id') or '').strip()
        try:
            new_count = int(data.get('new_count') or 0)
        except Exception:
            new_count = 0
        if not store_id or not group_id or new_count < 2 or new_count > 5:
            return jsonify({'success': False, 'error': 'store_id, group_id and new_count(2-5) required'}), 400
        ukey = _safe_user_key()
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
        groups = cfg.get('sync_groups') or {}
        grp = groups.get(group_id)
        if not grp or grp.get('store_id') != store_id:
            return jsonify({'success': False, 'error': 'group not found'}), 404
        members = grp.get('members') or []
        cur_count = len(members)
        if new_count <= cur_count:
            return jsonify({'success': False, 'error': 'new_count must be greater than current member count', 'current': cur_count}), 400
        if new_count > 5:
            return jsonify({'success': False, 'error': 'max 5 screens'}), 400
        screens_map = (cfg.get('screens') or {}).get(store_id)
        if not isinstance(screens_map, dict):
            return jsonify({'success': False, 'error': 'store not found'}), 404
        base = grp.get('base') or ''
        import re, uuid as _uuid
        m = re.match(r'^(.*?)(\d+)$', base)
        if not m:
            return jsonify({'success': False, 'error': 'base screen not numeric-suffixed; cannot auto-expand'}), 400
        prefix, num = m.group(1), int(m.group(2))
        added = []
        media_file = grp.get('filename')
        # Build needed candidate ids up to new_count
        for order in range(cur_count, new_count):
            sid = f"{prefix}{num + order}"
            scr = screens_map.get(sid)
            if not scr:
                # create blank screen
                short = sid.split('_',1)[1] if '_' in sid else sid
                is_promo = short.startswith('promo')
                scr = {
                    'file': None,
                    'vertical': True if is_promo else False,
                    'horizontal': False if is_promo else True,
                    'rotation': 0,
                    'protected': False
                }
                screens_map[sid] = scr
            pl = scr.setdefault('playlist', [])
            item = {
                'id': str(_uuid.uuid4()),
                'file': media_file,
                'enabled': True,
                'start': None,
                'end': None,
                'schedule': [],
                'duration': 10,
                'repeat': True,
                'link_next': False,
                'media_type': classify_media(media_file)
            }
            role = 'follower'
            item['sync_ref'] = {'group': group_id, 'role': role, 'order': order}
            pl.append(item)
            scr['file'] = media_file
            members.append({'screen_id': sid, 'item_id': item['id'], 'role': role, 'order': order})
            added.append(sid)
            _enqueue_command_in_cfg(cfg, store_id, sid, 'reload')
        grp['count'] = new_count
        grp['members'] = members
        if ukey:
            save_store_config_for_user_safe_key(ukey, cfg)
        else:
            save_store_config(cfg)
        return jsonify({'success': True, 'group_id': group_id, 'added': added, 'members': members, 'count': new_count})
    except Exception as e:
        app.logger.exception('expand_sync_group failed')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/sync/add_follower', methods=['POST'])
@login_required
def add_sync_follower():
    """Add one follower screen to a base sync layout.
    Body: { store_id, base_screen_id }
    Behavior:
      - If a sync group already exists with base == base_screen_id (or resolves to it), append one follower (max 5 total)
      - If none exists, create a new group of size 2 (master + one follower) using the base screen's current file/playlist first item.
      - Auto-create the follower screen if absent (sequential numeric: screen2, screen3 ...).
    Returns: { success, group_id, new_screen, members, count }
    """
    try:
        data = request.get_json(force=True) or {}
        store_id = str(data.get('store_id') or '').strip()
        base_screen_id = str(data.get('base_screen_id') or '').strip()
        if not store_id or not base_screen_id:
            return jsonify({'success': False, 'error': 'store_id and base_screen_id required'}), 400
        ukey = _safe_user_key()
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
        screens_map = (cfg.get('screens') or {}).get(store_id)
        if not isinstance(screens_map, dict):
            return jsonify({'success': False, 'error': 'store not found'}), 404
        # Normalize base id (accept short form screen1)
        if base_screen_id not in screens_map:
            cand = f"{store_id}_{base_screen_id}"
            if cand in screens_map:
                base_screen_id = cand
        base_scr = screens_map.get(base_screen_id)
        if not isinstance(base_scr, dict):
            return jsonify({'success': False, 'error': 'base screen not found'}), 404
        # Determine media file from base screen (file or first playlist item)
        media_file = base_scr.get('file')
        if not media_file:
            try:
                plb = base_scr.get('playlist') or []
                if plb:
                    media_file = plb[0].get('file')
            except Exception:
                pass
        if not media_file:
            return jsonify({'success': False, 'error': 'base screen has no media; assign a video first'}), 400
        groups = cfg.get('sync_groups') or {}
        # Locate existing group that uses this base
        group_id = None
        grp = None
        for gid, g in groups.items():
            if g.get('store_id') == store_id and g.get('base') == base_screen_id:
                group_id = gid; grp = g; break
        import uuid as _uuid, time as _time, re
        import re as _re
        m = _re.match(r'^(.*?)(\d+)$', base_screen_id)
        if not grp:
            # Create new group with count=2
            if not m:
                return jsonify({'success': False, 'error': 'base id not numeric-suffixed; cannot auto create group'}), 400
            prefix, num = m.group(1), int(m.group(2))
            group_id = str(_uuid.uuid4())
            members = []
            # Ensure playlist + master item
            pl = base_scr.setdefault('playlist', [])
            master_item = None
            for it in pl:
                if it.get('file') == media_file:
                    master_item = it; break
            if not master_item:
                master_item = {
                    'id': str(_uuid.uuid4()), 'file': media_file, 'enabled': True, 'start': None, 'end': None,
                    'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(media_file)
                }
                pl.append(master_item)
            master_item['sync_ref'] = {'group': group_id, 'role': 'master', 'order': 0}
            members.append({'screen_id': base_screen_id, 'item_id': master_item['id'], 'role': 'master', 'order': 0})
            # Create follower screen id
            follower_sid = f"{prefix}{num+1}"
            follower_scr = screens_map.get(follower_sid)
            if not follower_scr:
                short = follower_sid.split('_',1)[1] if '_' in follower_sid else follower_sid
                is_promo = short.startswith('promo')
                follower_scr = {
                    'file': None, 'vertical': True if is_promo else False, 'horizontal': False if is_promo else True,
                    'rotation': 0, 'protected': False
                }
                screens_map[follower_sid] = follower_scr
            fpl = follower_scr.setdefault('playlist', [])
            f_item = {
                'id': str(_uuid.uuid4()), 'file': media_file, 'enabled': True, 'start': None, 'end': None,
                'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(media_file)
            }
            f_item['sync_ref'] = {'group': group_id, 'role': 'follower', 'order': 1}
            fpl.append(f_item)
            follower_scr['file'] = media_file
            members.append({'screen_id': follower_sid, 'item_id': f_item['id'], 'role': 'follower', 'order': 1})
            now = int(_time.time())
            start_epoch = ((now // 5) + 2) * 5
            cfg.setdefault('sync_groups', {})[group_id] = {
                'store_id': store_id, 'base': base_screen_id, 'count': 2, 'filename': media_file,
                'members': members, 'created_at': now, 'start_epoch': start_epoch, 'mode': 'split-h'
            }
            _enqueue_command_in_cfg(cfg, store_id, base_screen_id, 'reload')
            _enqueue_command_in_cfg(cfg, store_id, follower_sid, 'reload')
            if ukey:
                save_store_config_for_user_safe_key(ukey, cfg)
            else:
                save_store_config(cfg)
            return jsonify({'success': True, 'group_id': group_id, 'new_screen': follower_sid, 'members': members, 'count': 2, 'created': True, 'filename': media_file})
        # Expand existing group
        members = grp.get('members') or []
        cur_count = len(members)
        if cur_count >= 5:
            return jsonify({'success': False, 'error': 'max 5 screens reached', 'count': cur_count}), 400
        if not m:
            return jsonify({'success': False, 'error': 'base id not numeric-suffixed; cannot expand'}, 400)
        prefix, num = m.group(1), int(m.group(2))
        new_order = cur_count
        follower_sid = f"{prefix}{num + new_order - 0}"  # order 0 is master, so order==cur_count -> suffix num+cur_count
        if follower_sid in [m['screen_id'] for m in members]:
            # Find next unused numeric id
            k = num + 1
            while True:
                candidate = f"{prefix}{k}"
                if candidate not in [m['screen_id'] for m in members]:
                    follower_sid = candidate
                    break
                k += 1
        follower_scr = screens_map.get(follower_sid)
        if not follower_scr:
            short = follower_sid.split('_',1)[1] if '_' in follower_sid else follower_sid
            is_promo = short.startswith('promo')
            follower_scr = {
                'file': None, 'vertical': True if is_promo else False, 'horizontal': False if is_promo else True,
                'rotation': 0, 'protected': False
            }
            screens_map[follower_sid] = follower_scr
        fpl = follower_scr.setdefault('playlist', [])
        import uuid as _uuid2
        f_item = {
            'id': str(_uuid2.uuid4()), 'file': media_file, 'enabled': True, 'start': None, 'end': None,
            'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(media_file)
        }
        f_item['sync_ref'] = {'group': group_id, 'role': 'follower', 'order': new_order}
        fpl.append(f_item)
        follower_scr['file'] = media_file
        members.append({'screen_id': follower_sid, 'item_id': f_item['id'], 'role': 'follower', 'order': new_order})
        grp['members'] = members
        grp['count'] = len(members)
        _enqueue_command_in_cfg(cfg, store_id, follower_sid, 'reload')
        if ukey:
            save_store_config_for_user_safe_key(ukey, cfg)
        else:
            save_store_config(cfg)
        return jsonify({'success': True, 'group_id': group_id, 'new_screen': follower_sid, 'members': members, 'count': grp['count'], 'created': False, 'filename': media_file})
    except Exception as e:
        app.logger.exception('add_sync_follower failed')
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))  # Use 5002 since 5000 seems blocked
    print(f"DEBUG: Starting Flask on port {port}", flush=True)
    logging.debug('Attempting to start Flask development server on port %s', port)
    try:
        app.run(debug=True, host='0.0.0.0', port=port)
    except Exception as e:
        logging.exception('Flask failed to start: %s', e)
        # Ensure a non-zero exit so supervising systems notice
        raise
