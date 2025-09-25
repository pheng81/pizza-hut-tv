# EA TV Pi Client - Troubleshooting Guide

## Issue: Desktop icon asks to execute but nothing launches

This typically means missing Python dependencies or permission issues.

## Quick Fix Steps:

### Step 1: Connect to Pi via SSH
```bash
ssh everydayadvertise@raspberrypi
# Password: pheng168
```

### Step 2: Install Required Packages
```bash
sudo apt-get update
sudo apt-get install python3-tk python3-pip vlc python3-vlc
pip3 install requests python-vlc
```

### Step 3: Fix Desktop Icon Permissions
```bash
cd ~/Desktop
chmod +x EATV.desktop

# Make it trusted (this varies by desktop environment)
# For GNOME/Ubuntu Desktop:
gio set EATV.desktop metadata::trusted true

# For other desktops, right-click the icon and select "Allow Launching"
```

### Step 4: Test Manually First
```bash
cd /home/everydayadvertise
python3 phtv_pi_client.py
```

### Step 5: If Still Issues, Check the Launcher
```bash
# Test the launcher script
./ea_tv_launcher.sh

# Check for errors
python3 -c "import requests, tkinter, vlc; print('All modules OK')"
```

## Alternative: Create New Desktop Icon

If the existing icon has issues, create a new one:

```bash
cat > ~/Desktop/EA_TV_Enhanced.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=EA TV Enhanced
Comment=Enhanced EA TV with Synchronization
Exec=python3 /home/everydayadvertise/phtv_pi_client.py
Icon=/home/everydayadvertise/ea_tv_icon.png
Terminal=true
Categories=AudioVideo;Player;
StartupNotify=true
EOF

chmod +x ~/Desktop/EA_TV_Enhanced.desktop
```

## Network Test
Test server connectivity:
```bash
curl -s "http://54.252.90.27:8082/api/sync-time"
```

## Expected Output
When working correctly, you should see:
- GUI window opens with screen selection
- Synchronized playback with webplayer
- No error messages in terminal

## If All Else Fails
Run the old working version temporarily:
```bash
python3 pi_player.py
```

Then compare what's different with the enhanced version.