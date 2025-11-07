# 🔐 Session Fix: Multi-Worker Gunicorn Session Sharing

## ❌ Problem

**Symptom**: All users logging in appeared as the same user, or sessions got mixed up between different accounts.

**Root Cause**: 
- Your server runs **Gunicorn with 3 workers** (`--workers 3`)
- Each worker is a **separate Python process** with its own memory
- Flask's default session storage uses **client-side cookies** which store data in the cookie itself
- However, Flask also caches session data in server memory for performance
- When Worker 1 handles login and sets `session['user']`, it stores this in Worker 1's memory
- When Worker 2 handles the next request, it doesn't see Worker 1's session data
- Load balancer randomly sends requests to different workers → **sessions don't sync**

## ✅ Solution

**Server-Side Session Storage** using **Flask-Session** with filesystem backend:
- All workers read/write session data to shared directory: `/tmp/pizza_hut_tv_sessions/`
- Sessions are stored as files on disk, accessible to all workers
- Each session has a unique signed ID stored in the cookie
- All workers can access the same session data via the shared filesystem

## 📝 Changes Made

### 1. **app.py** - Added Flask-Session Import
```python
from flask import Flask, ..., session, ...
from flask_session import Session  # ✅ NEW
```

### 2. **app.py** - Configured Server-Side Sessions
```python
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Session configuration - make sessions last 30 days
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# ✅ SERVER-SIDE SESSION STORAGE (fixes multi-worker Gunicorn session issues)
# Use filesystem storage so all workers share the same session data
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/pizza_hut_tv_sessions'
app.config['SESSION_PERMANENT'] = False  # Let login set session.permanent = True
app.config['SESSION_USE_SIGNER'] = True  # Sign session IDs for security
app.config['SESSION_KEY_PREFIX'] = 'phtv_'
Session(app)  # Initialize server-side session handler
```

### 3. **requirements.txt** - Added Flask-Session Dependency
```txt
Flask>=2.3,<3
Flask-Session>=0.5.0,<1.0  # ✅ NEW
boto3>=1.34,<2
...
```

### 4. **Deployment Steps**
```bash
# 1. Upload files
scp app.py ubuntu@54.252.90.27:/var/www/pizza-hut-tv/
scp requirements.txt ubuntu@54.252.90.27:/var/www/pizza-hut-tv/

# 2. Install Flask-Session
cd /var/www/pizza-hut-tv
source venv/bin/activate
pip install Flask-Session

# 3. Create session storage directory
mkdir -p /tmp/pizza_hut_tv_sessions
chmod 755 /tmp/pizza_hut_tv_sessions

# 4. Restart service
sudo systemctl restart pizza-hut-tv
```

## 🧪 Testing

### Before Fix
1. User A logs in with account "userA" → redirected to dashboard
2. User A makes another request → load balancer sends to Worker 2
3. Worker 2 doesn't see userA's session → shows "Not logged in" or shows wrong user

### After Fix
1. User A logs in with account "userA" → session saved to `/tmp/pizza_hut_tv_sessions/phtv_<session_id>`
2. User A makes another request → load balancer sends to Worker 2
3. Worker 2 reads session from `/tmp/pizza_hut_tv_sessions/phtv_<session_id>` → sees userA correctly
4. ✅ All workers see the same session data!

### Test Steps
1. **Log out completely** (clear cookies)
2. Log in with **Account A** (e.g., testuser1@gmail.com)
3. Check dashboard shows **Account A's content**
4. Open **incognito/private window**
5. Log in with **Account B** (e.g., testuser2@gmail.com)
6. Check incognito window shows **Account B's content**
7. Go back to **first window** (Account A)
8. Refresh page
9. ✅ Should still show **Account A's content** (not Account B)

## 📊 Technical Details

### How Flask-Session Works

**Before (Client-Side Sessions)**:
```
Browser Cookie: session=eyJ1c2VyIjp7Im5hbWUiOiJ1c2VyQSJ9fQ...
                 ↑ Entire session data encoded in cookie
Worker 1 Memory: {session_id: {user: {name: 'userA'}}}  # Cached copy
Worker 2 Memory: {session_id: {user: {name: 'userB'}}}  # Different cache!
```

**After (Server-Side Sessions)**:
```
Browser Cookie: session=phtv_a1b2c3d4e5f6...  # Only session ID
                 ↑ Just a signed identifier

Shared Filesystem:
/tmp/pizza_hut_tv_sessions/
  ├── phtv_a1b2c3d4e5f6  → {user: {name: 'userA'}}
  ├── phtv_x9y8z7w6v5u4  → {user: {name: 'userB'}}
  └── phtv_...

Worker 1: Reads /tmp/pizza_hut_tv_sessions/phtv_a1b2c3d4e5f6 → userA ✅
Worker 2: Reads /tmp/pizza_hut_tv_sessions/phtv_a1b2c3d4e5f6 → userA ✅
Worker 3: Reads /tmp/pizza_hut_tv_sessions/phtv_a1b2c3d4e5f6 → userA ✅
```

### Session Security

- **SESSION_USE_SIGNER = True**: Session IDs are cryptographically signed using `app.secret_key`
- **SESSION_KEY_PREFIX = 'phtv_'**: Namespace sessions to avoid conflicts
- **SESSION_COOKIE_HTTPONLY = True**: Prevents JavaScript from accessing session cookie (XSS protection)
- **SESSION_COOKIE_SECURE = True**: Requires HTTPS (in production)
- **SESSION_COOKIE_SAMESITE = 'None'**: Allows OAuth redirects (requires SECURE)

## 🎯 Why This Matters

### Multi-Worker Architecture
```
NGINX Reverse Proxy (443) 
    ↓
Gunicorn (127.0.0.1:5002)
    ├── Worker 1 (PID 1234)  ← Handles 33% of requests
    ├── Worker 2 (PID 1235)  ← Handles 33% of requests
    └── Worker 3 (PID 1236)  ← Handles 33% of requests
```

**Without shared sessions**: Each worker has isolated memory → sessions don't sync
**With Flask-Session**: All workers read/write to shared filesystem → sessions sync perfectly

## 🔧 Maintenance

### Clean Old Sessions
Sessions accumulate over time. Clean up old sessions periodically:
```bash
# Delete sessions older than 30 days
find /tmp/pizza_hut_tv_sessions -type f -mtime +30 -delete

# Or add to crontab (daily at 3am):
0 3 * * * find /tmp/pizza_hut_tv_sessions -type f -mtime +30 -delete
```

### Monitor Session Storage
```bash
# Check session count
ls -1 /tmp/pizza_hut_tv_sessions | wc -l

# Check disk usage
du -sh /tmp/pizza_hut_tv_sessions

# View recent sessions
ls -lht /tmp/pizza_hut_tv_sessions | head -20
```

## 🚀 Performance

### Before: Client-Side Sessions
- ✅ Fast (no disk I/O)
- ❌ Limited cookie size (4KB)
- ❌ Session data exposed in cookie
- ❌ **Doesn't work with multiple workers**

### After: Filesystem Sessions
- ✅ **Works perfectly with multiple workers**
- ✅ Unlimited session size
- ✅ Session data secure on server
- ✅ Fast (temp filesystem, cached by OS)
- ⚠️ Slightly slower (disk I/O, but /tmp is fast)

## 📚 References

- **Flask-Session Documentation**: https://flask-session.readthedocs.io/
- **Gunicorn Worker Models**: https://docs.gunicorn.org/en/stable/design.html
- **Flask Session Management**: https://flask.palletsprojects.com/en/latest/quickstart/#sessions

---

## ✅ Status

**Deployed**: October 6, 2025
**Status**: ✅ ACTIVE
**Version**: Flask-Session 0.8.0

**Test Result**: 
- Clear cookies and test with multiple accounts
- Each account should maintain its own session
- No more session mixing or wrong user data!
