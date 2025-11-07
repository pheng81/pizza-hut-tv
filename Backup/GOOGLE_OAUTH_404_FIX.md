# 🔧 Google OAuth 404 Error Fix

## ❌ Problem

**Error**: "404. That's an error. The requested URL was not found on this server."
**When**: Clicking "Sign in with Google" button
**Cause**: Google Cloud Console has wrong redirect URI configured

## ✅ Solution

You need to add the correct redirect URI in Google Cloud Console.

## 📝 Step-by-Step Fix

### 1. Go to Google Cloud Console
Open: https://console.cloud.google.com/

### 2. Select Your Project
- Click the project dropdown at the top
- Select the project that has your OAuth credentials
- (The one with Client ID: `REDACTED`)

### 3. Navigate to OAuth Credentials
1. Click **☰** menu (top left)
2. Click **APIs & Services**
3. Click **Credentials** (left sidebar)
4. Find your OAuth 2.0 Client ID
5. Click the **✏️ pencil icon** (Edit)

### 4. Add Authorized Redirect URIs
In the "Authorized redirect URIs" section, add these URLs:

```
https://api.everydayadvertise.com/auth/google/callback
https://everydayadvertise.com/auth/google/callback
http://localhost:5002/auth/google/callback
```

**Important**: 
- Must be **EXACT** URLs (no trailing slashes)
- Must start with `https://` (not `http://`)
- Must include `/auth/google/callback` path

### 5. Save Changes
1. Click **SAVE** button at the bottom
2. Wait a few seconds for changes to propagate (usually instant)

## 🧪 Test the Fix

1. **Log out** from your dashboard (if logged in)
2. Go to: https://api.everydayadvertise.com/
3. Click **"Sign in with Google"** button
4. Should redirect to Google login ✅
5. Select your Google account
6. Should redirect back to dashboard ✅

## 🔍 What Redirect URIs to Add

### Current Configuration (in your code):
```python
# app.py line 946
redirect_uri = 'https://api.everydayadvertise.com/auth/google/callback'
```

### Required in Google Cloud Console:
```
✅ https://api.everydayadvertise.com/auth/google/callback  (Primary - must have!)
✅ https://everydayadvertise.com/auth/google/callback      (Backup if no api. subdomain)
✅ http://localhost:5002/auth/google/callback              (For local development)
```

## 📸 Screenshots Guide

### Step 1: Find OAuth Credentials
```
Google Cloud Console
  └── APIs & Services
       └── Credentials
            └── OAuth 2.0 Client IDs
                 └── [Your Client ID] ← Click the pencil icon
```

### Step 2: Authorized Redirect URIs Section
```
┌─────────────────────────────────────────────────────────────┐
│ Authorized redirect URIs                                    │
├─────────────────────────────────────────────────────────────┤
│ + ADD URI                                                    │
│                                                              │
│ URIs 1: https://api.everydayadvertise.com/auth/google/call… │ ✓
│ URIs 2: https://everydayadvertise.com/auth/google/callback  │ ✓
│ URIs 3: http://localhost:5002/auth/google/callback          │ ✓
└─────────────────────────────────────────────────────────────┘
         [CANCEL]                              [SAVE]
```

## ⚠️ Common Mistakes

### ❌ Wrong - Trailing Slash
```
https://api.everydayadvertise.com/auth/google/callback/  ← NO!
```

### ❌ Wrong - Missing /auth/ prefix
```
https://api.everydayadvertise.com/google/callback  ← NO!
```

### ❌ Wrong - HTTP instead of HTTPS
```
http://api.everydayadvertise.com/auth/google/callback  ← NO! (except localhost)
```

### ✅ Correct
```
https://api.everydayadvertise.com/auth/google/callback  ← YES!
```

## 🔐 Security Notes

### Authorized JavaScript Origins (Optional)
If you also want to add JavaScript origins, add these:
```
https://api.everydayadvertise.com
https://everydayadvertise.com
http://localhost:5002
```

### Domain Verification (Optional)
If Google asks you to verify domain ownership:
1. You may need to verify ownership of `everydayadvertise.com`
2. Follow Google's domain verification process
3. Usually involves adding a TXT record to DNS or uploading a verification file

## 🐛 Troubleshooting

### Still Getting 404 After Adding URIs?

**1. Clear Browser Cache**
```
Ctrl+Shift+Delete → Clear cookies and cache
```

**2. Check OAuth Route Exists**
```bash
# SSH to server
ssh ubuntu@54.252.90.27

# Check if route is registered
curl -I http://localhost:5002/auth/google/callback
# Should return: 405 Method Not Allowed (GET not allowed, only POST)
# If 404, the route is missing
```

**3. Restart Service**
```bash
ssh ubuntu@54.252.90.27
sudo systemctl restart pizza-hut-tv
sudo systemctl status pizza-hut-tv
```

**4. Check Logs**
```bash
ssh ubuntu@54.252.90.27
sudo journalctl -u pizza-hut-tv -n 50 --no-pager
# Look for "OAuth: Google provider registered"
```

### Getting Different Error?

**"redirect_uri_mismatch"**
- The URI in Google Console doesn't match the code
- Double-check spelling and URL structure
- No trailing slashes!

**"access_denied"**
- User cancelled the Google login
- Try again

**"invalid_client"**
- Client ID or Secret is wrong
- Check environment variables in service file

**"state mismatch"**
- Session cookie not preserved
- Check cookie settings (SECURE, SAMESITE)
- Try clearing cookies

## 📋 Verification Checklist

Before testing, verify:

- [ ] Added `https://api.everydayadvertise.com/auth/google/callback` to Google Console
- [ ] Clicked SAVE in Google Console
- [ ] Cleared browser cache/cookies
- [ ] Service is running: `sudo systemctl status pizza-hut-tv`
- [ ] Environment variables set: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- [ ] NGINX is proxying correctly to port 5002
- [ ] SSL certificate is valid (https:// works)

## 🔄 Complete Test Flow

### Expected Flow:
```
1. User clicks "Sign in with Google"
   ↓
2. Browser redirects to: https://accounts.google.com/o/oauth2/v2/auth?...
   ↓
3. User selects Google account and approves
   ↓
4. Google redirects back to: https://api.everydayadvertise.com/auth/google/callback?code=...
   ↓
5. Your server exchanges code for token
   ↓
6. Server creates session and redirects to: /dashboard
   ↓
7. ✅ User is logged in!
```

### What's Happening Behind the Scenes:
```python
# 1. User clicks button (in dashboard.html)
<a href="/auth/google">Sign in with Google</a>

# 2. Flask route redirects to Google
@app.route('/auth/google')
def auth_google():
    redirect_uri = 'https://api.everydayadvertise.com/auth/google/callback'
    return client.authorize_redirect(redirect_uri)

# 3. Google authenticates user and redirects back
# URL: https://api.everydayadvertise.com/auth/google/callback?code=ABC123&state=XYZ

# 4. Flask handles callback
@app.route('/auth/google/callback')
def auth_google_callback():
    token = client.authorize_access_token()  # Exchange code for token
    userinfo = token.get('userinfo')
    email = userinfo.get('email')
    session['user'] = {'name': userinfo['name'], 'email': email, 'method': 'google'}
    return redirect('/dashboard')
```

## ✅ Final Check

After adding the redirect URI, test with these steps:

1. Open incognito window (Ctrl+Shift+N)
2. Go to https://api.everydayadvertise.com/
3. Click "Sign in with Google"
4. If you see Google login page → ✅ Good!
5. If you see 404 → ❌ URI not added correctly
6. Select Google account
7. If redirected to dashboard → ✅ Success!
8. If error → Check logs with `journalctl`

## 📞 Need Help?

If still not working:
1. Take screenshot of Google Console "Authorized redirect URIs" section
2. Check server logs: `sudo journalctl -u pizza-hut-tv -n 100 --no-pager`
3. Check what URL Google is redirecting to (look at browser address bar when 404 appears)
4. Verify the URL exactly matches what's in Google Console

---

## 🎯 Quick Fix Summary

**Problem**: 404 error when Google redirects back
**Cause**: Missing redirect URI in Google Cloud Console
**Fix**: Add `https://api.everydayadvertise.com/auth/google/callback` to Authorized redirect URIs
**Location**: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID → Edit
**Test**: Clear cookies → Try Google login again → Should work! ✅
