# 🚀 Pizza Hut TV Deployment Summary

## ✅ COMPLETED - Raspberry Pi Deployment
- **File**: `ea_tv.py` successfully deployed to Pi
- **Size**: 85KB
- **Updated**: September 29, 2025
- **Location**: `/home/everydayadvertise/Desktop/ea_tv.py`

### Key Features Deployed to Pi:
✅ **Mixed Media Handling**: Proper detection and specialized handling for slice videos + images
✅ **Schedule-Aware Transitions**: Respects time/date/day scheduling, stops when no content scheduled  
✅ **VLC Crop Fix**: Corrected duplicate mixed media detection that was breaking slice cropping
✅ **Smart Refresh Timing**: 10-30 second schedule checks for smooth transitions
✅ **Process Monitoring**: Automatic VLC restart when processes die

### Pi Client Capabilities:
- Multi-screen slice support (2, 3, 4, 5+ screens)
- Horizontal and vertical layouts
- Mixed media playlists (slice videos + images)
- Fade transitions between scheduled content
- Auto-restart on schedule changes
- VLC crash recovery

## 📋 TODO - Server Deployment  
The server code (`app.py`) contains these improvements but needs manual deployment:

### Server Updates Available:
- ✅ **Auto-clean fix**: Playlist auto-deletion disabled (`if False:`)  
- ✅ **Comprehensive scheduling**: Multi-window support, time/date/day filtering
- ✅ **Slice URL generation**: Proper slice parameters for multi-screen setups

### Manual Server Deployment Steps:
```bash
# 1. Connect to server (requires SSH key)
ssh ubuntu@54.252.90.27

# 2. Backup current version
cp /home/ubuntu/pizza-hut-tv/app.py /home/ubuntu/pizza-hut-tv/app.py.backup

# 3. Upload new app.py (use your preferred method)
# - SCP with SSH key
# - Git pull if using repository
# - Direct file copy

# 4. Restart Flask service
sudo systemctl restart pizza-hut-tv
sudo systemctl status pizza-hut-tv
```

## 🧪 Testing Instructions

### Test Pi Client:
```bash
# Basic functionality test
ssh everydayadvertise@raspberrypi.local "cd Desktop && python3 ea_tv.py --screen 2"

# Check for proper slice cropping
# Should show middle portion of 3-screen horizontal videos
```

### Test Server (after deployment):
```bash
# Check playlist endpoint
curl "https://everydayadvertise.com/playlist/1000/1000_screen2"

# Verify slice URLs are generated correctly  
# Should contain: slice_mode=split-h&slice_count=3&slice_order=1
```

## 🎯 Expected Behavior After Full Deployment:

1. **Schedule Transitions**: Pi will smoothly transition between scheduled content, stop when no schedule active
2. **Mixed Media**: Slice videos + images will play with specialized handling to avoid VLC crashes  
3. **Slice Cropping**: Screen 2/3 will show correct portions using server-side slicing for mixed media
4. **Scheduling**: Time/date/day filters will work properly, content only plays during scheduled windows

## 🔧 Troubleshooting:

### If Pi shows full video instead of slices:
- Check if mixed media detection is working (look for "Mixed media with slice videos detected")
- Verify slice URL parameters in logs
- Ensure server-side slicing is working correctly

### If transitions are rough:
- Check schedule timing (should check every 10-30 seconds)
- Verify VLC processes are restarting cleanly
- Look for VLC crash messages in logs

### If scheduling not working:
- Verify server deployment completed
- Check schedule windows in dashboard
- Ensure time/date settings are correct

---
**Deployment Status**: Pi ✅ | Server ⏳ (manual deployment needed)