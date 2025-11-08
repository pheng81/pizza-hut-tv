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
# Import fcntl only on Unix/Linux (not available on Windows)
try:
    import fcntl  # For file locking to prevent race conditions
except ImportError:
    fcntl = None  # Windows doesn't have fcntl
import random
import subprocess
import shutil
import smtplib
import ssl
import threading
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
import functools
from datetime import datetime, time as dtime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, send_file, make_response, session, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv, dotenv_values
from flask_socketio import SocketIO, emit, join_room, leave_room

# Ensure both names available for existing code
_shutil = shutil

# Base directory for all file operations (prevents relative path issues with gunicorn workers)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    # Ensure name exists so later references do not raise NameError when boto3 missing
    BotoConfig = None

# Global in-memory cache for library listings
_LIB_CACHE: dict = {}

# Global job tracking for async operations (auto-slicing, etc.)
# Using filesystem for cross-worker job status sharing
JOBS_DIR = os.path.join(tempfile.gettempdir(), 'pizza_hut_tv_jobs')
os.makedirs(JOBS_DIR, exist_ok=True)

def _get_job_status(job_id):
    """Get job status from filesystem (works across gunicorn workers)."""
    job_file = os.path.join(JOBS_DIR, f'{job_id}.json')
    try:
        if os.path.exists(job_file):
            with open(job_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[get_job_status] Error reading {job_id}: {e}")
    return None

def _set_job_status(job_id, status_data):
    """Set job status to filesystem (works across gunicorn workers)."""
    job_file = os.path.join(JOBS_DIR, f'{job_id}.json')
    try:
        with open(job_file, 'w') as f:
            json.dump(status_data, f)
    except Exception as e:
        print(f"[set_job_status] Error writing {job_id}: {e}")

# --- SQLite user database helpers ---
def _db_path() -> str:
    # Allow relocating the DB out of the repo so deploys don't overwrite it
    p = os.environ.get('USERS_DB_PATH') or os.path.join(BASE_DIR, 'database.db')
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
        # Super-admin visible flags
        if 'is_blocked' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0')
            except Exception:
                pass
        if 'role' not in cols:
            try:
                db.execute('ALTER TABLE users ADD COLUMN role TEXT')
            except Exception:
                pass
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

    # Dedicated superadmin table (separate from regular users)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS superadmins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)')
        db.commit()
    except Exception:
        pass

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
# Use a strong, consistent secret key for session signing
app.secret_key = os.environ.get('SECRET_KEY') or 'pizza-hut-tv-oauth-session-key-2025-production'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Initialize Socket.IO for WebSocket relay (TeamViewer-style)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=120,
    ping_interval=30,
    logger=True,
    engineio_logger=True
)

# Track connected Pis via WebSocket
connected_pis = {}  # { 'pi_id': {'sid': socket_id, 'connected_at': timestamp, 'ip': ip_address} }
pi_connection_lock = threading.Lock()

# Track connected Android TV devices via heartbeat
# Key = device_id (session_id or unique identifier)
# Value = {'store_id': str, 'screen_id': str, 'last_seen': timestamp, 'ip': str}
connected_android_tvs = {}
android_tv_lock = threading.Lock()

# Session configuration - make sessions last 30 days
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Honor X-Forwarded-* from Cloudflare/NGINX and prefer HTTPS for URL generation
# Safe for local dev; only affects how Flask infers scheme/host/port
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Cookie settings: Allow override for local development
cookie_secure = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
cookie_samesite = os.environ.get('SESSION_COOKIE_SAMESITE', 'None')
cookie_domain = os.environ.get('SESSION_COOKIE_DOMAIN', '.everydayadvertise.com') if os.environ.get('SESSION_COOKIE_DOMAIN') != '' else None

app.config.update(
    PREFERRED_URL_SCHEME='https',
    SESSION_COOKIE_SECURE=cookie_secure,  # Allow HTTP for local dev
    SESSION_COOKIE_SAMESITE=cookie_samesite,  # 'None' for production, 'Lax' for local
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_DOMAIN=cookie_domain,  # None for local dev, domain for production
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
                session.permanent = True  # Make session persist across browser restarts
                nxt = request.args.get('next')
                if not nxt:
                    # Use consistent domain for the dashboard after login
                    try:
                        host = request.host or ''
                        if host.startswith('api.') and 'everydayadvertise.com' in host:
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
                'SELECT username, password_hash, COALESCE(is_blocked, 0) AS is_blocked FROM users WHERE username = ?',
                (u,)
            ).fetchone()
            if row and check_password_hash(row['password_hash'], p or ''):
                # Blocked users cannot login
                try:
                    if int(row['is_blocked'] or 0) == 1:
                        raise RuntimeError('Account is blocked')
                except Exception:
                    pass
                session['user'] = {'name': row['username'], 'method': 'local'}
                session.permanent = True  # Make session persist across browser restarts
                # Ensure this user has a pairing code
                try:
                    _ensure_user_link_code(row['username'])
                except Exception:
                    pass
                nxt = request.args.get('next')
                if not nxt:
                    try:
                        host = request.host or ''
                        if host.startswith('api.') and 'everydayadvertise.com' in host:
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
            return redirect('https://api.everydayadvertise.com/')
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
        # Add page version for animated logo
        page_version = '3.0'
    except Exception:
        asset_bust = 0
        page_version = '3.0'
    resp = make_response(render_template('home.html', build_stamp=BUILD_STAMP, git_commit=GIT_COMMIT, asset_bust=asset_bust, page_version=page_version))
    try:
        # Force no-cache to show logo animation immediately
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        # Add ETag based on current time to force fresh loads
        import hashlib
        etag = hashlib.md5(str(int(_t.time())).encode()).hexdigest()
        resp.headers['ETag'] = etag
    except Exception:
        pass
    return resp

@app.route('/pair')
def pair():
    """Mobile pairing page for Android TV - scan QR code to enter pairing code"""
    code = request.args.get('code', '')
    return render_template('pair.html', code=code)

@app.route('/video-test')
def video_test():
    """Test page to verify all videos are loading and playing correctly"""
    return render_template('video_test.html')

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
            # Fallback to proper domain instead of IP
            redirect_uri = 'https://api.everydayadvertise.com/auth/google/callback'

        # CRITICAL: Clean up old OAuth state tokens before starting new flow
        # This prevents state mismatch from accumulated stale states
        keys_to_remove = [k for k in session.keys() if k.startswith('_state_google_')]
        for key in keys_to_remove:
            session.pop(key, None)
        logging.info(f'Cleaned up {len(keys_to_remove)} old OAuth state tokens')

        # Force session to be permanent for OAuth persistence
        session.permanent = True
        
        # Log session cookie and keys for debugging
        import uuid
        session_id = request.cookies.get('session') or request.cookies.get('sessionid') or 'NO_SESSION_COOKIE'
        logging.info(f'Google OAuth INIT: Session cookie: {session_id[:50]}...')
        logging.info(f'Google OAuth INIT: Session domain: {app.config.get("SESSION_COOKIE_DOMAIN")}')
        logging.info(f'Google OAuth INIT: Session secure: {app.config.get("SESSION_COOKIE_SECURE")}') 
        logging.info(f'Google OAuth INIT: Session samesite: {app.config.get("SESSION_COOKIE_SAMESITE")}')
        logging.info(f'Google OAuth INIT: Session keys before redirect: {list(session.keys())}')
        logging.info(f'Google OAuth INIT: Redirect URI: {redirect_uri}')

        return client.authorize_redirect(redirect_uri)
    except Exception as e:
        logging.warning('Google auth init failed: %s', e)
        flash('Google Sign-In not available', 'error')
        return redirect(url_for('login'))

@app.route('/auth/google/callback')
def auth_google_callback():
    logging.info('=== Google OAuth Callback Started ===')
    logging.info(f'Request args: {request.args}')
    session_id = request.cookies.get('session') or request.cookies.get('sessionid') or 'NO_SESSION_COOKIE'
    logging.info(f'Google OAuth Callback: Session cookie value: {session_id}')
    logging.info(f'Session keys before auth: {list(session.keys())}')
    logging.info(f'Request state: {request.args.get("state")}')
    
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
            logging.error('✗ Google client not available in callback')
            flash('Google Sign-In not configured', 'error')
            return redirect(url_for('login'))
    except Exception as _e:
        logging.error(f'✗ Google client prep failed in callback: {_e}')
        flash('Google Sign-In not configured', 'error')
        return redirect(url_for('login'))
    
    try:
        token = client.authorize_access_token()
        logging.info(f'✓ Google OAuth token received successfully')
        
        userinfo = token.get('userinfo') or {}
        # Some providers put userinfo under separate call; fallback
        if not userinfo:
            resp = client.get('userinfo')
            userinfo = resp.json() if resp else {}
        
        email = userinfo.get('email')
        logging.info(f'✓ Google userinfo received: email={email}, name={userinfo.get("name")}')
        
        if not email:
            logging.error('✗ Google login failed: no email in userinfo')
            flash('Google login failed: no email scope', 'error')
            return redirect(url_for('login'))
        
        # Optional domain restriction
        allowed_domain = os.environ.get('GOOGLE_ALLOWED_DOMAIN')
        if allowed_domain and not str(email).lower().endswith('@'+allowed_domain.lower()):
            logging.warning(f'✗ Email domain not allowed: {email}')
            flash('Email domain not allowed', 'error')
            return redirect(url_for('login'))
        
        session['user'] = {'name': userinfo.get('name') or email, 'email': email, 'method': 'google'}
        session.permanent = True  # Make session persist across browser restarts
        logging.info(f'✓ Google OAuth: Session set successfully for {email}, permanent={session.permanent}')
        logging.info(f'✓ Session keys after auth: {list(session.keys())}')
        
        # Upsert a local user record so we can store a pairing code
        try:
            db = get_db()
            uname = (email or '').strip().lower()
            if uname:
                try:
                    # Check if user exists
                    existing = db.execute('SELECT username FROM users WHERE username = ?', (uname,)).fetchone()
                    
                    if existing:
                        # User exists - update full_name and email_verified
                        logging.info(f'OAuth: User {uname} exists, updating info')
                        db.execute(
                            'UPDATE users SET full_name = ?, email_verified = 1 WHERE username = ?',
                            (userinfo.get('name') or uname, uname)
                        )
                    else:
                        # New user - insert
                        logging.info(f'OAuth: Creating new user {uname}')
                        db.execute(
                            'INSERT INTO users (username, full_name, email_verified) VALUES (?, ?, 1)',
                            (uname, userinfo.get('name') or uname)
                        )
                    
                    db.commit()
                    logging.info(f'✓ OAuth: User {uname} saved successfully')
                    _ensure_user_link_code(uname)
                    
                except Exception as e:
                    logging.error(f'✗ OAuth: Failed to save user {uname}: {e}')
                    db.rollback()
                    # Don't fail the login - user can still use the system
                    
        except Exception as e:
            logging.error(f'✗ OAuth: User creation failed completely: {e}')
        nxt = request.args.get('next')
        if not nxt:
            try:
                host = request.host or ''
                if host.startswith('api.') and 'everydayadvertise.com' in host:
                    return redirect('https://api.everydayadvertise.com/dashboard')
            except Exception:
                pass
            nxt = url_for('dashboard')
        
        logging.info(f'✓ Google OAuth login complete, redirecting to: {nxt}')
        return redirect(nxt)
        
    except Exception as e:
        logging.error(f'✗ Google OAuth callback failed: {e}')
        logging.error(f'✗ Error type: {type(e).__name__}')
        logging.exception('✗ Full traceback:')
        
        # Check for specific error types
        error_msg = str(e).lower()
        if 'state' in error_msg or 'csrf' in error_msg or 'mismatch' in error_msg:
            logging.error('✗ State mismatch detected - session cookie may not be preserved during OAuth redirect')
            flash('Login session expired during authentication. Please try again.', 'error')
        elif 'token' in error_msg:
            logging.error('✗ Token exchange failed')
            flash('Failed to obtain login token from Google. Please try again.', 'error')
        else:
            flash('Google login failed. Please try again.', 'error')
        
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
        session.permanent = True  # Make session persist across browser restarts
        
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
                if host.startswith('api.') and 'everydayadvertise.com' in host:
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
        session.permanent = True  # Make session persist across browser restarts
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
                if host.startswith('api.') and 'everydayadvertise.com' in host:
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
        elif p.startswith('/static/'):
            # Static assets (JS, CSS, images)
            resp.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
        else:
            # HTML pages - no cache
            resp.headers.setdefault('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        
        # Remove deprecated headers to clean up browser warnings
        resp.headers.pop('X-Frame-Options', None)  # Use CSP frame-ancestors instead
        resp.headers.pop('P3P', None)  # Deprecated, IE-only header
        resp.headers.pop('Pragma', None)  # Deprecated, use Cache-Control
        resp.headers.pop('Expires', None)  # Use Cache-Control instead
        resp.headers.pop('X-XSS-Protection', None)  # Deprecated, browser-specific
        
        # Remove any CSP headers that might be blocking (let browser defaults handle it)
        # We don't need CSP for this app - it causes more issues than it solves
        resp.headers.pop('Content-Security-Policy', None)
        resp.headers.pop('content-security-policy', None)
        
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

# ---- Local <-> R2 media repair helpers ----
def r2_download_to_local(key: str) -> bool:
    """Best-effort restore: download object from R2 into local UPLOAD_FOLDER.
    Returns True if file now exists locally.
    """
    try:
        if not r2_enabled():
            return False
        s3 = get_s3_client()
        if not s3:
            return False
        # Normalize key (no leading slash)
        key_norm = key.lstrip('/')
        dest = os.path.join(app.config['UPLOAD_FOLDER'], key_norm).replace('\\', '/')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # Skip if already present
        if os.path.exists(dest):
            return True
        with open(dest, 'wb') as fh:
            s3.download_fileobj(os.environ['R2_BUCKET_NAME'], key_norm, fh)
        logging.info('[R2-RESTORE] Restored %s', key_norm)
        return True
    except Exception as e:
        try:
            logging.warning('[R2-RESTORE] Failed %s: %s', key, e)
        except Exception:
            pass
        return False

def ensure_local_media_for_playlist_item(item: dict):
    """If playlist item references a media file under user namespace and it's missing locally,
    attempt to restore from R2.
    """
    try:
        if not item:
            return
        f = item.get('file') or ''
        if not f or f.startswith('http://') or f.startswith('https://'):
            return
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], f)
        if os.path.exists(local_path):
            return
        # Only attempt restore if appears to be our managed user path (users/ or public/ etc.)
        if r2_enabled() and ('/' in f):
            r2_download_to_local(f)
    except Exception:
        pass

# Lightweight background thread to periodically scan recent user month folders
_r2_repair_thread_started = False
def _r2_repair_worker():
    while True:
        try:
            if not r2_enabled():
                time.sleep(30)
                continue
            root = app.config.get('UPLOAD_FOLDER') or 'static/uploads'
            # Scan only deepest recent folders (pattern users/*/<YYYY-MM>) to limit I/O
            now = datetime.utcnow()
            recent_tags = {now.strftime('%Y-%m'), (now - timedelta(days=31)).strftime('%Y-%m')}
            users_dir = os.path.join(root, 'users')
            if os.path.isdir(users_dir):
                for user_id in os.listdir(users_dir):
                    udir = os.path.join(users_dir, user_id)
                    if not os.path.isdir(udir):
                        continue
                    for tag in recent_tags:
                        tdir = os.path.join(udir, tag)
                        if not os.path.isdir(tdir):
                            continue
                        # For each file, nothing to do (local present). We cannot know if R2 copy missing here without listing bucket (expensive) – skip.
                        # (Future: maintain manifest / hash list.)
                        pass
            time.sleep(120)
        except Exception:
            time.sleep(30)

def start_r2_repair_thread():
    global _r2_repair_thread_started
    if _r2_repair_thread_started:
        return
    try:
        th = threading.Thread(target=_r2_repair_worker, name='r2-repair', daemon=True)
        th.start()
        _r2_repair_thread_started = True
    except Exception as e:
        logging.warning('Failed to start r2 repair thread: %s', e)

# Kick off background thread at import time (safe / idempotent)
start_r2_repair_thread()

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

@app.route('/api/server_time', methods=['GET'])
def server_time():
    """Return precise server time in milliseconds for client synchronization"""
    import time
    server_time_ms = time.time() * 1000
    return jsonify({
        'server_time_ms': server_time_ms,
        'server_time_seconds': time.time(),
        'iso_time': datetime.now(timezone.utc).isoformat(),
        'timestamp': int(time.time())
    })

@app.route('/api/sync-time', methods=['GET'])
def sync_time():
    """Return synchronized timestamp for global screen synchronization"""
    import time
    # All screens sync to aligned 2-second intervals
    current_time = time.time() * 1000  # milliseconds
    sync_interval = 2000  # 2 seconds in ms
    next_sync = math.ceil(current_time / sync_interval) * sync_interval
    
    return jsonify({
        'timestamp': int(next_sync),
        'current_time': int(current_time),
        'sync_interval': sync_interval,
        'delay_ms': int(next_sync - current_time)
    })

# Global store for effect synchronization
global_effects = {}

@app.route('/api/sync-effect', methods=['POST'])
def sync_effect():
    """Sync transition effects across all screens for a store"""
    try:
        data = request.get_json()
        store_code = data.get('store_code')
        effect_id = data.get('effect_id')
        effect_name = data.get('effect_name')
        enabled_val = data.get('enabled')
        timestamp = data.get('timestamp', time.time())
        
        if not store_code:
            return jsonify({'error': 'Missing store_code'}), 400
        # Allow updates that only toggle master enabled without effect change
        if not effect_id and enabled_val is None:
            return jsonify({'error': 'Nothing to update (need effect_id/effect_name or enabled)'}), 400
        
        # Store effect globally for all screens in this store
        prev = global_effects.get(store_code, {})
        # Parse enabled flag if provided
        def _to_bool(v, default=None):
            if v is None:
                return default
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            if isinstance(v, str):
                return v.strip().lower() in ('1','true','on','enabled','yes')
            return default
        enabled_flag = _to_bool(enabled_val, prev.get('enabled', True))
        global_effects[store_code] = {
            'effect_id': effect_id or prev.get('effect_id') or '1',
            'effect_name': effect_name or prev.get('effect_name') or 'fade',
            'enabled': enabled_flag,
            'timestamp': timestamp,
            'updated_at': time.time()
        }
        
        print(f"🎨 Effect synced for store {store_code}: {effect_name} (#{effect_id})")
        
        return jsonify({
            'success': True,
            'store_code': store_code,
            'effect_id': effect_id,
            'effect_name': effect_name or prev.get('effect_name') or 'fade',
            'enabled': enabled_flag,
            'synced_at': time.time()
        })
        
    except Exception as e:
        print(f"❌ Effect sync error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-effect/<store_code>', methods=['GET'])
def get_effect(store_code):
    """Get current effect setting for a store"""
    try:
        effect_data = global_effects.get(store_code)
        if not effect_data:
            effect_data = {
                'effect_id': '1',
                'effect_name': 'fade',
                'enabled': True,
                'timestamp': time.time(),
                'updated_at': time.time()
            }
            global_effects[store_code] = effect_data
        
        return jsonify(effect_data)
        
    except Exception as e:
        print(f"❌ Get effect error: {e}")
        return jsonify({'error': str(e)}), 500

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
    
    # SECURITY FIX: Use helper to get effective user (session takes priority over pair code)
    user_key = _resolve_effective_user_key()
    if not user_key:
        return jsonify({'success': False, 'error': 'pair code required'}), 403
    
    cfg = load_store_config_for_user_safe_key(user_key)
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
    current_timestamp = int(time.time())
    store_screens[screen_id]['last_seen'] = current_timestamp
    logging.debug('HB set last_seen for %s/%s', store_id, screen_id)
    
    # Track Android TV device in connected_android_tvs for real-time status
    device_id = data.get('device_id')  # Android TV should send unique device_id
    if not device_id:
        # Fallback: use session_id or generate from store+screen
        device_id = data.get('session_id') or f"{store_id}_{screen_id}"
    
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in str(client_ip):
        client_ip = client_ip.split(',')[0].strip()
    
    with android_tv_lock:
        connected_android_tvs[device_id] = {
            'store_id': store_id,
            'screen_id': screen_id,
            'last_seen': current_timestamp,
            'ip': client_ip,
            'user_key': user_key
        }
    
    logging.info(f'[Android TV] Heartbeat from device {device_id}: {store_id}/{screen_id} @ {client_ip}')
    
    if user_key:
        save_store_config_for_user_safe_key(user_key, cfg)
    else:
        save_store_config(cfg)
    return jsonify({'success': True})

# -------- Public API for TV app: list screens for a store (pair-code or session required) --------
@app.route('/api/screens/<store_id>', methods=['GET'])
def api_screens_for_store(store_id: str):
    """Return list of screens for a store for Android TV app.
    Auth: session user (dashboard) OR X-User-Code pairing header / user_code query param.
    Response shape matches Android app expectation: { success, store_id, screens: [{id: "..."}] }
    """
    try:
        # Prefer logged-in session user; otherwise accept pair code header
        ukey = _resolve_effective_user_key()
        if not ukey:
            return jsonify({'success': False, 'error': 'pair code required'}), 403

        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey))
        screens_all = cfg.get('screens') or {}

        # Legacy mapping: if old store_id like '1881' no longer exists, map to current master store
        try:
            if store_id not in screens_all and str(store_id) == '1881':
                m = cfg.get('master_store_id')
                if m and m in screens_all:
                    store_id = m
        except Exception:
            pass

        store_map = screens_all.get(store_id)
        if not isinstance(store_map, dict):
            return jsonify({'success': False, 'error': 'store not found'}), 404

        # Build simple list of screen ids; keep existing keys as-is
        # Include rotation value for each screen so Android TV app can apply orientation
        screen_list = []
        for sid in sorted(store_map.keys()):
            screen_data = store_map.get(sid, {})
            rotation = screen_data.get('rotation', 0) if isinstance(screen_data, dict) else 0
            screen_list.append({'id': sid, 'rotation': rotation})
        return jsonify({'success': True, 'store_id': store_id, 'screens': screen_list})
    except Exception as e:
        app.logger.exception('api_screens_for_store failed')
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/api/configure_remote_pi', methods=['POST'])
@login_required
def configure_remote_pi():
    """
    Configure a remote Raspberry Pi with pairing code, store ID, and screen ID.
    This creates a configuration command that the Pi will fetch and apply.
    """
    try:
        data = request.get_json()
        pi_id = data.get('pi_id', '').strip()
        pair_code = data.get('pair_code', '').strip()
        store_id = data.get('store_id', '').strip()
        screen_id = data.get('screen_id', '').strip()
        auto_start = data.get('auto_start', True)

        if not all([pi_id, pair_code, store_id, screen_id]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: pi_id, pair_code, store_id, screen_id'
            }), 400

        # Validate pair code format (4 digits)
        if not pair_code.isdigit() or len(pair_code) != 4:
            return jsonify({
                'success': False,
                'message': 'Pair code must be a 4-digit number'
            }), 400

        # Load current user's config to validate store exists
        cfg = ensure_playlists_structure(load_store_config())
        
        # Verify store exists
        store_exists = any(str(s.get('id')) == str(store_id) for s in cfg.get('stores', []))
        if not store_exists:
            return jsonify({
                'success': False,
                'message': f'Store ID {store_id} not found in your configuration'
            }), 404

        # Create configuration command for the Pi
        # Store this in a dedicated pi_configurations collection or commands queue
        pi_config = {
            'pi_id': pi_id,
            'pair_code': pair_code,
            'store_id': store_id,
            'screen_id': screen_id,
            'auto_start': auto_start,
            'server_url': request.host_url.rstrip('/'),
            'configured_at': int(time.time()),
            'configured_by': session.get('user', {}).get('email', 'unknown')
        }

        # Store in user's config under pi_configurations
        if 'pi_configurations' not in cfg:
            cfg['pi_configurations'] = {}
        
        cfg['pi_configurations'][pi_id] = pi_config
        
        # IMPORTANT: Also update the screen's pi_id field so Pi Device Manager can display it
        if 'screens' not in cfg:
            cfg['screens'] = {}
        if store_id not in cfg['screens']:
            cfg['screens'][store_id] = {}
        if screen_id not in cfg['screens'][store_id]:
            cfg['screens'][store_id][screen_id] = {}
        
        # Set the pi_id on the screen so it shows up in Pi Device Manager
        cfg['screens'][store_id][screen_id]['pi_id'] = pi_id
        
        save_store_config(cfg)

        # Update pi_id_ip_map.json to show the assignment in Pi Device Manager
        try:
            import json
            pi_map_file = 'pi_id_ip_map.json'
            pi_map = {}
            try:
                with open(pi_map_file, 'r') as f:
                    pi_map = json.load(f)
            except Exception:
                pass
            
            # Get the IP address from connected_pis if available
            pi_ip = 'Unknown'
            if pi_id in connected_pis:
                pi_ip = connected_pis[pi_id].get('ip', 'Unknown')
            elif pi_id in pi_map:
                pi_ip = pi_map[pi_id]
            
            # Update the map
            pi_map[pi_id] = pi_ip
            
            with open(pi_map_file, 'w') as f:
                json.dump(pi_map, f, indent=2)
            
            print(f"✅ Updated pi_id_ip_map.json: {pi_id} -> {pi_ip}")
        except Exception as e:
            print(f"⚠️ Failed to update pi_id_ip_map.json: {e}")

        # Also enqueue a configuration command to the screen's command queue
        # so if the Pi is already running, it can pick up the new config
        _enqueue_command_in_cfg(
            cfg,
            store_id,
            screen_id,
            ctype='configure',
            item_id=pi_id,
            file=None
        )
        save_store_config(cfg)

        return jsonify({
            'success': True,
            'message': f'Pi {pi_id} configured successfully',
            'config': {
                'pi_id': pi_id,
                'store_id': store_id,
                'screen_id': screen_id,
                'pair_code': pair_code
            }
        })

    except Exception as e:
        print(f"ERROR in configure_remote_pi: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/get_pi_config/<pi_id>', methods=['GET'])
def get_pi_config(pi_id):
    """
    Allow a Pi to fetch its configuration using its Pi ID.
    This can be called during Pi setup/boot to auto-configure.
    """
    try:
        # Check for authorization via pair code or user code
        header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
        user_key = _resolve_user_key_by_code(header_code)
        
        if not user_key:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 403

        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(user_key))
        
        # Look up Pi configuration
        pi_configs = cfg.get('pi_configurations', {})
        pi_config = pi_configs.get(pi_id)
        
        if not pi_config:
            return jsonify({
                'success': False,
                'error': f'No configuration found for Pi ID: {pi_id}'
            }), 404

        return jsonify({
            'success': True,
            'config': pi_config
        })

    except Exception as e:
        print(f"ERROR in get_pi_config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
    # SECURITY FIX: Use helper to get effective user (session takes priority over pair code)
    user_key = _resolve_effective_user_key()
    if not user_key:
        return {'success': False, 'error': 'pair code required'}, 403
    
    cfg = load_store_config_for_user_safe_key(user_key)
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
    # SECURITY FIX: Use helper to get effective user (session takes priority over pair code)
    user_key = _resolve_effective_user_key()
    if not user_key:
        return {'success': False, 'error': 'pair code required'}, 403
    
    cfg = load_store_config_for_user_safe_key(user_key)
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
CONFIG_FILE = os.path.join(BASE_DIR, 'store_config.json')
PI_MAP_FILE = os.path.join(BASE_DIR, 'pi_id_ip_map.json')

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

def _resolve_effective_user_key() -> Optional[str]:
    """SECURITY: Resolve the effective user key for API requests.
    
    CRITICAL RULE: Always prioritize the logged-in session user over pair code headers.
    This prevents cross-user data leakage when an authenticated dashboard user enters
    another user's pairing code.
    
    Priority order:
    1. Session user (from logged-in dashboard) - HIGHEST PRIORITY
    2. Pair code from header/query (from TV devices without session)
    3. None (unauthenticated request)
    
    Returns:
        str: User key for config lookup
        None: No authenticated user found
    """
    # FIRST: Check if user is logged into dashboard
    session_key = _safe_user_key()
    if session_key:
        return session_key
    
    # SECOND: Check for pair code from TV device
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    if header_code:
        return _resolve_user_key_by_code(header_code)
    
    # No authentication found
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

# Cache folders for video slicing
SLICE_CACHE_FOLDER = os.path.join('static', 'cache', 'slices')
TEMP_CACHE_FOLDER = os.path.join('static', 'cache', 'temp')
os.makedirs(SLICE_CACHE_FOLDER, exist_ok=True)
os.makedirs(TEMP_CACHE_FOLDER, exist_ok=True)

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
# Increased size limit for large multi-screen videos (1GB)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

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
@app.route('/sync/slice_and_create', methods=['POST'])
def slice_and_create():
    """
    Physically slice a video for multi-screen sync and update playlists.
    Expects JSON: {
        'video_path': str,
        'store_id': str,
        'screen_ids': [str],
        'slice_params': { ... }
    }
    """
    try:
        data = request.get_json()
        video_path = data.get('video_path')
        store_id = data.get('store_id')
        screen_ids = data.get('screen_ids')
        slice_params = data.get('slice_params', {})
        if not video_path or not store_id or not screen_ids:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        # Ensure video exists
        if not os.path.isfile(video_path):
            return jsonify({'success': False, 'error': f'Video not found: {video_path}'}), 404

        # Example: slice video into N segments (1 per screen)
        # This demo uses ffmpeg to slice by time; customize as needed
        slice_dir = os.path.join(SLICE_CACHE_FOLDER, f'{store_id}_{uuid.uuid4().hex}')
        os.makedirs(slice_dir, exist_ok=True)
        duration = slice_params.get('duration')
        num_screens = len(screen_ids)
        # Get video duration if not provided
        if not duration:
            try:
                import subprocess
                result = subprocess.run([
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', video_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                duration = float(result.stdout.strip())
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to get video duration: {e}'}), 500

        segment_length = duration / num_screens
        slice_files = []
        for idx, screen_id in enumerate(screen_ids):
            start = idx * segment_length
            out_file = os.path.join(slice_dir, f'slice_{screen_id}.mp4')
            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-ss', str(start), '-t', str(segment_length),
                '-c', 'copy', out_file
            ]
            try:
                subprocess.run(cmd, check=True)
                slice_files.append({'screen_id': screen_id, 'file': out_file})
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to slice for screen {screen_id}: {e}'}), 500

        # Update playlist for each screen (demo: update config file)
        cfg = load_store_config()
        screens = cfg.get('screens', {}).get(store_id, {})
        for entry in slice_files:
            sid = entry['screen_id']
            file_path = entry['file']
            if sid in screens:
                screens[sid]['playlist'] = [file_path]
        save_store_config(cfg)

        return jsonify({'success': True, 'slices': slice_files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
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
        # If a CDN base is configured, redirect so clients (ExoPlayer) can fetch from R2/Cloudflare
        try:
            cdn = os.environ.get('MEDIA_BASE_URL')
            if isinstance(cdn, str) and (cdn.startswith('http://') or cdn.startswith('https://')):
                if not cdn.endswith('/'):
                    cdn = cdn + '/'
                target = cdn + filename
                logging.debug("/media redirecting missing file to CDN: %s -> %s", filename, target)
                # 302 is widely followed; client will reissue Range to the target
                return redirect(target, code=302)
        except Exception:
            pass
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
        # Fast metadata response; if file missing, prefer HEAD redirect to CDN
        if not os.path.exists(file_path):
            try:
                cdn = os.environ.get('MEDIA_BASE_URL')
                if isinstance(cdn, str) and (cdn.startswith('http://') or cdn.startswith('https://')):
                    if not cdn.endswith('/'):
                        cdn = cdn + '/'
                    target = cdn + filename
                    return redirect(target, code=302)
            except Exception:
                pass
            return jsonify({'error': 'not found'}), 404
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
                resp.headers['ETag'] = f"W/\"{file_size}-{int(mtime)}\""
            except Exception:
                pass
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
            # SAFETY: Backup existing playlist before any modifications
            existing_playlist = sdata.get('playlist')
            if existing_playlist and isinstance(existing_playlist, list) and len(existing_playlist) > 0:
                print(f"DEBUG: Found existing playlist for {store_id}/{sid} with {len(existing_playlist)} items")
            
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
                    print(f"DEBUG: Created new playlist for {store_id}/{sid} from file: {sdata['file']}")
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
            # NEW: Attempt R2 restore for missing local files referenced by playlist
            try:
                for _it in sdata.get('playlist', []) or []:
                    ensure_local_media_for_playlist_item(_it)
            except Exception:
                pass
                if 'rotation_meta' not in sdata:
                    sdata['rotation_meta'] = {'last_index': 0, 'last_ts': 0}
                    changed = True
    if changed:
        save_store_config(config)
    return config

# -------- Manual R2 media diagnostics & repair endpoints --------
@app.route('/r2/restore_one', methods=['POST'])
@login_required
def r2_restore_one():
    try:
        data = request.get_json(force=True) or {}
        key = (data.get('key') or '').strip().lstrip('/')
        if not key:
            return jsonify({'success': False, 'error': 'key required'}), 400
        ok = r2_download_to_local(key)
        return jsonify({'success': ok, 'key': key})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/r2/repair_user', methods=['POST'])
@login_required
def r2_repair_user():
    """Force a best-effort restore of missing local files for a given user safe key.
    Scans month folders current + previous month.
    Body: {"user_key": "kayson2_at_gmail.com"}
    """
    try:
        if not r2_enabled():
            return jsonify({'success': False, 'error': 'R2 not enabled'}), 400
        data = request.get_json(force=True) or {}
        user_key = (data.get('user_key') or '').strip()
        if not user_key:
            return jsonify({'success': False, 'error': 'user_key required'}), 400
        root = app.config.get('UPLOAD_FOLDER') or 'static/uploads'
        user_dir = os.path.join(root, 'users', user_key)
        if not os.path.isdir(user_dir):
            return jsonify({'success': False, 'error': 'user directory missing'}), 404
        now = datetime.utcnow()
        months = {now.strftime('%Y-%m'), (now - timedelta(days=31)).strftime('%Y-%m')}
        restored = []
        skipped = 0
        for m in months:
            mdir = os.path.join(user_dir, m)
            if not os.path.isdir(mdir):
                continue
            for fname in os.listdir(mdir):
                if fname.lower().endswith(('.mp4','.jpg','.jpeg','.png','.webp','.gif')):
                    # already exists, nothing
                    continue
            # We can't know missing keys unless we track manifest; skip.
        return jsonify({'success': True, 'note': 'Scan complete (no manifest yet)', 'restored': restored, 'skipped': skipped})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
        row = db.execute('SELECT username, COALESCE(is_blocked, 0) AS is_blocked FROM users WHERE link_code = ?', (code,)).fetchone()
        if not row:
            return None
        try:
            if int(row['is_blocked'] or 0) == 1:
                return None
        except Exception:
            pass
        uname = (row['username'] or '').strip().lower()
        return _safe_key_from_username(uname)
    except Exception:
        return None

# ---------------------- Super Admin auth & dashboard ----------------------
from functools import wraps as _wraps

def superadmin_required(view):
    @_wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('super_admin'):
            return redirect(url_for('superadmin_login', next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.route('/superadmin/login', methods=['GET','POST'])
def superadmin_login():
    if request.method == 'POST':
        u = (request.form.get('username') or '').strip().lower()
        p = request.form.get('password') or ''
        try:
            db = get_db()
            row = db.execute('SELECT username, password_hash FROM superadmins WHERE username = ?', (u,)).fetchone()
            if row and check_password_hash(row['password_hash'], p or ''):
                session['super_admin'] = {'name': row['username']}
                session.permanent = True
                nxt = request.args.get('next') or url_for('superadmin_dashboard')
                return redirect(nxt)
        except Exception as e:
            logging.warning('Superadmin login DB error: %s', e)
        # Fallback: env-based master credentials if table empty
        try:
            env_u = os.environ.get('SUPERADMIN_USERNAME')
            env_p = os.environ.get('SUPERADMIN_PASSWORD')
            if env_u and env_p and u == env_u and p == env_p:
                session['super_admin'] = {'name': env_u}
                session.permanent = True
                return redirect(url_for('superadmin_dashboard'))
        except Exception:
            pass
        flash('Invalid credentials', 'error')
    return render_template('superadmin/login.html')

@app.route('/superadmin/logout')
def superadmin_logout():
    session.pop('super_admin', None)
    return redirect(url_for('home'))

def _collect_user_metrics():
    """Return list of users with counts: stores, screens, online screens."""
    db = get_db()
    cur = db.execute('SELECT id, username, full_name, link_code, COALESCE(is_blocked,0) AS is_blocked, CASE WHEN password_hash IS NULL OR password_hash = '' THEN 0 ELSE 1 END AS has_password FROM users ORDER BY username')
    users = []
    now = int(time.time())
    for row in cur.fetchall() or []:
        uname = (row['username'] or '').strip().lower()
        safe = _safe_key_from_username(uname) or ''
        cfg = load_store_config_for_user_safe_key(safe) if safe else {'stores': [], 'screens': {}}
        stores = cfg.get('stores', []) or []
        screens_map = cfg.get('screens', {}) or {}
        screens_count = sum(len(s or {}) for s in screens_map.values())
        online = 0
        try:
            for sid_map in screens_map.values():
                for s in (sid_map or {}).values():
                    last = int(s.get('last_seen', 0) or 0)
                    if (now - last) < HEARTBEAT_TIMEOUT:
                        online += 1
        except Exception:
            pass
        users.append({
            'id': row['id'],
            'username': uname,
            'full_name': row['full_name'],
            'link_code': row['link_code'],
            'is_blocked': int(row['is_blocked'] or 0),
            'has_password': int(row['has_password'] or 0),
            'stores_count': len(stores),
            'screens_count': screens_count,
            'online_screens': online,
        })
    return users

@app.route('/superadmin')
@app.route('/superadmin/dashboard')
@superadmin_required
def superadmin_dashboard():
    users = _collect_user_metrics()
    totals = {
        'users': len(users),
        'stores': sum(u['stores_count'] for u in users),
        'screens': sum(u['screens_count'] for u in users),
        'online': sum(u['online_screens'] for u in users),
    }
    return render_template('superadmin/dashboard.html', users=users, totals=totals)

@app.route('/superadmin/users/create', methods=['POST'])
@superadmin_required
def superadmin_create_user():
    data = request.form
    email = (data.get('username') or '').strip().lower()
    full_name = (data.get('full_name') or '').strip()
    pwd = data.get('password') or ''
    if not email or not pwd:
        flash('Username and password required', 'error')
        return redirect(url_for('superadmin_dashboard'))
    try:
        db = get_db()
        db.execute('INSERT INTO users (username, password_hash, full_name, is_blocked) VALUES (?, ?, ?, 0)', (
            email, generate_password_hash(pwd), full_name
        ))
        db.commit()
        try:
            _ensure_user_link_code(email)
        except Exception:
            pass
        flash('User created', 'success')
    except sqlite3.IntegrityError:
        flash('Username already exists', 'error')
    except Exception as e:
        flash(f'Create failed: {e}', 'error')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/users/<int:user_id>/block', methods=['POST'])
@superadmin_required
def superadmin_block_user(user_id):
    db = get_db()
    db.execute('UPDATE users SET is_blocked = 1 WHERE id = ?', (user_id,))
    db.commit()
    flash('User blocked', 'success')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/users/<int:user_id>/unblock', methods=['POST'])
@superadmin_required
def superadmin_unblock_user(user_id):
    db = get_db()
    db.execute('UPDATE users SET is_blocked = 0 WHERE id = ?', (user_id,))
    db.commit()
    flash('User unblocked', 'success')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/users/<int:user_id>/password', methods=['POST'])
@superadmin_required
def superadmin_reset_password(user_id):
    pwd = request.form.get('password') or ''
    if len(pwd) < 6:
        flash('Password must be at least 6 characters', 'error')
        return redirect(url_for('superadmin_dashboard'))
    db = get_db()
    db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (generate_password_hash(pwd), user_id))
    db.commit()
    flash('Password updated', 'success')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/users/<int:user_id>/rename', methods=['POST'])
@superadmin_required
def superadmin_rename_user(user_id):
    email = (request.form.get('username') or '').strip().lower()
    full_name = (request.form.get('full_name') or '').strip()
    if not email:
        flash('Username required', 'error')
        return redirect(url_for('superadmin_dashboard'))
    try:
        db = get_db()
        # Fetch current username to rename config files if needed
        cur = db.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        old_email = (cur['username'] or '').strip().lower() if cur else None
        db.execute('UPDATE users SET username = ?, full_name = ? WHERE id = ?', (email, full_name, user_id))
        db.commit()
        # Move per-user config file
        try:
            old_safe = _safe_key_from_username(old_email)
            new_safe = _safe_key_from_username(email)
            if old_safe and new_safe and old_safe != new_safe:
                old_path = _config_path_for_user_safe_key(old_safe)
                new_path = _config_path_for_user_safe_key(new_safe)
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    os.replace(old_path, new_path)
        except Exception:
            pass
        flash('User updated', 'success')
    except sqlite3.IntegrityError:
        flash('Username already exists', 'error')
    except Exception as e:
        flash(f'Update failed: {e}', 'error')
    return redirect(url_for('superadmin_dashboard'))

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
    return os.path.join(BASE_DIR, f"store_config__{safe_key}.json")

def load_store_config_for_user_safe_key(safe_key: str):
    """Load another user's config by safe key (used for code-based listing).
    SECURITY: Each user starts with EMPTY config - NO cross-user data inheritance.
    """
    path = _config_path_for_user_safe_key(safe_key)
    lock_path = path + '.lock'
    
    if not os.path.exists(path):
        # SECURITY FIX: Each user starts with EMPTY config
        # DO NOT seed from global config - that contains OTHER users' stores/screens!
        logging.info(f'🔒 Creating new empty config for user: {safe_key}')
        cfg = get_default_config(user_scoped=True)
        
        # Ensure empty stores and screens
        cfg['stores'] = []
        cfg['screens'] = {}
        cfg['master_store_id'] = None
        
        logging.info(f'✓ New user {safe_key} starts with empty config (no cross-user data)')
        # Save to user-scoped file with locking
        save_store_config_for_user_safe_key(safe_key, cfg)
        return cfg
    
    # Acquire shared lock for reading
    try:
        lock_file = open(lock_path, 'w')
        if fcntl:  # Only use file locking on Unix/Linux
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
        
        try:
            with open(path, 'r') as f:
                cfg = json.load(f)
        except json.JSONDecodeError as e:
            # Only treat JSON decode errors as corruption
            logging.error(f'⚠️ Corrupt JSON in {path}: {e}')
            try:
                shutil.copyfile(path, path + f'.corrupt.{int(time.time())}')
            except Exception:
                pass
            cfg = get_default_config(user_scoped=True)
        finally:
            if fcntl:  # Only use file locking on Unix/Linux
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            try:
                os.remove(lock_path)
            except:
                pass
    except Exception as e:
        logging.error(f'Error loading config for {safe_key}: {e}')
        # If we can't even lock, try to load anyway
        try:
            with open(path, 'r') as f:
                cfg = json.load(f)
        except Exception:
            cfg = get_default_config(user_scoped=True)
    
    # backfill master_store_id
    if 'master_store_id' not in cfg and cfg.get('stores'):
        cfg['master_store_id'] = cfg['stores'][0]['id']
        save_store_config_for_user_safe_key(safe_key, cfg)
    return cfg

def save_store_config_for_user_safe_key(safe_key: str, config):
    """Save the given config to the per-user JSON path atomically with file locking."""
    path = _config_path_for_user_safe_key(safe_key)
    lock_path = path + '.lock'
    
    # Acquire exclusive lock
    try:
        lock_file = open(lock_path, 'w')
        if fcntl:  # Only use file locking on Unix/Linux
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        
        try:
            # Write to temp file with unique name to avoid collisions
            tmp = path + f'.tmp.{os.getpid()}.{threading.get_ident()}'
            with open(tmp, 'w') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
            print(f"Configuration atomically saved to {path}")
        finally:
            # Release lock
            if fcntl:  # Only use file locking on Unix/Linux
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            try:
                os.remove(lock_path)
            except:
                pass
    except Exception as e:
        print(f"Error saving per-user configuration: {e}")
        raise

@app.route('/api/stores_by_code/<code>', methods=['GET'])
@with_etag_json
def stores_by_code(code):
    """Return stores and screens for the user identified by a 4-digit code.
    Response: {success, user:{username}, stores:[{id,name}], screens:{store_id:{screen_id:{...}}}}
    """
    logging.info(f'🔑 /api/stores_by_code/{code} called')
    try:
        raw = (code or '').strip()
        if not (len(raw) == 4 and raw.isdigit()):
            logging.warning(f'❌ Invalid code format: {raw}')
            return {'success': False, 'error': 'invalid code'}, 400
        db = get_db()
        row = db.execute('SELECT username FROM users WHERE link_code = ?', (raw,)).fetchone()
        logging.info(f'🔍 Database lookup for code {raw}: {row}')
        if not row:
            logging.warning(f'❌ Code {raw} not found in database')
            return {'success': False, 'error': 'code not found'}, 404
        uname = (row['username'] or '').strip().lower()
        safe_key = _safe_key_from_username(uname)
        logging.info(f'✓ Code {raw} → user {uname} (safe_key: {safe_key})')
        if not safe_key:
            return {'success': False, 'error': 'invalid user'}, 404
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(safe_key))
        logging.info(f'📊 Returning {len(cfg.get("stores", []))} stores, {sum(len(s) for s in cfg.get("screens", {}).values())} screens for code {raw}')
        # Return minimal listing to the TV app
        return {
            'success': True,
            'user': {'username': uname},
            'stores': cfg.get('stores', []),
            'screens': cfg.get('screens', {})
        }
    except Exception as e:
        logging.error(f'❌ stores_by_code error: {e}')
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
        
        # Build avatar URL with validation
        if avatar_rel:
            try:
                # Normalize path separators
                avatar_rel = avatar_rel.replace('\\', '/')
                # Check if file actually exists
                avatar_full_path = os.path.join('static', avatar_rel) if not avatar_rel.startswith('static') else avatar_rel
                if os.path.exists(avatar_full_path):
                    avatar_url = url_for('static', filename=avatar_rel)
                    # Add cache-buster
                    try:
                        ts = int(os.path.getmtime(avatar_full_path))
                        avatar_url = f"{avatar_url}?t={ts}"
                    except Exception:
                        pass
                else:
                    logging.warning(f'Avatar file not found for {uname}: {avatar_full_path}')
                    # Clear invalid avatar from database
                    db.execute('UPDATE users SET avatar = NULL WHERE username = ?', (uname,))
                    db.commit()
            except Exception as e:
                logging.warning(f'Error building avatar URL for {uname}: {e}')
                avatar_url = None
        
        code = _ensure_user_link_code(uname)
        return jsonify({'success': True, 'username': uname, 'full_name': full_name, 'avatar_url': avatar_url, 'link_code': code})
    except Exception as e:
        logging.error(f'Error in /api/me: {e}', exc_info=True)
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
        # Check if file was uploaded
        if 'avatar' not in request.files:
            logging.warning('Avatar upload failed: no file in request')
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        f = request.files['avatar']
        if not f or f.filename == '':
            logging.warning('Avatar upload failed: empty file')
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Get username before any processing
        uname = _get_current_username_from_session()
        if not uname:
            logging.warning('Avatar upload failed: no username in session')
            return jsonify({'success': False, 'error': 'Authentication required'}), 403
        
        safe_key = _safe_key_from_username(uname) or 'user'
        logging.info(f'Processing avatar upload for user: {uname} (key: {safe_key})')
        
        # Process image to square 256x256 PNG
        from PIL import Image, ImageOps  # type: ignore
        
        try:
            im = Image.open(f.stream)
            im = ImageOps.exif_transpose(im)
            im = ImageOps.fit(im, (256, 256), Image.Resampling.LANCZOS)
        except Exception as img_err:
            logging.error(f'Image processing failed for {uname}: {img_err}')
            return jsonify({'success': False, 'error': 'Invalid image file'}), 400
        
        # Ensure avatar folder exists
        os.makedirs(AVATAR_FOLDER, exist_ok=True)
        
        save_path = os.path.join(AVATAR_FOLDER, f'{safe_key}.png')
        
        # Save with error handling
        try:
            im.save(save_path, format='PNG', optimize=True)
            logging.info(f'Avatar saved to: {save_path}')
        except Exception as save_err:
            logging.error(f'Failed to save avatar for {uname}: {save_err}')
            return jsonify({'success': False, 'error': 'Failed to save image'}), 500
        
        # Store relative path for static url building (normalize path separators)
        rel = os.path.join('uploads', 'avatars', f'{safe_key}.png').replace('\\', '/')
        
        # Update database with error handling
        try:
            db = get_db()
            db.execute('UPDATE users SET avatar = ? WHERE username = ?', (rel, uname))
            db.commit()
            logging.info(f'Database updated with avatar path for {uname}: {rel}')
        except Exception as db_err:
            logging.error(f'Database update failed for {uname}: {db_err}')
            # Try to remove the saved file since DB update failed
            try:
                os.remove(save_path)
            except Exception:
                pass
            return jsonify({'success': False, 'error': 'Failed to update profile'}), 500
        
        # Build URL with cache-buster
        url = url_for('static', filename=rel)
        try:
            ts = int(os.path.getmtime(save_path))
            sep = '&' if ('?' in url) else '?'
            url = f"{url}{sep}t={ts}"
        except Exception as ts_err:
            logging.warning(f'Could not add timestamp to avatar URL: {ts_err}')
            # Fallback to current timestamp
            import time
            url = f"{url}?t={int(time.time())}"
        
        logging.info(f'Avatar upload successful for {uname}: {url}')
        return jsonify({'success': True, 'avatar_url': url})
        
    except Exception as e:
        logging.error(f'Avatar upload error: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def save_store_config(config):
    """Save store configuration to the active JSON file (per-user or global) with automatic backup."""
    try:
        cfg_path = _effective_config_path()
        
        # SAFETY: Create backup before overwriting if file exists and has content
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r') as f:
                    existing_cfg = json.load(f)
                # Count total playlist items for safety check
                total_items = 0
                for store_id, screens in existing_cfg.get('screens', {}).items():
                    for screen_id, screen_data in screens.items():
                        total_items += len(screen_data.get('playlist', []))
                
                if total_items > 0:
                    # Create timestamped backup
                    import time
                    timestamp = int(time.time())
                    backup_path = f"{cfg_path}.backup-{timestamp}"
                    shutil.copyfile(cfg_path, backup_path)
                    print(f"DEBUG: Created backup with {total_items} playlist items: {backup_path}")
                    
                    # Keep only last 5 backups to prevent disk bloat
                    try:
                        import glob
                        backup_files = sorted(glob.glob(f"{cfg_path}.backup-*"))
                        if len(backup_files) > 5:
                            for old_backup in backup_files[:-5]:
                                os.remove(old_backup)
                                print(f"DEBUG: Cleaned old backup: {old_backup}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"Warning: Could not create backup: {e}")
        
        # Atomic write: write to temp file then replace
        tmp_file = cfg_path + '.tmp'
        with open(tmp_file, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, cfg_path)
        print(f"Configuration atomically saved to {cfg_path}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        raise

def cleanup_slice_cache():
    """Clean up old video slice cache files to prevent disk bloat."""
    try:
        import glob
        import time
        
        # Clean slices older than 7 days
        slice_pattern = os.path.join(SLICE_CACHE_FOLDER, "*.mp4")
        temp_pattern = os.path.join(TEMP_CACHE_FOLDER, "*")
        
        current_time = time.time()
        week_ago = current_time - (7 * 24 * 60 * 60)  # 7 days in seconds
        
        cleaned_count = 0
        
        # Clean old slice files
        for cache_file in glob.glob(slice_pattern):
            try:
                if os.path.getmtime(cache_file) < week_ago:
                    os.remove(cache_file)
                    cleaned_count += 1
            except Exception:
                pass
        
        # Clean old temp files (older than 1 day)
        day_ago = current_time - (24 * 60 * 60)
        for temp_file in glob.glob(temp_pattern):
            try:
                if os.path.getmtime(temp_file) < day_ago:
                    os.remove(temp_file)
                    cleaned_count += 1
            except Exception:
                pass
        
        if cleaned_count > 0:
            print(f"DEBUG: Cleaned {cleaned_count} old cache files")
        
    except Exception as e:
        print(f"WARNING: Cache cleanup failed: {e}")

# Run cache cleanup on startup
cleanup_slice_cache()

def check_ffmpeg_available():
    """Check if FFmpeg is available in the system PATH or common locations."""
    # Common FFmpeg locations on Windows
    ffmpeg_locations = [
        'ffmpeg',  # System PATH
        'C:\\ffmpeg\\bin\\ffmpeg.exe',
        'C:\\FFmpeg\\bin\\ffmpeg.exe',
        os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
    ]
    
    for ffmpeg_path in ffmpeg_locations:
        try:
            result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"DEBUG: FFmpeg found at: {ffmpeg_path}")
                # Store the working path for later use
                global FFMPEG_PATH
                FFMPEG_PATH = ffmpeg_path
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
        except Exception as e:
            print(f"WARNING: FFmpeg check failed for {ffmpeg_path}: {e}")
            continue
    
    print("WARNING: FFmpeg not found in any common locations")
    print("Install FFmpeg using: python setup_ffmpeg.ps1")
    return False

# Check FFmpeg availability on startup
FFMPEG_PATH = 'ffmpeg'  # Default to PATH
FFMPEG_AVAILABLE = check_ffmpeg_available()
if not FFMPEG_AVAILABLE:
    print("WARNING: Video slicing will not work without FFmpeg.")
    print("Install FFmpeg using: powershell -ExecutionPolicy Bypass -File setup_ffmpeg.ps1")

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

# ---- Auto-Slicing Helper Functions ----

def detect_video_resolution(video_path):
    """
    Use FFprobe to detect video resolution and other metadata.
    Returns dict with width, height, fps, has_audio.
    """
    if not FFMPEG_AVAILABLE:
        print("WARNING: FFmpeg not available, cannot detect resolution")
        return None
    
    try:
        ffprobe_cmd = FFMPEG_PATH.replace('ffmpeg', 'ffprobe') if 'ffmpeg' in FFMPEG_PATH else 'ffprobe'
        probe_cmd = [
            ffprobe_cmd, '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        if probe_result.returncode != 0:
            print(f"ERROR: ffprobe failed: {probe_result.stderr}")
            return None
        
        probe_data = json.loads(probe_result.stdout)
        
        # Find video and audio streams
        video_stream = None
        has_audio = False
        
        for stream in probe_data.get('streams', []):
            codec_type = stream.get('codec_type')
            if codec_type == 'video' and video_stream is None:
                video_stream = stream
            if codec_type == 'audio':
                has_audio = True
        
        if not video_stream:
            print("ERROR: No video stream found")
            return None
        
        width = int(video_stream.get('width', 0) or 0)
        height = int(video_stream.get('height', 0) or 0)
        
        # Parse FPS from r_frame_rate
        fps = 30  # default
        rfr = (video_stream.get('r_frame_rate') or '').strip()
        try:
            if rfr and '/' in rfr:
                num, den = rfr.split('/')
                num_val = float(num)
                den_val = float(den) if float(den) != 0 else 1.0
                if num_val > 0 and den_val > 0:
                    fps_val = num_val / den_val
                    if 10 <= fps_val <= 120:
                        fps = int(round(fps_val))
        except Exception:
            pass
        
        print(f"[detect_video_resolution] {video_path}: {width}x{height}, fps={fps}, audio={has_audio}")
        
        return {
            'width': width,
            'height': height,
            'fps': fps,
            'has_audio': has_audio
        }
    
    except Exception as e:
        print(f"ERROR: Failed to detect video resolution: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_screen_layout(width, height):
    """
    Calculate multi-screen layout based on resolution.
    
    Returns dict with:
    - screen_count: number of screens (1-7)
    - layout: 'horizontal', 'vertical', or 'single'
    - base_width: 1920 for both horizontal and vertical
    - base_height: 1080 for both horizontal and vertical
    
    Horizontal layouts (side-by-side) - width multiplied by 1920:
    - 1920x1080 = 1 screen
    - 3840x1080 = 2 screens
    - 5760x1080 = 3 screens
    - 7680x1080 = 4 screens
    - 9600x1080 = 5 screens
    - 11520x1080 = 6 screens
    - 13440x1080 = 7 screens
    
    Vertical layouts (stacked) - width stays 1920, height multiplied by 1080:
    - 1920x1080 = 1 screen
    - 1920x2160 = 2 screens
    - 1920x3240 = 3 screens
    - 1920x4320 = 4 screens
    - 1920x5400 = 5 screens
    - 1920x6480 = 6 screens
    - 1920x7560 = 7 screens
    """
    
    # Check horizontal layout (side-by-side - width multiplied)
    if height == 1080 and width >= 1920:
        screens = width // 1920
        if width % 1920 == 0 and 1 <= screens <= 7:
            print(f"[calculate_screen_layout] Detected HORIZONTAL (side-by-side) layout: {screens} screens ({width}x{height})")
            return {
                'screen_count': screens,
                'layout': 'horizontal',
                'base_width': 1920,
                'base_height': 1080
            }
    
    # Check vertical layout (stacked - height multiplied)
    if width == 1920 and height >= 1080:
        screens = height // 1080
        if height % 1080 == 0 and 1 <= screens <= 7:
            print(f"[calculate_screen_layout] Detected VERTICAL (stacked) layout: {screens} screens ({width}x{height})")
            return {
                'screen_count': screens,
                'layout': 'vertical',
                'base_width': 1920,
                'base_height': 1080
            }
    
    # Single screen or non-standard resolution
    print(f"[calculate_screen_layout] Single screen or non-standard resolution: {width}x{height}")
    return {
        'screen_count': 1,
        'layout': 'single',
        'base_width': width,
        'base_height': height
    }


def slice_video_for_multi_screen(input_path, output_dir, base_filename, layout_info, video_info):
    """
    Slice a multi-screen video into individual screen files using FFmpeg.
    
    Args:
        input_path: Path to original video file
        output_dir: Directory to save sliced videos
        base_filename: Base name for output files (without extension)
        layout_info: Dict from calculate_screen_layout()
        video_info: Dict from detect_video_resolution()
    
    Returns:
        List of dicts with 'screen_number', 'filename', 'path' for each slice
    """
    
    if not FFMPEG_AVAILABLE:
        print("ERROR: FFmpeg not available, cannot slice video")
        return []
    
    screen_count = layout_info['screen_count']
    layout_type = layout_info['layout']
    
    if screen_count == 1:
        print("[slice_video_for_multi_screen] Single screen, no slicing needed")
        return []
    
    width = video_info['width']
    height = video_info['height']
    fps = video_info['fps']
    has_audio = video_info['has_audio']
    
    # Helper to enforce even dimensions for yuv420p
    def _even(x):
        return x - (x % 2)
    
    slices = []
    gop = max(2, int(round(fps)))  # ~1s GOP
    
    print(f"[slice_video_for_multi_screen] Slicing {input_path} into {screen_count} {layout_type} screens")
    
    for screen_idx in range(screen_count):
        screen_number = screen_idx + 1
        output_filename = f"{base_filename}-screen{screen_number}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        # Calculate crop parameters based on layout
        if layout_type == 'horizontal':
            # Horizontal split: crop width
            w_per = width / screen_count
            left = int(round(screen_idx * w_per))
            right = int(round((screen_idx + 1) * w_per))
            crop_x = max(0, min(left, width - 2))
            slice_width = max(2, min(right - left, width - crop_x))
            slice_height = height
            crop_y = 0
        
        elif layout_type == 'vertical':
            # Vertical split: crop height
            h_per = height / screen_count
            top = int(round(screen_idx * h_per))
            bottom = int(round((screen_idx + 1) * h_per))
            crop_y = max(0, min(top, height - 2))
            slice_height = max(2, min(bottom - top, height - crop_y))
            slice_width = width
            crop_x = 0
        
        else:
            print(f"ERROR: Unknown layout type: {layout_type}")
            continue
        
        # Enforce even dimensions
        crop_x = _even(crop_x)
        crop_y = _even(crop_y)
        slice_width = _even(min(slice_width, width - crop_x))
        slice_height = _even(min(slice_height, height - crop_y))
        
        if slice_width < 2:
            slice_width = 2
        if slice_height < 2:
            slice_height = 2
        
        print(f"[slice_video_for_multi_screen] Screen {screen_number}: crop={slice_width}:{slice_height}:{crop_x}:{crop_y}")
        
        # Build FFmpeg command
        crop_filter = f"crop={slice_width}:{slice_height}:{crop_x}:{crop_y}"
        
        ffmpeg_cmd = [
            FFMPEG_PATH, '-y',  # overwrite output file
            '-i', input_path,
            '-vf', crop_filter,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main',
            '-level', '4.0',
            '-preset', 'fast',  # Faster encoding for upload
            '-crf', '23',  # Good quality/size balance
            '-g', str(gop),
            '-keyint_min', str(gop),
            '-sc_threshold', '0',
            '-vsync', 'cfr',
            '-r', str(max(10, fps)),
            '-force_key_frames', f"expr:gte(t,n_forced*1)",
            '-movflags', '+faststart+frag_keyframe+empty_moov',
            '-frag_duration', '1000000',
            '-map', '0:v:0',
        ]
        
        if has_audio:
            ffmpeg_cmd += [
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ac', '2',
                '-ar', '48000',
                '-map', '0:a:0?',
            ]
        else:
            ffmpeg_cmd += ['-an']
        
        ffmpeg_cmd += ['-map_metadata', '-1', '-map_chapters', '-1']
        ffmpeg_cmd.append(output_path)
        
        # Run FFmpeg
        try:
            print(f"[slice_video_for_multi_screen] Running FFmpeg for screen {screen_number}...")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"[slice_video_for_multi_screen] Screen {screen_number} created: {output_filename} ({file_size/1024/1024:.2f} MB)")
                
                slices.append({
                    'screen_number': screen_number,
                    'filename': output_filename,
                    'path': output_path,
                    'size': file_size
                })
            else:
                print(f"ERROR: FFmpeg failed for screen {screen_number}")
                print(f"STDERR: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            print(f"ERROR: FFmpeg timeout for screen {screen_number}")
        except Exception as e:
            print(f"ERROR: Failed to create slice for screen {screen_number}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"[slice_video_for_multi_screen] Successfully created {len(slices)} slices")
    return slices


def _process_single_screen_ffmpeg(params):
    """
    Process a single screen slice using FFmpeg. 
    Designed to be called by multiprocessing.Pool for parallel execution.
    
    Args:
        params: Dict with screen_number, input_path, output_path, crop params, etc.
    
    Returns:
        Dict with success status and slice info, or error
    """
    try:
        screen_number = params['screen_number']
        input_path = params['input_path']
        output_path = params['output_path']
        output_filename = params['output_filename']
        crop_x = params['crop_x']
        crop_y = params['crop_y']
        slice_width = params['slice_width']
        slice_height = params['slice_height']
        fps = params['fps']
        gop = params['gop']
        has_audio = params['has_audio']
        
        crop_filter = f"crop={slice_width}:{slice_height}:{crop_x}:{crop_y}"
        
        # Build FFmpeg command - optimized for speed
        ffmpeg_cmd = [
            FFMPEG_PATH, '-y',
            '-i', input_path,
            '-vf', crop_filter,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main',
            '-level', '4.0',
            '-preset', 'ultrafast',  # Fastest encoding
            '-crf', '23',
            '-g', str(gop),
            '-keyint_min', str(gop),
            '-sc_threshold', '0',
            '-vsync', 'cfr',
            '-r', str(max(10, fps)),
            '-force_key_frames', f"expr:gte(t,n_forced*1)",
            '-movflags', '+faststart+frag_keyframe+empty_moov',
            '-frag_duration', '1000000',
            '-map', '0:v:0',
        ]
        
        if has_audio:
            ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '128k', '-ac', '2', '-ar', '48000', '-map', '0:a:0?']
        else:
            ffmpeg_cmd += ['-an']
        
        ffmpeg_cmd += ['-map_metadata', '-1', '-map_chapters', '-1', output_path]
        
        # Run FFmpeg
        print(f"[parallel_slice] Processing screen {screen_number} (PID {os.getpid()})...")
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"[parallel_slice] Screen {screen_number} created: {file_size/1024/1024:.2f} MB")
            
            return {
                'success': True,
                'screen_number': screen_number,
                'filename': output_filename,
                'path': output_path,
                'size': file_size
            }
        else:
            error_msg = f'FFmpeg failed for screen {screen_number}: {result.stderr[:200]}'
            print(f"ERROR: {error_msg}")
            return {
                'success': False,
                'screen_number': screen_number,
                'error': error_msg
            }
    
    except Exception as e:
        error_msg = f'Exception processing screen {params.get("screen_number", "?")}: {str(e)}'
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'screen_number': params.get('screen_number', 0),
            'error': error_msg
        }


def _background_slice_and_upload(job_id, input_path, req_prefix, base_filename, layout_info, video_info, local_dir):
    """
    Background worker to slice video and upload slices to R2.
    Uses filesystem for job status (works across gunicorn workers).
    NOW WITH PARALLEL PROCESSING for 3-4x speed improvement!
    """
    try:
        screen_count = layout_info['screen_count']
        _set_job_status(job_id, {
            'status': 'processing', 
            'progress': 0, 
            'result': [],
            'current_screen': 0,
            'screen_count': screen_count
        })
        
        slice_temp_dir = os.path.join(os.path.dirname(input_path), 'slices_temp')
        os.makedirs(slice_temp_dir, exist_ok=True)
        
        # Slice the video with PARALLEL PROCESSING
        print(f"[background_slice] Starting PARALLEL slicing of {screen_count} screens...")
        
        if not FFMPEG_AVAILABLE:
            _set_job_status(job_id, {'status': 'error', 'error': 'FFmpeg not available'})
            return
        
        width = video_info['width']
        height = video_info['height']
        fps = video_info['fps']
        has_audio = video_info['has_audio']
        
        def _even(x):
            return x - (x % 2)
        
        gop = max(2, int(round(fps)))
        layout_type = layout_info['layout']
        
        # Prepare parameters for all screens
        screen_params = []
        for screen_idx in range(screen_count):
            screen_number = screen_idx + 1
            output_filename = f"{base_filename}-screen{screen_number}.mp4"
            output_path = os.path.join(slice_temp_dir, output_filename)
            
            # Calculate crop parameters
            if layout_type == 'horizontal':
                w_per = width / screen_count
                left = int(round(screen_idx * w_per))
                right = int(round((screen_idx + 1) * w_per))
                crop_x = max(0, min(left, width - 2))
                slice_width = max(2, min(right - left, width - crop_x))
                slice_height = height
                crop_y = 0
            elif layout_type == 'vertical':
                h_per = height / screen_count
                top = int(round(screen_idx * h_per))
                bottom = int(round((screen_idx + 1) * h_per))
                crop_y = max(0, min(top, height - 2))
                slice_height = max(2, min(bottom - top, height - crop_y))
                slice_width = width
                crop_x = 0
            else:
                continue
            
            crop_x = _even(crop_x)
            crop_y = _even(crop_y)
            slice_width = _even(min(slice_width, width - crop_x))
            slice_height = _even(min(slice_height, height - crop_y))
            
            if slice_width < 2:
                slice_width = 2
            if slice_height < 2:
                slice_height = 2
            
            screen_params.append({
                'screen_number': screen_number,
                'input_path': input_path,
                'output_path': output_path,
                'output_filename': output_filename,
                'crop_x': crop_x,
                'crop_y': crop_y,
                'slice_width': slice_width,
                'slice_height': slice_height,
                'fps': fps,
                'gop': gop,
                'has_audio': has_audio
            })
        
        # Process all screens in PARALLEL using ThreadPoolExecutor (works with gunicorn!)
        num_workers = min(screen_count, 4)  # Use up to 4 concurrent threads
        print(f"[background_slice] 🚀 Starting PARALLEL processing with {num_workers} workers for {screen_count} screens")
        
        slices = []
        completed_count = 0
        
        try:
            # Use ThreadPoolExecutor which works perfectly with gunicorn workers
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit all tasks and track them
                future_to_screen = {
                    executor.submit(_process_single_screen_ffmpeg, params): params['screen_number'] 
                    for params in screen_params
                }
                
                # Process results as they complete (real-time updates!)
                for future in as_completed(future_to_screen):
                    screen_num = future_to_screen[future]
                    try:
                        result = future.result()
                        if result and result.get('success'):
                            completed_count += 1
                            slices.append({
                                'screen_number': result['screen_number'],
                                'filename': result['filename'],
                                'path': result['path'],
                                'size': result['size']
                            })
                            # Update progress as EACH screen completes in real-time (50-75%)
                            # Upload takes 0-50%, slicing takes 50-75%, R2 upload takes 75-100%
                            progress = 50 + int((completed_count / screen_count) * 25)
                            print(f"[background_slice] ✅ Screen {result['screen_number']} complete! ({completed_count}/{screen_count} = {progress}%)")
                            _set_job_status(job_id, {
                                'status': 'processing',
                                'progress': progress,
                                'result': slices,
                                'current_screen': completed_count,
                                'screen_count': screen_count,
                                'stage': f'Slicing screen {completed_count}/{screen_count}'
                            })
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'Processing failed'
                            print(f"ERROR: Failed to process screen {screen_num}: {error_msg}")
                            _set_job_status(job_id, {'status': 'error', 'error': error_msg})
                            return
                    except Exception as e:
                        error_msg = f'Exception getting result for screen {screen_num}: {str(e)}'
                        print(f"ERROR: {error_msg}")
                        _set_job_status(job_id, {'status': 'error', 'error': error_msg})
                        return
        
        except Exception as e:
            print(f"ERROR: Parallel processing failed: {e}")
            import traceback
            traceback.print_exc()
            _set_job_status(job_id, {'status': 'error', 'error': f'Parallel processing error: {str(e)}'})
            return
        
        if not slices or len(slices) != screen_count:
            _set_job_status(job_id, {'status': 'error', 'error': f'Failed to create all slices (got {len(slices)}/{screen_count})'})
            return
        
        # Sort slices by screen number to ensure correct order
        slices.sort(key=lambda x: x['screen_number'])
        
        print(f"[background_slice] All {len(slices)} screens sliced successfully in parallel!")
        
        # Update: slicing complete, starting uploads (75%)
        _set_job_status(job_id, {
            'status': 'processing', 
            'progress': 75, 
            'result': [],
            'current_screen': screen_count,
            'screen_count': screen_count,
            'stage': 'Uploading sliced videos to CDN...'
        })
        
        # Upload each slice to R2
        sliced_files = []
        for i, slice_info in enumerate(slices):
            slice_path = slice_info['path']
            slice_filename = slice_info['filename']
            slice_key = _join_prefix_key(req_prefix, slice_filename)
            
            try:
                # Save locally
                local_slice_dest = os.path.join(local_dir, slice_filename)
                shutil.copy2(slice_path, local_slice_dest)
                print(f"[background_slice] Saved slice locally: {local_slice_dest}")
                
                # Upload to R2
                if r2_enabled():
                    with open(slice_path, 'rb') as fh:
                        data = fh.read()
                    r2_put_bytes(slice_key, data, content_type='video/mp4')
                    print(f"[background_slice] R2 upload ok: {slice_key}")
                
                sliced_files.append({
                    'screen_number': slice_info['screen_number'],
                    'filename': slice_key,
                    'url': build_public_url(slice_key),
                    'size': slice_info['size']
                })
                
                # Update progress: 75-100% for uploading to CDN
                progress = 75 + int((i + 1) / len(slices) * 25)
                _set_job_status(job_id, {
                    'status': 'processing', 
                    'progress': progress, 
                    'result': sliced_files,
                    'current_screen': screen_count,
                    'screen_count': screen_count
                })
                
            except Exception as upload_e:
                print(f"ERROR: Failed to upload slice {slice_filename}: {upload_e}")
        
        # Cleanup temp directory
        try:
            if os.path.exists(slice_temp_dir):
                shutil.rmtree(slice_temp_dir)
        except Exception:
            pass
        
        # Mark complete
        _set_job_status(job_id, {
            'status': 'complete',
            'progress': 100,
            'result': sliced_files,
            'layout': layout_info['layout'],
            'screen_count': len(sliced_files)
        })
        print(f"[background_slice] Job {job_id} complete: {len(sliced_files)} slices uploaded")
        
    except Exception as e:
        print(f"ERROR: Background slice job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        _set_job_status(job_id, {'status': 'error', 'error': str(e)})


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
        # Prefer PATH lookup; on Windows, both 'ffmpeg' and 'ffmpeg.exe' are valid
        found = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
        if found:
            return found
        # 3) Common system locations (systemd may have a reduced PATH)
        for p in ('/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/bin/ffmpeg'):
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
        # 4) Windows common install path
        for p in (r'C:\\ffmpeg\\bin\\ffmpeg.exe', r'C:\\ffmpeg\\ffmpeg.exe'):
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
        # Use the provided parent_config to resolve sync groups; avoid referencing undefined names
        groups = {}
        if isinstance(parent_config, dict):
            sg = parent_config.get('sync_groups')
            if isinstance(sg, dict):
                groups = sg
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
        # SYNC FIX: When all screens have empty playlists, use the same default file
        # to ensure synchronized playback across screens 1, 2, and 3
        default_file = screen.get('file')
        if not default_file and store_id == '1000':
            # For store 1000, use the test video as default for all screens
            default_file = 'users/toengpheng_at_gmail.com/2025-09/aa5bfb25-ff6f-4a67-878f-060187487b3c.mp4'
        return default_file
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
    logging.info(f"🏠 DASHBOARD ACCESS - Session keys: {list(session.keys())}, User: {session.get('user', {})}")
    try:
        print("DEBUG: Loading store config...")
        # Load user-specific config to prevent cross-user data leakage
        ukey = _safe_user_key()
        print(f"DEBUG: User safe key: {ukey}")
        print(f"DEBUG: Session user: {session.get('user', {})}")
        logging.info(f"🔑 Dashboard user_key: {ukey}")
        
        if not ukey:
            logging.error(f"❌ CRITICAL: Dashboard accessed with NO user key! Session: {dict(session)}")
        
        config = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
        print(f"DEBUG: Loaded config for user key: {ukey}, stores: {[s.get('id') for s in config.get('stores', [])]}")
        logging.info(f"📊 Dashboard showing {len(config.get('stores', []))} stores, {sum(len(s) for s in config.get('screens', {}).values())} total screens for user: {ukey or 'GLOBAL CONFIG'}")
        # Guard: ensure stores/screens keys exist even for new users
        if 'stores' not in config or not isinstance(config.get('stores'), list):
            config['stores'] = []
        if 'screens' not in config or not isinstance(config.get('screens'), dict):
            config['screens'] = {}
        print(f"DEBUG: Screen IDs in config: {list(config.get('screens', {}).keys())}")
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

@app.route('/pi-manager')
@login_required
def pi_manager():
    """Pi Device Manager Dashboard"""
    try:
        # Load user-specific config
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        # Get all Pi devices from connected_pis and pi_id_ip_map
        import json
        pi_devices = []
        
        # Load pi_id_ip_map.json
        try:
            with open('pi_id_ip_map.json', 'r') as f:
                pi_map = json.load(f)
        except Exception:
            pi_map = {}
        
        # Combine data from connected_pis and pi_map
        all_pi_ids = set(list(connected_pis.keys()) + list(pi_map.keys()))
        
        # Pi offline timeout: consider offline if no heartbeat for 120 seconds (2 minutes)
        # Pis send heartbeats every 30 seconds, so 120s allows up to 3 missed heartbeats
        PI_OFFLINE_TIMEOUT = 120
        import time as time_module
        current_time = time_module.time()
        
        logging.info(f"=== Pi Manager Status Check at {current_time} ===")
        
        for pi_id in all_pi_ids:
            # Get last_seen timestamp from connected_pis or pi_map
            last_seen_timestamp = None
            
            # First try connected_pis (for currently/recently connected Pis)
            if pi_id in connected_pis:
                last_seen_timestamp = connected_pis[pi_id].get('last_seen')
                logging.debug(f"Pi {pi_id}: last_seen from connected_pis = {last_seen_timestamp}")
            
            # If not in connected_pis, check pi_map for persisted data
            if not last_seen_timestamp and pi_id in pi_map:
                pi_data = pi_map[pi_id]
                logging.debug(f"Pi {pi_id}: pi_map data = {pi_data}")
                if isinstance(pi_data, dict):
                    last_seen_timestamp = pi_data.get('last_seen')
                    logging.debug(f"Pi {pi_id}: last_seen from pi_map = {last_seen_timestamp}")
            
            # Format last_seen and determine online status
            if last_seen_timestamp and isinstance(last_seen_timestamp, (int, float)):
                from datetime import datetime
                last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %I:%M:%S %p')
                # Check if Pi is online based on last_seen timestamp
                time_since_last_seen = current_time - last_seen_timestamp
                is_online = time_since_last_seen < PI_OFFLINE_TIMEOUT
                logging.info(f"Pi {pi_id}: last_seen={last_seen_formatted}, time_since={time_since_last_seen:.1f}s, is_online={is_online}")
            else:
                last_seen_formatted = 'Never'
                is_online = False
                logging.info(f"Pi {pi_id}: No valid timestamp, showing 'Never'")
            
            # Get IP from pi_map or from connected_pis
            ip_address = None
            if pi_id in pi_map:
                pi_data = pi_map[pi_id]
                logging.debug(f"pi_id={pi_id}, pi_data type={type(pi_data)}, value={pi_data}")
                if isinstance(pi_data, dict):
                    ip_address = pi_data.get('ip')
                    logging.debug(f"Extracted IP from dict: {ip_address}")
                elif isinstance(pi_data, str):
                    ip_address = pi_data  # Legacy format (just IP string)
                    logging.debug(f"Using legacy IP string: {ip_address}")
            
            if not ip_address and pi_id in connected_pis:
                ip_address = connected_pis[pi_id].get('ip', 'Unknown')
                logging.debug(f"Got IP from connected_pis: {ip_address}")
            if not ip_address:
                ip_address = 'Unknown'
                logging.debug(f"No IP found, using 'Unknown'")
            
            logging.debug(f"Final ip_address before pi_info: type={type(ip_address)}, value={ip_address}")
            
            # Ensure IP is always a string (failsafe)
            if not isinstance(ip_address, str):
                logging.warning(f"Pi {pi_id}: IP address is not a string: {ip_address}, converting...")
                ip_address = str(ip_address) if ip_address else 'Unknown'
            
            pi_info = {
                'id': pi_id,
                'ip': ip_address,
                'status': 'online' if is_online else 'offline',
                'connected_at': connected_pis.get(pi_id, {}).get('connected_at', None),
                'last_seen': last_seen_formatted,
                'location': '',  # Custom location name
                'store_id': None,
                'store_name': 'Not Assigned',
                'screen_id': None,
                'screen_name': 'Not Assigned'
            }
            
            # FIRST: Try to get assignment from real-time heartbeat data in connected_pis
            found = False
            if pi_id in connected_pis:
                heartbeat_store_id = connected_pis[pi_id].get('store_id')
                heartbeat_screen_id = connected_pis[pi_id].get('screen_id')
                
                if heartbeat_store_id and heartbeat_screen_id:
                    # Find store name from config
                    store_name = heartbeat_store_id
                    for store in config.get('stores', []):
                        if store.get('id') == heartbeat_store_id:
                            store_name = store.get('name', heartbeat_store_id)
                            break
                    
                    # Get screen name from config if available
                    screen_name = heartbeat_screen_id
                    screen_data = config.get('screens', {}).get(heartbeat_store_id, {}).get(heartbeat_screen_id, {})
                    if screen_data:
                        screen_name = screen_data.get('name', heartbeat_screen_id)
                        pi_info['location'] = screen_data.get('location_name', '')
                    
                    pi_info['store_id'] = heartbeat_store_id
                    pi_info['store_name'] = store_name
                    pi_info['screen_id'] = heartbeat_screen_id
                    pi_info['screen_name'] = screen_name
                    found = True
                    logging.info(f"[Pi Manager] ✅ Found assignment from HEARTBEAT: {pi_id} -> {heartbeat_store_id}/{heartbeat_screen_id}")
            
            # FALLBACK: If not in heartbeat, try config file (for offline Pis)
            if not found:
                logging.info(f"[Pi Manager] Looking for assignment in CONFIG for Pi ID: '{pi_id}'")
                for store in config.get('stores', []):
                    store_id = store.get('id')
                    for screen_id, screen_data in config.get('screens', {}).get(store_id, {}).items():
                        screen_pi_id = screen_data.get('pi_id')
                        logging.debug(f"[Pi Manager] Checking {store_id}/{screen_id}: pi_id='{screen_pi_id}' vs '{pi_id}'")
                        if screen_pi_id == pi_id:
                            pi_info['store_id'] = store_id
                            pi_info['store_name'] = store.get('name', store_id)
                            pi_info['screen_id'] = screen_id
                            pi_info['screen_name'] = screen_data.get('name', screen_id)
                            # Get custom location name if set
                            pi_info['location'] = screen_data.get('location_name', '')
                            found = True
                            logging.info(f"[Pi Manager] ✅ Found assignment from CONFIG: {pi_id} -> {store_id}/{screen_id}")
                            break
                    if found:
                        break
            
            if not found:
                logging.warning(f"[Pi Manager] ❌ No assignment found for Pi ID: '{pi_id}'")
            
            pi_devices.append(pi_info)
        
        # Calculate statistics
        total_stores = len(config.get('stores', []))
        total_screens = sum(len(screens) for screens in config.get('screens', {}).values())
        
        # Count online Pi devices
        pi_online_count = len([p for p in pi_devices if p['status'] == 'online'])
        
        # Count online Android TV devices
        android_tv_online_count = 0
        ANDROID_TV_OFFLINE_TIMEOUT = 120
        with android_tv_lock:
            for device_id, tv_data in connected_android_tvs.items():
                # Only count devices for current user
                if ukey and tv_data.get('user_key') != ukey:
                    continue
                last_seen_timestamp = tv_data.get('last_seen')
                if last_seen_timestamp and isinstance(last_seen_timestamp, (int, float)):
                    time_since_last_seen = current_time - last_seen_timestamp
                    if time_since_last_seen < ANDROID_TV_OFFLINE_TIMEOUT:
                        android_tv_online_count += 1
        
        # Total online = Pi devices + Android TV devices
        online_count = pi_online_count + android_tv_online_count
        
        # Offline = all screens defined in config minus those currently online
        offline_count = total_screens - online_count
        
        # Compute user info for header menu
        try:
            u = session.get('user') or {}
            uname = (u.get('email') or u.get('name') or u.get('username') or '').strip()
            link_code = _ensure_user_link_code(uname) if uname else ''
        except Exception:
            uname = ''
            link_code = ''
        
        # Get available Pi IDs (registered but not yet assigned)
        assigned_pi_ids = set()
        for store in config.get('stores', []):
            store_id = store.get('id')
            for screen_id, screen_data in config.get('screens', {}).get(store_id, {}).items():
                if screen_data.get('pi_id'):
                    assigned_pi_ids.add(screen_data.get('pi_id'))
        
        available_pi_ids = [pi_id for pi_id in all_pi_ids if pi_id not in assigned_pi_ids]
        
        resp = make_response(render_template(
            'pi_manager.html',
            pi_devices=pi_devices,
            available_pi_ids=available_pi_ids,
            pi_map=pi_map,
            stores=config.get('stores', []),
            all_screens=config.get('screens', {}),
            total_stores=total_stores,
            total_screens=total_screens,
            online_count=online_count,
            offline_count=offline_count,
            user_email=uname,
            link_code=link_code,
            build_stamp=BUILD_STAMP,
            git_commit=GIT_COMMIT
        ))
        # Prevent browser caching to ensure fresh store names are displayed
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        logging.error(f"Error in pi_manager route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {e}", 500

@app.route('/api/pi_status')
@login_required
def get_pi_status():
    """API endpoint to get current Pi device statuses (for auto-refresh)"""
    try:
        import json
        import time as time_module
        
        # Pi offline timeout: consider offline if no heartbeat for 120 seconds (2 minutes)
        # Pis send heartbeats every 30 seconds, so 120s allows up to 3 missed heartbeats
        PI_OFFLINE_TIMEOUT = 120
        current_time = time_module.time()
        logging.info(f"=== API Pi Status Check at {current_time} ===")
        
        statuses = {}
        for pi_id, pi_data in connected_pis.items():
            last_seen_timestamp = pi_data.get('last_seen')
            if last_seen_timestamp and isinstance(last_seen_timestamp, (int, float)):
                from datetime import datetime
                last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %I:%M:%S %p')
                time_since_last_seen = current_time - last_seen_timestamp
                is_online = time_since_last_seen < PI_OFFLINE_TIMEOUT
                logging.info(f"API: Pi {pi_id}: last_seen={last_seen_formatted}, time_since={time_since_last_seen:.1f}s, is_online={is_online}")
            else:
                last_seen_formatted = 'Never'
                is_online = False
                logging.info(f"API: Pi {pi_id}: No valid timestamp, showing 'Never'")
            
            statuses[pi_id] = {
                'status': 'online' if is_online else 'offline',
                'last_seen': last_seen_formatted,
                'ip': pi_data.get('ip', 'Unknown')
            }
        
        # Also check pi_id_ip_map for devices not in connected_pis
        try:
            with open('pi_id_ip_map.json', 'r') as f:
                pi_map = json.load(f)
            for pi_id in pi_map.keys():
                if pi_id not in statuses:
                    statuses[pi_id] = {
                        'status': 'offline',
                        'last_seen': 'Never',
                        'ip': pi_map.get(pi_id, 'Unknown')
                    }
        except Exception:
            pass
        
        return jsonify(statuses)
    except Exception as e:
        logging.error(f"Error in get_pi_status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/android_tv_status')
@login_required
def get_android_tv_status():
    """API endpoint to get current Android TV device statuses (for auto-refresh)"""
    try:
        import time as time_module
        from datetime import datetime
        
        # Android TV offline timeout: consider offline if no heartbeat for 120 seconds (2 minutes)
        # Android TVs send heartbeats every ~30s, so 120s allows up to 3 missed heartbeats
        ANDROID_TV_OFFLINE_TIMEOUT = 120
        current_time = time_module.time()
        logging.info(f"=== API Android TV Status Check at {current_time} ===")
        
        # Get user-specific config
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        devices = []
        
        with android_tv_lock:
            for device_id, tv_data in connected_android_tvs.items():
                # Only show devices for current user
                if ukey and tv_data.get('user_key') != ukey:
                    continue
                
                last_seen_timestamp = tv_data.get('last_seen')
                store_id = tv_data.get('store_id')
                screen_id = tv_data.get('screen_id')
                
                if last_seen_timestamp and isinstance(last_seen_timestamp, (int, float)):
                    last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %I:%M:%S %p')
                    time_since_last_seen = current_time - last_seen_timestamp
                    is_online = time_since_last_seen < ANDROID_TV_OFFLINE_TIMEOUT
                    logging.info(f"API: Android TV {device_id}: last_seen={last_seen_formatted}, time_since={time_since_last_seen:.1f}s, is_online={is_online}")
                else:
                    last_seen_formatted = 'Never'
                    is_online = False
                    logging.info(f"API: Android TV {device_id}: No valid timestamp")
                
                # Get store and screen names
                store_name = store_id
                screen_name = screen_id
                location = ''
                
                for store in config.get('stores', []):
                    if store.get('id') == store_id:
                        store_name = store.get('name', store_id)
                        break
                
                screen_data = config.get('screens', {}).get(store_id, {}).get(screen_id, {})
                if screen_data:
                    screen_name = screen_data.get('name', screen_id)
                    location = screen_data.get('location_name', '')
                
                devices.append({
                    'id': device_id,
                    'status': 'online' if is_online else 'offline',
                    'last_seen': last_seen_formatted,
                    'ip': tv_data.get('ip', 'Unknown'),
                    'store_id': store_id,
                    'store_name': store_name,
                    'screen_id': screen_id,
                    'screen_name': screen_name,
                    'location': location
                })
        
        return jsonify({'devices': devices})
    except Exception as e:
        logging.error(f"Error in get_android_tv_status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/all_screens_status')
@login_required
def get_all_screens_status():
    """API endpoint to get ALL screens from config with their online/offline status"""
    try:
        import time as time_module
        import json
        from datetime import datetime
        
        # Get user-specific config
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        PI_OFFLINE_TIMEOUT = 120
        ANDROID_TV_OFFLINE_TIMEOUT = 120
        current_time = time_module.time()
        
        # Build a map of which screens are online
        online_screens = {}  # {store_id: {screen_id: device_info}}
        
        # Check Pi devices
        try:
            with open('pi_id_ip_map.json', 'r') as f:
                pi_map = json.load(f)
        except Exception:
            pi_map = {}
        
        all_pi_ids = set(list(connected_pis.keys()) + list(pi_map.keys()))
        
        for pi_id in all_pi_ids:
            # Check if Pi is online
            last_seen_timestamp = None
            if pi_id in connected_pis:
                last_seen_timestamp = connected_pis[pi_id].get('last_seen')
            elif pi_id in pi_map and isinstance(pi_map[pi_id], dict):
                last_seen_timestamp = pi_map[pi_id].get('last_seen')
            
            is_online = False
            ip_address = 'Unknown'
            
            if last_seen_timestamp and isinstance(last_seen_timestamp, (int, float)):
                time_since_last_seen = current_time - last_seen_timestamp
                is_online = time_since_last_seen < PI_OFFLINE_TIMEOUT
                last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %I:%M:%S %p')
            else:
                last_seen_formatted = 'Never'
            
            # Get IP
            if pi_id in pi_map:
                pi_data = pi_map[pi_id]
                if isinstance(pi_data, dict):
                    ip_address = pi_data.get('ip', 'Unknown')
                elif isinstance(pi_data, str):
                    ip_address = pi_data
            if ip_address == 'Unknown' and pi_id in connected_pis:
                ip_address = connected_pis[pi_id].get('ip', 'Unknown')
            
            # Find which screen this Pi is assigned to
            assignment_found = False
            
            # First check heartbeat data
            if pi_id in connected_pis:
                store_id = connected_pis[pi_id].get('store_id')
                screen_id = connected_pis[pi_id].get('screen_id')
                if store_id and screen_id:
                    if store_id not in online_screens:
                        online_screens[store_id] = {}
                    online_screens[store_id][screen_id] = {
                        'device_type': 'pi',
                        'device_id': pi_id,
                        'is_online': is_online,
                        'last_seen': last_seen_formatted,
                        'ip': ip_address
                    }
                    assignment_found = True
            
            # Check config if not found in heartbeat
            if not assignment_found:
                for store in config.get('stores', []):
                    store_id = store.get('id')
                    for screen_id, screen_data in config.get('screens', {}).get(store_id, {}).items():
                        if screen_data.get('pi_id') == pi_id:
                            if store_id not in online_screens:
                                online_screens[store_id] = {}
                            online_screens[store_id][screen_id] = {
                                'device_type': 'pi',
                                'device_id': pi_id,
                                'is_online': is_online,
                                'last_seen': last_seen_formatted,
                                'ip': ip_address
                            }
                            assignment_found = True
                            break
                    if assignment_found:
                        break
        
        # Check Android TV devices
        with android_tv_lock:
            for device_id, tv_data in connected_android_tvs.items():
                # Only check devices for current user
                if ukey and tv_data.get('user_key') != ukey:
                    continue
                
                last_seen_timestamp = tv_data.get('last_seen')
                store_id = tv_data.get('store_id')
                screen_id = tv_data.get('screen_id')
                
                if not store_id or not screen_id:
                    continue
                
                is_online = False
                if last_seen_timestamp and isinstance(last_seen_timestamp, (int, float)):
                    time_since_last_seen = current_time - last_seen_timestamp
                    is_online = time_since_last_seen < ANDROID_TV_OFFLINE_TIMEOUT
                    last_seen_formatted = datetime.fromtimestamp(last_seen_timestamp).strftime('%Y-%m-%d %I:%M:%S %p')
                else:
                    last_seen_formatted = 'Never'
                
                if store_id not in online_screens:
                    online_screens[store_id] = {}
                online_screens[store_id][screen_id] = {
                    'device_type': 'android_tv',
                    'device_id': device_id,
                    'is_online': is_online,
                    'last_seen': last_seen_formatted,
                    'ip': tv_data.get('ip', 'Unknown')
                }
        
        # Now build the complete list of all screens from config
        all_screens = []
        
        for store in config.get('stores', []):
            store_id = store.get('id')
            store_name = store.get('name', store_id)
            
            for screen_id, screen_data in config.get('screens', {}).get(store_id, {}).items():
                screen_name = screen_data.get('name', screen_id)
                location = screen_data.get('location_name', '')
                
                # Check if this screen has an online device
                device_info = online_screens.get(store_id, {}).get(screen_id)
                
                if device_info:
                    # Screen has a device (online or offline)
                    all_screens.append({
                        'screen_id': screen_id,
                        'screen_name': screen_name,
                        'store_id': store_id,
                        'store_name': store_name,
                        'location': location,
                        'device_type': device_info['device_type'],
                        'device_id': device_info['device_id'],
                        'status': 'online' if device_info['is_online'] else 'offline',
                        'last_seen': device_info['last_seen'],
                        'ip': device_info['ip']
                    })
                else:
                    # Screen has no device assigned or device never connected
                    all_screens.append({
                        'screen_id': screen_id,
                        'screen_name': screen_name,
                        'store_id': store_id,
                        'store_name': store_name,
                        'location': location,
                        'device_type': 'none',
                        'device_id': 'Not Assigned',
                        'status': 'offline',
                        'last_seen': 'Never',
                        'ip': 'N/A'
                    })
        
        return jsonify({'screens': all_screens})
    except Exception as e:
        logging.error(f"Error in get_all_screens_status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload_to_screen', methods=['POST'])
@login_required
def upload_to_screen():
    """Upload file to specific screen"""
    store_id = request.form.get('store_id')
    screen_id = request.form.get('screen_id')
    apply_to_all = request.form.get('apply_to_all', '').lower() == 'true'

    # Load user-specific config
    ukey = _safe_user_key()
    
    # Normalize screen_id: accept legacy short form (e.g. 'screen1') by expanding to '<store_id>_screen1' if needed
    try:
        cfg = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        if store_id and screen_id and store_id in cfg.get('screens', {}):
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

        # Update configuration with user-specific config
        ukey = _safe_user_key()
        config = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
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
        
        print(f"🔄🔄🔄 UPDATE_ROTATION CALLED: store={store_id}, screen={screen_id}, rotation={rotation}", flush=True)
        app.logger.info(f"UPDATE_ROTATION: store={store_id}, screen={screen_id}, rotation={rotation}")

        if not store_id or not screen_id:
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400

        ukey = _safe_user_key()
        print(f"🔄 User key: {ukey}", flush=True)
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        # Normalize to canonical store/screen IDs present in config
        ns, nid = _normalize_screen_ref(config, str(store_id), str(screen_id))
        if not ns or not nid:
            return jsonify({'error': 'Screen not found'}), 404

        if rotation not in [0, 90, 180, 270]:
            return jsonify({'error': 'Invalid rotation value'}), 400

        # Persist rotation
        config['screens'][ns][nid]['rotation'] = rotation

        # Mirror into GLOBAL config so devices without user_code see the change
        try:
            global_cfg = load_store_config()
            gscreens = global_cfg.setdefault('screens', {}).setdefault(ns, {})
            if nid not in gscreens:
                gscreens[nid] = {}
            gscreens[nid]['rotation'] = rotation
            save_store_config(global_cfg)
        except Exception as e:
            app.logger.debug(f"mirror rotation to global failed (non-fatal): {e}")

        # Push a lightweight command so Pi updates immediately (client polls /api/commands ~1.5s)
        enqueued = False
        try:
            if _enqueue_command_in_cfg(config, ns, nid, ctype='reload'):
                enqueued = True
        except Exception as e:
            app.logger.debug(f"enqueue reload (user cfg) failed (non-fatal): {e}")

        # Also enqueue into global cfg to cover devices not sending user_code
        try:
            gcfg2 = load_store_config()
            if _enqueue_command_in_cfg(gcfg2, ns, nid, ctype='reload'):
                # Save global cfg immediately
                save_store_config(gcfg2)
                enqueued = True
        except Exception as e:
            app.logger.debug(f"enqueue reload (global cfg) failed (non-fatal): {e}")

        # Attempt to notify the assigned Pi via WebSocket for instant apply
        try:
            # Prefer current config's mapping, else fallback to global
            pi_id = (config.get('screens', {})
                          .get(ns, {})
                          .get(nid, {})
                          .get('pi_id'))
            if not pi_id:
                gc = load_store_config()
                pi_id = (gc.get('screens', {})
                            .get(ns, {})
                            .get(nid, {})
                            .get('pi_id'))
            payload = {
                'store_id': ns,
                'screen_id': nid,
                'reason': 'rotation_changed'
            }
            if pi_id and pi_id in connected_pis:
                pi_session = connected_pis[pi_id]['sid']
                try:
                    logging.info('WS push: reload_client (targeted) pi_id=%s store=%s screen=%s reason=%s', pi_id, ns, nid, payload.get('reason'))
                except Exception:
                    pass
                socketio.emit('reload_client', payload, room=pi_session)
            else:
                try:
                    logging.info('WS push: reload_client (broadcast) store=%s screen=%s reason=%s', ns, nid, payload.get('reason'))
                except Exception:
                    pass
                # Fallback: broadcast with store/screen for client-side filtering
                socketio.emit('reload_client', payload, namespace='/')
        except Exception as e:
            app.logger.debug(f"reload_client emit failed (non-fatal): {e}")

        # Save user-specific config (if applicable)
        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
        else:
            save_store_config(config)

        return jsonify({'success': True, 'rotation': rotation, 'pushed': enqueued})
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
    
    ukey = _safe_user_key()
    config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
    # Normalize to canonical ids
    ns, nid = _normalize_screen_ref(config, str(store_id), str(screen_id))
    if ns and nid:
        # Persist orientation-related setting
        config['screens'][ns][nid][orientation] = value

        # Mirror into GLOBAL config so devices without user_code see the change
        try:
            global_cfg = load_store_config()
            gscreens = global_cfg.setdefault('screens', {}).setdefault(ns, {})
            if nid not in gscreens:
                gscreens[nid] = {}
            gscreens[nid][orientation] = value
            save_store_config(global_cfg)
        except Exception as e:
            app.logger.debug(f"mirror orientation to global failed (non-fatal): {e}")

        # Queue a reload so Pi applies orientation without waiting for playlist poll interval
        enqueued = False
        try:
            if _enqueue_command_in_cfg(config, ns, nid, ctype='reload'):
                enqueued = True
        except Exception as e:
            app.logger.debug(f"enqueue reload (user cfg) failed (non-fatal): {e}")

        # Also enqueue into global cfg to cover devices not sending user_code
        try:
            gcfg2 = load_store_config()
            if _enqueue_command_in_cfg(gcfg2, ns, nid, ctype='reload'):
                save_store_config(gcfg2)
                enqueued = True
        except Exception as e:
            app.logger.debug(f"enqueue reload (global cfg) failed (non-fatal): {e}")

        # Attempt to notify the assigned Pi via WebSocket for instant apply
        try:
            pi_id = (config.get('screens', {})
                          .get(ns, {})
                          .get(nid, {})
                          .get('pi_id'))
            if not pi_id:
                gc = load_store_config()
                pi_id = (gc.get('screens', {})
                            .get(ns, {})
                            .get(nid, {})
                            .get('pi_id'))
            payload = {
                'store_id': ns,
                'screen_id': nid,
                'reason': 'orientation_changed',
                'orientation': orientation,
                'value': value
            }
            if pi_id and pi_id in connected_pis:
                pi_session = connected_pis[pi_id]['sid']
                try:
                    logging.info('WS push: reload_client (targeted) pi_id=%s store=%s screen=%s reason=%s', pi_id, ns, nid, payload.get('reason'))
                except Exception:
                    pass
                socketio.emit('reload_client', payload, room=pi_session)
            else:
                try:
                    logging.info('WS push: reload_client (broadcast) store=%s screen=%s reason=%s', ns, nid, payload.get('reason'))
                except Exception:
                    pass
                socketio.emit('reload_client', payload, namespace='/')
        except Exception as e:
            app.logger.debug(f"reload_client emit failed (non-fatal): {e}")

        # Save config including queued command
        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
        else:
            save_store_config(config)
        return jsonify({'success': True, 'pushed': enqueued})
    
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
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        ns, nid = _normalize_screen_ref(config, str(store_id), str(screen_id))
        if not ns or not nid:
            return jsonify({'error': 'Screen not found'}), 404
        if mode == 'vertical':
            config['screens'][ns][nid]['vertical'] = True
            config['screens'][ns][nid]['horizontal'] = False
        elif mode == 'horizontal':
            config['screens'][ns][nid]['vertical'] = False
            config['screens'][ns][nid]['horizontal'] = True
        else:  # default
            config['screens'][ns][nid]['vertical'] = False
            config['screens'][ns][nid]['horizontal'] = False

        # Mirror orientation mode into GLOBAL config
        try:
            global_cfg = load_store_config()
            gscreens = global_cfg.setdefault('screens', {}).setdefault(ns, {})
            if nid not in gscreens:
                gscreens[nid] = {}
            if mode == 'vertical':
                gscreens[nid]['vertical'] = True
                gscreens[nid]['horizontal'] = False
            elif mode == 'horizontal':
                gscreens[nid]['vertical'] = False
                gscreens[nid]['horizontal'] = True
            else:
                gscreens[nid]['vertical'] = False
                gscreens[nid]['horizontal'] = False
            save_store_config(global_cfg)
        except Exception as e:
            app.logger.debug(f"mirror orientation mode to global failed (non-fatal): {e}")
        # Queue a reload so the Pi applies the change instantly
        try:
            _enqueue_command_in_cfg(config, ns, nid, ctype='reload')
        except Exception as e:
            app.logger.debug(f"enqueue reload failed (non-fatal): {e}")

        # Attempt to notify the assigned Pi via WebSocket for instant apply
        try:
            pi_id = (config.get('screens', {})
                          .get(ns, {})
                          .get(nid, {})
                          .get('pi_id'))
            if not pi_id:
                gc = load_store_config()
                pi_id = (gc.get('screens', {})
                            .get(ns, {})
                            .get(nid, {})
                            .get('pi_id'))
            payload = {
                'store_id': ns,
                'screen_id': nid,
                'reason': 'orientation_mode',
                'mode': mode
            }
            if pi_id and pi_id in connected_pis:
                pi_session = connected_pis[pi_id]['sid']
                try:
                    logging.info('WS push: reload_client (targeted) pi_id=%s store=%s screen=%s reason=%s', pi_id, ns, nid, payload.get('reason'))
                except Exception:
                    pass
                socketio.emit('reload_client', payload, room=pi_session)
            else:
                try:
                    logging.info('WS push: reload_client (broadcast) store=%s screen=%s reason=%s', ns, nid, payload.get('reason'))
                except Exception:
                    pass
                socketio.emit('reload_client', payload, namespace='/')
        except Exception as e:
            app.logger.debug(f"reload_client emit failed (non-fatal): {e}")

        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
        else:
            save_store_config(config)
        return jsonify({'success': True, 'mode': mode, 'pushed': True})
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
            
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        if store_id in config['screens'] and screen_id in config['screens'][store_id]:
            config['screens'][store_id][screen_id]['protected'] = protected
            if ukey:
                save_store_config_for_user_safe_key(ukey, config)
            else:
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

        ukey = _safe_user_key()
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
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

        if ukey:
            save_store_config_for_user_safe_key(ukey, cfg)
        else:
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
    
    # SECURITY FIX: Use user-scoped config based on pair code
    try:
        if code and len(code) == 4 and code.isdigit():
            user_key = _resolve_user_key_by_code(code)
            if user_key:
                config = load_store_config_for_user_safe_key(user_key)
                logging.info(f'🔒 Webplayer using user-scoped config for code {code} → {user_key}')
            else:
                logging.warning(f'⚠ Invalid webplayer code: {code}')
                config = load_store_config()
        else:
            logging.info('⚠ Webplayer accessed without valid code - using global config')
            config = load_store_config()
        screen_config = ensure_playlists_structure(config).get('screens', {}).get(store_id, {}).get(screen_id, {})
    except Exception as e:
        logging.error(f'❌ Webplayer config load error: {e}')
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
        
        print(f"DEBUG DELETE_SCREEN: Delete screen request - store_id: {store_id}, screen_id: {screen_id}")
        print(f"DEBUG DELETE_SCREEN: Request data: {data}")
        
        if not store_id or not screen_id:
            print("DEBUG DELETE_SCREEN: Missing store_id or screen_id")
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400

        ukey = _safe_user_key()
        print(f"DEBUG DELETE_SCREEN: User key: {ukey}")
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        print(f"DEBUG DELETE_SCREEN: Config loaded, screens: {config.get('screens', {})}")
        print(f"DEBUG DELETE_SCREEN: Available stores: {list(config['screens'].keys())}")
        
        if store_id not in config['screens']:
            print(f"DEBUG DELETE_SCREEN: Store {store_id} not found in config")
            print(f"DEBUG DELETE_SCREEN: Available stores in detail: {config.get('screens', {})}")
            return jsonify({'error': 'Store not found'}), 404
        
        print(f"DEBUG DELETE_SCREEN: Store {store_id} found, checking screen...")
        
        # Normalize provided id: accept both prefixed (e.g., "1881_screen1") and unprefixed ("screen1")
        actual_id = screen_id
        store_screens = config['screens'].get(store_id, {})
        print(f"DEBUG DELETE_SCREEN: Store screens: {list(store_screens.keys())}")
        print(f"DEBUG DELETE_SCREEN: Looking for screen_id: {screen_id}, actual_id: {actual_id}")
        
        if actual_id not in store_screens:
            print(f"DEBUG DELETE_SCREEN: Screen {actual_id} not directly in store {store_id}, attempting mapping")
            # If given id is prefixed but for a different store, remap suffix to this store
            if '_' in screen_id:
                short = screen_id.split('_', 1)[1]
                candidate = f"{store_id}_{short}"
                print(f"DEBUG DELETE_SCREEN: Trying prefixed variant: {candidate}")
                if candidate in store_screens:
                    actual_id = candidate
                    print(f"DEBUG DELETE_SCREEN: Found using prefixed variant: {actual_id}")
                elif short in store_screens:
                    actual_id = short
                    print(f"DEBUG DELETE_SCREEN: Found using short name: {actual_id}")
            else:
                # Unprefixed -> try store-prefixed variant
                candidate = f"{store_id}_{screen_id}"
                print(f"DEBUG DELETE_SCREEN: Trying unprefixed -> prefixed: {candidate}")
                if candidate in store_screens:
                    actual_id = candidate
                    print(f"DEBUG DELETE_SCREEN: Found using prefixed: {actual_id}")
        
        if actual_id not in store_screens:
            print(f"DEBUG DELETE_SCREEN: Screen {screen_id} not found (mapped={actual_id}) in store {store_id}")
            print(f"DEBUG DELETE_SCREEN: Available screens in store {store_id}: {list(store_screens.keys())}")
            return jsonify({'error': 'Screen not found'}), 404
        
        print(f"DEBUG DELETE_SCREEN: Found screen {actual_id} in store {store_id}")
        print(f"DEBUG DELETE_SCREEN: Screen data: {store_screens[actual_id]}")
        
        # Delete associated file if exists
        screen_data = config['screens'][store_id][actual_id]
        print(f"DEBUG DELETE_SCREEN: Screen data to delete: {screen_data}")
        file_deleted = False
        file_error_message = None
        
        if screen_data.get('file'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], screen_data['file'])
            print(f"DEBUG DELETE_SCREEN: Checking file: {filepath}")
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"✓ DELETE_SCREEN: Successfully deleted file: {filepath}")
                    file_deleted = True
                except PermissionError as e:
                    print(f"⚠ DELETE_SCREEN: Permission denied deleting file {filepath}: {e}")
                    print(f"⚠ DELETE_SCREEN: File will remain on server but screen will be deleted from config")
                    file_error_message = f"Screen deleted but file could not be removed due to permissions: {screen_data['file']}"
                    # Continue execution - don't let this stop the screen deletion
                except Exception as e:
                    print(f"⚠ DELETE_SCREEN: Could not delete file {filepath}: {e}")
                    file_error_message = f"Screen deleted but file could not be removed: {screen_data['file']}"
                    # Continue execution - don't let this stop the screen deletion
            else:
                print(f"DEBUG DELETE_SCREEN: File does not exist: {filepath}")
                file_deleted = True  # Consider it "deleted" if it doesn't exist
        
        # Remove screen from configuration
        print(f"DEBUG DELETE_SCREEN: About to delete screen from config...")
        del config['screens'][store_id][actual_id]
        print(f"DEBUG DELETE_SCREEN: Removed screen {actual_id} from config")

        # Clean up any sync groups referencing this screen
        print(f"DEBUG DELETE_SCREEN: Starting sync group cleanup...")
        try:
            groups = config.get('sync_groups') or {}
            print(f"DEBUG DELETE_SCREEN: Found {len(groups)} sync groups")
            changed = False
            for gid, grp in list(groups.items()):
                print(f"DEBUG DELETE_SCREEN: Checking group {gid}: {grp}")
                if grp.get('store_id') != store_id:
                    print(f"DEBUG DELETE_SCREEN: Group {gid} belongs to different store, skipping")
                    continue
                members = grp.get('members') or []
                if grp.get('base') == actual_id:
                    print(f"DEBUG DELETE_SCREEN: Group {gid} has deleted screen as base, removing entire group")
                    # Remove entire group; scrub sync_ref items from all member screens
                    for m in members:
                        msid = m.get('screen_id')
                        print(f"DEBUG DELETE_SCREEN: Cleaning member screen {msid}")
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
            print(f"DEBUG DELETE_SCREEN: Saving config with user key: {ukey}")
            save_store_config_for_user_safe_key(ukey, config)
        else:
            print(f"DEBUG DELETE_SCREEN: Saving config (no user key)")
            save_store_config(config)
        print(f"✓ DELETE_SCREEN: Configuration saved successfully")
        
        # Create user-friendly response message
        if file_error_message:
            # File couldn't be deleted, but screen was removed
            response_message = f'Screen {actual_id} deleted successfully'
            warning_message = 'File could not be removed from server (permission issue)'
        else:
            # Everything deleted successfully
            response_message = f'Screen {actual_id} deleted successfully'
            warning_message = None
        
        return jsonify({
            'success': True,
            'message': response_message,
            'warning': warning_message  # Optional warning field
        })
        
    except Exception as e:
        print(f"ERROR DELETE_SCREEN: Error deleting screen: {e}")
        import traceback
        print(f"ERROR DELETE_SCREEN: Traceback: {traceback.format_exc()}")
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

# ---------------- Schedule Filtering Helpers (match Pi client logic) ----------------
def parse_time_string(time_str, now):
    """Parse time string - matches custom_player.py logic + dashboard ISO format"""
    if not time_str:
        return None
    
    time_str = str(time_str).strip()
    if not time_str:
        return None
    
    # Try mm/dd/yyyy HH:MM:SS format (from dashboard date picker)
    if len(time_str) == 19 and time_str.count('/') == 2 and time_str.count(':') == 2:
        try:
            return datetime.strptime(time_str, '%m/%d/%Y %H:%M:%S')
        except:
            pass
    
    # Try mm/dd/yyyy format (date only)
    if len(time_str) == 10 and time_str.count('/') == 2:
        try:
            return datetime.strptime(time_str, '%m/%d/%Y')
        except:
            pass
    
    # ISO datetime with T: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM
    if 'T' in time_str:
        try:
            # Try with seconds
            return datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
        except:
            try:
                # Try without seconds
                return datetime.strptime(time_str, '%Y-%m-%dT%H:%M')
            except:
                return None
    
    # Full datetime with space: YYYY-MM-DD HH:MM:SS
    if len(time_str) == 19 and time_str.count('-') == 2 and time_str.count(':') == 2:
        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None
    
    # Date only: YYYY-MM-DD
    if len(time_str) == 10 and time_str.count('-') == 2:
        try:
            return datetime.strptime(time_str, '%Y-%m-%d')
        except:
            return None
    
    # Time only: HH:MM or HH:MM:SS
    if ':' in time_str:
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        except:
            return None
    
    return None


def is_in_time_window(now, start_str, end_str, days=None, store_tz=None):
    """Check if now is within time window - MATCHES DASHBOARD
    
    Args:
        now: Current time (should be in store's timezone)
        start_str: Start time string
        end_str: End time string  
        days: List or space-separated string of days (mon, tue, etc.)
        store_tz: Timezone name (e.g. 'Australia/Sydney') - for logging only
    """
    # Check weekday first
    if days:
        weekday = ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]
        print(f"DEBUG SCHEDULE: Current weekday='{weekday}' ({now.strftime('%Y-%m-%d %H:%M:%S')} {store_tz or 'UTC'}), Required days={days}, Type={type(days)}")
        # Handle both string and list formats
        if isinstance(days, str):
            days_list = days.split()
        else:
            days_list = days if isinstance(days, list) else [days]
        if weekday not in days_list:
            print(f"DEBUG SCHEDULE: Weekday '{weekday}' not in {days_list} - BLOCKING")
            return False
        print(f"DEBUG SCHEDULE: Weekday '{weekday}' found in {days_list} - OK")
    
    if not (start_str or end_str):
        return True
    
    # Parse times
    start_time = parse_time_string(start_str, now) if start_str else None
    end_time = parse_time_string(end_str, now) if end_str else None
    
    # Date-only normalization
    if end_str and len(end_str) == 10 and end_time:
        end_time = end_time.replace(hour=23, minute=59, second=59)
    if start_str and len(start_str) == 10 and not end_str and start_time:
        end_time = start_time.replace(hour=23, minute=59, second=59)
    if end_str and len(end_str) == 10 and not start_str and end_time:
        start_time = end_time.replace(hour=0, minute=0, second=0)
    
    # Handle overnight wrap (e.g., 22:00 - 02:00)
    if start_time and end_time:
        time_only = (':' in (start_str or '') and len(start_str or '') <= 8)
        if end_time < start_time:
            if not time_only and start_time.date() == end_time.date():
                # Same-date absolute: treat as end + 1 day
                end_time_plus = end_time + timedelta(days=1)
                return start_time <= now <= end_time_plus
            # Overnight: active if after start OR before end
            return now >= start_time or now <= end_time
        else:
            # Normal: active if between start and end
            return start_time <= now <= end_time
    
    # Single boundary
    if start_time and now < start_time:
        return False
    if end_time and now > end_time:
        return False
    
    return True


def is_item_active_now(item, timezone_offset_hours=0):
    """Check if item should play based on schedule - MATCHES DASHBOARD LOGIC
    
    Args:
        item: Playlist item dictionary
        timezone_offset_hours: Hours to add to UTC (e.g. 11 for Sydney DST)
    """
    # Get current time in store's timezone
    if timezone_offset_hours:
        now = datetime.now() + timedelta(hours=timezone_offset_hours)
        print(f"DEBUG SCHEDULE: Server UTC + {timezone_offset_hours}h = {now.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        now = datetime.now()
        print(f"DEBUG SCHEDULE: Using server time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"DEBUG SCHEDULE: Current time: {now.strftime('%Y-%m-%d %H:%M:%S %A')}")
    print(f"DEBUG SCHEDULE: Checking item: {item.get('file', 'unknown')}")
    
    # Check if item itself is enabled
    if not item.get('enabled', True):
        print(f"DEBUG SCHEDULE: Item disabled - BLOCKING")
        return False
    
    # Check multiple schedule windows first (priority)
    schedule_windows = item.get('schedule', [])
    print(f"DEBUG SCHEDULE: Schedule windows: {schedule_windows}")
    if schedule_windows:
        for window in schedule_windows:
            # Skip disabled windows
            if not window.get('enabled', True):
                print(f"DEBUG SCHEDULE: Window disabled - skipping")
                continue
            print(f"DEBUG SCHEDULE: Checking window: start={window.get('start')}, end={window.get('end')}, days={window.get('days')}")
            if is_in_time_window(now, window.get('start'), window.get('end'), window.get('days'), f"UTC+{timezone_offset_hours}"):
                print(f"DEBUG SCHEDULE: Window ACTIVE - item should play")
                return True  # Active in at least one enabled window
        print(f"DEBUG SCHEDULE: No active windows - BLOCKING")
        return False  # No enabled windows are active
    
    # Check single start/end window (legacy format)
    start = item.get('start')
    end = item.get('end')
    days = item.get('days', [])
    print(f"DEBUG SCHEDULE: Legacy format - start={start}, end={end}, days={days}")
    
    if start or end or days:
        return is_in_time_window(now, start, end, days, f"UTC+{timezone_offset_hours}")
    
    # No schedule restrictions = always active
    return True

# ---------------- Playlist API Endpoints (moved above app.run) ----------------
@app.route('/debug/schedule/<store_id>/<screen_id>')
def debug_schedule(store_id, screen_id):
    """Debug endpoint to see schedule filtering logic"""
    from datetime import datetime
    header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
    user_key = _resolve_user_key_by_code(header_code)
    if not user_key:
        return {'error': 'pair code required'}, 403
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(user_key))
    screens = cfg.get('screens', {}).get(store_id, {})
    screen = screens.get(screen_id)
    if not screen:
        return {'error': 'screen not found'}, 404
    
    now = datetime.now()
    result = {
        'server_time': now.strftime('%Y-%m-%d %H:%M:%S %A'),
        'server_weekday': ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()],
        'playlist_items': []
    }
    
    for item in screen.get('playlist', []):
        item_debug = {
            'file': item.get('file'),
            'enabled': item.get('enabled', True),
            'start': item.get('start'),
            'end': item.get('end'),
            'days': item.get('days'),
            'schedule': item.get('schedule', []),
            'is_active': is_item_active_now(item)
        }
        result['playlist_items'].append(item_debug)
    
    return jsonify(result)

@app.route('/playlist/<store_id>/<screen_id>')
@slowlog(300)
@with_etag_json
def get_playlist(store_id, screen_id):
    print(f"DEBUG: GET /playlist {store_id} {screen_id}")
    
    # SECURITY FIX: Always prefer logged-in session user over pair code header
    # This prevents cross-user data leakage when authenticated user enters another user's pairing code
    session_ukey = _safe_user_key()
    
    if session_ukey:
        # User is logged in - ALWAYS use their session, IGNORE any pair code in header
        ukey = session_ukey
        print(f"DEBUG: Using session user key: {ukey}")
    else:
        # No logged-in session - try pair code from header
        header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
        user_key = _resolve_user_key_by_code(header_code)
        
        if user_key:
            # Valid pair code provided
            ukey = user_key
            print(f"DEBUG: Using pair code user key: {ukey}")
        else:
            # No session and no valid pair code - check if public access allowed
            allow_public = os.environ.get('ALLOW_PUBLIC_PLAYLIST', '').lower() in ('1', 'true', 'yes', 'y')
            public_stores = {s.strip() for s in (os.environ.get('PUBLIC_PLAYLIST_STORES') or '').split(',') if s.strip()}
            
            if allow_public and (not public_stores or store_id in public_stores):
                ukey = None  # Use global/shared config path
                print(f"DEBUG: Using public/global config for store {store_id}")
            else:
                print(f"DEBUG: Access denied - no session, no pair code, public access not allowed")
                return {'success': False, 'error': 'pair code required'}, 403
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
            # Persist in whichever config space we're using (use ukey from above)
            try:
                if ukey:
                    save_store_config_for_user_safe_key(ukey, cfg)
                else:
                    save_store_config(cfg)
            except Exception:
                pass
            screen = sdata
            print(f"DEBUG: Auto-created screen entry {store_id}/{screen_id}")
        except Exception:
            print("DEBUG: Screen not found for playlist (after mapping)")
            return jsonify({'success': False, 'error': 'screen not found'}), 404
    # FIXED: Auto-clean missing-file items (local disk only) - DO NOT RUN IF R2 IS ENABLED
    # This was causing playlist data loss when files exist on CDN but not locally
    if not r2_enabled():
        original = screen.get('playlist', [])
        cleaned = []
        removed = 0
        for item in original:
            f = item.get('file')
            if f:
                path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                if not os.path.exists(path):
                    # SAFETY: Only remove if file path looks like a local upload, not CDN URL
                    if not f.startswith('http') and not f.startswith('users/'):
                        removed += 1
                        print(f"DEBUG: Removing local missing file: {f}")
                        continue
            cleaned.append(item)
            if removed:
                screen['playlist'] = cleaned
                if ukey:
                    save_store_config_for_user_safe_key(ukey, cfg)
                else:
                    save_store_config(cfg)
            print(f"DEBUG: Auto-removed {removed} missing LOCAL file playlist items")
    else:
        print("DEBUG: R2 enabled - skipping local file existence check to preserve CDN-based playlists")
    pl = screen.get('playlist', [])
    # Effective User-Agent detection with optional override via query for debugging/testing
    try:
        _ua_override = (request.args.get('ua_override') or request.args.get('ua') or '').strip().lower()
    except Exception:
        _ua_override = ''
    try:
        _ua_header = request.headers.get('User-Agent', '').strip().lower()
    except Exception:
        _ua_header = ''
    ua_effective = _ua_override or _ua_header
    if _ua_override:
        print(f"DEBUG: UA override in query detected -> using ua='{ua_effective}' (header was '{_ua_header}')")
    
    # Check if schedule filtering should be skipped (for dashboard management)
    skip_schedule_filter = request.args.get('skip_schedule_filter', '').lower() in ('1', 'true', 'yes')
    debug_schedule = request.args.get('debug_schedule', '').lower() in ('1', 'true', 'yes')
    
    # Get store timezone from configuration
    # For now, hardcode Sydney timezone offset (UTC+10 or UTC+11 for DST)
    # TODO: Add timezone field to store config in dashboard
    store_tz = 'Australia/Sydney'
    timezone_offset_hours = 11  # Sydney is currently in DST (UTC+11)
    print(f"DEBUG SCHEDULE: Using timezone: {store_tz} (UTC+{timezone_offset_hours})")
    
    if debug_schedule:
        # Return debug info about schedule filtering
        now = datetime.now() + timedelta(hours=timezone_offset_hours)
        
        debug_info = {
            'store_timezone': store_tz,
            'timezone_offset': timezone_offset_hours,
            'server_time_utc': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'store_time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'store_weekday': ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()],
            'items': []
        }
        for item in pl:
            debug_info['items'].append({
                'file': item.get('file', 'unknown')[:60],
                'days': item.get('days'),
                'start': item.get('start'),
                'end': item.get('end'),
                'enabled': item.get('enabled', True),
                'is_active': is_item_active_now(item, timezone_offset_hours)
            })
        return jsonify(debug_info)
    
    # Decorate with public URL and last known status for clients/dashboard
    last_status = screen.get('last_item_status') or {}
    out = []
    for item in pl:
        try:
            # SCHEDULE FILTERING: Only include items that should be playing now
            # Skip filtering for dashboard so all items can be managed
            if not skip_schedule_filter:
                is_active = is_item_active_now(item, timezone_offset_hours)
                print(f"DEBUG: Item '{item.get('file', 'unknown')[:60]}' active={is_active}, days={item.get('days')}")
                if not is_active:
                    print(f"DEBUG: Skipping item - not active based on schedule")
                    continue
                else:
                    print(f"DEBUG: ✓ Item PASSED schedule filter - will be included")
            
            it = dict(item)

            # Always start with the plain public URL
            base_url = build_public_url(it.get('file'))
            it['url'] = base_url
            # (Retain previous verbosity for troubleshooting)
            if base_url:
                print(f"DEBUG: Base media URL resolved: {base_url}")
            else:
                print("DEBUG: Base URL missing (no file?)")

            # Ensure the effect is serialized explicitly for clients
            if 'effect' in item and isinstance(item.get('effect'), str):
                it['effect'] = item.get('effect')
            # If part of a sync group, attach group timing info
            try:
                # Only augment items that explicitly belong to a sync group.
                # Do NOT infer sync_ref for unrelated items on the same screen to avoid mislabeling normal videos as slices.
                sref = item.get('sync_ref') if isinstance(item, dict) else None
                gid = None
                if isinstance(sref, dict):
                    gid = sref.get('group')
                if gid:
                    grp = (cfg.get('sync_groups') or {}).get(gid) or {}
                    se = grp.get('start_epoch') or grp.get('start') or grp.get('created_at')
                    it.setdefault('sync_ref', dict(sref or {}))
                    if se:
                        it['sync_ref']['start_epoch'] = int(se)
                    
                    # CRITICAL: Always include count, mode, and order for Android TV clients
                    # Android ExoPlayer needs these fields to calculate video slice positions
                    try:
                        cnt = int(grp.get('count') or len(grp.get('members', [])) or 1)
                        it['sync_ref']['count'] = cnt
                    except Exception:
                        it['sync_ref']['count'] = 1
                    
                    # Always include mode for video slicing direction
                    it['sync_ref']['mode'] = grp.get('mode') or 'split-h'
                    
                    # Always include order/position for this screen in the sync group
                    try:
                        # Find current screen's order in group members; consider both short and store-prefixed IDs
                        alt_ids = {screen_id}
                        try:
                            if '_' in screen_id:
                                short = screen_id.split('_', 1)[1]
                                alt_ids.add(short)
                            else:
                                alt_ids.add(f"{store_id}_{screen_id}")
                        except Exception:
                            pass
                        found = False
                        for i, mem in enumerate(grp.get('members', [])):
                            sid = mem.get('screen_id')
                            if sid and sid in alt_ids:
                                it['sync_ref']['order'] = mem.get('order', i)
                                found = True
                                break
                        if not found:
                            # Preserve existing order if provided on the item; otherwise default to 0
                            try:
                                ex_order = sref.get('order')
                                it['sync_ref']['order'] = int(ex_order) if ex_order is not None else 0
                            except Exception:
                                it['sync_ref']['order'] = 0
                    except Exception:
                        # As a last resort, leave existing order or 0
                        try:
                            ex_order = sref.get('order')
                            it['sync_ref']['order'] = int(ex_order) if ex_order is not None else 0
                        except Exception:
                            it['sync_ref']['order'] = 0
            except Exception:
                pass
            # --- Dynamic slice URL assignment (after sync_ref augmentation) ---
            try:
                sref2 = it.get('sync_ref') if isinstance(it, dict) else None
                media_type = it.get('media_type') or item.get('media_type')
                if isinstance(sref2, dict) and media_type == 'video':
                    scount = int(sref2.get('count') or 1)
                    sorder = int(sref2.get('order') or 0)
                    smode = (sref2.get('mode') or 'split-h').lower()
                    if scount > 1:
                        ua = ua_effective
                        android_tokens = ('android', 'okhttp', 'exoplayer', 'nvidia', 'bravia', 'shield')
                        pi_tokens = ('raspberrypi', 'raspberry pi', 'phtv-pi')
                        is_android = any(tok in ua for tok in android_tokens)
                        is_pi = any(tok in ua.lower() for tok in pi_tokens)
                        is_slice_client = is_android or is_pi  # Both Android and Pi get slice URLs
                        vfile = it.get('file')
                        print(f"DEBUG: Slice decision ua='{ua}' is_android={is_android} is_pi={is_pi} count={scount} order={sorder} mode={smode}")
                        if vfile:
                            slice_url = url_for('slice_video', video_path=vfile, _external=True)
                            # Force main domain for bypass consistency
                            slice_url = slice_url.replace('api.everydayadvertise.com', 'everydayadvertise.com')
                            slice_url += f"?slice_mode={smode}&slice_count={scount}&slice_order={sorder}"
                            # Add cache-busting for all secondary screens to ensure bypass works
                            if sorder >= 1:
                                import time
                                slice_url += f"&cb={int(time.time())}"
                            # Always expose slice_url so clients can opt-in reliably
                            it['slice_url'] = slice_url
                            it['slice_info'] = {'mode': smode, 'count': scount, 'order': sorder}
                            it['slice_aware'] = True
                            # Provide a UA-agnostic preferred_url to simplify client logic
                            it['preferred_url'] = slice_url
                            if is_slice_client:
                                # For Android and Pi, prefer server-sliced URL
                                it['url'] = slice_url
                                client_type = "Android" if is_android else "Pi" if is_pi else "Slice-client"
                                print(f"DEBUG: Assigned slice URL ({client_type}): {slice_url}")
                            else:
                                # Non-slice clients: leave base URL; client may CSS/JS crop, but can still read slice_url
                                print(f"DEBUG: Exposed slice_url (non-slice client): {slice_url}")
                        else:
                            print("DEBUG: Cannot assign slice URL (missing file field)")
            except Exception as e_slice:
                print(f"WARNING: Slice URL assignment error: {e_slice}")
            # Image display hints for clients (e.g., Android TV): prefer fill/cover (match Pi/webplayer)
            try:
                mt_hint = it.get('media_type') or item.get('media_type') or classify_media(it.get('file') or '')
                if mt_hint == 'image':
                    # Hints: 'image_fit' is semantic, 'image_scale' mirrors Android ScaleType names
                    # If this playlist is being served to Android clients, instruct them to center-crop to avoid letterboxing.
                    # For other clients, these are harmless hints.
                    try:
                        ua = request.headers.get('User-Agent','')
                        is_android = ('Android' in ua) or ('TV' in ua and 'Android' in ua)
                    except Exception:
                        is_android = False
                    if is_android:
                        it.setdefault('image_fit', 'cover')           # fill screen, keep aspect, crop if needed
                        it.setdefault('image_scale', 'center_crop')    # Android ImageView.ScaleType equivalent
                    else:
                        # Non-Android default remains cover to match webplayer/Pi behavior
                        it.setdefault('image_fit', 'cover')
                        it.setdefault('image_scale', 'center_crop')
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
                    'count': int(grp.get('count') or len(grp.get('members', [])) or 1),
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
                                # Derive a reasonable group id, count, mode, and order so followers can slice too
                                try:
                                    # Try to find an existing declared sync group for these siblings
                                    sync_groups = (cfg.get('sync_groups') or {})
                                    derived_gid = None
                                    derived_count = None
                                    derived_mode = None
                                    # Prefer a group that lists the base screen among members
                                    for gid, grp in sync_groups.items():
                                        try:
                                            for mem in (grp.get('members') or []):
                                                sid = mem.get('screen_id')
                                                if sid and (sid == f"{store_id}_{base_short}" or sid == base_short):
                                                    derived_gid = gid
                                                    try:
                                                        derived_count = int(grp.get('count') or len(grp.get('members', [])) or 1)
                                                    except Exception:
                                                        derived_count = None
                                                    derived_mode = grp.get('mode') or 'split-h'
                                                    raise StopIteration
                                        except StopIteration:
                                            break
                                        except Exception:
                                            continue
                                    # If no explicit group, estimate count from sibling screens that exist in config
                                    if derived_count is None:
                                        try:
                                            # Count consecutive siblings (prefix1..prefixN) that exist
                                            n = 1
                                            while True:
                                                sid_short = f"{prefix}{n}"
                                                sid_prefx = f"{store_id}_{sid_short}"
                                                if (screens or {}).get(sid_prefx) or (screens or {}).get(sid_short):
                                                    n += 1
                                                    if n > 20:
                                                        break  # sanity
                                                else:
                                                    break
                                            # n-1 because we increment after last existing
                                            derived_count = max(1, n - 1)
                                        except Exception:
                                            derived_count = 1
                                    if not derived_mode:
                                        derived_mode = 'split-h'
                                    if not derived_gid:
                                        derived_gid = f"implicit:{store_id}:{prefix}"
                                except Exception:
                                    derived_gid = f"implicit:{store_id}:{prefix}"
                                    derived_count = 1
                                    derived_mode = 'split-h'
                                # Compute this follower's order (0-based)
                                follower_order = max(0, num - 1)
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
                                        'group': derived_gid,
                                        'role': 'follower',
                                        'order': follower_order,
                                        'virtual': True,
                                        'start_epoch': se,
                                        # Ensure count>=2 to trigger slicing across siblings when applicable
                                        'count': int(derived_count or 1),
                                        'mode': derived_mode
                                    }
                                })
    except Exception:
        pass
    # Post-process: ensure any synthesized or late-added sync items also get slice URLs for Android clients
    try:
        ua = ua_effective
        android_tokens = ('android', 'okhttp', 'exoplayer', 'nvidia', 'bravia', 'shield')
        pi_tokens = ('raspberrypi', 'raspberry pi', 'phtv-pi')
        is_android = any(tok in ua for tok in android_tokens)
        is_pi = any(tok in ua.lower() for tok in pi_tokens)
        is_slice_client = is_android or is_pi  # Both Android and Pi get slice URLs
        for i, it in enumerate(out):
            try:
                if not isinstance(it, dict):
                    continue
                media_type = it.get('media_type') or classify_media(it.get('file') or '')
                sref = it.get('sync_ref') if isinstance(it.get('sync_ref'), dict) else None
                if media_type != 'video' or not sref:
                    continue
                scount = int(sref.get('count') or 1)
                if scount <= 1:
                    continue
                sorder = int(sref.get('order') or 0)
                smode = str(sref.get('mode') or 'split-h').lower()
                vfile = it.get('file')
                if not vfile:
                    continue
                # Always expose slice_url/info so clients can opt-in
                slice_url = url_for('slice_video', video_path=vfile, _external=True)
                # Force main domain for bypass consistency
                slice_url = slice_url.replace('api.everydayadvertise.com', 'everydayadvertise.com')
                slice_url += f"?slice_mode={smode}&slice_count={scount}&slice_order={sorder}"
                # Add cache-busting for all secondary screens to ensure bypass works
                if sorder >= 1:
                    import time
                    slice_url += f"&cb={int(time.time())}"
                it['slice_url'] = it.get('slice_url') or slice_url
                it['slice_info'] = it.get('slice_info') or {'mode': smode, 'count': scount, 'order': sorder}
                it['slice_aware'] = True
                # Provide UA-agnostic preferred_url for clients
                it['preferred_url'] = it.get('preferred_url') or slice_url
                # For Android and Pi UA, prefer server slice URL in main url field if not already set
                cur_url = it.get('url') or ''
                if is_slice_client and '/slice-video/' not in cur_url:
                    it['url'] = slice_url
                    client_type = "Android" if is_android else "Pi" if is_pi else "Slice-client"
                    print(f"DEBUG: Post-assigned slice URL for item[{i}] ({client_type}): {slice_url}")
            except Exception as _e_postslice:
                print(f"WARNING: Post slice assign failed for item[{i}]: {_e_postslice}")
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

# Legacy query-parameter playlist endpoint for backward compatibility
@app.route('/playlist')
@slowlog(300)
@with_etag_json
def legacy_playlist_query():
    store_id = request.args.get('store_id') or request.args.get('store') or ''
    screen_id = request.args.get('screen_id') or request.args.get('screen') or ''
    if not store_id or not screen_id:
        return {'success': False, 'error': 'store_id and screen_id required'}, 400
    return get_playlist(store_id, screen_id)

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

        # AUTO-SLICING: Detect if this is a multi-screen video and auto-slice it
        sliced_files = []
        media_type = classify_media(filename)
        
        if media_type == 'video' and FFMPEG_AVAILABLE:
            print("[upload_media] Video detected, checking for multi-screen layout...")
            
            # Detect video resolution
            video_info = detect_video_resolution(dest)
            
            if video_info:
                width = video_info['width']
                height = video_info['height']
                
                # Calculate screen layout
                layout_info = calculate_screen_layout(width, height)
                screen_count = layout_info['screen_count']
                
                if screen_count > 1:
                    print(f"[upload_media] Multi-screen video detected: {screen_count} screens ({layout_info['layout']} layout)")
                    
                    # Start background slicing job instead of blocking
                    job_id = f"slice_{uuid.uuid4().hex[:12]}"
                    base_name = filename.rsplit('.', 1)[0]
                    
                    # Start background thread
                    slice_thread = threading.Thread(
                        target=_background_slice_and_upload,
                        args=(job_id, dest, req_prefix, base_name, layout_info, video_info, local_dir),
                        daemon=True
                    )
                    slice_thread.start()
                    
                    print(f"[upload_media] Started background slicing job: {job_id}")
                    
                    # Return immediately with job ID
                    # Upload original file to R2 first
                    if r2_enabled():
                        with open(dest, 'rb') as fh:
                            data = fh.read()
                        key = _join_prefix_key(req_prefix, filename)
                        r2_put_bytes(key, data, content_type=_guess_mime(filename))
                        print(f"[upload_media] R2 put ok key={key}")
                    
                    dt = int((time.time()-t0)*1000)
                    key = _join_prefix_key(req_prefix, filename)
                    print(f"[upload_media] done (async) file={key} ms={dt}")
                    
                    return jsonify({
                        'success': True,
                        'filename': key,
                        'media_type': media_type,
                        'url': build_public_url(key),
                        'slice_job_id': job_id,
                        'screen_count': screen_count,
                        'layout': layout_info['layout'],
                        'message': f'Processing {screen_count}-screen video in background...'
                    })
                
                else:
                    print(f"[upload_media] Single screen video ({width}x{height}), no slicing needed")
            
            else:
                print("[upload_media] Could not detect video resolution, skipping auto-slice")

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
        
        # Return response with slice information if available
        response_data = {
            'success': True, 
            'filename': key, 
            'media_type': media_type, 
            'url': build_public_url(key)
        }
        
        if sliced_files:
            response_data['sliced_files'] = sliced_files
            response_data['screen_count'] = len(sliced_files)
            response_data['layout'] = layout_info['layout']
            print(f"[upload_media] Returning response with {len(sliced_files)} sliced files")
        else:
            # For videos that weren't sliced (single-screen or detection failed),
            # include screen_count=1 so dashboard knows to show single-screen message
            if media_type == 'video':
                response_data['screen_count'] = 1
                print(f"[upload_media] Returning single-screen video response")
        
        return jsonify(response_data)
    except Exception as e:
        print(f"upload_media error: {e}")
        import traceback as _tb
        _tb.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- Check auto-slice job status ----
@app.route('/slice_job_status/<job_id>', methods=['GET'])
@login_required
def slice_job_status(job_id):
    """Check the status of a background slicing job."""
    job_info = _get_job_status(job_id)
    if not job_info:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    return jsonify({'success': True, **job_info})

# ---- List all completed slice jobs ----
@app.route('/api/list_slice_jobs', methods=['GET'])
@login_required
def list_slice_jobs():
    """
    List all completed slice jobs, sorted by most recent first.
    Used by the "Auto-Sync Screens" button to find the last job.
    """
    try:
        import os
        import glob
        
        job_dir = '/tmp/pizza_hut_tv_jobs'
        if not os.path.exists(job_dir):
            return jsonify({'success': True, 'jobs': []})
        
        # Get all job files
        job_files = glob.glob(os.path.join(job_dir, 'slice_*.json'))
        
        # Read and parse each job
        jobs = []
        for job_file in job_files:
            try:
                # Get file modification time for sorting
                mtime = os.path.getmtime(job_file)
                
                with open(job_file, 'r') as f:
                    job_data = json.load(f)
                
                # Extract job_id from filename
                job_id = os.path.basename(job_file).replace('.json', '')
                
                jobs.append({
                    'job_id': job_id,
                    'status': job_data.get('status', 'unknown'),
                    'progress': job_data.get('progress', 0),
                    'result': job_data.get('result', []),
                    'layout': job_data.get('layout', 'horizontal'),
                    'screen_count': job_data.get('screen_count', 0),
                    'timestamp': mtime
                })
            except Exception as e:
                print(f"[list_slice_jobs] Error reading {job_file}: {e}")
                continue
        
        # Sort by timestamp (most recent first)
        jobs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Only return completed jobs
        completed_jobs = [j for j in jobs if j['status'] == 'complete']
        
        print(f"[list_slice_jobs] Found {len(completed_jobs)} completed jobs out of {len(jobs)} total")
        
        return jsonify({
            'success': True,
            'jobs': completed_jobs,
            'total': len(completed_jobs)
        })
        
    except Exception as e:
        print(f"[list_slice_jobs] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- Auto-create sync screens from sliced videos ----
@app.route('/auto_create_sync_screens', methods=['POST'])
@login_required
def auto_create_sync_screens():
    """
    Automatically create sync screens and add pre-sliced videos.
    Body: {sliced_files: [{screen_number, filename, url, size}], layout: 'horizontal'|'vertical', store_id: int}
    """
    try:
        print("[auto_create_sync_screens] === ENDPOINT CALLED ===")
        data = request.get_json()
        print(f"[auto_create_sync_screens] Received data: {data}")
        sliced_files = data.get('sliced_files', [])
        layout = data.get('layout', 'horizontal')
        store_id = data.get('store_id')
        
        print(f"[auto_create_sync_screens] sliced_files count: {len(sliced_files)}, layout: {layout}, store_id: {store_id}")
        
        if not sliced_files or not store_id:
            print(f"[auto_create_sync_screens] ERROR: Missing data - sliced_files: {bool(sliced_files)}, store_id: {bool(store_id)}")
            return jsonify({'success': False, 'error': 'Missing sliced_files or store_id'}), 400
        
        # Get user session info for config loading
        user_info = session.get('user', {})
        if not user_info:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 403
        
        # Use the existing config loading system
        cfg = ensure_playlists_structure(load_store_config())
        if not cfg:
            return jsonify({'success': False, 'error': 'Could not load config'}), 500
        
        ns = str(store_id)
        if ns not in cfg.get('screens', {}):
            cfg['screens'][ns] = {}
        
        # Generate a shared start_epoch for all sync screens (aligned to current time)
        import time
        start_epoch = int(time.time())
        sync_group = f"sync_group_{int(time.time())}"
        
        print(f"[auto_create_sync_screens] Creating sync group: {sync_group} with start_epoch: {start_epoch}")
        
        created_screens = []
        
        # Create sync screens for each sliced video (keeping individual files for speed)
        for slice_info in sliced_files:
            screen_num = slice_info.get('screen_number', 0)
            filename = slice_info.get('filename', '')
            url = slice_info.get('url', '')
            
            if not screen_num or not filename:
                print(f"[auto_create_sync_screens] Skipping incomplete slice: {slice_info}")
                continue
            
            screen_id = f"{store_id}_screen{screen_num}"
            
            # Create new screen with ENHANCED sync configuration for individual video files
            screen_config = {
                'horizontal': (layout == 'horizontal'),
                'file': url or filename,  # Set file for dashboard display
                'playlist': [{
                    'file': filename,       # Use individual sliced video file for speed
                    'url': url,            # Individual CDN URL for fast loading
                    'duration': 0,         # Auto-detect
                    'type': 'video',
                    'sync_ref': {
                        'start_epoch': start_epoch,
                        'group': sync_group,
                        'precision_mode': 'high',  # Enable high-precision sync
                        'preload_buffer': 2000,    # 2s preload for smooth sync start
                        'sync_tolerance': 10       # 10ms tolerance for perfect sync
                    }
                }],
                'fresh': True
            }
            
            cfg['screens'][ns][screen_id] = screen_config
            created_screens.append(screen_id)
            
            print(f"[auto_create_sync_screens] Created screen {screen_id} with sync_ref: start_epoch={start_epoch}, group={sync_group}")
        
        # Save updated config using the existing save system
        save_store_config(cfg)
        
        print(f"[auto_create_sync_screens] === SUCCESS === Created {len(created_screens)} screens: {created_screens}")
        
        return jsonify({
            'success': True,
            'screens': created_screens,
            'count': len(created_screens),
            'message': f'Created {len(created_screens)} sync screens with videos'
        })
        
    except Exception as e:
        print(f"ERROR: auto_create_sync_screens failed: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Allow YouTube URLs (youtube:VIDEO_ID format)
        is_youtube = key.startswith('youtube:')
        
        # Final check: key must begin with user_root/ OR be a YouTube URL
        if not is_youtube and not key.startswith(user_root + '/'):
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
        
        # Skip file type validation for YouTube URLs
        if not is_youtube and not allowed_file(key):
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
        
        # Auto-create screen if it doesn't exist
        if store_id in config.get('screens', {}):
            # Determine if this is a promo screen (vertical) or regular screen (horizontal)
            screen_type = screen_id.split('_', 1)[-1] if '_' in screen_id else screen_id
            is_promo = screen_type.startswith('promo')
            
            # Create the screen
            config['screens'][store_id][screen_id] = {
                'file': None,
                'vertical': is_promo,
                'horizontal': not is_promo,
                'rotation': 0,
                'protected': False,
                'playlist': []
            }
            
            # Now assign to the newly created screen
            _assign_to(store_id, screen_id)
            save_store_config(config)
            
            return jsonify({
                'success': True,
                'filename': key,
                'url': build_public_url(key),
                'media_type': classify_media(key),
                'store_id': store_id,
                'screen_id': screen_id,
                'applied_to_all': False,
                'screen_created': True
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
    # SECURITY FIX: Always prefer logged-in session user over pair code header
    session_ukey = _safe_user_key()
    logging.info(f'🔍 /stores called - session_ukey={session_ukey}')
    if session_ukey:
        ukey = session_ukey
        logging.info(f'✓ Using session user: {ukey}')
    else:
        header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
        user_key = _resolve_user_key_by_code(header_code)
        logging.info(f'⚠ No session user, trying pair code: {header_code} → {user_key}')
        if not user_key:
            return {'success': False, 'error': 'pair code required'}, 403
        ukey = user_key
    
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    stores_count = len(cfg.get('stores', []))
    logging.info(f'📊 Returning {stores_count} stores for user: {ukey}')
    return {'success': True, 'stores': cfg.get('stores', [])}

@app.route('/screens_list/<store_id>')
@with_etag_json
def list_screens_legacy_array(store_id):
    """Legacy endpoint returning an array of {'id': screen_id} objects.

    NOTE: The dashboard now uses /screens/<store_id> which returns a mapping
    of screen_id -> screen_object. This endpoint retained for older TV clients.
    """
    # SECURITY FIX: Always prefer logged-in session user over pair code header
    session_ukey = _safe_user_key()
    logging.info(f'🔍 /screens_list/{store_id} called - session_ukey={session_ukey}')
    if session_ukey:
        ukey = session_ukey
        logging.info(f'✓ Using session user: {ukey}')
    else:
        header_code = request.headers.get('X-User-Code') or request.args.get('user_code')
        user_key = _resolve_user_key_by_code(header_code)
        logging.info(f'⚠ No session user, trying pair code: {header_code} → {user_key}')
        if not user_key:
            return {'success': False, 'error': 'pair code required'}, 403
        ukey = user_key
    cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
    if store_id not in (cfg.get('screens') or {}):
        logging.warning(f'❌ Store {store_id} not found in config for user: {ukey}')
        return {'success': False, 'error': 'store not found'}, 404
    screens = cfg.get('screens', {}).get(store_id, {})
    logging.info(f'📊 Returning {len(screens)} screens for store {store_id}, user: {ukey}')
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

    # Canonicalize an effect name to the 10-effect set (hyphen form)
    def _normalize_effect_value(val):
        if val is None:
            return None
        v = str(val).strip().lower()
        if v == '' or v in ('none', 'default'):
            return None
        # Accept numbers (button mapping / legacy ids)
        try:
            n = int(v)
        except Exception:
            n = None
        if n is not None:
            num_map = {
                1: 'cut', 2: 'fade', 3: 'dissolve', 4: 'slide-l', 5: 'slide-r',
                6: 'slide-up', 7: 'slide-down', 8: 'zoom-in', 9: 'zoom-out', 10: 'wipe-lr'
            }
            return num_map.get(n)
        aliases = {
            'cut': 'cut',
            'fade': 'fade',
            'dissolve': 'dissolve', 'crossfade': 'dissolve', 'cross-fade': 'dissolve',
            'slide_left': 'slide-l', 'slide-left': 'slide-l', 'slide-l': 'slide-l', 'left': 'slide-l',
            'slide_right': 'slide-r', 'slide-right': 'slide-r', 'slide-r': 'slide-r', 'right': 'slide-r',
            'slide_up': 'slide-up', 'slide-up': 'slide-up', 'up': 'slide-up',
            'slide_down': 'slide-down', 'slide-down': 'slide-down', 'down': 'slide-down',
            'zoom_in': 'zoom-in', 'zoom-in': 'zoom-in', 'zoomin': 'zoom-in',
            'zoom_out': 'zoom-out', 'zoom-out': 'zoom-out', 'zoomout': 'zoom-out',
            'wipe': 'wipe-lr', 'wipe-lr': 'wipe-lr', 'wipe_l_r': 'wipe-lr', 'wipe-left-right': 'wipe-lr',
            # Legacy dashboard extras -> nearest mapping in 10
            'rotate': 'slide-r', 'zoom-cross': 'dissolve', 'whip-pan': 'slide-r', 'center-split': 'wipe-lr',
            'glitch': 'dissolve', 'ripple': 'dissolve'
        }
        return aliases.get(v)
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
            # Transition effect for item playback (persist canonically)
            if 'effect' in payload or 'effect_id' in payload:
                raw = payload.get('effect') if 'effect' in payload else payload.get('effect_id')
                norm = _normalize_effect_value(raw)
                if norm:
                    item['effect'] = norm
                else:
                    # clear if explicitly empty/default/none
                    if str(raw).strip().lower() in ('', 'none', 'default', '0', 'false'):
                        item.pop('effect', None)
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
                # Sanitize entries; preserve optional per-window 'effect' canonically
                new_sched = []
                for win in payload['schedule']:
                    if isinstance(win, dict):
                        w = {'start': win.get('start'), 'end': win.get('end')}
                        if 'days' in win and isinstance(win.get('days'), list):
                            w['days'] = [str(d).lower()[:3] for d in win.get('days') if d]
                        if 'effect' in win or 'effect_id' in win:
                            raw_e = win.get('effect') if 'effect' in win else win.get('effect_id')
                            norm_e = _normalize_effect_value(raw_e)
                            if norm_e:
                                w['effect'] = norm_e
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
                                        if 'effect' in prop_keys or 'effect_id' in prop_keys:
                                            raw = payload.get('effect') if 'effect' in payload else payload.get('effect_id')
                                            norm = _normalize_effect_value(raw)
                                            if norm:
                                                it2['effect'] = norm
                                            elif str(raw).strip().lower() in ('', 'default', 'none', '0', 'false'):
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
                                                    if 'effect' in win or 'effect_id' in win:
                                                        raw_e = win.get('effect') if 'effect' in win else win.get('effect_id')
                                                        norm_e = _normalize_effect_value(raw_e)
                                                        if norm_e:
                                                            w['effect'] = norm_e
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
        logging.info(f'🔍 /screens/{store_id} called - user: {ukey}')
        cfg = ensure_playlists_structure(load_store_config_for_user_safe_key(ukey) if ukey else load_store_config())
        screens_all = cfg.get('screens') or {}
        logging.info(f'📊 User {ukey} has {len(screens_all)} stores, store {store_id} has {len(screens_all.get(store_id, {}))} screens')
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
        create_schedules = data.get('create_schedules', False)  # New flag for schedule sync

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
                # Create schedule for sync items - master gets full schedule, followers get sync indicator
                schedule = []
                if create_schedules:
                    if idx == 0:  # Master screen gets the actual schedule
                        # Create a default schedule - user can modify this later
                        schedule = [{
                            'start': '09:00',
                            'end': '17:00', 
                            'days': ['mon', 'tue', 'wed', 'thu', 'fri']
                        }]
                    else:  # Follower screens get sync indicator
                        schedule = [{'sync_master': True, 'group_id': group_id}]
                
                item = {
                    'id': str(uuid.uuid4()),
                    'file': key,
                    'enabled': True,
                    'start': None,
                    'end': None,
                    'schedule': schedule,
                    'duration': 10,
                    'repeat': True,
                    'link_next': False,
                    'media_type': classify_media(key)
                }
                pl.append(item)
            role = 'master' if idx == 0 else 'follower'
            # Include count and mode immediately so clients don't rely on later augmentation
            item['sync_ref'] = {'group': group_id, 'role': role, 'order': idx, 'count': count, 'mode': 'split-h'}
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
            item['sync_ref'] = {'group': group_id, 'role': role, 'order': order, 'count': new_count, 'mode': 'split-h'}
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

def serve_video_file_with_range_support(file_path, is_cached='false'):
    """
    Serve a video file from an arbitrary file path with robust HTTP Range (Partial Content) support.
    Closely mirrors the /media implementation which is known to work well with ExoPlayer & Android's MediaHTTP.
    """
    from flask import Response, request
    import os

    # Derive basic metadata/headers
    file_size = os.path.getsize(file_path)
    mtime = os.path.getmtime(file_path)
    lm_http = http_date(mtime)
    ext = (os.path.splitext(file_path)[1] or '.mp4').lstrip('.').lower()
    mimetype = _video_mime(ext)

    # Helper: stream a byte range [start, end] inclusive in smaller sub-chunks
    def partial_gen(start: int, end: int):
        with open(file_path, 'rb') as f:
            f.seek(start)
            remaining = end - start + 1
            chunk = 1024 * 1024  # 1MB sub-chunks
            while remaining > 0:
                read_len = min(chunk, remaining)
                data = f.read(read_len)
                if not data:
                    break
                remaining -= len(data)
                yield data

    # Helper: stream entire file in chunks (when no Range header)
    def generate_full():
        chunk_size = 1024 * 1024  # 1MB
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    range_header = request.headers.get('Range')
    method = request.method.upper() if hasattr(request, 'method') else 'GET'
    # Handle Range requests
    if range_header:
        try:
            units, rng = range_header.split('=')
            if units.strip().lower() != 'bytes':
                raise ValueError('Only bytes ranges are supported')

            # Support open-ended and explicit end ranges: "bytes=start-end" or "bytes=start-"
            start_str, end_str = (rng.split('-') + [''])[:2]
            start = int(start_str) if start_str else 0

            # If no end specified, serve up to CHUNK_MAX to keep transfers predictable for some clients
            CHUNK_MAX = 8 * 1024 * 1024  # 8MB per response for open-ended requests
            if end_str.strip() == '':
                end = min(start + CHUNK_MAX - 1, file_size - 1)
            else:
                end = int(end_str)

            end = min(end, file_size - 1)
            if start > end or start >= file_size:
                return Response(status=416, headers={'Content-Range': f'bytes */{file_size}'})

            length = end - start + 1
            # For HEAD with Range: return headers only (no body) but 206 status
            if method == 'HEAD':
                resp = Response(status=206, mimetype=mimetype)
            else:
                resp = Response(partial_gen(start, end), 206, mimetype=mimetype)
            resp.headers.add('Accept-Ranges', 'bytes')
            resp.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            resp.headers.add('Content-Length', str(length))
            resp.headers.add('Last-Modified', lm_http)
            resp.headers.setdefault('Cache-Control', 'public, max-age=86400')
            resp.headers['X-Slice-Cached'] = is_cached
            # Advertise slice encoder version for diagnostics
            try:
                resp.headers['X-Slice-Encoder-Version'] = SLICE_ENCODER_VERSION
            except Exception:
                pass
            resp.headers['X-Slice-Range-Supported'] = 'true'
            # Helpful for diagnostics
            resp.headers['X-Debug-Served-Range'] = f'{start}-{end}'
            
            # Add CORS headers for webplayer compatibility
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Range, Content-Type'
            resp.headers['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length'
            
            print(f"DEBUG: slice-video range: {start}-{end}/{file_size} hdr={range_header}")
            return resp
        except Exception as e:
            print(f"Range parse error (slice-video): {e} | raw={range_header}")
            # Fallback to full-file response below

    # No Range header: stream whole file
    if method == 'HEAD':
        # Return 206 with full Content-Range to satisfy strict clients on HEAD
        resp = Response(status=206, mimetype=mimetype)
        resp.headers.add('Content-Range', f'bytes 0-{file_size-1}/{file_size}')
    else:
        resp = Response(generate_full(), 200, mimetype=mimetype)
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(file_size))
    resp.headers.add('Last-Modified', lm_http)
    try:
        resp.headers['ETag'] = f"W/\"{file_size}-{int(mtime)}\""
    except Exception:
        pass
    resp.headers.setdefault('Cache-Control', 'public, max-age=86400')
    resp.headers['X-Slice-Cached'] = is_cached
    try:
        resp.headers['X-Slice-Encoder-Version'] = SLICE_ENCODER_VERSION
    except Exception:
        pass
    resp.headers['X-Slice-Range-Supported'] = 'true'
    
    # Add CORS headers for webplayer compatibility
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Range, Content-Type'
    resp.headers['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length'
    
    print(f"DEBUG: slice-video full file {file_size} bytes for {file_path}")
    return resp

# Video slicing endpoint for Android TV compatibility
SLICE_ENCODER_VERSION = "v3-main-20250918"
@app.route('/slice-video/<path:video_path>')
def slice_video(video_path):
    """Serve a cropped slice of an ultra-wide video for Android TV clients."""
    try:
        # Get slice parameters from query string
        slice_mode = request.args.get('slice_mode', 'split-h')
        slice_count = int(request.args.get('slice_count', 1))
        slice_order = int(request.args.get('slice_order', 0))

        print(
            "DEBUG: slice_video request - path=%s, mode=%s, count=%s, order=%s"
            % (video_path, slice_mode, slice_count, slice_order)
        )

        # EMERGENCY BYPASS: All secondary screens (slice_order>=1) have buffering issues, serve original video
        if slice_order >= 1:
            screen_num = slice_order + 1  # slice_order 0=screen1, 1=screen2, 2=screen3, etc.
            print(f"BYPASS: Screen {screen_num} (slice_order={slice_order}) detected, serving original video instead of slice")
            base_url = get_media_base_url() + video_path
            response = redirect(base_url)
            response.headers['X-Slice-Bypass'] = f'screen{screen_num}-buffering-fix'
            response.headers['X-Slice-Info'] = f"mode={slice_mode},count={slice_count},order={slice_order}"
            # Prevent caching of the redirect to ensure bypass always works
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

        force_refresh = str(request.args.get('refresh') or '').strip().lower() in (
            '1', 'true', 'yes'
        )

        if slice_count <= 1:
            base_url = get_media_base_url() + video_path
            return redirect(base_url)

        if not FFMPEG_AVAILABLE:
            print("WARNING: FFmpeg not available, redirecting to original video")
            print("INFO: Install FFmpeg and restart the Flask server to enable slicing")
            base_url = get_media_base_url() + video_path
            response = redirect(base_url)
            response.headers['X-Slice-Fallback'] = 'ffmpeg-unavailable'
            response.headers['X-Slice-Info'] = (
                f"mode={slice_mode},count={slice_count},order={slice_order}"
            )
            return response

        cache_key = (
            f"{SLICE_ENCODER_VERSION}__"
            f"{video_path.replace('/', '_').replace('\\', '_')}"
            f"_slice_{slice_mode}_{slice_count}_{slice_order}"
        )
        cached_slice_path = os.path.join(SLICE_CACHE_FOLDER, f"{cache_key}.mp4")

        if os.path.exists(cached_slice_path):
            if force_refresh:
                try:
                    os.remove(cached_slice_path)
                    print(
                        "DEBUG: Removed cached slice due to refresh request: %s"
                        % cached_slice_path
                    )
                except Exception as _e_del:
                    print(
                        "WARNING: Failed to delete cached slice for refresh: %s"
                        % _e_del
                    )
            else:
                print(f"DEBUG: Serving cached slice: {cached_slice_path}")
                return serve_video_file_with_range_support(cached_slice_path, 'true')

        if r2_enabled():
            original_url = get_media_base_url() + video_path
            safe_filename = video_path.replace('/', '_').replace('\\', '_')
            temp_video_path = os.path.join(TEMP_CACHE_FOLDER, safe_filename)

            if not os.path.exists(temp_video_path):
                print(f"DEBUG: Downloading video from CDN: {original_url}")
                try:
                    urllib.request.urlretrieve(original_url, temp_video_path)
                    print(
                        "DEBUG: Downloaded %.2f MB"
                        % (os.path.getsize(temp_video_path) / 1024 / 1024)
                    )
                except Exception as e:
                    print(f"ERROR: Failed to download video: {e}")
                    base_url = get_media_base_url() + video_path
                    return redirect(base_url)

            original_video_path = temp_video_path
        else:
            original_video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_path)

        if not os.path.exists(original_video_path):
            print(f"ERROR: Original video not found: {original_video_path}")
            return jsonify({'error': 'Original video not found'}), 404

        success = generate_video_slice_ffmpeg(
            original_video_path,
            cached_slice_path,
            slice_mode,
            slice_count,
            slice_order,
        )

        if success and os.path.exists(cached_slice_path):
            print(f"DEBUG: Successfully created slice: {cached_slice_path}")
            print(
                "DEBUG: Slice file size: %.2f MB"
                % (os.path.getsize(cached_slice_path) / 1024 / 1024)
            )
            return serve_video_file_with_range_support(cached_slice_path, 'false')

        print("ERROR: Failed to create video slice")
        base_url = get_media_base_url() + video_path
        response = redirect(base_url)
        response.headers['X-Slice-Fallback'] = 'generation-failed'
        return response

    except Exception as e:
        app.logger.exception('slice_video failed')
        print(f"ERROR: slice_video exception: {e}")
        try:
            base_url = get_media_base_url() + video_path
            response = redirect(base_url)
            response.headers['X-Slice-Fallback'] = 'exception'
            return response
        except Exception:
            return jsonify({'error': str(e)}), 500

def generate_video_slice_ffmpeg(input_path, output_path, mode, count, order):
    """
    Generate video slice using FFmpeg crop filter.
    Similar to webplayer logic but creates actual video files.
    """
    try:
        # Check if FFmpeg is available
        if not FFMPEG_AVAILABLE:
            print("ERROR: FFmpeg not available, cannot slice video")
            return False
        
        import subprocess

        # First, get video dimensions, fps, and whether audio exists
        ffprobe_cmd = FFMPEG_PATH.replace('ffmpeg', 'ffprobe') if 'ffmpeg' in FFMPEG_PATH else 'ffprobe'
        probe_cmd = [
            ffprobe_cmd, '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', input_path
        ]

        has_audio = False
        input_width = 0
        input_height = 0
        fps = 30

        try:
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            if probe_result.returncode != 0:
                print(f"ERROR: ffprobe failed: {probe_result.stderr}")
                return False

            import json
            probe_data = json.loads(probe_result.stdout)

            # Find streams
            video_stream = None
            for stream in probe_data.get('streams', []):
                ctype = stream.get('codec_type')
                if ctype == 'video' and video_stream is None:
                    video_stream = stream
                if ctype == 'audio':
                    has_audio = True

            if not video_stream:
                print("ERROR: No video stream found")
                return False

            input_width = int(video_stream.get('width', 0) or 0)
            input_height = int(video_stream.get('height', 0) or 0)

            # Parse FPS from r_frame_rate like "30000/1001" or "30/1"
            rfr = (video_stream.get('r_frame_rate') or '').strip()
            try:
                if rfr and '/' in rfr:
                    num, den = rfr.split('/')
                    num = float(num)
                    den = float(den) if float(den) != 0 else 1.0
                    if num > 0 and den > 0:
                        fps_val = num / den
                        # bound fps to reasonable range
                        if 10 <= fps_val <= 120:
                            fps = int(round(fps_val))
            except Exception:
                pass

            print(f"DEBUG: Input video dimensions: {input_width}x{input_height}, fps={fps}, has_audio={has_audio}")

        except Exception as e:
            print(f"WARNING: Could not probe video, using defaults: {e}")
            # Default for ultra-wide sync videos
            input_width = 5760
            input_height = 1080
            has_audio = False
            fps = 30
        
        # Calculate slice dimensions and position
        # Helpers to enforce even dimensions/offsets for yuv420p safety
        def _even(x: int) -> int:
            return x - (x % 2)

        if mode == 'split-h':
            # Horizontal split (most common for sync videos)
            # Use float widths to avoid cumulative rounding drift, then clamp to frame
            w_per = input_width / max(1, count)
            left = int(round(order * w_per))
            right = int(round((order + 1) * w_per))
            crop_x = max(0, min(left, input_width - 2))
            slice_width = max(2, min(right - left, input_width - crop_x))
            slice_height = input_height
            crop_y = 0
            
            # Debug logging for troubleshooting
            print(f"DEBUG: Slice calculation - input: {input_width}x{input_height}, count: {count}, order: {order}")
            print(f"DEBUG: w_per: {w_per}, left: {left}, right: {right}")
            print(f"DEBUG: Final crop - x: {crop_x}, y: {crop_y}, w: {slice_width}, h: {slice_height}")
        elif mode == 'split-v':
            # Vertical split
            h_per = input_height / max(1, count)
            top = int(round(order * h_per))
            bottom = int(round((order + 1) * h_per))
            crop_y = max(0, min(top, input_height - 2))
            slice_height = max(2, min(bottom - top, input_height - crop_y))
            slice_width = input_width
            crop_x = 0
        else:
            print(f"ERROR: Unsupported slice mode: {mode}")
            return False

        # Enforce even crop offsets and sizes for yuv420p
        crop_x = _even(crop_x)
        crop_y = _even(crop_y)
        # Ensure width/height are even and within bounds
        slice_width = _even(min(slice_width, input_width - crop_x))
        slice_height = _even(min(slice_height, input_height - crop_y))
        # As a last resort, clamp to minimal even sizes
        if slice_width < 2:
            slice_width = 2
        if slice_height < 2:
            slice_height = 2

        print(f"DEBUG: Crop parameters (even) - x={crop_x}, y={crop_y}, w={slice_width}, h={slice_height}")

        # Build FFmpeg command for cropping with conservative, widely compatible settings
        # crop=w:h:x:y - width:height:x_offset:y_offset
        crop_filter = f"crop={slice_width}:{slice_height}:{crop_x}:{crop_y}"

        # Keyframe cadence: force exact 1s keyframes and set GOP accordingly for smoother looping
        # Also enforce constant frame rate to avoid jitter on some decoders
        gop = max(2, int(round(fps)))  # ~1s GOP

        ffmpeg_cmd = [
            FFMPEG_PATH, '-y',  # overwrite output file
            '-i', input_path,
            '-vf', crop_filter,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            # Use Main profile for better ExoPlayer compatibility with cropped videos
            '-profile:v', 'main',
            '-level', '4.0',
            '-preset', 'medium',  # More careful encoding for stability
            '-crf', '18',  # Higher quality for better parsing stability
            '-g', str(gop),
            '-keyint_min', str(gop),
            '-sc_threshold', '0',
            '-vsync', 'cfr',
            '-r', str(max(10, fps)),
            '-force_key_frames', f"expr:gte(t,n_forced*1)",
            '-movflags', '+faststart+frag_keyframe+empty_moov',  # Better streaming compatibility
            '-frag_duration', '1000000',  # 1s fragments for better seeking
            '-map', '0:v:0',
        ]

        if has_audio:
            ffmpeg_cmd += [
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ac', '2',
                '-ar', '48000',
                '-map', '0:a:0?',  # map first audio if present, but don't fail if missing
            ]
        else:
            ffmpeg_cmd += ['-an']

        # Strip metadata/chapters to avoid oddities
        ffmpeg_cmd += ['-map_metadata', '-1', '-map_chapters', '-1']

        ffmpeg_cmd += [output_path]
        
        print(f"DEBUG: Running FFmpeg: {' '.join(ffmpeg_cmd)}")
        
        # Run FFmpeg with shorter timeout for faster failure detection
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print(f"DEBUG: FFmpeg succeeded, output file size: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
            return True
        else:
            print(f"ERROR: FFmpeg failed: {result.stderr}")
            return False
        
    except subprocess.TimeoutExpired:
        print("ERROR: FFmpeg timeout")
        return False
    except Exception as e:
        print(f"ERROR: FFmpeg exception: {e}")
        return False

@app.route('/admin/ffmpeg-status')
def ffmpeg_status():
    """Admin endpoint to check FFmpeg status and test video slicing."""
    try:
        # Re-check FFmpeg availability
        global FFMPEG_AVAILABLE, FFMPEG_PATH
        FFMPEG_AVAILABLE = check_ffmpeg_available()
        
        status = {
            'ffmpeg_available': FFMPEG_AVAILABLE,
            'ffmpeg_path': FFMPEG_PATH if FFMPEG_AVAILABLE else None,
            'slice_cache_folder': SLICE_CACHE_FOLDER,
            'temp_cache_folder': TEMP_CACHE_FOLDER,
            'cache_exists': os.path.exists(SLICE_CACHE_FOLDER),
            'temp_exists': os.path.exists(TEMP_CACHE_FOLDER)
        }
        
        if FFMPEG_AVAILABLE:
            # Test FFmpeg version
            try:
                result = subprocess.run([FFMPEG_PATH, '-version'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    status['ffmpeg_version'] = version_line
                else:
                    status['ffmpeg_error'] = result.stderr
            except Exception as e:
                status['ffmpeg_test_error'] = str(e)
        
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Remote Pi Manager API endpoints
@app.route('/api/configure-pi', methods=['POST'])
def configure_pi():
    """Configure a Pi remotely using Pi ID"""
    try:
        logging.info(f'Remote Pi Manager API called - Content-Type: {request.content_type}')
        logging.info(f'Remote Pi Manager API called - Data: {request.data}')
        
        data = request.get_json(force=True)  # Force JSON parsing
        if not data:
            logging.error('No JSON data received')
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
            
        logging.info(f'Parsed JSON data: {data}')
        
        pi_id = data.get('pi_id', '').strip()
        pair_code = data.get('pair_code', '').strip()
        store_id = data.get('store_id', '').strip()
        screen_id = data.get('screen_id', '').strip()
        pi_ip = data.get('pi_ip', '').strip()

        # Validate required fields (except pi_ip which can be auto-resolved)
        if not all([pi_id, pair_code, store_id, screen_id]):
            logging.error(f'Missing fields: pi_id={pi_id}, pair_code={pair_code}, store_id={store_id}, screen_id={screen_id}')
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        # If no IP provided, resolve from mapping file
        if not pi_ip:
            import json
            try:
                with open('pi_id_ip_map.json', 'r') as f:
                    pi_map = json.load(f)
                pi_ip = pi_map.get(pi_id)
                if pi_ip:
                    logging.info(f'Resolved Pi IP from mapping: {pi_id} -> {pi_ip}')
            except Exception as e:
                logging.error(f'Error loading pi_id_ip_map.json: {e}')
                return jsonify({'success': False, 'message': 'Could not resolve Pi IP'}), 400

        if not pi_ip:
            logging.error(f'No IP found for Pi ID: {pi_id}')
            return jsonify({'success': False, 'message': f'No IP found for Pi ID: {pi_id}. Pi may not be registered.'}), 400

        # POST configuration to Pi's HTTP server
        try:
            import requests
        except ImportError:
            logging.error('requests module not installed')
            return jsonify({'success': False, 'message': 'Server missing requests module'}), 500

        pi_url = f'http://{pi_ip}:8080/configure'
        payload = {
            'pi_id': pi_id,
            'pair_code': pair_code,
            'store_id': store_id,
            'screen_id': screen_id
        }
        try:
            resp = requests.post(pi_url, json=payload, timeout=5)
            resp.raise_for_status()
            pi_response = resp.json()
            logging.info(f'Pi response: {pi_response}')
            return jsonify({'success': True, 'message': 'Configuration sent to Pi', 'pi_response': pi_response})
        except Exception as e:
            logging.error(f'Error sending config to Pi: {e}')
            return jsonify({'success': False, 'message': f'Failed to configure Pi: {e}'}), 500
        
    except Exception as e:
        logging.error(f'Remote Pi configuration error: {e}')
        return jsonify({'success': False, 'message': 'Configuration failed'}), 500

@app.route('/api/register_pi', methods=['POST'])
def register_pi():
    """Register Pi identifier and IP address automatically."""
    try:
        data = request.get_json(force=True)
        pi_id = data.get('pi_id', '').strip()
        pi_ip = data.get('pi_ip', '').strip()
        if not pi_id or not pi_ip:
            return jsonify({'success': False, 'message': 'Missing pi_id or pi_ip'}), 400
        
        # Thread-safe update
        def update_map():
            try:
                map_path = 'pi_id_ip_map.json'
                try:
                    with open(map_path, 'r') as f:
                        pi_map = json.load(f)
                except Exception:
                    pi_map = {}
                pi_map[pi_id] = pi_ip
                with open(map_path, 'w') as f:
                    json.dump(pi_map, f, indent=4)
                logging.info(f'✅ Pi registered: {pi_id} -> {pi_ip}')
            except Exception as e:
                logging.error(f'Error updating pi_id_ip_map.json: {e}')
        
        threading.Thread(target=update_map).start()
        return jsonify({'success': True, 'message': f'Registered {pi_id} with IP {pi_ip}'}), 200
    except Exception as e:
        logging.error(f'Pi registration error: {e}')
        return jsonify({'success': False, 'message': f'Error: {e}'}), 500

@app.route('/api/pi-status/<pi_id>')
def pi_status(pi_id):
    """Get status of a specific Pi"""
    try:
        logging.info(f'Pi status request for: {pi_id}')

        # Get Pi IP from query parameter
        pi_ip = request.args.get('pi_ip')

        # If no IP provided, resolve from mapping file
        if not pi_ip:
            import json
            try:
                with open('pi_id_ip_map.json', 'r') as f:
                    pi_map = json.load(f)
                pi_ip = pi_map.get(pi_id)
            except Exception as e:
                logging.error(f'Error loading pi_id_ip_map.json: {e}')
                return jsonify({
                    'pi_id': pi_id,
                    'status': 'offline',
                    'message': 'Could not resolve Pi IP'
                }), 200

        if not pi_ip:
            return jsonify({
                'pi_id': pi_id,
                'status': 'offline',
                'message': 'No IP found for Pi ID'
            }), 200

        # Try to contact Pi's HTTP server
        try:
            import requests
        except ImportError:
            logging.error('requests module not installed')
            return jsonify({
                'pi_id': pi_id,
                'status': 'unknown',
                'message': 'Server missing requests module'
            }), 500

        pi_url = f'http://{pi_ip}:8080/status'
        try:
            resp = requests.get(pi_url, timeout=3)
            resp.raise_for_status()
            pi_data = resp.json()

            return jsonify({
                'pi_id': pi_id,
                'status': 'online',
                'last_seen': pi_data.get('last_seen', 'Just now'),
                'version': pi_data.get('version', 'Unknown'),
                'current_state': pi_data.get('state', 'Unknown')
            })
        except Exception as e:
            logging.warning(f'Pi {pi_id} at {pi_ip} not responding: {e}')
            return jsonify({
                'pi_id': pi_id,
                'status': 'offline',
                'message': f'Pi not responding: {e}'
            }), 200

    except Exception as e:
        logging.error(f'Pi status error: {e}')
        return jsonify({'success': False, 'message': 'Status check failed'}), 500

# =============================================================================
# WebSocket Relay System (TeamViewer-Style Architecture)
# =============================================================================
# Pis connect TO server (outgoing, always allowed)
# Dashboard sends commands THROUGH server to connected Pis
# NO PORT FORWARDING NEEDED!
# =============================================================================

# Decorator to wrap all SocketIO handlers with error handling
def socketio_error_handler(func):
    """Wrap SocketIO handlers to catch and log exceptions without crashing"""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f'❌ SocketIO handler {func.__name__} error: {e}', exc_info=True)
            # Optionally emit error back to client
            try:
                from flask_socketio import emit
                emit('error', {'message': f'Server error in {func.__name__}', 'error': str(e)})
            except:
                pass
    return wrapper

@socketio.on('connect')
@socketio_error_handler
def handle_connect(auth=None):
    """Handle new WebSocket connection.

    Flask-SocketIO (python-socketio v5+) may pass an auth payload to the
    connect handler. Accept an optional parameter to avoid a TypeError when
    the client includes auth during the handshake.
    """
    try:
        logging.info(
            '🌐 WebSocket connection from %s%s',
            getattr(request, 'sid', 'unknown'),
            f" auth={auth}" if auth is not None else ''
        )
    except Exception:
        logging.info('🌐 WebSocket connection established')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    # Find Pi and update last_seen timestamp instead of deleting
    with pi_connection_lock:
        for pi_id, pi_info in list(connected_pis.items()):
            if isinstance(pi_info, dict) and pi_info.get('sid') == request.sid:
                # Update last_seen to current time when disconnecting
                disconnect_time = time.time()
                connected_pis[pi_id]['last_seen'] = disconnect_time
                connected_pis[pi_id]['connected'] = False
                logging.info(f'❌ Pi disconnected: {pi_id} (was connected for {disconnect_time - pi_info["connected_at"]:.0f}s)')
                
                # Save last_seen to persistent storage
                def save_disconnect():
                    try:
                        map_path = 'pi_id_ip_map.json'
                        try:
                            with open(map_path, 'r') as f:
                                pi_map = json.load(f)
                        except Exception:
                            pi_map = {}
                        
                        if pi_id in pi_map:
                            if isinstance(pi_map[pi_id], dict):
                                pi_map[pi_id]['last_seen'] = disconnect_time
                            else:
                                # Convert legacy format to new format
                                pi_map[pi_id] = {
                                    'ip': pi_map[pi_id],
                                    'last_seen': disconnect_time
                                }
                        else:
                            pi_map[pi_id] = {
                                'ip': pi_info.get('ip', 'Unknown'),
                                'last_seen': disconnect_time
                            }
                        
                        with open(map_path, 'w') as f:
                            json.dump(pi_map, f, indent=4)
                    except Exception as e:
                        logging.error(f'Error saving disconnect time: {e}')
                
                threading.Thread(target=save_disconnect, daemon=True).start()
                break

@socketio.on('register_pi')
@socketio_error_handler
def handle_pi_registration(data):
    """
    Pi connects and registers itself via WebSocket
    This is called when Pi boots up and establishes persistent connection
    """
    try:
        pi_id = data.get('pi_id', '').strip()
        pi_version = data.get('version', 'Unknown')
        
        if not pi_id:
            emit('registration_failed', {'message': 'Missing pi_id'})
            return
        
        # Get Pi's public IP from request headers (real IP behind proxy)
        pi_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if ',' in pi_ip:
            pi_ip = pi_ip.split(',')[0].strip()  # Take first IP if multiple
        
        # Store Pi connection info
        with pi_connection_lock:
            connected_pis[pi_id] = {
                'sid': request.sid,
                'connected_at': time.time(),
                'last_seen': time.time(),
                'connected': True,
                'ip': pi_ip,
                'version': pi_version
            }
        
        # Update IP mapping file (for backward compatibility)
        def update_map():
            try:
                map_path = 'pi_id_ip_map.json'
                try:
                    with open(map_path, 'r') as f:
                        pi_map = json.load(f)
                except Exception:
                    pi_map = {}
                
                # Store both IP and last_seen timestamp
                pi_map[pi_id] = {
                    'ip': pi_ip,
                    'last_seen': time.time()
                }
                
                with open(map_path, 'w') as f:
                    json.dump(pi_map, f, indent=4)
            except Exception as e:
                logging.error(f'Error updating pi_id_ip_map.json: {e}')
        
        threading.Thread(target=update_map, daemon=True).start()
        
        logging.info(f'✅ Pi registered via WebSocket: {pi_id} ({pi_ip}) - {pi_version}')
        emit('registered', {
            'status': 'success',
            'pi_id': pi_id,
            'message': f'Registered {pi_id} successfully'
        })
        
    except Exception as e:
        logging.error(f'Pi registration error: {e}')
        emit('registration_failed', {'message': f'Registration failed: {e}'})

@socketio.on('pi_heartbeat')
@socketio_error_handler
def handle_pi_heartbeat(data):
    """
    Pi sends periodic heartbeat to maintain connection
    Update last seen timestamp and registration info
    """
    pi_id = data.get('pi_id')
    if pi_id and pi_id in connected_pis:
        connected_pis[pi_id]['last_heartbeat'] = time.time()
        connected_pis[pi_id]['last_seen'] = time.time()
        connected_pis[pi_id]['connected'] = True
        
        # Update registration with current store/screen if provided
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        pair_code = data.get('pair_code')
        
        # Update connected_pis dictionary with current assignment for dashboard display
        if store_id:
            connected_pis[pi_id]['store_id'] = store_id
        if screen_id:
            connected_pis[pi_id]['screen_id'] = screen_id
        if pair_code:
            connected_pis[pi_id]['pair_code'] = pair_code
        
        if store_id and screen_id and pair_code:
            try:
                # Find which user owns this pair_code (it's stored in link_code column)
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users WHERE link_code = ?", (pair_code,))
                user_row = cursor.fetchone()
                
                if user_row:
                    username = user_row[0]
                    # Convert username (email) to safe key and get config path
                    safe_key = username.lower().replace('@', '_at_')
                    safe_key = ''.join(c for c in safe_key if (c.isalnum() or c in '._-'))
                    config_path = _config_path_for_user_safe_key(safe_key)
                    
                    try:
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                    except:
                        config = {}
                    
                    # First, remove this pi_id from ANY other screens (Pi can only be assigned to ONE screen)
                    if 'screens' in config:
                        for sid in config['screens']:
                            for scr_id in config['screens'][sid]:
                                if config['screens'][sid][scr_id].get('pi_id') == pi_id:
                                    if not (sid == store_id and scr_id == screen_id):
                                        # Remove pi_id from old screen
                                        logging.info(f'🔄 Moving {pi_id} from {sid}/{scr_id} to {store_id}/{screen_id}')
                                        config['screens'][sid][scr_id].pop('pi_id', None)
                    
                    # Update the screen's pi_id
                    if 'screens' not in config:
                        config['screens'] = {}
                    if store_id not in config['screens']:
                        config['screens'][store_id] = {}
                    if screen_id not in config['screens'][store_id]:
                        config['screens'][store_id][screen_id] = {}
                    
                    # Update this screen's pi_id
                    config['screens'][store_id][screen_id]['pi_id'] = pi_id
                    
                    # Save updated config
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    logging.info(f'✅ Updated registration for {pi_id}: {store_id}/{screen_id} (user: {username})')
                else:
                    logging.warning(f'❌ No user found with pair_code: {pair_code}')
                conn.close()
            except Exception as e:
                logging.error(f'❌ Failed to update registration for {pi_id}: {e}')
        
        emit('heartbeat_ack', {'status': 'ok'})

@socketio.on('pi_status_update')
@socketio_error_handler
def handle_pi_status_update(data):
    """
    Pi sends status updates (currently playing, errors, etc.)
    Store for dashboard to query
    """
    pi_id = data.get('pi_id')
    if pi_id and pi_id in connected_pis:
        connected_pis[pi_id]['status'] = data.get('status', {})
        logging.debug(f'📊 Status update from {pi_id}: {data.get("status", {})}')

@socketio.on('config_applied')
@socketio_error_handler
def handle_config_applied(data):
    """
    Pi confirms configuration was applied successfully
    Emit to any listening dashboard sessions
    """
    pi_id = data.get('pi_id')
    status = data.get('status') or data.get('message') or 'ok'
    logging.info(f'✅ Configuration applied on {pi_id}: {status}')

    # Broadcast to all dashboard sessions (they can filter by pi_id)
    socketio.emit('pi_config_result', {
        'pi_id': pi_id,
        'status': status,
        'timestamp': time.time()
    }, broadcast=True)

# ===== WebPlayer Mobile-to-TV Code Sharing =====
webplayer_sessions = {}  # Store active webplayer sessions (session_id -> sid)
webplayer_session_codes = {}  # Last pairing code sent per session_id (for HTTP poll fallback)
webplayer_store_codes = {}   # Last store code sent per session_id (for HTTP poll fallback)
webplayer_last_selection = {}  # Last selected screen per session_id (for HTTP poll fallback)

@socketio.on('join_session')
@socketio_error_handler
def handle_join_session(data):
    """TV/Desktop joins a session to receive codes from mobile"""
    session_id = data.get('session_id')
    if session_id:
        webplayer_sessions[session_id] = request.sid
        logging.info(f'📺 WebPlayer session joined: {session_id} (sid: {request.sid})')

@socketio.on('send_code')
@socketio_error_handler
def handle_send_code(data):
    """Mobile sends code to TV via session ID"""
    session_id = data.get('session_id')
    code = data.get('code')
    
    if session_id and code:
        # Store last code for polling fallback
        try:
            webplayer_session_codes[session_id] = {
                'code': str(code)[:4],
                'ts': time.time()
            }
        except Exception:
            pass
        if session_id in webplayer_sessions:
            target_sid = webplayer_sessions[session_id]
            emit('code_entered', {'session_id': session_id, 'code': code}, room=target_sid)
            logging.info(f'📱 Code {code} sent from mobile to TV session {session_id}')
            # Acknowledge to mobile
            emit('code_sent_ack', {'status': 'success'})
        else:
            emit('code_sent_ack', {'status': 'queued', 'message': 'TV session not connected yet'})
    else:
        emit('code_sent_ack', {'status': 'error', 'message': 'Session or code missing'})

@app.route('/api/session_poll/<session_id>', methods=['GET'])
def api_session_poll(session_id: str):
    """HTTP fallback for TVs that cannot receive Socket.IO events reliably.
    Returns {'success': true, 'code': '1234'} when a recent code exists for the session.
    Codes older than 60s are discarded.
    """
    try:
        rec = webplayer_session_codes.get(session_id)
        if not rec:
            return jsonify({'success': True, 'code': None})
        if time.time() - rec.get('ts', 0) > 60:
            # Expire old codes
            try:
                webplayer_session_codes.pop(session_id, None)
            except Exception:
                pass
            return jsonify({'success': True, 'code': None})
        return jsonify({'success': True, 'code': rec.get('code')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@socketio.on('send_store_code')
@socketio_error_handler
def handle_send_store_code(data):
    """Mobile sends store code to TV via session ID"""
    session_id = data.get('session_id')
    store_code = data.get('store_code')
    
    # Record last store code for HTTP polling fallback (non-fatal if this fails)
    try:
        if session_id and store_code:
            webplayer_store_codes[session_id] = {
                'store_code': str(store_code),
                'ts': time.time()
            }
    except Exception:
        pass

    if session_id and store_code and session_id in webplayer_sessions:
        target_sid = webplayer_sessions[session_id]
        emit('store_code_entered', {'session_id': session_id, 'store_code': store_code}, room=target_sid)
        logging.info(f'📱 Store code {store_code} sent from mobile to TV session {session_id}')
        # Acknowledge to mobile
        emit('store_code_sent_ack', {'status': 'success'})
    else:
        emit('store_code_sent_ack', {'status': 'error', 'message': 'Session not found'})

@app.route('/api/store_session_poll/<session_id>', methods=['GET'])
def api_store_session_poll(session_id: str):
    """HTTP fallback for TVs that cannot receive Socket.IO events reliably for store code.
    Returns {'success': true, 'store_code': '1000'} when a recent store code exists for the session.
    Store codes older than 120s are discarded.
    """
    try:
        rec = webplayer_store_codes.get(session_id)
        if not rec:
            return jsonify({'success': True, 'store_code': None})
        if time.time() - rec.get('ts', 0) > 120:
            # Expire old store codes
            try:
                webplayer_store_codes.pop(session_id, None)
            except Exception:
                pass
            return jsonify({'success': True, 'store_code': None})
        return jsonify({'success': True, 'store_code': rec.get('store_code')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/store_session_push', methods=['POST'])
def api_store_session_push():
    """HTTP write path from mobile to push store code to the polling cache.
    Body: {"session_id": "tv_...", "store_code": "1234"}
    """
    try:
        data = request.get_json(silent=True) or {}
        session_id = (data.get('session_id') or '').strip()
        store_code = str(data.get('store_code') or '').strip()
        if not session_id or not store_code:
            return jsonify({'success': False, 'error': 'session_id and store_code required'}), 400
        webplayer_store_codes[session_id] = {'store_code': store_code, 'ts': time.time()}
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@socketio.on('send_screen_selection')
@socketio_error_handler
def handle_send_screen_selection(data):
    """Mobile sends screen selection to TV via session ID"""
    session_id = data.get('session_id')
    screen_id = data.get('screen_id')
    store_id = data.get('store_id')
    
    # Record last selection for HTTP poll fallback
    try:
        if session_id and screen_id:
            webplayer_last_selection[session_id] = {
                'store_id': store_id,
                'screen_id': screen_id,
                'ts': time.time()
            }
    except Exception:
        pass

    if session_id and screen_id and session_id in webplayer_sessions:
        target_sid = webplayer_sessions[session_id]
        emit('screen_selected', {
            'session_id': session_id, 
            'screen_id': screen_id,
            'store_id': store_id
        }, room=target_sid)
        logging.info(f'📱 Screen {screen_id} selected from mobile to TV session {session_id}')
        # Acknowledge to mobile
        emit('screen_sent_ack', {'status': 'success'})
    else:
        emit('screen_sent_ack', {'status': 'error', 'message': 'Session not found'})

@socketio.on('leave_session')
@socketio_error_handler
def handle_leave_session(data):
    """Clean up session when TV/Desktop leaves"""
    session_id = data.get('session_id')
    if session_id and session_id in webplayer_sessions:
        del webplayer_sessions[session_id]
        logging.info(f'📺 WebPlayer session left: {session_id}')

# ===== Android TV Remote Control Commands =====

@socketio.on('android_tv_register')
@socketio_error_handler
def handle_android_tv_register(data):
    """Android TV registers with server and provides device_id for remote control"""
    device_id = data.get('device_id')
    store_id = data.get('store_id')
    screen_id = data.get('screen_id')
    
    if device_id:
        with android_tv_lock:
            if device_id not in connected_android_tvs:
                connected_android_tvs[device_id] = {}
            
            connected_android_tvs[device_id]['socket_id'] = request.sid
            connected_android_tvs[device_id]['store_id'] = store_id
            connected_android_tvs[device_id]['screen_id'] = screen_id
            connected_android_tvs[device_id]['last_seen'] = int(time.time())
        
        logging.info(f'📱 Android TV registered: {device_id} (sid: {request.sid})')
        emit('registration_ack', {'status': 'success', 'device_id': device_id})

@socketio.on('android_tv_command')
@socketio_error_handler
def handle_android_tv_command(data):
    """Dashboard sends remote command to Android TV device"""
    device_id = data.get('device_id')
    command = data.get('command')  # 'refresh_screen', 'reload_playlist', 'restart_app'
    
    if not device_id or not command:
        emit('command_result', {'status': 'error', 'message': 'device_id and command required'})
        return
    
    with android_tv_lock:
        device_data = connected_android_tvs.get(device_id)
    
    if not device_data:
        emit('command_result', {'status': 'error', 'message': 'Device not found'})
        logging.warning(f'⚠️ Android TV command failed: device {device_id} not found')
        return
    
    socket_id = device_data.get('socket_id')
    if not socket_id:
        emit('command_result', {'status': 'error', 'message': 'Device not connected via Socket.IO'})
        logging.warning(f'⚠️ Android TV command failed: device {device_id} has no socket connection')
        return
    
    # Send command to Android TV device
    socketio.emit('remote_command', {
        'command': command,
        'timestamp': time.time()
    }, room=socket_id)
    
    logging.info(f'📱 Sent command "{command}" to Android TV {device_id}')
    emit('command_result', {'status': 'success', 'message': f'Command "{command}" sent to {device_id}'})

@app.route('/api/android_tv_command', methods=['POST'])
@login_required
def api_android_tv_command():
    """HTTP endpoint for sending commands to Android TV devices (alternative to Socket.IO)"""
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')
        command = data.get('command')
        
        if not device_id or not command:
            return jsonify({'success': False, 'error': 'device_id and command required'}), 400
        
        with android_tv_lock:
            device_data = connected_android_tvs.get(device_id)
        
        if not device_data:
            return jsonify({'success': False, 'error': 'Device not found'}), 404
        
        socket_id = device_data.get('socket_id')
        if not socket_id:
            return jsonify({'success': False, 'error': 'Device not connected via Socket.IO'}), 503
        
        # Send command to Android TV device
        socketio.emit('remote_command', {
            'command': command,
            'timestamp': time.time()
        }, room=socket_id)
        
        logging.info(f'📱 HTTP: Sent command "{command}" to Android TV {device_id}')
        return jsonify({'success': True, 'message': f'Command "{command}" sent to {device_id}'})
        
    except Exception as e:
        logging.error(f'Error in android_tv_command: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/android_tv_remove', methods=['POST'])
@login_required
def api_android_tv_remove():
    """Remove Android TV device from tracking"""
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')
        
        if not device_id:
            return jsonify({'success': False, 'error': 'device_id required'}), 400
        
        with android_tv_lock:
            if device_id in connected_android_tvs:
                del connected_android_tvs[device_id]
                logging.info(f'🗑️ Removed Android TV device: {device_id}')
                return jsonify({'success': True, 'message': f'Device {device_id} removed'})
            else:
                return jsonify({'success': False, 'error': 'Device not found'}), 404
    
    except Exception as e:
        logging.error(f'Error in android_tv_remove: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/selection_session_poll/<session_id>', methods=['GET'])
def api_selection_session_poll(session_id: str):
    """HTTP fallback: get last selected screen for a session within 120s.
    Returns: {'success': true, 'selection': {'store_id': str, 'screen_id': str}} or selection=None.
    """
    try:
        rec = webplayer_last_selection.get(session_id)
        if not rec:
            return jsonify({'success': True, 'selection': None})
        if time.time() - rec.get('ts', 0) > 120:
            try:
                webplayer_last_selection.pop(session_id, None)
            except Exception:
                pass
            return jsonify({'success': True, 'selection': None})
        return jsonify({'success': True, 'selection': {'store_id': rec.get('store_id'), 'screen_id': rec.get('screen_id')}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/selection_session_push', methods=['POST'])
def api_selection_session_push():
    """HTTP write path from mobile to push the last selected screen into the polling cache.
    Body: {"session_id": "tv_...", "store_id": "1111", "screen_id": "1111_screen1"}
    """
    try:
        data = request.get_json(silent=True) or {}
        session_id = (data.get('session_id') or '').strip()
        store_id = (data.get('store_id') or '').strip()
        screen_id = (data.get('screen_id') or '').strip()
        if not session_id or not screen_id:
            return jsonify({'success': False, 'error': 'session_id and screen_id required'}), 400
        webplayer_last_selection[session_id] = {'store_id': store_id, 'screen_id': screen_id, 'ts': time.time()}
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@socketio.on('request_screenshot')
@socketio_error_handler
def handle_screenshot_request(data):
    """
    Dashboard requests screenshot from a Pi (legacy/fallback)
    Relay the request to the target Pi
    """
    pi_id = data.get('pi_id')
    logging.info(f'📸 Screenshot request for Pi: {pi_id}')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        # Emit to the specific Pi's session
        socketio.emit('request_screenshot', data, room=pi_session)
        logging.info(f'📸 Screenshot request forwarded to {pi_id}')
    else:
        # Pi not connected, send error back to requester
        emit('screenshot_data', {
            'pi_id': pi_id,
            'error': 'Pi not connected',
            'timestamp': time.time()
        })
        logging.warning(f'❌ Screenshot request failed - Pi {pi_id} not connected')

@socketio.on('start_live_stream')
@socketio_error_handler
def handle_start_live_stream(data):
    """
    Dashboard requests to start live streaming from a Pi
    Forward request to Pi to start continuous frame capture
    """
    pi_id = data.get('pi_id')
    logging.info(f'📺 Live stream START request for Pi: {pi_id}')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        # Emit to the specific Pi's session
        socketio.emit('start_live_stream', data, room=pi_session)
        logging.info(f'📺 Live stream start forwarded to {pi_id}')
    else:
        # Pi not connected, send error back
        emit('stream_error', {
            'pi_id': pi_id,
            'error': 'Pi not connected',
            'timestamp': time.time()
        })
        logging.warning(f'❌ Live stream start failed - Pi {pi_id} not connected')

@socketio.on('stop_live_stream')
@socketio_error_handler
def handle_stop_live_stream(data):
    """
    Dashboard requests to stop live streaming from a Pi
    """
    pi_id = data.get('pi_id')
    logging.info(f'📺 Live stream STOP request for Pi: {pi_id}')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        socketio.emit('stop_live_stream', data, room=pi_session)
        logging.info(f'📺 Live stream stop forwarded to {pi_id}')

@socketio.on('live_frame')
@socketio_error_handler
def handle_live_frame(data):
    """
    Pi sends live frame data
    Relay to all dashboard sessions viewing this Pi
    """
    pi_id = data.get('pi_id')
    frame_number = data.get('frame_number', 0)
    
    # Log every 30th frame to avoid spam
    if frame_number % 30 == 0:
        frame_size = len(data.get('frame', ''))
        logging.debug(f'📺 Frame #{frame_number} from {pi_id} ({frame_size} bytes)')
    
    # Emit to ALL clients (including sender) instead of broadcast=True
    # broadcast=True excludes the sender, but we want dashboards to receive it
    socketio.emit('live_frame', data, namespace='/')

@socketio.on('screenshot_data')
@socketio_error_handler
def handle_screenshot_data(data):
    """
    Pi sends screenshot data back (legacy/fallback)
    Relay to all dashboard sessions (they filter by pi_id)
    """
    pi_id = data.get('pi_id')
    has_screenshot = 'screenshot' in data
    has_error = 'error' in data
    
    if has_screenshot:
        # Calculate approximate size for logging
        screenshot_size = len(data['screenshot']) if data['screenshot'] else 0
        logging.info(f'📸 Screenshot received from {pi_id} ({screenshot_size} bytes)')
    elif has_error:
        logging.warning(f'❌ Screenshot error from {pi_id}: {data["error"]}')
    
    # Broadcast to all dashboard sessions
    socketio.emit('screenshot_data', data, broadcast=True)

# VNC-over-WebSocket proxy handlers
@socketio.on('vnc_connect')
@socketio_error_handler
def handle_vnc_connect(data):
    """
    Dashboard requests to connect to Pi's VNC via WebSocket tunnel
    """
    pi_id = data.get('pi_id')
    dashboard_sid = request.sid
    
    logging.info(f'🖥️ VNC connect request from dashboard {dashboard_sid} to Pi: {pi_id}')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        # Forward connect request to Pi, include dashboard sid for routing back
        socketio.emit('vnc_connect', {
            'pi_id': pi_id,
            'dashboard_sid': dashboard_sid
        }, room=pi_session)
        logging.info(f'🖥️ VNC connect forwarded to {pi_id}')
    else:
        # Pi not connected
        emit('vnc_error', {'message': f'Pi {pi_id} not connected'})

@socketio.on('vnc_data')
@socketio_error_handler
def handle_vnc_data(data):
    """
    Relay VNC data between dashboard and Pi
    Data can flow both ways: dashboard->Pi or Pi->dashboard
    """
    target_sid = data.get('target_sid')
    pi_id = data.get('pi_id')
    
    if target_sid:
        # Forward VNC data to specific session (could be dashboard or Pi)
        socketio.emit('vnc_data', data, room=target_sid)
    elif pi_id and pi_id in connected_pis:
        # If no target_sid but has pi_id, send to Pi
        pi_session = connected_pis[pi_id]['sid']
        socketio.emit('vnc_data', data, room=pi_session)

@socketio.on('vnc_disconnect')
@socketio_error_handler
def handle_vnc_disconnect(data):
    """
    Dashboard or Pi disconnects VNC session
    """
    pi_id = data.get('pi_id')
    dashboard_sid = data.get('dashboard_sid')
    
    logging.info(f'🖥️ VNC disconnect request for Pi: {pi_id}')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        socketio.emit('vnc_disconnect', {
            'pi_id': pi_id,
            'dashboard_sid': dashboard_sid
        }, room=pi_session)
        logging.info(f'🖥️ VNC disconnect forwarded to {pi_id}')

@socketio.on('restart_client')
@socketio_error_handler
def handle_restart_client(data):
    """
    Dashboard requests to restart the complete_pi_client software on Pi
    Forward request to Pi
    """
    pi_id = data.get('pi_id')
    logging.info(f'🔄 Client restart request for Pi: {pi_id}')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        # Emit to the specific Pi's session
        socketio.emit('restart_client', data, room=pi_session)
        logging.info(f'🔄 Client restart command forwarded to {pi_id}')
    else:
        # Pi not connected, send error back
        emit('client_restart_error', {
            'pi_id': pi_id,
            'error': 'Pi not connected',
            'timestamp': time.time()
        })
        logging.warning(f'❌ Client restart failed - Pi {pi_id} not connected')

@socketio.on('client_restarting')
@socketio_error_handler
def handle_client_restarting(data):
    """
    Pi confirms it's restarting the client
    Relay to dashboard
    """
    pi_id = data.get('pi_id')
    status = data.get('status')
    logging.info(f'🔄 Client restart status from {pi_id}: {status}')
    
    # Broadcast to all dashboard sessions
    socketio.emit('client_restarting', data, broadcast=True)

# Update the pi_status endpoint to check WebSocket connections
@app.route('/api/pi-status-ws/<pi_id>')
def pi_status_websocket(pi_id):
    """
    Check if Pi is online via WebSocket connection
    PREFERRED method - instant, no network delay
    """
    try:
        with pi_connection_lock:
            if pi_id in connected_pis:
                pi_info = connected_pis[pi_id]
                return jsonify({
                    'pi_id': pi_id,
                    'status': 'online',
                    'connection_type': 'websocket',
                    'connected_since': pi_info['connected_at'],
                    'ip_address': pi_info['ip'],
                    'version': pi_info.get('version', 'Unknown'),
                    'last_heartbeat': pi_info.get('last_heartbeat', pi_info['connected_at'])
                })
            else:
                return jsonify({
                    'pi_id': pi_id,
                    'status': 'offline',
                    'connection_type': 'none',
                    'message': 'Pi not connected to WebSocket server'
                }), 200
    except Exception as e:
        logging.error(f'WebSocket status check error: {e}')
        return jsonify({'success': False, 'message': 'Status check failed'}), 500

# Update configure-pi endpoint to use WebSocket
@app.route('/api/configure-pi-ws', methods=['POST'])
def configure_pi_websocket():
    """
    Send configuration to Pi via WebSocket (PREFERRED method)
    No port forwarding needed!
    """
    try:
        data = request.get_json(force=True)
        pi_id = data.get('pi_id', '').strip()
        pair_code = data.get('pair_code', '').strip()
        store_id = data.get('store_id', '').strip()
        screen_id = data.get('screen_id', '').strip()
        auto_start = data.get('auto_start', True)
        
        if not all([pi_id, pair_code, store_id, screen_id]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: pi_id, pair_code, store_id, screen_id'
            }), 400
        
        # Check if Pi is connected via WebSocket
        with pi_connection_lock:
            if pi_id not in connected_pis:
                return jsonify({
                    'success': False,
                    'message': f'Pi {pi_id} is not connected. Please ensure Pi is online and connected to server.'
                }), 400
            
            pi_sid = connected_pis[pi_id]['sid']
        
        # Send configuration to Pi via WebSocket - BROADCAST with PI_ID so client can filter
        logging.info(f'📡 Broadcasting configuration to all clients (target: {pi_id}, sid: {pi_sid}): store={store_id}, screen={screen_id}')
        socketio.emit('configure', {
            'target_pi_id': pi_id,  # Add target so Pi can filter
            'pair_code': pair_code,
            'store_id': store_id,
            'screen_id': screen_id,
            'auto_start': auto_start
        })
        
        logging.info(f'✅ Configuration broadcast sent (target PI: {pi_id})')
        
        # IMPORTANT: Also save the Pi assignment to config file so it persists
        try:
            ukey = _safe_user_key()
            config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
            
            # Ensure screens dict exists for this store
            if store_id not in config.get('screens', {}):
                config['screens'][store_id] = {}
                logging.info(f'[configure-pi-ws] Created screens entry for store: {store_id}')
            
            # Auto-create screen if it doesn't exist
            if screen_id not in config['screens'][store_id]:
                logging.info(f'[configure-pi-ws] Screen {screen_id} not found - creating it')
                config['screens'][store_id][screen_id] = {
                    'name': screen_id.replace('_', ' ').title(),
                    'orientation': 'landscape',
                    'playlist': []
                }
            
            # Save the pi_id assignment
            config['screens'][store_id][screen_id]['pi_id'] = pi_id
            logging.info(f'[configure-pi-ws] Setting pi_id={pi_id} for {store_id}/{screen_id}')
            
            # Save config
            if ukey:
                save_store_config_for_user_safe_key(ukey, config)
                logging.info(f'[configure-pi-ws] ✅ Saved config for user: {ukey}')
            else:
                save_store_config(config)
                logging.info(f'[configure-pi-ws] ✅ Saved global config')
                
        except Exception as save_error:
            logging.error(f'[configure-pi-ws] Failed to save assignment: {save_error}')
            # Don't fail the whole request - config was still sent to Pi
        
        return jsonify({
            'success': True,
            'message': f'Configuration sent to Pi {pi_id} via WebSocket',
            'method': 'websocket'
        }), 200
        
    except Exception as e:
        logging.error(f'WebSocket configuration error: {e}')
        return jsonify({'success': False, 'message': f'Configuration failed: {e}'}), 500

@app.route('/api/pi-close-screen', methods=['POST'])
def pi_close_screen():
    """Send close screen command to Pi via WebSocket"""
    try:
        data = request.get_json()
        pi_id = data.get('pi_id', '').strip()
        
        if not pi_id:
            return jsonify({'success': False, 'message': 'Pi ID required'}), 400
        
        logging.info(f'[v2.0] Close screen request for Pi: {pi_id}')
        
        # Check if Pi is connected
        with pi_connection_lock:
            if pi_id not in connected_pis:
                logging.warning(f'[v2.0] Pi {pi_id} not connected')
                return jsonify({
                    'success': False,
                    'message': f'Pi {pi_id} is not currently connected'
                }), 404
            
            pi_sid = connected_pis[pi_id]['sid']
        
        # Send close_screen event to Pi
        logging.info(f'[v2.0] Sending close_screen event to Pi {pi_id} (sid: {pi_sid})')
        socketio.emit('close_screen', {
            'timestamp': time.time()
        }, room=pi_sid)
        
        logging.info(f'[v2.0] Close screen command sent to Pi {pi_id}')
        
        return jsonify({
            'success': True,
            'message': f'Close screen command sent to Pi {pi_id}'
        }), 200
        
    except Exception as e:
        logging.error(f'Close screen error: {e}')
        return jsonify({'success': False, 'message': f'Close screen failed: {e}'}), 500

@app.route('/api/pi-restart', methods=['POST'])
def pi_restart():
    """Send restart command to Pi via WebSocket"""
    try:
        data = request.get_json()
        pi_id = data.get('pi_id', '').strip()
        
        if not pi_id:
            return jsonify({'success': False, 'message': 'Pi ID required'}), 400
        
        logging.info(f'[v2.0] Restart request for Pi: {pi_id}')
        
        # Check if Pi is connected
        with pi_connection_lock:
            if pi_id not in connected_pis:
                logging.warning(f'[v2.0] Pi {pi_id} not connected')
                return jsonify({
                    'success': False,
                    'message': f'Pi {pi_id} is not currently connected'
                }), 404
            
            pi_sid = connected_pis[pi_id]['sid']
        
        # Send restart_pi event to Pi
        logging.info(f'[v2.0] Sending restart_pi event to Pi {pi_id} (sid: {pi_sid})')
        logging.info(f'[v2.0] Event data: timestamp={time.time()}')
        logging.info(f'[v2.0] Emitting to room: {pi_sid}')
        
        socketio.emit('restart_pi', {
            'pi_id': pi_id,
            'timestamp': time.time()
        }, room=pi_sid)
        
        logging.info(f'[v2.0] Restart command sent to Pi {pi_id}')
        
        return jsonify({
            'success': True,
            'message': f'Restart command sent to Pi {pi_id}'
        }), 200
        
    except Exception as e:
        logging.error(f'Restart Pi error: {e}')
        return jsonify({'success': False, 'message': f'Restart failed: {e}'}), 500

@app.route('/api/pi-delete', methods=['POST'])
def pi_delete():
    """Delete a Pi device from the database"""
    try:
        data = request.get_json()
        pi_id = data.get('pi_id', '').strip()
        
        if not pi_id:
            return jsonify({'success': False, 'message': 'Pi ID required'}), 400
        
        logging.info(f'[DELETE] Delete request for Pi: {pi_id}')
        
        # Track if we actually did anything
        actions_taken = []
        
        # 1. Remove from connected_pis if currently connected
        with pi_connection_lock:
            if pi_id in connected_pis:
                logging.info(f'[DELETE] Removing connected Pi {pi_id} from connected_pis')
                # Send disconnect event to the Pi
                pi_sid = connected_pis[pi_id]['sid']
                try:
                    socketio.emit('force_disconnect', {
                        'reason': 'Device deleted from system'
                    }, room=pi_sid)
                    actions_taken.append('disconnected from server')
                except Exception as e:
                    logging.warning(f'[DELETE] Could not send disconnect to {pi_id}: {e}')
                del connected_pis[pi_id]
                actions_taken.append('removed from active connections')
        
        # 2. Remove Pi assignments from all user config files
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users')
                users = cursor.fetchall()
                
                assignments_removed = 0
                for user in users:
                    user_id = user['id']
                    try:
                        config = load_store_config_for_user_safe_key(user_id)
                        if config and 'screens' in config:
                            modified = False
                            # Check all stores and screens for this pi_id
                            for store_id, screens in config['screens'].items():
                                for screen_id, screen_data in screens.items():
                                    if isinstance(screen_data, dict) and screen_data.get('pi_id') == pi_id:
                                        logging.info(f'[DELETE] Removing {pi_id} assignment from user {user_id}, store {store_id}, screen {screen_id}')
                                        screen_data['pi_id'] = None
                                        modified = True
                                        assignments_removed += 1
                            
                            if modified:
                                save_store_config_for_user_safe_key(user_id, config)
                    except Exception as e:
                        logging.warning(f'[DELETE] Error checking user {user_id} config: {e}')
                
                if assignments_removed > 0:
                    actions_taken.append(f'removed {assignments_removed} assignment(s)')
        except Exception as e:
            logging.warning(f'[DELETE] Error removing Pi assignments: {e}')
        
        # 3. Remove from pi_id_ip_map.json (persistent storage)
        try:
            import json
            import os
            pi_map_file = 'pi_id_ip_map.json'
            if os.path.exists(pi_map_file):
                with open(pi_map_file, 'r') as f:
                    pi_map = json.load(f)
                
                if pi_id in pi_map:
                    del pi_map[pi_id]
                    with open(pi_map_file, 'w') as f:
                        json.dump(pi_map, f, indent=2)
                    actions_taken.append('removed from device registry')
                    logging.info(f'[DELETE] Removed {pi_id} from pi_id_ip_map.json')
        except Exception as e:
            logging.warning(f'[DELETE] Error removing from pi_id_ip_map.json: {e}')
        
        # Always succeed - if Pi was shown in the list, allow deletion
        # This handles offline/unassigned Pis that just need to be removed from the UI
        if not actions_taken:
            actions_taken.append('marked for removal (was not connected or assigned)')
        
        message = f'Pi {pi_id} deleted - ' + ', '.join(actions_taken)
        logging.info(f'[DELETE] {message}')
        
        return jsonify({
            'success': True,
            'message': f'Pi {pi_id} removed from system'
        }), 200
        
    except Exception as e:
        logging.error(f'Delete Pi error: {e}')
        return jsonify({'success': False, 'message': f'Delete failed: {e}'}), 500

# List all connected Pis (useful for admin dashboard)
@app.route('/api/connected-pis')
def list_connected_pis():
    """List all currently connected Pis via WebSocket"""
    try:
        with pi_connection_lock:
            pis = []
            for pi_id, pi_info in connected_pis.items():
                pis.append({
                    'pi_id': pi_id,
                    'ip': pi_info['ip'],
                    'version': pi_info.get('version', 'Unknown'),
                    'connected_since': pi_info['connected_at'],
                    'uptime_seconds': time.time() - pi_info['connected_at']
                })
            return jsonify({
                'success': True,
                'count': len(pis),
                'pis': pis
            })
    except Exception as e:
        logging.error(f'Error listing connected Pis: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500

# VNC WebSocket Proxy (solves HTTPS mixed content issue)
@app.route('/api/vnc-proxy/<pi_id>')
def vnc_proxy_info(pi_id):
    """Get VNC proxy information for a Pi"""
    try:
        with pi_connection_lock:
            if pi_id not in connected_pis:
                return jsonify({
                    'success': False,
                    'message': 'Pi not connected'
                }), 404
            
            pi_info = connected_pis[pi_id]
            pi_ip = pi_info['ip']
            
            # Return info about how to connect via noVNC
            # Client will use: https://your-domain/vnc/<pi_id>
            return jsonify({
                'success': True,
                'pi_id': pi_id,
                'pi_ip': pi_ip,
                'vnc_url': f'/vnc/{pi_id}',  # Relative URL for iframe
                'websocket_port': 6080,
                'vnc_port': 5900
            })
    except Exception as e:
        logging.error(f'VNC proxy info error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500

# Serve VNC viewer page via HTTPS (WebSocket tunnel)
@app.route('/vnc/<pi_id>')
def vnc_viewer(pi_id):
    """
    Serve VNC viewer page for specific Pi
    Uses WebSocket tunnel to avoid mixed content and NAT issues
    """
    try:
        with pi_connection_lock:
            if pi_id not in connected_pis:
                return "Pi not connected", 404
        
        # Render our custom VNC viewer that uses WebSocket proxy
        return render_template('vnc_viewer.html', pi_id=pi_id)
    
    except Exception as e:
        logging.error(f'VNC viewer error: {e}')
        return f"Error loading VNC viewer: {str(e)}", 500
    except Exception as e:
        logging.error(f'VNC viewer error: {e}')
        return f"Error loading VNC viewer: {e}", 500

# ============================================================================
# Pi Device Manager API Endpoints
# ============================================================================

@app.route('/api/add-pi-device', methods=['POST'])
@login_required
def add_pi_device():
    """Add a new Pi device to the system"""
    try:
        data = request.get_json()
        pi_id = data.get('pi_id', '').strip()
        ip_address = data.get('ip_address', '').strip()
        store_id = data.get('store_id', '').strip()
        screen_id = data.get('screen_id', '').strip()
        
        if not all([pi_id, ip_address, store_id, screen_id]):
            return jsonify({
                'success': False,
                'message': 'All fields are required'
            }), 400
        
        # Load user-specific config
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        # Update pi_id_ip_map.json
        import json
        map_path = 'pi_id_ip_map.json'
        try:
            with open(map_path, 'r') as f:
                pi_map = json.load(f)
        except FileNotFoundError:
            pi_map = {}
        
        pi_map[pi_id] = ip_address
        
        with open(map_path, 'w') as f:
            json.dump(pi_map, f, indent=2)
        
        # Update screen configuration with Pi ID
        if store_id not in config.get('screens', {}):
            config['screens'][store_id] = {}
            logging.info(f'[add_pi_device] Created screens entry for store: {store_id}')
        
        # Auto-create screen if it doesn't exist
        if screen_id not in config['screens'][store_id]:
            logging.info(f'[add_pi_device] Screen {screen_id} not found - creating it')
            config['screens'][store_id][screen_id] = {
                'name': screen_id.replace('_', ' ').title(),
                'orientation': 'landscape',
                'playlist': []
            }
        
        # Set the pi_id for this screen
        config['screens'][store_id][screen_id]['pi_id'] = pi_id
        logging.info(f'[add_pi_device] Setting pi_id={pi_id} for {store_id}/{screen_id}')
        
        # Save the config
        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
            logging.info(f'[add_pi_device] Saved config for user: {ukey}')
        else:
            save_store_config(config)
            logging.info(f'[add_pi_device] Saved global config')
        
        logging.info(f'✅ Added Pi device: {pi_id} -> {ip_address} for {store_id}/{screen_id}')
        
        return jsonify({
            'success': True,
            'message': f'Pi device {pi_id} added successfully'
        }), 200
        
    except Exception as e:
        logging.error(f'Error adding Pi device: {e}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/restart-pi/<pi_id>', methods=['POST'])
@login_required
def restart_pi(pi_id):
    """Send restart command to Pi device"""
    try:
        logging.info(f'Restart request for Pi: {pi_id}')
        
        # Check if Pi is connected via WebSocket
        with pi_connection_lock:
            if pi_id not in connected_pis:
                return jsonify({
                    'success': False,
                    'message': f'Pi {pi_id} is not currently connected'
                }), 404
            
            pi_sid = connected_pis[pi_id]['sid']
        
        # Send restart command via WebSocket
        socketio.emit('restart_pi', {
            'pi_id': pi_id,
            'timestamp': time.time()
        }, room=pi_sid)
        
        logging.info(f'Restart command sent to Pi {pi_id}')
        
        return jsonify({
            'success': True,
            'message': f'Restart command sent to Pi {pi_id}'
        }), 200
        
    except Exception as e:
        logging.error(f'Error restarting Pi: {e}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/update-pi-location', methods=['POST'])
@login_required
def update_pi_location():
    """Update custom location name and coordinates for a Pi device"""
    try:
        data = request.get_json()
        pi_id = data.get('pi_id', '').strip()
        location_name = data.get('location_name', '').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        address = data.get('address', '').strip()
        
        if not pi_id:
            return jsonify({
                'success': False,
                'message': 'Pi ID is required'
            }), 400
        
        # Load user-specific config
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        # Find the screen with this pi_id
        found = False
        for store in config.get('stores', []):
            store_id = store.get('id')
            for screen_id, screen_data in config.get('screens', {}).get(store_id, {}).items():
                if screen_data.get('pi_id') == pi_id:
                    # Update location data
                    config['screens'][store_id][screen_id]['location_name'] = location_name
                    if latitude is not None and longitude is not None:
                        config['screens'][store_id][screen_id]['latitude'] = latitude
                        config['screens'][store_id][screen_id]['longitude'] = longitude
                    if address:
                        config['screens'][store_id][screen_id]['address'] = address
                    found = True
                    break
            if found:
                break
        
        if not found:
            return jsonify({
                'success': False,
                'message': f'Pi {pi_id} not found in any screen configuration'
            }), 404
        
        # Save config (correct parameter order: safe_key first, then config)
        if ukey:
            save_store_config_for_user_safe_key(ukey, config)
        else:
            save_store_config(config)
        
        logging.info(f'Updated location for Pi {pi_id}: {location_name} ({latitude}, {longitude})')
        
        return jsonify({
            'success': True,
            'message': 'Location updated successfully',
            'location_name': location_name,
            'latitude': latitude,
            'longitude': longitude,
            'address': address
        }), 200
        
    except Exception as e:
        logging.error(f'Error updating Pi location: {e}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/get-pi-location', methods=['GET'])
@login_required
def get_pi_location():
    """Get location data for a specific Pi device"""
    try:
        pi_id = request.args.get('pi_id', '').strip()
        
        if not pi_id:
            return jsonify({
                'success': False,
                'message': 'Pi ID is required'
            }), 400
        
        # Load user-specific config
        ukey = _safe_user_key()
        config = load_store_config_for_user_safe_key(ukey) if ukey else load_store_config()
        
        # Find the screen with this pi_id
        for store in config.get('stores', []):
            store_id = store.get('id')
            for screen_id, screen_data in config.get('screens', {}).get(store_id, {}).items():
                if screen_data.get('pi_id') == pi_id:
                    return jsonify({
                        'success': True,
                        'location_name': screen_data.get('location_name', ''),
                        'latitude': screen_data.get('latitude'),
                        'longitude': screen_data.get('longitude'),
                        'address': screen_data.get('address', ''),
                        'label': screen_data.get('location_name', '')
                    }), 200
        
        # Pi not found
        return jsonify({
            'success': False,
            'message': f'Pi {pi_id} not found'
        }), 404
        
    except Exception as e:
        logging.error(f'Error getting Pi location: {e}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))  # Use 5002 since 5000 seems blocked
    print(f"DEBUG: Starting Flask with Socket.IO on port {port}", flush=True)
    logging.debug('Attempting to start Flask+SocketIO development server on port %s', port)
    try:
        # Use socketio.run instead of app.run for WebSocket support
        socketio.run(app, debug=True, host='0.0.0.0', port=port)
    except Exception as e:
        logging.exception('Flask+SocketIO failed to start: %s', e)
        # Ensure a non-zero exit so supervising systems notice
        raise
