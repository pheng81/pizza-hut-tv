# Google OAuth Login Issue - Fix Documentation

**Date**: October 4, 2025
**Issue**: After logging in with Google OAuth, users are asked to login again

## Root Cause

The session was **not being made permanent**, which caused it to expire:
- When browser was closed (non-permanent sessions)
- After a very short time (default Flask session timeout)
- When navigating between pages

## Problems Identified

### 1. **Non-Permanent Sessions** ❌
```python
# BEFORE - Session not marked as permanent
session['user'] = {'name': email, 'email': email, 'method': 'google'}
# Session expires when browser closes or after ~31 minutes
```

### 2. **No Session Lifetime Configuration** ❌
- No `PERMANENT_SESSION_LIFETIME` was set
- Default Flask session timeout is very short
- Sessions didn't persist across browser restarts

### 3. **Missing HTTPONLY Flag** ❌
- Session cookie could be accessed by JavaScript
- Security risk (XSS attacks could steal sessions)

### 4. **No Logging for OAuth Flow** ❌
- When login failed, no way to debug what went wrong
- Silent failures made troubleshooting impossible

## Fixes Applied

### ✅ Fix 1: Make Sessions Permanent
Added `session.permanent = True` after every successful login:

```python
# Google OAuth
session['user'] = {'name': userinfo.get('name') or email, 'email': email, 'method': 'google'}
session.permanent = True  # ✅ Session now persists

# Regular Login
session['user'] = {'name': row['username'], 'method': 'local'}
session.permanent = True  # ✅ Session now persists

# Microsoft OAuth
session['user'] = {'name': name or email, 'email': email, 'method': 'microsoft'}
session.permanent = True  # ✅ Session now persists
```

### ✅ Fix 2: Configure Session Lifetime
Set sessions to last 30 days:

```python
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
```

### ✅ Fix 3: Enhanced Session Security
Added HTTPONLY flag to prevent JavaScript access:

```python
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,  # Prevent XSS attacks
    SESSION_COOKIE_SECURE=True,    # HTTPS only (production)
    SESSION_COOKIE_SAMESITE='Lax', # CSRF protection
)
```

### ✅ Fix 4: Added Debug Logging
Added logging to track OAuth flow:

```python
logging.info(f'Google OAuth token received: {bool(token)}')
logging.info(f'Google userinfo received: email={userinfo.get("email")}')
logging.info(f'Google OAuth: Session set for {email}, permanent={session.permanent}')
```

## Session Configuration Details

### Before:
```python
# Session expires after ~31 minutes
# Session lost when browser closes
# No session lifetime configured
```

### After:
```python
PERMANENT_SESSION_LIFETIME = 30 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True (production)
SESSION_COOKIE_SAMESITE = 'Lax'
session.permanent = True (on login)
```

## Testing the Fix

### 1. Test Google Login Flow:
1. Go to login page
2. Click "Sign in with Google"
3. Complete Google OAuth
4. Should redirect to dashboard
5. **Close browser completely**
6. Re-open browser and go to site
7. **Should still be logged in** ✅

### 2. Check Session Cookie:
Open browser DevTools > Application > Cookies
- Look for `session` cookie
- Should have `Expires` date (not "Session")
- Should show ~30 days in future
- Should have `HttpOnly` flag

### 3. Monitor Logs:
```bash
sudo journalctl -u pizza-hut-tv -f | grep -i "google oauth"
```

You should see:
```
Google OAuth token received: True
Google userinfo received: email=user@example.com, name=John Doe
Google OAuth: Session set for user@example.com, permanent=True
```

## X-Frame-Options Warning

The warning you saw:
```
X-Frame-Options may only be set via an HTTP header
```

This is a browser warning (not an error) that happens when:
- A `<meta>` tag tries to set `X-Frame-Options`
- Should be set as HTTP header instead

### To Fix (if present):
1. Remove any `<meta http-equiv="X-Frame-Options">` tags
2. Set it as HTTP header in Nginx instead (already configured)

This is **not related** to the login issue.

## Security Improvements

The fixes also improved security:

| Setting | Purpose | Value |
|---------|---------|-------|
| `SESSION_COOKIE_HTTPONLY` | Prevent XSS | `True` |
| `SESSION_COOKIE_SECURE` | HTTPS only | `True` (prod) |
| `SESSION_COOKIE_SAMESITE` | CSRF protection | `Lax` |
| `PERMANENT_SESSION_LIFETIME` | Session duration | 30 days |
| `session.permanent` | Persist sessions | `True` |

## Common Issues & Solutions

### Issue: Still getting logged out
**Check:**
1. Browser blocking third-party cookies
2. Browser in incognito/private mode
3. Cookie settings in browser
4. Nginx timeout settings

### Issue: "Session expired" message
**Check:**
1. Server time is correct: `date` on server
2. SESSION_COOKIE_DOMAIN matches your domain
3. No Redis/session store conflicts

### Issue: Google OAuth fails silently
**Check logs:**
```bash
sudo journalctl -u pizza-hut-tv -f | grep -i oauth
```

Look for:
- "Google OAuth token received"
- "Google userinfo received"
- "Google OAuth: Session set"

## Files Changed

- ✅ `app.py` - Added session.permanent to all login methods
- ✅ `app.py` - Added PERMANENT_SESSION_LIFETIME config
- ✅ `app.py` - Added SESSION_COOKIE_HTTPONLY
- ✅ `app.py` - Added OAuth debug logging

## Deployment

```powershell
.\deploy_to_server.ps1 -Server '54.252.90.27' -KeyPath 'C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem'
```

## Summary

**Before:** Sessions expired immediately, users had to re-login constantly

**After:** Sessions persist for 30 days, users stay logged in across browser restarts

**Key Change:** Added `session.permanent = True` after every successful login

This is a **critical fix** that affects all login methods:
- ✅ Google OAuth
- ✅ Microsoft OAuth  
- ✅ Regular username/password
- ✅ Admin login

All users will now have persistent sessions! 🎉
