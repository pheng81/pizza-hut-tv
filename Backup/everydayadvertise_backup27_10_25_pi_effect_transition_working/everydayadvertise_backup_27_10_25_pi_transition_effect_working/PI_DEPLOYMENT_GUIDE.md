# 🍕 Pizza Hut TV - Raspberry Pi Deployment Guide

## Overview

This guide covers deploying the enhanced Pizza Hut TV client on Raspberry Pi devices. The system provides professional-grade digital signage with enterprise synchronization capabilities.

## 🎯 Features

### Core Features
- **Hardware-Accelerated Playback**: OMXPlayer, VLC, and Pygame backends
- **Professional Synchronization**: Frame-perfect sync with webplayer
- **Auto-Recovery**: Network resilience and error recovery
- **Performance Monitoring**: Real-time system monitoring
- **Zero-Config Deployment**: Auto-discovery and configuration
- **Multi-Backend Fallback**: Automatic video backend selection

### Pi-Specific Optimizations
- **GPU Memory Management**: Automatic detection and recommendations
- **Hardware Detection**: Pi model detection and optimization
- **Power Management**: Optimized for 24/7 operation
- **Service Management**: Systemd integration with auto-restart

## 🚀 Quick Start

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Download installation script
wget https://your-server.com/install_enhanced_pi.sh
chmod +x install_enhanced_pi.sh

# Run installation
./install_enhanced_pi.sh
```

### 2. Copy Client Files

```bash
# Copy the enhanced client
scp enhanced_pi_client.py pi@raspberrypi:/home/pi/pizza-hut-tv/
scp pi_config_tool.py pi@raspberrypi:/home/pi/pizza-hut-tv/
scp pi_requirements.txt pi@raspberrypi:/home/pi/pizza-hut-tv/
```

### 3. Configure Client

```bash
# SSH to Pi
ssh pi@raspberrypi

# Run configuration tool
cd /home/pi/pizza-hut-tv
python3 pi_config_tool.py
```

### 4. Start Service

```bash
# Start the service
sudo systemctl start phtv-client

# Enable auto-start
sudo systemctl enable phtv-client

# Check status
sudo systemctl status phtv-client
```

## 🛠️ Manual Installation

### Prerequisites

```bash
# System packages
sudo apt install -y \
    python3-pip python3-venv python3-dev \
    omxplayer vlc ffmpeg \
    libsdl2-dev libfreetype6-dev \
    libraspberrypi-dev supervisor
```

### Python Environment

```bash
# Create installation directory
sudo mkdir -p /home/pi/pizza-hut-tv
sudo chown pi:pi /home/pi/pizza-hut-tv
cd /home/pi/pizza-hut-tv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r pi_requirements.txt
```

### Configuration

Create `/home/pi/pizza-hut-tv/config.json`:

```json
{
  "server_url": "https://everydayadvertise.com",
  "store_id": "PHTV001",
  "screen_id": "tv1",
  "fullscreen": true,
  "auto_start": true,
  "sync_enabled": true,
  "performance_monitoring": true,
  "debug_mode": false,
  "video_backend": "auto",
  "network_timeout": 10,
  "playlist_refresh_interval": 5,
  "sync_tolerance": 0.05
}
```

### Service Setup

Create `/etc/systemd/system/phtv-client.service`:

```ini
[Unit]
Description=Pizza Hut TV Enhanced Pi Client
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=pi
WorkingDirectory=/home/pi/pizza-hut-tv
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 30
ExecStart=/home/pi/pizza-hut-tv/venv/bin/python /home/pi/pizza-hut-tv/enhanced_pi_client.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=phtv-client

[Install]
WantedBy=multi-user.target
```

## 🔧 Configuration Options

### Video Backends

| Backend    | Description                    | Pi Models    | Performance |
|------------|--------------------------------|--------------|-------------|
| OMXPlayer  | Hardware-accelerated (legacy)  | Pi 3, Pi 4   | Excellent   |
| VLC        | Hardware-accelerated (modern)  | Pi 4, Pi 5   | Excellent   |
| Pygame     | Software fallback              | All models   | Basic       |

### Performance Settings

```json
{
  "video_backend": "auto",           // auto, omxplayer, vlc, pygame
  "gpu_memory": 128,                 // GPU memory split (MB)
  "fullscreen": true,                // Fullscreen playback
  "sync_tolerance": 0.05,            // Sync tolerance (seconds)
  "network_timeout": 10,             // Network timeout (seconds)
  "playlist_refresh_interval": 5,    // Playlist refresh (seconds)
  "performance_monitoring": true     // Enable monitoring
}
```

## 📊 Monitoring & Management

### Service Commands

```bash
# Service control
sudo systemctl start phtv-client
sudo systemctl stop phtv-client
sudo systemctl restart phtv-client
sudo systemctl status phtv-client

# View logs
journalctl -u phtv-client -f
journalctl -u phtv-client -n 100

# Quick scripts
/home/pi/pizza-hut-tv/status.sh
/home/pi/pizza-hut-tv/update.sh
```

### Performance Monitoring

The client provides built-in monitoring:

```bash
# Real-time status
tail -f /var/log/phtv/client.log

# System resources
htop
vcgencmd measure_temp
vcgencmd get_throttled
```

### Configuration Tool

```bash
# Interactive configuration
cd /home/pi/pizza-hut-tv
python3 pi_config_tool.py
```

Features:
- Auto-detect servers on network
- Test server connectivity
- Configure store/screen IDs
- Select video backend
- System information display

## 🔄 Synchronization

### Global Sync Architecture

The Pi client uses the same synchronization system as the webplayer:

1. **Server Timestamp**: Fetches global time from `/api/sync-time`
2. **Sync Intervals**: 2-second aligned intervals
3. **Tolerance**: 50ms sync tolerance
4. **Fallback**: Local sync if server unavailable

### Sync API Endpoint

```javascript
// Server provides sync timing
GET /api/sync-time
{
  "current_time": 1693891234567,
  "sync_interval": 2000,
  "timestamp": 1693891236000
}
```

## 🚨 Troubleshooting

### Common Issues

#### No Video Output
```bash
# Check GPU memory
vcgencmd get_mem gpu

# Increase GPU memory if < 128MB
sudo raspi-config  # Advanced → Memory Split → 128

# Check video backends
python3 -c "
try:
    import vlc; print('VLC: OK')
except: print('VLC: Failed')
    
import subprocess
try:
    subprocess.run(['omxplayer', '--version'], timeout=5)
    print('OMXPlayer: OK')
except: print('OMXPlayer: Failed')
"
```

#### Network Issues
```bash
# Test server connectivity
curl -I https://everydayadvertise.com/api/health

# Check DNS
nslookup everydayadvertise.com

# Test playlist API
curl "https://everydayadvertise.com/api/playlist/PHTV001/tv1"
```

#### Service Not Starting
```bash
# Check service status
sudo systemctl status phtv-client

# Check logs
journalctl -u phtv-client -n 50

# Manual test
cd /home/pi/pizza-hut-tv
source venv/bin/activate
python3 enhanced_pi_client.py --debug
```

#### Sync Issues
```bash
# Check system time
timedatectl status

# Enable NTP
sudo timedatectl set-ntp true

# Check network latency
ping -c 5 everydayadvertise.com
```

### Log Locations

```bash
# Service logs
journalctl -u phtv-client

# Application logs
/var/log/phtv/client.log

# System logs
/var/log/syslog
```

## 🔒 Security

### Network Security
- Uses HTTPS for all API communications
- Certificate validation enabled
- Secure credential storage

### System Security
- Runs as non-root user (`pi`)
- Minimal permissions required
- Automatic security updates recommended

### Firewall Configuration

```bash
# Allow outbound HTTPS
sudo ufw allow out 443/tcp

# Allow SSH (for management)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

## 📈 Performance Optimization

### Pi 4/5 Optimizations

```bash
# GPU memory (in /boot/config.txt)
gpu_mem=128

# Enable hardware acceleration
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable wifi-powersave
```

### Pi 3 Optimizations

```bash
# GPU memory
gpu_mem=128

# Legacy graphics driver
dtoverlay=vc4-fkms-v3d

# CPU governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## 🔄 Updates

### Automatic Updates

```bash
# Update script (run weekly)
#!/bin/bash
cd /home/pi/pizza-hut-tv
sudo systemctl stop phtv-client
git pull origin main  # if using git
source venv/bin/activate
pip install --upgrade -r pi_requirements.txt
sudo systemctl start phtv-client
```

### Manual Updates

```bash
# Stop service
sudo systemctl stop phtv-client

# Update files
scp enhanced_pi_client.py pi@raspberrypi:/home/pi/pizza-hut-tv/

# Update dependencies
cd /home/pi/pizza-hut-tv
source venv/bin/activate
pip install --upgrade -r pi_requirements.txt

# Start service
sudo systemctl start phtv-client
```

## 📞 Support

### Health Check

```bash
# Run comprehensive health check
python3 pi_config_tool.py

# Options: 4 (System Information)
# Check all backends and system status
```

### Diagnostic Information

When reporting issues, include:

1. Pi model and OS version
2. Service status and logs
3. Network connectivity test
4. GPU memory configuration
5. Video backend availability

```bash
# Generate diagnostic report
echo "=== Pi Model ===" > diagnostic.txt
grep Model /proc/cpuinfo >> diagnostic.txt

echo -e "\n=== GPU Memory ===" >> diagnostic.txt
vcgencmd get_mem gpu >> diagnostic.txt

echo -e "\n=== Service Status ===" >> diagnostic.txt
sudo systemctl status phtv-client --no-pager >> diagnostic.txt

echo -e "\n=== Recent Logs ===" >> diagnostic.txt
journalctl -u phtv-client -n 20 --no-pager >> diagnostic.txt

echo -e "\n=== Network Test ===" >> diagnostic.txt
curl -I https://everydayadvertise.com/api/health >> diagnostic.txt 2>&1
```

## 🎉 Success Checklist

- [ ] Pi boots to desktop automatically
- [ ] Service starts automatically on boot
- [ ] Video plays in fullscreen
- [ ] Synchronization works with other screens
- [ ] Performance monitoring shows healthy stats
- [ ] Network recovery works after disconnection
- [ ] Configuration tool runs without errors
- [ ] All video backends detected correctly

---

🍕 **Pizza Hut TV Enhanced Pi Client** - Professional digital signage for Raspberry Pi