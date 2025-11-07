# Google OAuth Multiple Login Attempts - Fix Documentation

## Issue
When logging in with Google OAuth, users have to attempt login multiple times before successfully logging in. Browser shows various warnings about form elements, security headers, and cookies.

## Root Cause Analysis

### 1. OAuth State Parameter Session Issue
The Google OAuth flow uses a `state` parameter stored in Flask session to prevent CSRF attacks. If the session cookie isn't properly maintained during the Google redirect, the state verification fails, causing login to fail silently.

**Problem**: `SESSION_COOKIE_SAMESITE='Lax'` can sometimes interfere with OAuth redirects from Google back to our site.

### 2. Browser Warnings
Multiple browser warnings appearing in console:
- Form elements missing labels/placeholders
- Missing cache-control headers
- Invalid cookie expires format
- CSP blocking eval
- Deprecated headers (X-Frame-Options, P3P, Pragma, Expires)

## Solution

### Fix 1: Improve OAuth Session Handling

Change SameSite policy to 'None' specifically for OAuth flows, or ensure the callback can handle state properly.

```python
# Option 1: Use SameSite=None for production (requires HTTPS)
app.config.update(
    SESSION_COOKIE_SECURE=True,  # Required for SameSite=None
    SESSION_COOKIE_SAMESITE='None',  # Allow cross-site cookies for OAuth
    SESSION_COOKIE_HTTPONLY=True,
)

# Option 2: Add better error handling in OAuth callback
@app.route('/auth/google/callback')
def auth_google_callback():
    try:
        token = client.authorize_access_token()
    except Exception as e:
        # Log the specific error
        logging.error(f'OAuth token exchange failed: {e}')
        # Check if it's a state mismatch
        if 'state' in str(e).lower():
            logging.error('OAuth state mismatch - session may not be preserved')
            flash('Login session expired. Please try again.', 'error')
        return redirect(url_for('login'))
```

### Fix 2: Add Proper Cache-Control Headers

```python
@app.after_request
def add_security_headers(response):
    """Add security and cache headers to all responses"""
    # Cache control for static assets
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    else:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # Remove deprecated headers
    response.headers.pop('X-Frame-Options', None)
    response.headers.pop('P3P', None)
    
    # Add modern CSP with frame-ancestors instead of X-Frame-Options
    if not response.headers.get('Content-Security-Policy'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' https://accounts.google.com https://api.everydayadvertise.com https://cdn.everydayadvertise.com; "
            "frame-src 'self' https://accounts.google.com; "
            "frame-ancestors 'none';"
        )
    
    # Remove unnecessary security headers
    response.headers.pop('X-XSS-Protection', None)
    response.headers.pop('content-security-policy', None)  # Remove duplicate lowercase
    
    return response
```

### Fix 3: Improve Form Accessibility

Add proper labels and attributes to form elements:

```html
<!-- Login form with proper labels -->
<div class="mb-3">
    <label for="username" class="form-label">Username</label>
    <input type="text" 
           class="form-control" 
           id="username" 
           name="username" 
           placeholder="Enter your username"
           autocomplete="username"
           required>
</div>
<div class="mb-3">
    <label for="password" class="form-label">Password</label>
    <input type="password" 
           class="form-control" 
           id="password" 
           name="password" 
           placeholder="Enter your password"
           autocomplete="current-password"
           required>
</div>
```

### Fix 4: OAuth Error Logging

Add comprehensive logging to diagnose OAuth failures:

```python
@app.route('/auth/google/callback')
def auth_google_callback():
    logging.info('=== Google OAuth Callback Started ===')
    logging.info(f'Request args: {request.args}')
    logging.info(f'Session keys: {list(session.keys())}')
    
    try:
        token = client.authorize_access_token()
        logging.info(f'✓ Token received successfully')
        
        userinfo = token.get('userinfo') or {}
        email = userinfo.get('email')
        logging.info(f'✓ User info: {email}')
        
        session['user'] = {'name': userinfo.get('name') or email, 'email': email, 'method': 'google'}
        session.permanent = True
        logging.info(f'✓ Session set successfully, permanent={session.permanent}')
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logging.error(f'✗ OAuth callback failed: {e}')
        logging.error(f'✗ Error type: {type(e).__name__}')
        logging.error(f'✗ Full traceback:', exc_info=True)
        
        # Check for specific error types
        error_msg = str(e).lower()
        if 'state' in error_msg or 'csrf' in error_msg:
            flash('Login session expired. Please try again.', 'error')
            logging.error('✗ State mismatch detected - session cookie issue')
        elif 'token' in error_msg:
            flash('Failed to obtain login token. Please try again.', 'error')
        else:
            flash('Google login failed. Please try again.', 'error')
        
        return redirect(url_for('login'))
```

## Implementation

### Step 1: Update Session Configuration

```python
# In app.py, update session config
app.config.update(
    PREFERRED_URL_SCHEME='https',
    SESSION_COOKIE_SECURE=True,  # Required for production HTTPS
    SESSION_COOKIE_SAMESITE='None',  # Allow OAuth redirects
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_DOMAIN=None,  # Don't restrict domain
)
```

### Step 2: Add Security Headers Function

Add the `add_security_headers` function after app initialization.

### Step 3: Enhance OAuth Callback

Update the `auth_google_callback` function with better error handling and logging.

### Step 4: Fix Form Elements

Update login.html with proper labels and attributes.

## Testing

1. Clear browser cookies and cache
2. Navigate to login page
3. Click "Sign in with Google"
4. Check browser console for errors
5. Check server logs:
   ```bash
   sudo journalctl -u pizza-hut-tv -f | grep -A 5 "OAuth"
   ```

## Expected Results

- Login succeeds on first attempt
- No CSRF/state errors in logs
- Browser console shows no critical errors
- Session persists properly

## Troubleshooting

### Still getting state mismatch errors

**Symptom**: Logs show "state mismatch" or "CSRF" errors

**Solution**: 
1. Check if cookies are being blocked by browser
2. Verify HTTPS is being used (required for SameSite=None)
3. Check Google OAuth console for correct redirect URI
4. Ensure session secret key is consistent across all Gunicorn workers

### Cookies not persisting

**Symptom**: Session clears after redirect

**Solution**:
1. Verify `SESSION_COOKIE_SECURE=True` is set in production
2. Check that site is accessed via HTTPS
3. Verify no browser extensions are blocking cookies
4. Check cookie in browser DevTools → Application → Cookies

### Browser still showing warnings

**Symptom**: Console shows CSP or header warnings

**Solution**:
1. The warnings about Google's cookies are from Google's domain, not ours
2. Only fix warnings from our domain (api.everydayadvertise.com)
3. Some Google warnings are unavoidable and don't affect functionality
