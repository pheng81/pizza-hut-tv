# Pizza Hut TV - Raspberry Pi Client
## Overview

The Raspberry Pi client displays Pizza Hut TV content on Raspberry Pi devices. It works seamlessly with your existing Android TV and webplayer setup, supporting the same playlist API and slice video system.

## Features

✅ **Full compatibility** with existing Pizza Hut TV system  
✅ **Hardware-optimized** video playback using omxplayer  
✅ **Multi-screen support** with slice video system  
✅ **Schedule-aware** content loading  
✅ **Auto-recovery** from network issues  
✅ **Fullscreen display** with no UI distractions  

## Requirements

- **Raspberry Pi 3B+** or newer (Pi 4 recommended)
- **Raspberry Pi OS** with desktop environment
- **Network connection** to Pizza Hut TV server
- **HDMI display** connected

## Quick Installation

1. **Copy files to your Pi:**
   ```bash
   # Transfer phtv_pi_client.py and install_pi_client.sh to your Pi
   scp phtv_pi_client.py install_pi_client.sh pi@your-pi-ip:~/
   ```

2. **Run the installer:**
   ```bash
   ssh pi@your-pi-ip
   cd ~
   chmod +x install_pi_client.sh
   ./install_pi_client.sh
   ```

3. **Configure your settings:**
   ```bash
   nano ~/pizza-hut-tv-pi/config.sh
   ```
   
   Update these values:
   ```bash
   export PHTV_SERVER="http://your-server:5002"
   export PHTV_STORE="your-store-id"
   export PHTV_SCREEN="your-screen-id"
   ```

4. **Test the client:**
   ```bash
   cd ~/pizza-hut-tv-pi
   ./start_phtv.sh
   ```

## Configuration Options

### Server Settings (Required)
- `PHTV_SERVER`: URL of your Pizza Hut TV server
- `PHTV_STORE`: Store ID (same as your Android TV setup)
- `PHTV_SCREEN`: Screen ID for this Pi client

### Display Settings
- `PHTV_FULLSCREEN`: Set to "false" for windowed mode
- `PHTV_DEBUG`: Set to "true" for detailed logging

### Example Configuration
```bash
# For a 3-screen setup where Pi is screen 2
export PHTV_SERVER="http://192.168.1.115:5002"
export PHTV_STORE="1000"
export PHTV_SCREEN="1000_screen2"
```

## Running the Client

### Manual Start (for testing)
```bash
cd ~/pizza-hut-tv-pi
./start_phtv.sh
```

### Auto-start on Boot
```bash
# Enable service
sudo systemctl enable pizza-hut-tv

# Start service  
sudo systemctl start pizza-hut-tv

# Check status
sudo systemctl status pizza-hut-tv

# View logs
journalctl -u pizza-hut-tv -f
```

## Controls

When the client is running:
- **ESC** or **Q** = Quit client
- **SPACE** = Skip to next video
- **N** = Next video  
- **R** = Refresh playlist from server

## Multi-Screen Setup

The Pi client works with your existing multi-screen slice video system:

1. **Configure slice settings** in the dashboard for your content
2. **Set the Pi's screen position** (left, center, right for 3-screen setup)
3. **The server automatically detects** Pi clients and serves appropriate slice URLs
4. **Videos play in sync** across all screens (Pi, Android TV, webplayer)

### Example 3-Screen Setup:
- **Screen 1** (Left): `1000_screen1` - Android TV  
- **Screen 2** (Center): `1000_screen2` - Raspberry Pi
- **Screen 3** (Right): `1000_screen3` - Webplayer

## Troubleshooting

### Video Won't Play
```bash
# Check if video players are installed
which omxplayer
which cvlc

# Install missing players
sudo apt update
sudo apt install omxplayer vlc
```

### Network Issues  
```bash
# Test server connection
curl -I http://your-server:5002/api/playlist/your-store/your-screen

# Check if server is accessible
ping your-server-ip
```

### Display Issues
```bash  
# Check display resolution
tvservice -s

# Force HDMI output (add to /boot/config.txt)
hdmi_force_hotplug=1
hdmi_drive=2
```

### Service Issues
```bash
# Restart service
sudo systemctl restart pizza-hut-tv

# Check logs
journalctl -u pizza-hut-tv --since "10 minutes ago"

# Disable auto-start
sudo systemctl disable pizza-hut-tv
```

## Advanced Configuration

### Custom Video Players
The client tries players in this order:
1. **omxplayer** (Pi-optimized, hardware acceleration)  
2. **VLC** (software fallback)

### Performance Tuning
For better performance on older Pi models:

1. **Increase GPU memory** in `/boot/config.txt`:
   ```
   gpu_mem=256
   ```

2. **Use Pi 4** for 4K content or high frame rates

3. **Wired network** recommended for large video files

## Integration with Existing System

The Pi client integrates seamlessly:

- ✅ **Uses same API** as Android TV and webplayer
- ✅ **Supports same scheduling** system  
- ✅ **Gets slice videos** automatically
- ✅ **No server changes** needed (already included)
- ✅ **Same dashboard** controls all clients

## System Requirements

### Minimum (720p content):
- Raspberry Pi 3B+
- 1GB RAM  
- 8GB SD card
- 10Mbps network

### Recommended (1080p content):
- Raspberry Pi 4 (4GB RAM)
- 32GB SD card (Class 10)
- 100Mbps network
- Heat sink/fan for continuous operation

## File Locations

After installation:
- **Client**: `~/pizza-hut-tv-pi/phtv_pi_client.py`
- **Config**: `~/pizza-hut-tv-pi/config.sh`
- **Startup**: `~/pizza-hut-tv-pi/start_phtv.sh`
- **Service**: `/etc/systemd/system/pizza-hut-tv.service`
- **Logs**: `journalctl -u pizza-hut-tv`

## Support

For issues with the Pi client:

1. **Check the logs** first: `journalctl -u pizza-hut-tv -f`
2. **Test manually** with debug enabled: `./start_phtv.sh` with `PHTV_DEBUG="true"`
3. **Verify server connectivity** from Pi
4. **Check video player installation**

The Pi client is designed to be reliable and self-recovering, automatically handling network issues and playlist changes.