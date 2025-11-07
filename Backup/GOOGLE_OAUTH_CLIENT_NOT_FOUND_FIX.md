# 🚨 URGENT: Google OAuth Client Not Found Error

## ❌ Error Detected

**Error**: `invalid_client - The OAuth client was not found`
**Cause**: Your Google OAuth Client ID has been deleted, disabled, or never existed in Google Cloud Console
**Client ID**: `REDACTED`

## 🔍 Diagnosis

When clicking "Sign in with Google", Google responds with:
```
https://accounts.google.com/signin/oauth/error?
authError=invalid_client
message=The OAuth client was not found
```

This means Google doesn't recognize the Client ID in your server configuration.

## ✅ Solution: Create New OAuth Client

### Step 1: Go to Google Cloud Console
Open: https://console.cloud.google.com/apis/credentials

### Step 2: Select or Create Project
- If you have an existing project "everydayadvertise", select it
- If not, create a new project:
  1. Click "Select a project" dropdown
  2. Click "NEW PROJECT"
  3. Name: "everydayadvertise"
  4. Click "CREATE"

### Step 3: Configure OAuth Consent Screen (if needed)
1. Click **OAuth consent screen** (left sidebar)
2. Select **External** (for public users)
3. Fill in:
   - App name: `Everyday Advertise`
   - User support email: `your-email@gmail.com`
   - Developer contact: `your-email@gmail.com`
4. Click **SAVE AND CONTINUE**
5. Skip "Scopes" (click SAVE AND CONTINUE)
6. Skip "Test users" (click SAVE AND CONTINUE)
7. Click **BACK TO DASHBOARD**

### Step 4: Create OAuth 2.0 Client ID
1. Click **Credentials** (left sidebar)
2. Click **+ CREATE CREDENTIALS**
3. Select **OAuth client ID**
4. Application type: **Web application**
5. Name: `Pizza Hut TV Web Client`

6. **Authorized JavaScript origins** (click + ADD URI):
   ```
   https://api.everydayadvertise.com
   https://everydayadvertise.com
   http://localhost:5002
   ```

7. **Authorized redirect URIs** (click + ADD URI):
   ```
   https://api.everydayadvertise.com/auth/google/callback
   https://everydayadvertise.com/auth/google/callback
   http://localhost:5002/auth/google/callback
   ```

8. Click **CREATE**

### Step 5: Copy Credentials
You'll see a popup with:
- **Client ID**: `something.apps.googleusercontent.com`
- **Client Secret**: `[REDACTED: store as env GOOGLE_CLIENT_SECRET]`

**IMPORTANT**: Copy both and save them somewhere safe!

### Step 6: Update Server Configuration
SSH to your server and update the service file:

```bash
# SSH to server
ssh -i "your-key.pem" ubuntu@54.252.90.27

# Edit service file
sudo nano /etc/systemd/system/pizza-hut-tv.service
```

Find these lines:
```
Environment=GOOGLE_CLIENT_ID=OLD_CLIENT_ID
Environment=GOOGLE_CLIENT_SECRET=OLD_SECRET
```

Replace with your NEW credentials:
```
Environment=GOOGLE_CLIENT_ID=YOUR_NEW_CLIENT_ID.apps.googleusercontent.com
Environment=GOOGLE_CLIENT_SECRET=YOUR_NEW_CLIENT_SECRET
```

Save (Ctrl+X, Y, Enter)

### Step 7: Reload and Restart Service
```bash
sudo systemctl daemon-reload
sudo systemctl restart pizza-hut-tv
sudo systemctl status pizza-hut-tv
```

### Step 8: Test
1. Clear browser cookies (Ctrl+Shift+Delete)
2. Go to: https://api.everydayadvertise.com/
3. Click "Continue with Google"
4. Should work now! ✅

## 🔍 Alternative: Check Existing Client

Before creating a new one, check if your client exists but is disabled:

### Method 1: Search in Google Cloud Console
1. Go to: https://console.cloud.google.com/apis/credentials
2. Look for any OAuth 2.0 Client IDs
3. Click each one to check if the Client ID matches:
   ```
   REDACTED
   ```

### Method 2: Check All Projects
The client might be in a different project:
1. Click the project dropdown (top bar)
2. Click "ALL" tab
3. Check each project for OAuth credentials

### If Found:
- Click the pencil icon (✏️) to edit
- Verify redirect URIs include:
  ```
  https://api.everydayadvertise.com/auth/google/callback
  ```
- Make sure it's not disabled
- Click SAVE

## 📋 Verification Checklist

After updating credentials:

- [ ] New Client ID copied from Google Cloud Console
- [ ] New Client Secret copied from Google Cloud Console
- [ ] Service file updated with new credentials
- [ ] Service reloaded: `sudo systemctl daemon-reload`
- [ ] Service restarted: `sudo systemctl restart pizza-hut-tv`
- [ ] Service running: `sudo systemctl status pizza-hut-tv` (green "active")
- [ ] Redirect URIs include: `https://api.everydayadvertise.com/auth/google/callback`
- [ ] Browser cookies cleared
- [ ] Google login tested

## 🐛 Troubleshooting

### Still Getting "invalid_client"?
- Double-check Client ID in service file matches Google Console exactly
- No typos or extra spaces
- Restart service after changing

### Getting "redirect_uri_mismatch"?
- Add exact URI to Google Console: `https://api.everydayadvertise.com/auth/google/callback`
- No trailing slash
- Must be HTTPS (not HTTP)

### Getting "access_denied"?
- User cancelled login (normal)
- Or app is not published/verified (add yourself as test user)

### Can't Find Google Cloud Console Project?
- You may need to create a new project
- Follow Step 2 above

## 📞 Quick Test Commands

Check if OAuth client exists:
```bash
# This should redirect to Google login, NOT error page
curl -sL 'https://api.everydayadvertise.com/auth/google' | head -1
```

If you see:
- `accounts.google.com/o/oauth2/v2/auth` → ✅ Working!
- `accounts.google.com/signin/oauth/error` → ❌ Client not found

Check server logs:
```bash
ssh ubuntu@54.252.90.27
sudo journalctl -u pizza-hut-tv -n 50 | grep -i google
```

## 🎯 Summary

**Problem**: Google OAuth Client ID doesn't exist or was deleted
**Solution**: Create new OAuth client in Google Cloud Console OR find and enable existing one
**Critical Info Needed**:
- Client ID (from Google Console)
- Client Secret (from Google Console)
- Redirect URI: `https://api.everydayadvertise.com/auth/google/callback`

---

**Next Step**: Go to https://console.cloud.google.com/apis/credentials and either:
1. Find the existing client and verify it's enabled
2. Create a new OAuth client with the settings above

Then update the server configuration with the correct credentials! 🚀
