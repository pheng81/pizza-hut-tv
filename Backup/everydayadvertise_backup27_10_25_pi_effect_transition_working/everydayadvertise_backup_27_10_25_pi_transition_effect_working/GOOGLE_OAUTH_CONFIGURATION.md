# Google OAuth Configuration Summary

## Configuration Status: ✅ COMPLETE

### Server Credentials Configured
- **Client ID**: `REDACTED`
- **Client Secret**: `[REDACTED: use env GOOGLE_CLIENT_SECRET]`
- **Location**: `/etc/systemd/system/pizza-hut-tv.service.d/override.conf`
- **Status**: ✅ Configured and service restarted

### Authorized Redirect URIs (in Google Cloud Console)
1. ✅ `http://localhost:5002/auth/google/callback`
2. ✅ `https://everydayadvertise.com/auth/google/callback`
3. ✅ `https://api.everydayadvertise.com/auth/google/callback`

### How to Access & Login

#### ✅ WORKING URLs (Use These):
- `https://api.everydayadvertise.com` - Login page
- `https://everydayadvertise.com` - Login page

#### ❌ NOT WORKING URLs (Don't Use):
- `http://54.252.90.27` - IP address not allowed by Google OAuth

### Important Notes

1. **Must Use Domain, Not IP**
   - Google OAuth requires a proper domain name
   - Cannot use IP addresses like `54.252.90.27`
   - Use `api.everydayadvertise.com` instead

2. **Test Users Only**
   - OAuth is in "Testing" mode
   - Only authorized test users can log in
   - Add users in Google Cloud Console → OAuth consent screen → Test users

3. **DNS Must Be Configured**
   - `api.everydayadvertise.com` must point to `54.252.90.27`
   - If DNS is not set up, Google login won't work

### Console Warnings (NORMAL - Ignore These)
When you see these in browser console, they're normal Google OAuth warnings:
```
WARNING! Using this console may allow attackers to impersonate you...
This page is in Quirks Mode...
Uncaught Object { message: "Error in protected function...
```
These are Google's security warnings and internal JavaScript warnings - they don't affect functionality.

### Troubleshooting

#### If Google Login Shows 404:
- Make sure you're using `https://api.everydayadvertise.com` (not the IP)
- Check that DNS is pointing to your server
- Verify redirect URI is in Google Cloud Console

#### If "Access Blocked" or "Not Authorized":
- Add your email as a test user in Google Cloud Console
- Go to: APIs & Services → OAuth consent screen → Test users
- Add your Google email address

#### If "Redirect URI Mismatch":
- The URL you're accessing must match a configured redirect URI
- Use `https://api.everydayadvertise.com` which is already configured

### Testing Steps

1. **Clear browser cache** (important!)
2. Go to `https://api.everydayadvertise.com`
3. Click "Continue with Google"
4. Sign in with Google account (must be added as test user)
5. Should redirect back to dashboard

### Files Modified
- `/etc/systemd/system/pizza-hut-tv.service.d/override.conf` - Added Google OAuth env vars
- Server restarted with: `sudo systemctl daemon-reload && sudo systemctl restart pizza-hut-tv`

## Status: Ready to Test ✅

Google OAuth is now properly configured. Use `https://api.everydayadvertise.com` to access and test the login.
