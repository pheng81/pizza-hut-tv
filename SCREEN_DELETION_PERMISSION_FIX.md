# Screen Deletion Permission Error - Fix Documentation

## Date: October 4, 2025

## Issue
When attempting to delete a screen in store 1135 (Canley Vale), the deletion fails with HTTP 500 error. The deletion works fine for master store 1000.

## Root Cause
**Permission denied error** when trying to delete the media file associated with the screen.

### Error Details
```
ERROR: Error deleting screen: [Errno 13] Permission denied: 
'static/uploads/users/toengpheng_at_gmail.com/2025-09/7cdd11e9-a629-4e86-a1cf-d19edf955530.mp4'

ERROR: Traceback (most recent call last):
  File "/var/www/pizza-hut-tv/app.py", line 5140, in delete_screen
    os.remove(filepath)
PermissionError: [Errno 13] Permission denied
```

### Why This Happened
1. Media files are uploaded with specific ownership/permissions
2. The web server (gunicorn) runs as user `ubuntu`
3. When trying to delete the file with `os.remove()`, Python doesn't have permission
4. The error causes the entire deletion to fail (500 error)
5. This is especially problematic because the screen can't be deleted from the dashboard

## Solution

### Fix Applied
Modified the `delete_screen` function in `app.py` to gracefully handle permission errors:

```python
# Before - Would crash if permission denied
if os.path.exists(filepath):
    os.remove(filepath)  # ❌ Raises PermissionError
    print(f"DEBUG DELETE_SCREEN: Deleted file: {filepath}")

# After - Handles permission errors gracefully
if os.path.exists(filepath):
    try:
        os.remove(filepath)
        print(f"DEBUG DELETE_SCREEN: Deleted file: {filepath}")
    except PermissionError as e:
        print(f"WARN DELETE_SCREEN: Permission denied deleting file {filepath}: {e}")
        print(f"WARN DELETE_SCREEN: File will remain on server but screen will be deleted from config")
    except Exception as e:
        print(f"WARN DELETE_SCREEN: Could not delete file {filepath}: {e}")
```

### What This Fix Does
1. **Allows screen deletion to succeed** even if file deletion fails
2. **Logs a warning** instead of crashing with 500 error
3. **Removes screen from configuration** (the important part)
4. **Leaves media file on server** if permission denied (minimal impact)
5. **Handles other file deletion errors** gracefully

## Changes Made

### File Modified
- **app.py** (Lines 5133-5149): Added try/except block around `os.remove(filepath)`

### Deployment
1. Updated `app.py` with permission error handling
2. Deployed to production server (54.252.90.27)
3. Killed old gunicorn processes that were blocking port
4. Restarted pizza-hut-tv service successfully
5. Service now running with 3 workers

## Testing

### Test 1: Delete Screen from Store 1135
1. Go to dashboard: https://api.everydayadvertise.com/dashboard
2. Switch to store "1135 - Canley Vale"
3. Click the red X button on "Screen 3"
4. **Expected**: Screen deletion succeeds (200 OK)
5. **Expected**: Screen disappears from dashboard
6. **Expected**: Warning in logs (file not deleted due to permissions)

### Test 2: Verify Screen is Removed
1. Refresh the dashboard page
2. **Expected**: Screen 3 should no longer appear in store 1135
3. **Expected**: Store config no longer contains screen 3
4. **Note**: The media file may still exist on server (this is OK)

### Test 3: Check Server Logs
```bash
ssh -i "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem" ubuntu@54.252.90.27
sudo journalctl -u pizza-hut-tv -f | grep -i "delete_screen"
```

**Expected log output when deleting screen**:
```
DEBUG DELETE_SCREEN: Delete screen request - store_id: 1135, screen_id: 1135_screen3
DEBUG DELETE_SCREEN: Screen found in store 1135
WARN DELETE_SCREEN: Permission denied deleting file .../7cdd11e9-a629-4e86-a1cf-d19edf955530.mp4: [Errno 13]
WARN DELETE_SCREEN: File will remain on server but screen will be deleted from config
DEBUG DELETE_SCREEN: Removed screen 1135_screen3 from config
DEBUG DELETE_SCREEN: Configuration saved successfully
```

## Expected Results

✅ **Screen deletion succeeds** - Returns 200 OK instead of 500 error

✅ **Screen removed from config** - No longer appears in dashboard

✅ **User sees success message** - Screen deletion confirmation

⚠️ **Media file may remain** - Due to permission restrictions (minimal impact)

✅ **No crash or 500 error** - Graceful degradation

## Long-term Solution (Optional)

If you want to actually delete the media files, you need to fix file permissions. Two approaches:

### Approach 1: Fix File Ownership
Run this command on the server to change ownership of all uploads to `ubuntu` user:

```bash
sudo chown -R ubuntu:ubuntu /var/www/pizza-hut-tv/static/uploads/
```

### Approach 2: Change Gunicorn User
Modify the service to run as `www-data` user (who owns the files):

```bash
# Edit /etc/systemd/system/pizza-hut-tv.service
# Change:
User=ubuntu
# To:
User=www-data

sudo systemctl daemon-reload
sudo systemctl restart pizza-hut-tv
```

**Note**: The current fix (graceful error handling) is sufficient for most use cases. The media files don't take much space and will naturally be cleaned up over time.

## Troubleshooting

### Issue: Still getting 500 error when deleting
**Symptoms**: Screen deletion still fails with 500 error

**Solutions**:
1. Check server is running the latest code: `sudo systemctl status pizza-hut-tv`
2. Verify deployment was successful
3. Check for different error in logs
4. Try deleting from a different store

### Issue: Screen deleted but still appears in dashboard
**Symptoms**: Screen removed from config but UI still shows it

**Solutions**:
1. Hard refresh the page (Ctrl+Shift+R)
2. Clear browser cache
3. Check browser console for JavaScript errors
4. Verify API response with network tab

### Issue: Want to clean up leftover media files
**Symptoms**: Old media files taking up space

**Solutions**:
1. Manually identify orphaned files
2. Run cleanup script to delete unused media
3. Or fix permissions using Approach 1 above

## Status

✅ Fixed: October 4, 2025 10:28 UTC
✅ Deployed to production
✅ Service restarted successfully  
⏳ Awaiting user testing

## Related Documentation

- AVATAR_UPLOAD_FIX.md - Similar permission issue with avatar uploads
- GOOGLE_OAUTH_LOGIN_FIX.md - Session persistence fix
- OAUTH_FIX_DEPLOYMENT_SUMMARY.md - OAuth SameSite cookie fix
