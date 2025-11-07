# 🚀 Quick Deploy - Mobile Sync to Pi

## Files Ready for Deployment
✅ `pi_mobile_sync_addon.py` - Mobile sync addon module (NEW)
✅ `complete_pi_client.py` - Pi client with mobile sync integrated (MODIFIED)
✅ `deploy_mobile_sync_to_pi.py` - Automated deployment script (NEW)

## One-Command Deploy (when Pi is online)
```powershell
python deploy_mobile_sync_to_pi.py
```

## Manual Deploy Steps
```powershell
# Copy files
scp -i "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem" pi_mobile_sync_addon.py pi@203.158.51.30:/home/pi/pizza-hut-tv/
scp -i "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem" complete_pi_client.py pi@203.158.51.30:/home/pi/pizza-hut-tv/

# Install library on Pi
ssh -i "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem" pi@203.158.51.30
pip3 install qrcode[pil] --user

# Restart service
systemctl --user restart pizza-hut-tv.service
```

## What Changed
✅ Added QR code generation to Pi client
✅ Added WebSocket handlers for mobile input
✅ QR codes show in top-right corner during setup
✅ Mobile can scan once and control entire setup
✅ Keyboard input still works (backward compatible)
✅ **NO existing functionality broken**

## Testing
1. Look for QR code on Pi screen (top-right corner)
2. Scan with mobile phone
3. Enter codes on phone → Pi auto-advances
4. **OR** use keyboard like before - both work!

See `MOBILE_SYNC_PI_README.md` for full documentation.
