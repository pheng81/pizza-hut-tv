# Pizza Hut TV Server Deployment

## Quick Deploy Command
```powershell
cd 'c:\Users\toeng\Pizza Hut TV'
.\deploy_to_server.ps1 -Server '54.252.90.27' -KeyPath 'C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem'
```

## What Gets Deployed
- `app.py` - Main Flask application (with auto-clean bug fix)
- `requirements.txt` - Python dependencies
- `database.db` - Application database
- `users.sqlite` - User database
- `templates/webplayer/` - Updated webplayer templates

## Server Details
- **Server**: 54.252.90.27 (Ubuntu Lightsail)
- **Service**: `pizza-hut-tv.service`
- **Path**: `/home/ubuntu/pizza-hut-tv/`
- **Port**: 5002 (internal), 80/443 (external via nginx)

## Post-Deploy Verification
```bash
# Check service status
sudo systemctl status pizza-hut-tv

# Test API endpoint
curl 'http://127.0.0.1:5002/playlist/1000/1000_screen2?user_code=4682'

# Check logs
tail -f pizza-hut-tv/server.log
```

## Bug Fix Applied
✅ **Auto-clean playlist deletion bug FIXED**
- Changed `if not r2_enabled():` to `if False:` in `get_playlist()`
- Playlists will no longer randomly disappear
- Server preserves all playlist data

## Last Deployed
September 27, 2025 - Auto-clean bug fix and template updates