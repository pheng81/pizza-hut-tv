from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
import os
from werkzeug.utils import secure_filename  # may be unused but kept for backward compat
import uuid
import json
import shutil
from datetime import datetime, time as dtime, timedelta
import logging
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Optional boto3 for R2 (S3-compatible)
try:
    import boto3
    from botocore.config import Config as BotoConfig
except Exception:
    boto3 = None

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
print('DEBUG: app.py initialization start', flush=True)
logging.debug('App module import start')

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

# --- R2 (S3-compatible) integration ---
def r2_enabled() -> bool:
    return bool(
        os.environ.get('R2_BUCKET_NAME') and os.environ.get('R2_ENDPOINT_URL') and os.environ.get('R2_ACCESS_KEY_ID') and os.environ.get('R2_SECRET_ACCESS_KEY') and boto3 is not None
    )

_s3_client = None
def get_s3_client():
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not r2_enabled():
        return None
    _s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        endpoint_url=os.environ['R2_ENDPOINT_URL'],
        config=BotoConfig(signature_version='s3v4')
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
    cfg = load_store_config()
    store_screens = cfg.get('screens', {}).get(store_id)
    if not isinstance(store_screens, dict):
        logging.debug('HB store not found: %s', store_id)
        return jsonify({'success': False, 'error': 'Store not found'}), 404
    # Accept either full key (e.g., "1112_screen1") or plain ("screen1")
    if screen_id not in store_screens:
        candidate = f"{store_id}_{screen_id}" if '_' not in screen_id else None
        if candidate and candidate in store_screens:
            screen_id = candidate
        else:
            logging.debug('HB screen not found: store=%s screen=%s candidate=%s keys=%s', store_id, screen_id, candidate, list(store_screens.keys()))
            return jsonify({'success': False, 'error': 'Screen not found'}), 404
    # record last_seen epoch seconds
    store_screens[screen_id]['last_seen'] = int(time.time())
    logging.debug('HB set last_seen for %s/%s', store_id, screen_id)
    save_store_config(cfg)
    return jsonify({'success': True})

@app.route('/api/screen_status', methods=['GET'])
def screen_status():
    """Return online/offline status for all screens across all stores."""
    cfg = load_store_config()
    now = int(time.time())
    result = {}
    for store_id, screens in cfg.get('screens', {}).items():
        for sid, sdata in (screens or {}).items():
            last_seen = int(sdata.get('last_seen', 0) or 0)
            online = (now - last_seen) < HEARTBEAT_TIMEOUT
            result.setdefault(store_id, {})[sid] = 'online' if online else 'offline'
    return jsonify({'success': True, 'status': result})

@app.route('/api/screen_status/<store_id>', methods=['GET'])
def screen_status_by_store(store_id):
    """Return status mapping for a specific store (lighter payload for dashboard)."""
    cfg = load_store_config()
    now = int(time.time())
    screens = cfg.get('screens', {}).get(store_id, {}) or {}
    result = {}
    for sid, sdata in screens.items():
        last_seen = int(sdata.get('last_seen', 0) or 0)
        online = (now - last_seen) < HEARTBEAT_TIMEOUT
        result[sid] = 'online' if online else 'offline'
    logging.debug('STATUS store=%s result=%s', store_id, result)
    return jsonify({'success': True, 'status': result})

# -------------------- Core Configuration & Media Type Definitions --------------------
CONFIG_FILE = 'store_config.json'
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Cache folder for generated thumbnails
THUMB_FOLDER = os.path.join('static', 'thumbs')
os.makedirs(THUMB_FOLDER, exist_ok=True)

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
    """Load JSON config; create default if missing; backfill structural keys."""
    if not os.path.exists(CONFIG_FILE):
        cfg = get_default_config()
        # Add master_store_id using first store if available
        if cfg.get('stores'):
            cfg['master_store_id'] = cfg['stores'][0]['id']
        save_store_config(cfg)
        return cfg
    try:
        with open(CONFIG_FILE, 'r') as f:
            cfg = json.load(f)
    except Exception:
        # Backup corrupt file and reset to default
        backup_path = CONFIG_FILE + '.corrupt.bak'
        try:
            shutil.copyfile(CONFIG_FILE, backup_path)
            print(f"Backed up corrupt config to {backup_path}")
        except Exception:
            pass
        cfg = get_default_config()
    # Backfill master_store_id if missing
    if 'master_store_id' not in cfg and cfg.get('stores'):
        cfg['master_store_id'] = cfg['stores'][0]['id']
        save_store_config(cfg)
    return cfg

@app.route('/supported_extensions')
def supported_extensions():
    """Expose supported extensions categorized for front-end dynamic usage."""
    resp = jsonify({
        'success': True,
        'images': sorted(list(IMAGE_EXTENSIONS - ANIMATED_EXTENSIONS)),  # pure still images
        'animated': sorted(list(ANIMATED_EXTENSIONS)),
        'videos': sorted(list(VIDEO_EXTENSIONS)),
        'all': sorted(list(ALLOWED_EXTENSIONS))
    })
    try:
        resp.headers['Cache-Control'] = 'public, max-age=3600'
    except Exception:
        pass
    return resp

# -------------------- Video Streaming with HTTP Range Support --------------------
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
    range_header = request.headers.get('Range')
    logging.debug(f"/media request filename=%s method=%s range=%s", filename, request.method, range_header)
    if request.method == 'HEAD':
        # Fast metadata response
        resp = Response(status=200, mimetype=f'video/{"mp4" if ext=="m4v" else ext}')
        resp.headers.add('Accept-Ranges', 'bytes')
        resp.headers.add('Content-Length', str(file_size))
        return resp
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
            resp = Response(partial_gen(start, end), 206, mimetype=f'video/{"mp4" if ext=="m4v" else ext}')
            resp.headers.add('Accept-Ranges', 'bytes')
            resp.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            resp.headers.add('Content-Length', str(length))
            # Encourage client to keep-alive & not cache excessively during development
            resp.headers.add('Cache-Control', 'public, max-age=60')
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
    resp = Response(generate(), 200, mimetype=f'video/{"mp4" if ext=="m4v" else ext}')
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(file_size))
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

def get_default_config():
    """Get default store configuration"""
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

def save_store_config(config):
    """Save store configuration to JSON file"""
    try:
        # Atomic write: write to temp file then replace
        tmp_file = CONFIG_FILE + '.tmp'
        with open(tmp_file, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, CONFIG_FILE)
        print(f"Configuration atomically saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # Pillow optional; we'll fallback to original

@app.route('/thumb/<int:width>/<path:filename>')
def thumbnail(width: int, filename: str):
    """Return a cached thumbnail for an uploaded image under static/uploads.
    - width: target max width; height preserved by aspect ratio
    - caches to static/thumbs/{width}_{basename}[.jpg]
    - if not an image or Pillow missing, redirect to original
    """
    try:
        basename = os.path.basename(filename)
        if not _is_image(basename):
            return redirect(url_for('static', filename=f'uploads/{basename}'))
        src_path = _safe_upload_path(basename)
        if not os.path.exists(src_path):
            return jsonify({'error': 'not found'}), 404

        cached_name = f"{width}_{basename}"
        cached_path = os.path.abspath(os.path.join(THUMB_FOLDER, cached_name))

        # Decide if we need to rebuild
        rebuild = True
        if os.path.exists(cached_path):
            try:
                rebuild = os.path.getmtime(cached_path) < os.path.getmtime(src_path)
            except Exception:
                rebuild = True

        if rebuild:
            if Image is None:
                return redirect(url_for('static', filename=f'uploads/{basename}'))
            try:
                os.makedirs(THUMB_FOLDER, exist_ok=True)
                with Image.open(src_path) as im:
                    # Convert paletted/alpha to RGB for JPEG when needed
                    if im.mode in ('P', 'RGBA', 'LA'):
                        im = im.convert('RGB')
                    im_copy = im.copy()
                    # Preserve aspect ratio using thumbnail(); very tall max height to avoid constraining height
                    im_copy.thumbnail((int(width) if width>0 else 300, 10000), Image.LANCZOS)
                    ext = _image_ext(basename)
                    fmt = 'JPEG' if ext in ('jpg','jpeg') else ('PNG' if ext == 'png' else None)
                    save_kwargs = {'optimize': True}
                    if fmt == 'JPEG':
                        save_kwargs['quality'] = 85
                    if fmt:
                        im_copy.save(cached_path, fmt, **save_kwargs)
                    else:
                        # Default to JPEG to shrink size if uncommon format
                        if not cached_path.lower().endswith('.jpg'):
                            cached_path = cached_path + '.jpg'
                        im_copy.save(cached_path, 'JPEG', quality=85, optimize=True)
                        cached_name = os.path.basename(cached_path)
            except Exception as e:
                logging.error('Thumbnail build failed for %s: %s', basename, e)
                return redirect(url_for('static', filename=f'uploads/{basename}'))

        resp = send_file(cached_path)
        try:
            resp.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
        except Exception:
            pass
        return resp
    except Exception as e:
        logging.error('Thumbnail error: %s', e)
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

@app.route('/')
def dashboard():
    """Main dashboard page"""
    print("DEBUG: Dashboard route called")
    try:
        print("DEBUG: Loading store config...")
        config = ensure_playlists_structure(load_store_config())
        print("DEBUG: Config loaded successfully")
        print(f"DEBUG: Config has {len(config.get('stores', []))} stores")
        print("DEBUG: Rendering template...")
        return render_template('dashboard.html', config=config, media_base_url=get_media_base_url())
    except Exception as e:
        print(f"DEBUG: Error in dashboard route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {e}", 500

@app.route('/upload_to_screen', methods=['POST'])
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
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        # Detect content-type
        content_type = file.mimetype or 'application/octet-stream'
        if r2_enabled():
            data = file.read()
            r2_put_bytes(filename, data, content_type)
            print(f"[upload_to_screen] Uploaded to R2 as {filename}")
        else:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            print(f"[upload_to_screen] Saved as {filename} -> {filepath}")

        # Update configuration
        config = ensure_playlists_structure(load_store_config())
    else:
        print(f"[upload_to_screen] Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type'}), 400

    if apply_to_all:
        master_store_id = config.get('master_store_id')
        # If not master, downgrade to single-store behavior instead of blocking
        if store_id != master_store_id:
            print(f"[upload_to_screen] apply_to_all requested by non-master store {store_id}. Downgrading to single-store upload.")
            apply_to_all = False
        
    if apply_to_all:
        master_store_id = config.get('master_store_id')

        original_screen_id = screen_id
        screen_type = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id

        updated_stores = []
        skipped_stores = []
        created_screens = []

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
                scr['file'] = filename
                pl = scr.setdefault('playlist', [])
                if not any(i.get('file') == filename for i in pl):
                    pl.append({'id': str(uuid.uuid4()), 'file': filename, 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(filename)})
                updated_stores.append(current_store_id)

        save_store_config(config)
        print(f"[upload_to_screen] Apply-to-all updated stores={updated_stores} skipped={skipped_stores} created={created_screens}")
        message = f'File applied to {screen_type} in {len(updated_stores)} stores'
        if created_screens:
            message += f'. Created {len(created_screens)} missing screens'
        if skipped_stores:
            message += f'. Skipped {len(skipped_stores)} protected stores'
    return jsonify({'success': True,
             'filename': filename,
             'url': build_public_url(filename),
             'media_type': classify_media(filename),
             'store_id': store_id,
             'screen_id': screen_id,
             'applied_to_all': True,
             'updated_stores': updated_stores,
             'skipped_stores': skipped_stores,
             'created_screens': created_screens,
             'message': message})
    # Single-store path
    if store_id in config['screens'] and screen_id in config['screens'][store_id]:
        screen_obj = config['screens'][store_id][screen_id]
        screen_obj['file'] = filename
        pl = screen_obj.setdefault('playlist', [])
        if not any(i.get('file') == filename for i in pl):
            pl.append({'id': str(uuid.uuid4()), 'file': filename, 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(filename)})
        save_store_config(config)
        print(f"[upload_to_screen] Single-store success store={store_id} screen={screen_id} file={filename} playlist_len={len(pl)}")
    return jsonify({'success': True,
            'filename': filename,
            'url': build_public_url(filename),
            'media_type': classify_media(filename),
            'store_id': store_id,
            'screen_id': screen_id,
            'applied_to_all': False})

@app.route('/update_rotation', methods=['POST'])
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
    return render_template('tv_view.html', screen_config=screen_config, screen_id=screen_id, store_id=store_id, active_file=active_file)

@app.route('/delete_from_screen', methods=['POST'])
def delete_from_screen():
    """Delete file from specific screen or force delete from gallery"""
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
        
        # Fallback: allow legacy (un-prefixed) screen IDs by auto-expanding
        if (not force_delete and store_id in config.get('screens', {}) and
            screen_id not in config['screens'][store_id]):
            legacy_candidate = f"{store_id}_{screen_id}"  # try store-specific form
            if legacy_candidate in config['screens'][store_id]:
                print(f"Mapped legacy screen_id '{screen_id}' -> '{legacy_candidate}'")
                screen_id = legacy_candidate
        
        # Handle force delete from gallery (delete file completely)
        if force_delete and filename:
            print(f"Processing force delete for filename: {filename}")
            try:
                # Remove file from storage
                removed_physical = False
                if r2_enabled():
                    try:
                        r2_delete_object(filename)
                        removed_physical = True
                        print(f"Force deleted R2 object: {filename}")
                    except Exception as e:
                        print(f"R2 force delete failed (continuing): {e}")
                else:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        removed_physical = True
                        print(f"Force deleted file: {filepath}")
                
                # Remove file from all screens that use it
                for sid, screens in config['screens'].items():
                    for scr_id, screen_data in screens.items():
                        if screen_data.get('file') == filename:
                            config['screens'][sid][scr_id]['file'] = None
                            print(f"Removed {filename} from store {sid}, screen {scr_id}")
                
                save_store_config(config)
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
                # Determine if other screens still reference this file
                still_in_use = False
                for other_store_id, screens in config.get('screens', {}).items():
                    for other_screen_id, sdata in screens.items():
                        if (other_store_id, other_screen_id) != (store_id, screen_id) and sdata.get('file') == current_filename:
                            still_in_use = True
                            break
                    if still_in_use:
                        break
                print(f"Reference check - file '{current_filename}' still_in_use={still_in_use}")

                # Only remove the physical file if no other screen uses it
                if not still_in_use:
                    if r2_enabled():
                        try:
                            r2_delete_object(current_filename)
                            print(f"Deleted R2 object: {current_filename}")
                        except Exception as de:
                            print(f"R2 delete failed: {de}")
                    else:
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_filename)
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
                config['screens'][store_id][screen_id]['playlist'] = [i for i in pl if i.get('file') != current_filename]
                save_store_config(config)

                return jsonify({
                    'success': True,
                    'message': 'File removed from screen',
                    'file_was_shared': still_in_use,
                    'file_deleted': not still_in_use
                })
            except Exception as e:
                print(f"Error during delete operation: {e}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
        
        print(f"Invalid parameters - store_id: {store_id}, screen_id: {screen_id}")
        print(f"Available stores: {list(config['screens'].keys())}")
        if store_id in config['screens']:
            print(f"Available screens for {store_id}: {list(config['screens'][store_id].keys())}")
        
        return jsonify({'error': 'Invalid parameters or screen not found'}), 400
        
    except Exception as e:
        print(f"Unexpected error in delete_from_screen: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/apply_to_all', methods=['POST'])
def apply_to_all():
    """Apply settings to all stores"""
    # This would implement the "Apply to all Stores" functionality
    return jsonify({'success': True, 'message': 'Settings applied to all stores'})

@app.route('/replicate_screen', methods=['POST'])
def replicate_screen():
    """Replicate an existing master store screen file to all other stores (respecting protection)."""
    try:
        data = request.get_json() or {}
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
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

        source_file = master_screens[screen_id].get('file')
        if not source_file:
            return jsonify({'error': 'No file on this screen to replicate'}), 400

        # Logical screen type for cross-store mapping
        screen_type = screen_id.split('_', 1)[1] if '_' in screen_id else screen_id

        updated_stores = []
        skipped_stores = []
        created_screens = []

        for sid, screens in config.get('screens', {}).items():
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

            screens[actual_id]['file'] = source_file
            pl = screens[actual_id].setdefault('playlist', [])
            if not any(i.get('file') == source_file for i in pl):
                pl.append({'id': str(uuid.uuid4()), 'file': source_file, 'enabled': True, 'start': None, 'end': None, 'schedule': [], 'duration': 10, 'repeat': True, 'link_next': False, 'media_type': classify_media(source_file)})
            updated_stores.append(sid)

        save_store_config(config)

        message = f"Replicated {screen_type} to {len(updated_stores)} stores"
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
def delete_unused_files():
    """Delete all unused files"""
    try:
        config = load_store_config()
        used_files = set()
        
        # Collect all used files
        for store_id, screens in config['screens'].items():
            for screen_id, screen_data in screens.items():
                if screen_data.get('file'):
                    used_files.add(screen_data['file'])
                for item in screen_data.get('playlist', []):
                    if item.get('file'): used_files.add(item['file'])
        
        # Find and delete unused files
        deleted_count = 0
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if allowed_file(filename) and filename not in used_files:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"Deleted unused file: {filename}")
        
        return jsonify({'success': True, 'deleted_count': deleted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_delete')
def test_delete():
    """Test page for debugging delete functionality"""
    return render_template('test_delete.html')

@app.route('/add_screen', methods=['POST'])
def add_screen():
    """Add a new screen to a store"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_type = data.get('screen_type', 'screen')  # 'screen' or 'promo'
        
        if not store_id:
            return jsonify({'error': 'Store ID is required'}), 400
            
        config = load_store_config()
        
        if store_id not in config['screens']:
            config['screens'][store_id] = {}
        
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

        # Create store-specific screen ID: store_id + screen_type + number
        new_screen_id = f"{store_id}_{screen_type}{next_num}"
        
        # Set default orientation based on screen type
        is_promo = screen_type.startswith('promo')
        
        # Add new screen with default settings
        config['screens'][store_id][new_screen_id] = {
            'file': None,
            'vertical': is_promo,  # Promos default to vertical
            'horizontal': not is_promo,  # Regular screens default to horizontal
            'rotation': 0,
            'protected': False
        }
        
        save_store_config(config)
        
        return jsonify({
            'success': True, 
            'screen_id': new_screen_id,
            'message': f'Added {new_screen_id} successfully'
        })
        
    except Exception as e:
        print(f"Error adding screen: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_screen', methods=['POST'])
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
            
        config = load_store_config()
        print(f"DEBUG: Available stores: {list(config['screens'].keys())}")
        
        if store_id not in config['screens']:
            print(f"DEBUG: Store {store_id} not found in config")
            return jsonify({'error': 'Store not found'}), 404
            
        if screen_id not in config['screens'][store_id]:
            print(f"DEBUG: Screen {screen_id} not found in store {store_id}")
            print(f"DEBUG: Available screens in store {store_id}: {list(config['screens'][store_id].keys())}")
            return jsonify({'error': 'Screen not found'}), 404
        
        print(f"DEBUG: Found screen {screen_id} in store {store_id}")
        
        # Delete associated file if exists
        screen_data = config['screens'][store_id][screen_id]
        if screen_data.get('file'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], screen_data['file'])
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"DEBUG: Deleted file: {filepath}")
        
        # Remove screen from configuration
        del config['screens'][store_id][screen_id]
        print(f"DEBUG: Removed screen {screen_id} from config")
        
        save_store_config(config)
        print(f"DEBUG: Configuration saved successfully")
        
        return jsonify({
            'success': True,
            'message': f'Screen {screen_id} deleted successfully'
        })
        
    except Exception as e:
        print(f"ERROR: Error deleting screen: {e}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_store', methods=['POST'])
def add_store():
    """Add a new store with default screens"""
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
        
        # Add default screens for new store (2 screens + 1 promo) with store-specific IDs
        config['screens'][store_id] = {
            f'{store_id}_screen1': {
                'file': None,
                'vertical': False,
                'horizontal': False,
                'rotation': 0
            },
            f'{store_id}_screen2': {
                'file': None,
                'vertical': False,
                'horizontal': False,
                'rotation': 0
            },
            f'{store_id}_promo1': {
                'file': None,
                'vertical': True,
                'horizontal': False,
                'rotation': 0
            }
        }
        
        save_store_config(config)
        
        return jsonify({
            'success': True,
            'store_id': store_id,
            'store_name': store_name,
            'message': f'Store {store_id} - {store_name} added successfully with default screens'
        })
        
    except Exception as e:
        print(f"Error adding store: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_store', methods=['POST'])
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
def get_playlist(store_id, screen_id):
    print(f"DEBUG: GET /playlist {store_id} {screen_id}")
    cfg = ensure_playlists_structure(load_store_config())
    screens = cfg.get('screens', {}).get(store_id, {})
    screen = screens.get(screen_id)
    if not screen:
        # Try mapping between legacy short and store-prefixed IDs
        alt = None
        if '_' in screen_id:
            short = screen_id.split('_', 1)[1]
            alt = screens.get(short)
            if alt is not None:
                screen_id = short
        else:
            prefixed = f"{store_id}_{screen_id}"
            alt = screens.get(prefixed)
            if alt is not None:
                screen_id = prefixed
        screen = alt
    if not screen:
        # If store exists, create the screen with defaults to avoid frontend errors
        if store_id in cfg.get('screens', {}):
            target_id = screen_id if '_' in screen_id else f"{store_id}_{screen_id}"
            print(f"DEBUG: Auto-creating missing screen {target_id} in store {store_id}")
            is_promo = target_id.split('_',1)[-1].startswith('promo') if '_' in target_id else target_id.startswith('promo')
            screens[target_id] = {
                'file': None,
                'vertical': True if is_promo else False,
                'horizontal': False if is_promo else False,
                'rotation': 0,
                'protected': False,
                'playlist': []
            }
            save_store_config(cfg)
            screen_id = target_id
            screen = screens[target_id]
        else:
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
            save_store_config(cfg)
            print(f"DEBUG: Auto-removed {removed} missing file playlist items")
    pl = screen.get('playlist', [])
    # Decorate with public URL for clients that support absolute URLs
    out = []
    for item in pl:
        try:
            it = dict(item)
            it['url'] = build_public_url(it.get('file'))
            out.append(it)
        except Exception:
            out.append(item)
    print(f"DEBUG: Returning playlist items: {len(out)}")
    return jsonify({'success': True, 'playlist': out})

# ---- Media library listing (for choosing existing uploads) ----
@app.route('/library')
def list_library():
    try:
        files = []
        if r2_enabled():
            for obj in r2_list_objects():
                name = obj.get('Key')
                if not name or not allowed_file(name):
                    continue
                size = int(obj.get('Size') or 0)
                mtime = int(obj.get('LastModified').timestamp()) if obj.get('LastModified') else 0
                files.append({
                    'name': name,
                    'media_type': classify_media(name),
                    'size': size,
                    'mtime': mtime,
                    'url': build_public_url(name)
                })
        else:
            folder = app.config['UPLOAD_FOLDER']
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                if not allowed_file(name):
                    continue
                stat = os.stat(path)
                files.append({
                    'name': name,
                    'media_type': classify_media(name),
                    'size': stat.st_size,
                    'mtime': int(stat.st_mtime),
                    'url': build_public_url(name)
                })
        # Sort by most recent first
        files.sort(key=lambda x: x['mtime'], reverse=True)
        resp = jsonify({'success': True, 'files': files})
        try:
            resp.headers['Cache-Control'] = 'public, max-age=60'
        except Exception:
            pass
        return resp
    except Exception as e:
        print(f"Error listing library: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ---- Upload media only (no playlist/config modification) ----
@app.route('/upload_media', methods=['POST'])
def upload_media():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    if not allowed_file(f.filename):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    try:
        ext = f.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        dest = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(dest)
        return jsonify({'success': True, 'filename': filename, 'media_type': classify_media(filename)})
    except Exception as e:
        print(f"upload_media error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# -------- Store & Screen discovery API (for device first-run setup) --------
@app.route('/stores')
def list_stores():
    cfg = ensure_playlists_structure(load_store_config())
    return jsonify({'success': True, 'stores': cfg.get('stores', [])})

@app.route('/screens/<store_id>')
def list_screens(store_id):
    cfg = ensure_playlists_structure(load_store_config())
    screens = cfg.get('screens', {}).get(store_id, {})
    # Return as array of {id: screen_id}
    arr = [{'id': sid} for sid in screens.keys()]
    return jsonify({'success': True, 'screens': arr})

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>', methods=['PATCH'])
def update_playlist_item(store_id, screen_id, item_id):
    print(f"DEBUG: PATCH playlist item {store_id} {screen_id} {item_id}")
    cfg = ensure_playlists_structure(load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    updated = False
    for item in screen.get('playlist', []):
        if item['id'] == item_id:
            payload = request.get_json() or {}
            # Allow replacing the media file by referencing an existing upload
            if 'file' in payload:
                new_file = payload.get('file')
                if new_file:
                    path = os.path.join(app.config['UPLOAD_FOLDER'], new_file)
                    if not os.path.exists(path):
                        return jsonify({'success': False, 'error': 'file not found in uploads'}), 400
                    if not allowed_file(new_file):
                        return jsonify({'success': False, 'error': 'invalid file type'}), 400
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
            break
    if updated:
        save_store_config(cfg)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'item not found'}), 404

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>', methods=['DELETE'])
def delete_playlist_item(store_id, screen_id, item_id):
    print(f"DEBUG: DELETE playlist item {store_id} {screen_id} {item_id}")
    cfg = ensure_playlists_structure(load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    before = len(screen.get('playlist', []))
    screen['playlist'] = [i for i in screen.get('playlist', []) if i.get('id') != item_id]
    if len(screen['playlist']) != before:
        save_store_config(cfg)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'item not found'}), 404

# ---- Schedule window management endpoints ----
@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>/schedule', methods=['POST'])
def add_schedule_window(store_id, screen_id, item_id):
    cfg = ensure_playlists_structure(load_store_config())
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
            save_store_config(cfg)
            return jsonify({'success': True, 'index': len(sched)-1, 'window': win})
    return jsonify({'success': False, 'error': 'item not found'}), 404

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>/schedule/<int:index>', methods=['PATCH'])
def update_schedule_window(store_id, screen_id, item_id, index):
    cfg = ensure_playlists_structure(load_store_config())
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
                save_store_config(cfg)
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'index out of range'}), 400
    return jsonify({'success': False, 'error': 'item not found'}), 404

@app.route('/playlist/item/<store_id>/<screen_id>/<item_id>/schedule/<int:index>', methods=['DELETE'])
def delete_schedule_window(store_id, screen_id, item_id, index):
    cfg = ensure_playlists_structure(load_store_config())
    screen = cfg.get('screens', {}).get(store_id, {}).get(screen_id)
    if not screen:
        return jsonify({'success': False, 'error': 'screen not found'}), 404
    for it in screen.get('playlist', []):
        if it.get('id') == item_id:
            sched = it.setdefault('schedule', [])
            if 0 <= index < len(sched):
                removed = sched.pop(index)
                save_store_config(cfg)
                return jsonify({'success': True, 'removed': removed})
            return jsonify({'success': False, 'error': 'index out of range'}), 400
    return jsonify({'success': False, 'error': 'item not found'}), 404

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
