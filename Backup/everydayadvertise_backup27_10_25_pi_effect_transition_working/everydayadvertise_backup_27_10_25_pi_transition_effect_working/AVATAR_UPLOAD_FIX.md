# Avatar Upload Issue - Diagnosis and Fix

**Date**: October 4, 2025
**Issue**: Profile image upload works sometimes but not always

## Problems Identified

### 1. **Insufficient Error Handling**
- No logging when uploads fail
- Generic error messages don't help debug issues
- No validation of username before processing

### 2. **Path Separator Issues (Windows/Linux)**
- Used `os.path.join()` but didn't normalize separators
- Windows uses `\` but URLs need `/`
- Could cause issues when deployed to Linux server

### 3. **Missing File Existence Checks**
- `/api/me` endpoint doesn't verify avatar file exists
- Could return broken URLs if file was deleted
- No cleanup of invalid database entries

### 4. **No Rollback on Partial Failures**
- If database update fails after file save, file remains orphaned
- No transaction handling between file save and DB update

### 5. **Cache-Busting Could Fail Silently**
- If `os.path.getmtime()` fails, no fallback timestamp
- Could show old cached images

## Fixes Applied

### ✅ Enhanced `/api/profile/avatar` endpoint:
```python
- Added detailed logging at each step
- Better error messages for users
- Validate username before processing image
- Wrap image processing in try-catch with specific error
- Ensure avatar folder exists before saving
- Normalize path separators (replace \ with /)
- Add fallback timestamp if mtime fails
- Rollback file save if database update fails
- Log all errors with stack traces
```

### ✅ Enhanced `/api/me` endpoint:
```python
- Validate avatar file actually exists
- Normalize path separators
- Clear invalid avatar entries from database
- Add cache-buster to avatar URLs
- Better error logging
```

## Testing Recommendations

### Local Testing:
1. Upload a profile image
2. Check browser console for errors
3. Check `startup_log.txt` for server logs
4. Verify file is saved to `static/uploads/avatars/`
5. Try refreshing page - image should persist

### Server Testing:
1. SSH to server and check `/var/www/pizza-hut-tv/static/uploads/avatars/`
2. Check permissions: `ls -la /var/www/pizza-hut-tv/static/uploads/avatars/`
3. Check server logs: `sudo journalctl -u pizza-hut-tv -f`
4. Upload avatar and watch logs in real-time

### Common Issues to Check:

| Issue | Solution |
|-------|----------|
| Folder doesn't exist | App now creates it automatically |
| Permission denied | Run `sudo chown -R www-data:www-data /var/www/pizza-hut-tv/static/uploads` |
| PIL not installed | Run `pip install Pillow` in venv |
| File size too large | Check Nginx/Flask upload limits |
| Path separator mismatch | Fixed - now normalizes to forward slashes |

## What Changed

### Before:
```python
# Simple, but no error handling
im.save(save_path, format='PNG')
rel = os.path.join('uploads', 'avatars', f'{safe_key}.png')
db.execute('UPDATE users SET avatar = ? WHERE username = ?', (rel, uname))
```

### After:
```python
# Robust error handling and logging
try:
    im.save(save_path, format='PNG', optimize=True)
    logging.info(f'Avatar saved to: {save_path}')
except Exception as save_err:
    logging.error(f'Failed to save avatar: {save_err}')
    return jsonify({'success': False, 'error': 'Failed to save image'}), 500

rel = os.path.join('uploads', 'avatars', f'{safe_key}.png').replace('\\', '/')

try:
    db.execute('UPDATE users SET avatar = ? WHERE username = ?', (rel, uname))
    db.commit()
except Exception as db_err:
    os.remove(save_path)  # Rollback file save
    return jsonify({'success': False, 'error': 'Failed to update profile'}), 500
```

## Next Steps

1. **Deploy to server** with these fixes
2. **Monitor logs** during next upload attempt
3. **Check permissions** on server avatar folder
4. **Test with different image formats** (JPEG, PNG, HEIC, etc.)
5. **Test with different file sizes** (small and large)

## Deploy Command

```powershell
.\deploy_to_server.ps1 -Server '54.252.90.27' -KeyPath 'C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem'
```

## Monitoring Commands

```bash
# Watch logs in real-time
sudo journalctl -u pizza-hut-tv -f

# Check avatar folder
ls -la /var/www/pizza-hut-tv/static/uploads/avatars/

# Check folder permissions
stat /var/www/pizza-hut-tv/static/uploads/avatars/

# Fix permissions if needed
sudo chown -R www-data:www-data /var/www/pizza-hut-tv/static/uploads
sudo chmod -R 755 /var/www/pizza-hut-tv/static/uploads
```

## Summary

The intermittent failures were likely caused by:
1. **Silent failures** - no logging made debugging impossible
2. **Path separator issues** - Windows paths with backslashes 
3. **Missing file validation** - broken URLs for deleted files
4. **No error recovery** - partial failures left system in bad state

All of these have been fixed with proper error handling, logging, validation, and rollback mechanisms.
