# Pizza Hut TV - Raspberry Pi Client

Complete software package for displaying Pizza Hut TV content on Raspberry Pi.

## Quick Setup

### 1-Command Install
```bash
curl -sSL https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/setup-pi.sh | bash
```

### Manual Install
```bash
# Download installer
wget https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/setup-pi.sh

# Make executable and run
chmod +x setup-pi.sh
./setup-pi.sh
```

## What Gets Installed

- **Complete Pi client** - Python-based video player optimized for Pi hardware
- **Auto-start service** - Systemd service that starts on boot
- **Video player support** - omxplayer (Pi-optimized) and VLC fallback
- **Easy configuration** - Simple config file for server settings
- **Logging & monitoring** - Full systemd integration with logs

## After Installation

### 1. Configure Server Settings
```bash
nano ~/pizza-hut-tv-pi/phtv-config
```

Edit these values:
```bash
PHTV_SERVER="http://YOUR_SERVER_IP:5002"  # Your server address
PHTV_STORE="YOUR_STORE_ID"                # Store ID (e.g., "1000")
PHTV_SCREEN="tv1"                         # Screen ID (tv1, tv2, etc.)
```

### 2. Test Manually
```bash
cd ~/pizza-hut-tv-pi
./phtv-start
```

### 3. Enable Auto-Start
```bash
sudo systemctl enable pizza-hut-tv
sudo systemctl start pizza-hut-tv
```

### 4. Monitor Service
```bash
# Check status
sudo systemctl status pizza-hut-tv

# View live logs
journalctl -u pizza-hut-tv -f

# Restart service
sudo systemctl restart pizza-hut-tv
```

## Features

- **Multi-screen support** - Works with slice video system
- **Auto playlist refresh** - Updates content without restart
- **Hardware optimized** - Uses omxplayer for best Pi performance
- **Error recovery** - Automatically handles network issues
- **Fullscreen display** - Optimized for TV/monitor display
- **Zero configuration** - Works out-of-box with Pizza Hut TV server

## Compatibility

- **Pi Models**: Pi 3, Pi 4, Pi Zero 2 W (recommended)
- **OS**: Raspberry Pi OS (Bullseye/Bookworm)
- **Video**: MP4, AVI, MKV (hardware accelerated on Pi)

## Architecture

The Pi client:
1. Connects to Pizza Hut TV server with `phtv-pi/1.0` User-Agent
2. Gets slice URLs automatically for multi-screen setups
3. Uses omxplayer for hardware-accelerated playback
4. Refreshes playlist every 5 seconds
5. Handles network reconnection automatically

## Troubleshooting

### Service Not Starting
```bash
# Check service logs
journalctl -u pizza-hut-tv -n 20

# Check config file
cat ~/pizza-hut-tv-pi/phtv-config
```

### Video Not Playing
```bash
# Test video players
omxplayer --version
cvlc --version

# Check server connection
curl http://YOUR_SERVER/api/playlist/YOUR_STORE/tv1
```

### Update Client
```bash
# Re-run installer (preserves config)
curl -sSL https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/setup-pi.sh | bash
```

## Manual Commands

```bash
# Start client
cd ~/pizza-hut-tv-pi && ./phtv-start

# Start with debug
cd ~/pizza-hut-tv-pi && python3 phtv_pi_client.py --server http://192.168.1.115:5002 --store 1000 --screen tv1 --debug

# Stop service
sudo systemctl stop pizza-hut-tv

# Disable auto-start
sudo systemctl disable pizza-hut-tv
```

## File Locations

- **Client files**: `~/pizza-hut-tv-pi/`
- **Configuration**: `~/pizza-hut-tv-pi/phtv-config`
- **Service file**: `/etc/systemd/system/pizza-hut-tv.service`
- **Logs**: `journalctl -u pizza-hut-tv`

## Support

The Pi client integrates seamlessly with your existing Pizza Hut TV system:
- Uses same playlist API as Android TV and webplayer
- Gets slice video URLs automatically 
- Works in multi-screen configurations
- No server changes required