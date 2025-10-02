# Custom Media Player - Installation & Usage Guide

## 🎬 Overview

This is a **custom Python-based media player** specifically designed for multi-screen slice video playback. It replaces VLC/MPV with a solution that has full control over:

- ✅ **Slice video cropping** - Shows correct portion per screen
- ✅ **Mixed media handling** - Videos + images in same playlist
- ✅ **Smooth transitions** - Fade effects between media
- ✅ **Sync across screens** - Perfect synchronization
- ✅ **Dashboard integration** - Works with existing scheduling system

## 📋 Features

### Intelligent Media Handling
- **Slice Videos (5760x1080)**: Automatically crops to show screen-specific portion
  - Screen 1: Shows left 1920px (0-1920)
  - Screen 2: Shows middle 1920px (1920-3840)
  - Screen 3: Shows right 1920px (3840-5760)
- **Normal Videos**: Scales to fit screen while maintaining aspect ratio
- **Images**: Displays full screen with proper aspect ratio
- **Mixed Playlists**: Handles videos + images seamlessly

### Transitions & Effects
- Smooth fade transitions between media items
- Configurable transition duration
- No flickering or black screens

### Scheduling & Sync
- Fetches playlists from server every 15 seconds
- Auto-detects schedule changes
- Loops playlist items based on duration
- Synchronizes across multiple screens

## 🚀 Installation

### Step 1: SSH into Raspberry Pi
```bash
ssh everydayadvertise@raspberrypi.local
```

### Step 2: Run Installation Script
```bash
cd ~/Desktop
chmod +x install_custom_player.sh
bash install_custom_player.sh
```

This will:
- Install Python dependencies (OpenCV, PIL, NumPy, Requests)
- Make player executable
- Create systemd service for autostart

## 🎮 Usage

### Manual Start (for testing)
```bash
# For screen 1
python3 /home/everydayadvertise/Desktop/custom_player.py 1000 1

# For screen 2 (middle slice)
python3 /home/everydayadvertise/Desktop/custom_player.py 1000 2

# For screen 3 (right slice)
python3 /home/everydayadvertise/Desktop/custom_player.py 1000 3
```

**Command Format:**
```
python3 custom_player.py <store_code> <screen_id> [android_tv_code]
```

### Autostart on Boot

Enable the systemd service:
```bash
sudo systemctl enable custom-player.service
sudo systemctl start custom-player.service
```

Check status:
```bash
sudo systemctl status custom-player.service
```

View real-time logs:
```bash
journalctl -u custom-player.service -f
```

Stop the service:
```bash
sudo systemctl stop custom-player.service
```

### Edit Autostart Configuration

To change screen number or store code:
```bash
sudo nano /etc/systemd/system/custom-player.service
```

Edit the `ExecStart` line:
```
ExecStart=/usr/bin/python3 /home/everydayadvertise/Desktop/custom_player.py 1000 2
                                                                          ^^^^ ^^^^
                                                                          store screen
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart custom-player.service
```

## 🔧 How It Works

### Media Detection & Processing

1. **Fetches playlist** from server (`/playlist/{store}/{screen_id}`)
2. **Resolves URLs** - prioritizes slice_url for slice-aware content
3. **Downloads media** and caches locally
4. **Detects media type**:
   - Videos: Opens with OpenCV VideoCapture
   - Images: Loads with PIL
5. **Intelligent cropping**:
   - Checks video dimensions
   - If 5760px wide → Crops to show screen-specific slice
   - If other size → Scales to fit screen
6. **Displays** with fade transitions
7. **Loops** through playlist continuously

### Sync Mechanism

- All screens fetch same playlist from server
- Each screen calculates its own crop offset
- Media starts at same time (network-dependent)
- Smooth transitions ensure no visible gaps

## 🐛 Troubleshooting

### Player won't start
```bash
# Check if dependencies installed
python3 -c "import cv2; import PIL; import numpy; import requests; print('All OK')"

# Check display
echo $DISPLAY  # Should show :0

# Try manual start with verbose output
python3 /home/everydayadvertise/Desktop/custom_player.py 1000 2
```

### Black screen showing
- Check if playlist has content: `curl https://everydayadvertise.com/playlist/1000/1000_screen2`
- Check network connection
- View logs: `journalctl -u custom-player.service -f`

### Wrong crop showing
- Verify screen number in command: `python3 custom_player.py 1000 2` (2 = middle screen)
- Check video dimensions (should be 5760x1080 for slice videos)

### Images not displaying
- Check image URL is accessible
- Verify image format (JPG/PNG supported)
- Check logs for download errors

### Stop the old VLC/MPV player
```bash
# Kill any running VLC/MPV
pkill vlc
pkill mpv

# Disable old autostart
sudo systemctl stop ea-tv.service
sudo systemctl disable ea-tv.service
```

## 📊 Dashboard Integration

The custom player works with your existing dashboard:
- Fetches schedules from same API
- Uses same screen ID format (`1000_screen2`)
- Respects schedule windows and timing
- No changes needed to dashboard code

## 🎯 Benefits Over VLC/MPV

| Feature | VLC/MPV | Custom Player |
|---------|---------|---------------|
| Slice video cropping | ⚠️ Global filter only | ✅ Per-video detection |
| Mixed media support | ❌ Breaks with crop | ✅ Seamless handling |
| Transition effects | ⚠️ Limited | ✅ Smooth fade |
| Image display | ⚠️ Cropped incorrectly | ✅ Full screen |
| Sync control | ⚠️ Process-based | ✅ Frame-level |
| Debugging | ❌ Black box | ✅ Full logging |

## 📝 Configuration

Edit `custom_player.py` to customize:

```python
# Transition duration (line ~30)
self.transition_duration = 0.5  # seconds (0.5 = half second fade)

# Enable/disable fade
self.fade_enabled = True  # Set to False for instant cuts

# Screen resolution
self.screen_width = 1920
self.screen_height = 1080

# Playlist refresh interval (line ~400)
time.sleep(15)  # Check server every 15 seconds
```

## 🔄 Updates

To update the player:
```bash
# Download new version (from your PC)
scp custom_player.py everydayadvertise@raspberrypi.local:/home/everydayadvertise/Desktop/

# Restart service
sudo systemctl restart custom-player.service
```

## 🎉 Testing

1. Start player manually: `python3 custom_player.py 1000 2`
2. Check console output for errors
3. Verify correct content showing on screen
4. Test schedule changes on dashboard
5. Confirm smooth transitions between items
6. Check sync across multiple screens

## 📞 Support

If issues persist:
1. Collect logs: `journalctl -u custom-player.service -n 100 > player_logs.txt`
2. Check playlist: `curl https://everydayadvertise.com/playlist/1000/1000_screen2`
3. Verify media URLs are accessible
4. Test with single screen first before multi-screen setup
