# 🍕 Pizza Hut TV - Complete Pi Webplayer Client

A full-featured Raspberry Pi client that replicates the web-based Pizza Hut TV player with native performance and enhanced reliability.

## 🌟 Features

### **Exact Webplayer Functionality**
- ✅ **Same Setup Flow**: 4-digit TV code → Store selection → Screen assignment
- ✅ **Same API Calls**: Uses identical endpoints as webplayer
- ✅ **Same Visual Design**: Pizza Hut gradient, colors, fonts, and layout
- ✅ **Same Synchronization**: Server time sync for multi-screen coordination
- ✅ **Same Effects**: 6 transition effects (fade, slide, zoom, rotate, cut)

### **Enhanced Pi Performance**
- 🚀 **Native Rendering**: Pygame-based graphics for smooth performance
- 🎬 **Media Caching**: Aggressive preloading and caching system
- 🔄 **Background Services**: Non-blocking network operations
- 💾 **Smart Cache Management**: Automatic cleanup and optimization
- 🎯 **Instant Switching**: Zero-delay media transitions

### **Professional Features**
- 🌐 **Server Time Sync**: Millisecond-accurate synchronization
- 📡 **Heartbeat System**: Keep-alive monitoring
- 🔄 **Auto-Updates**: Real-time playlist and effect synchronization
- 🎛️ **Remote Commands**: Server-side control and reload commands
- 📊 **Performance Monitoring**: Cache statistics and health reporting

## 🏗️ Architecture

### **Core Components**

1. **CompleteWebplayerClient** - Main application class
2. **MediaPlayer** - Handles media playback and transitions
3. **ServerTimeSync** - Server synchronization system
4. **PlaylistItem** - Data structure matching webplayer format

### **Service Threads**
- **Time Sync**: Server time synchronization (every 15s)
- **Heartbeat**: Keep-alive signals (every 30s)
- **Playlist**: Content updates (every 10s)
- **Effects**: Global effect sync (every 3s)
- **Commands**: Remote control polling (every 1.5s)

### **Media System**
- **Preloader**: Background media downloading
- **Cache Manager**: Memory and disk cache optimization
- **Transition Engine**: 6 effect types with smooth animations
- **Format Support**: Images (JPG, PNG, GIF, WebP) and Videos (MP4, WebM, etc.)

## 🚀 Quick Deployment

### **Windows PowerShell**
```powershell
# Deploy with default settings
.\Deploy-CompletePiClient.ps1

# Deploy with debug logging
.\Deploy-CompletePiClient.ps1 -Debug

# Deploy to custom Pi host
.\Deploy-CompletePiClient.ps1 -PiHost "user@custom-pi" -ServerUrl "https://your-server.com"
```

### **Cross-Platform Deployment**
```bash
# Make deployment script executable
chmod +x deploy_complete_pi_client.sh

# Deploy to Pi
./deploy_complete_pi_client.sh
```

## 📋 Requirements

### **Raspberry Pi**
- **Hardware**: Raspberry Pi 4 (recommended) or Pi 3B+
- **OS**: Raspberry Pi OS (Bullseye or newer)
- **Memory**: 2GB+ RAM recommended
- **Storage**: 8GB+ SD card with 2GB+ free space
- **Network**: WiFi or Ethernet connection

### **Python Dependencies**
- **pygame**: Graphics and input handling
- **requests**: HTTP client for API calls
- **pillow**: Image processing
- **numpy**: Numerical operations

## 🔧 Manual Installation

### **1. Prepare Raspberry Pi**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install python3-pip python3-venv python3-dev
sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev
sudo apt install libjpeg-dev zlib1g-dev

# Enable SSH (if not already enabled)
sudo systemctl enable ssh
sudo systemctl start ssh
```

### **2. Setup Python Environment**
```bash
# Create virtual environment
python3 -m venv pizza-hut-tv
source pizza-hut-tv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install pygame requests pillow numpy
```

### **3. Deploy Application Files**
```bash
# Copy files to Pi
scp complete_pi_client.py everydayadvertise@raspberrypi:~/
scp media_player.py everydayadvertise@raspberrypi:~/

# Make executable
chmod +x complete_pi_client.py
```

### **4. Create Systemd Service**
```bash
sudo tee /etc/systemd/system/pizza-hut-tv-complete.service > /dev/null << 'EOF'
[Unit]
Description=Pizza Hut TV Complete Digital Signage Client
After=graphical-session.target network-online.target
Wants=graphical-session.target network-online.target

[Service]
Type=simple
User=everydayadvertise
Environment=DISPLAY=:0
Environment=PYTHONPATH=/home/everydayadvertise
WorkingDirectory=/home/everydayadvertise
ExecStartPre=/bin/sleep 30
ExecStart=/home/everydayadvertise/pizza-hut-tv/bin/python /home/everydayadvertise/complete_pi_client.py --server https://everydayadvertise.com
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable pizza-hut-tv-complete
sudo systemctl start pizza-hut-tv-complete
```

## 🎮 Usage

### **Setup Flow**
1. **Boot**: Pi automatically starts the client fullscreen
2. **TV Code**: Enter 4-digit code from Android TV
3. **Store**: Select your Pizza Hut store
4. **Screen**: Choose screen assignment (tv1, tv2, tv3, tv4)
5. **Playback**: Automatic media playback begins

### **Controls**
- **ESC**: Exit application
- **F11**: Toggle fullscreen
- **SPACE**: Manual advance to next item (during playback)
- **Arrow Keys**: Navigate setup screens
- **Enter**: Confirm selections

### **Automatic Features**
- **Schedule Updates**: Real-time playlist changes
- **Effect Sync**: Global transition effects across all screens
- **Server Commands**: Remote reload and control
- **Health Monitoring**: Automatic recovery and restart

## 🔍 Monitoring & Troubleshooting

### **Service Status**
```bash
# Check service status
sudo systemctl status pizza-hut-tv-complete

# View live logs
journalctl -u pizza-hut-tv-complete -f

# Restart service
sudo systemctl restart pizza-hut-tv-complete
```

### **Performance Monitoring**
The client displays cache statistics in the overlay:
- **Memory Items**: Media cached in RAM
- **Download Items**: Files cached on disk
- **Cache Size**: Total disk cache usage (MB)

### **Common Issues**

**Connection Problems**
```bash
# Test server connectivity
curl -I https://everydayadvertise.com/api/server_time

# Check network interface
ip addr show

# Test DNS resolution
nslookup everydayadvertise.com
```

**Display Issues**
```bash
# Check X11 display
echo $DISPLAY

# List display modes
tvservice -m CEA

# Force specific resolution
sudo raspi-config  # Advanced Options > Resolution
```

**Service Issues**
```bash
# Check service logs for errors
journalctl -u pizza-hut-tv-complete -n 50

# Manual test run
source pizza-hut-tv/bin/activate
python complete_pi_client.py --debug
```

## 🔧 Configuration

### **Environment Variables**
- `DISPLAY=:0` - X11 display target
- `PYTHONPATH` - Python module search path

### **Command Line Options**
```bash
python complete_pi_client.py --help

Options:
  --server URL     Server URL (default: https://everydayadvertise.com)
  --debug          Enable debug logging
```

### **Cache Configuration**
Edit `media_player.py` to adjust cache settings:
```python
self.max_cache_items = 10      # Memory cache size
self.max_cache_size_mb = 500   # Disk cache limit (MB)
```

## 📊 API Compatibility

The Pi client uses the same API endpoints as the webplayer:

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `/api/stores_by_code/{code}` | Validate TV codes | On setup |
| `/playlist/{store}/{screen}` | Get content playlist | Every 10s |
| `/api/server_time` | Time synchronization | Every 15s |
| `/api/screen_heartbeat` | Keep-alive signal | Every 30s |
| `/api/get-effect/{store}` | Global effect sync | Every 3s |
| `/api/commands` | Remote commands | Every 1.5s |

## 🎯 Performance Optimization

### **Hardware Optimization**
- **GPU Memory Split**: Set to 128MB or higher (`sudo raspi-config`)
- **Overclocking**: Enable if thermal management allows
- **SD Card**: Use Class 10 or faster cards

### **Software Optimization**
- **Cache Management**: Automatic cleanup prevents memory issues  
- **Background Processing**: Non-blocking network operations
- **Resource Monitoring**: Built-in performance tracking

### **Network Optimization**
- **Preloading**: Next 4 items loaded in advance
- **Compression**: Automatic image optimization
- **Connection Pooling**: Reuse HTTP connections

## 🔒 Security

### **Network Security**
- **HTTPS Only**: All API calls use encrypted connections
- **Authentication**: TV codes provide access control
- **No Local Server**: Client-only, no incoming connections

### **System Security**
- **User Permissions**: Runs as non-root user
- **File Permissions**: Restricted file access
- **Service Isolation**: Systemd service boundaries

## 🤝 Integration

### **Digital Signage Networks**
The Pi client integrates seamlessly with existing Pizza Hut TV infrastructure:
- **Same Content**: Uses identical media files and playlists
- **Multi-Screen Support**: Coordinate multiple displays
- **Real-Time Updates**: Instant schedule changes
- **Remote Management**: Server-side control

### **Custom Extensions**
The modular design allows easy customization:
- **Custom Effects**: Add new transition animations
- **Media Formats**: Support additional file types
- **Network Protocols**: Integrate with other systems
- **Hardware Integration**: Connect external devices

---

## 📞 Support

For technical support or questions:
- **Service Logs**: `journalctl -u pizza-hut-tv-complete -f`
- **Manual Testing**: `python complete_pi_client.py --debug`
- **Network Testing**: Check connectivity to `https://everydayadvertise.com`

**🍕 Pizza Hut TV Complete Pi Client - Professional Digital Signage for Raspberry Pi** 🎯