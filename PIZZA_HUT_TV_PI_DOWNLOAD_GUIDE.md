# 🍕 Pizza Hut TV - Enhanced Raspberry Pi Client

## ✅ UPDATED GUI CLIENT - Proper Authentication Flow!

**Your Pi now has the updated GUI client that matches webplayer and Android TV exactly:**

✅ **Step 1: 4-digit Link Code** - Enter your TV pairing code (connects to user account)  
✅ **Step 2: Store Code** - Enter your store number (selects store location)  
✅ **Step 3: Screen Selection** - Choose which TV/screen in that store  
✅ **Step 4: Playback Controls** - Start/stop content with TV remote support  

🆕 **Perfect Authentication Flow** - Same as webplayer: Link Code → Store Code → Screen Selection  
🆕 **Updated GUI Interface** - Large buttons, TV-friendly navigation  
🆕 **TV Remote Ready** - Arrow keys ↑↓←→, Enter, F11 fullscreen  
🆕 **Production Server** - Connects to everydayadvertise.com  

## 🚀 How to Run on Your Pi

### Files on Your Pi:
✅ **pizza_hut_tv_gui_client_updated.py** (54KB) - New GUI with proper auth flow  
✅ **run_pizza_hut_tv_updated.sh** - Easy launcher for new GUI  
✅ **pizza_hut_tv_client_enhanced.py** - Text-based client  
✅ **fix-python-environment.sh** - Python environment fix (already applied)  

### Start the GUI Client:

**On Pi Desktop (Recommended for TV use):**
```bash
# Connect monitor/TV to Pi, then run:
./run_pizza_hut_tv_updated.sh
```

**Via SSH with X11 forwarding:**
```bash
# From Windows:
ssh -X everydayadvertise@raspberrypi
python3 pizza_hut_tv_gui_client_updated.py
```  

## Download and Install Options

### Option 1: Enhanced Installer (Recommended)

**On your Raspberry Pi, run this single command:**
```bash
curl -sSL https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/pizza-hut-tv-enhanced-installer.sh | bash
```

### Option 2: Manual Download

1. **Download the enhanced installer:**
   - Right-click and save: `pizza-hut-tv-enhanced-installer.sh`

2. **Transfer to your Pi:**
   - **SCP method:** `scp pizza-hut-tv-enhanced-installer.sh pi@YOUR_PI_IP:/home/pi/`
   - **USB method:** Copy to USB drive, then copy from USB to Pi

3. **Install on Pi:**
   ```bash
   chmod +x pizza-hut-tv-enhanced-installer.sh
   ./pizza-hut-tv-enhanced-installer.sh
   ```

### Option 3: Legacy Installer (Simple Version)

For basic functionality with manual configuration:
```bash
curl -sSL https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/pizza-hut-tv-complete-installer.sh | bash
```

### Option 3: Windows Helper

1. **Download all files to Windows**
2. **Run the included `copy-to-pi.bat`** for step-by-step transfer instructions

## What Gets Installed

**🆕 Enhanced Version Features:**
- ✅ **Universal store access** - connect to any user's content (heang2@gmail.com, test5@hotmail.com, etc.)
- ✅ **Production server connection** - everydayadvertise.com ready
- ✅ **4-digit link code authentication** - same as Android TV
- ✅ **Dynamic store discovery** - automatically finds available stores
- ✅ **Interactive store/screen selection** - choose from discovered options
- 🆕 **GUI Interface** - Large TV-friendly buttons with remote control support
- 🆕 **TV Remote Navigation** - Arrow keys, Enter, number keys 1-6, F11 fullscreen
- 🆕 **Dual Interface Choice** - GUI (desktop/TV) or text menu (SSH/terminal)
- ✅ **Menu-driven interface** - no command line knowledge needed
- ✅ **Hardware-optimized VLC playback** - Pi GPU acceleration
- ✅ **Automatic content updates** - refreshes playlists dynamically

**Standard Features:**
- ✅ **Complete Pizza Hut TV client** with menu interface
- ✅ **Configuration manager** - easy setup wizard
- ✅ **Connection testing** - verify everything works
- ✅ **Auto-save settings** - remembers your configuration
- ✅ **Error recovery** - handles network issues
- ✅ **Complete documentation** - README and help files

## Quick Start After Installation

**🆕 Enhanced Version Setup:**

### GUI Interface (Desktop/TV with Remote):
1. **Run:** `./run-pizza-hut-tv-gui` or `python3 pizza_hut_tv_gui_client.py`
2. **Navigate:** Use arrow keys (↑↓←→) and Enter, or number keys 1-6
3. **Authentication:** Press 4 or click "Authentication" to setup 4-digit link code
4. **Store Discovery:** Press 5 or click "Select Store" to discover and select your stores
5. **Test:** Press 1 or click "Test Connection" to verify connection and content
6. **Play:** Press 6 or click "Start Playback" to begin fullscreen playback
7. **Fullscreen:** Press F11 for full TV display mode

**TV Remote Controls:**
- **Arrow Keys:** Navigate between buttons
- **Enter/Return:** Activate selected button  
- **Number Keys 1-6:** Quick access to main functions
- **F11:** Toggle fullscreen mode
- **Space:** Start/Stop playback toggle
- **Backspace:** Stop playback

### Text Menu Interface (SSH/Terminal):
1. **Run:** `./run-pizza-hut-tv` or `python3 pizza_hut_tv_client.py`
2. **Authentication:** Choose option 4 to setup 4-digit link code or username/password
3. **Store Discovery:** Choose option 5 to discover and select your stores
4. **Test:** Choose option 1 to verify connection and content
5. **Play:** Choose option 6 to start playback

### Universal Interface (Both Installed):
1. **Run:** `./run-pizza-hut-tv-choose` to select interface type

## Package Features

### Smart Installation
- **Self-contained** - everything included in one file
- **System dependency handling** - installs VLC, Python packages
- **No internet required** after download
- **Safe installation** - doesn't modify system Python

### User-Friendly Interface  
- **Menu-driven** - no command line knowledge needed
- **Clear status display** - shows connection and content info
- **Helpful error messages** - guides you to solutions
- **Progress indicators** - see what's happening

### Professional Features
- **Automatic playlist refresh** - updates content without restart
- **Multi-screen support** - works with slice video system  
- **Hardware acceleration** - optimized for Pi GPU
- **Robust error handling** - continues working through issues
- **Configuration persistence** - saves settings between runs

## System Requirements

- **Raspberry Pi:** 3, 4, or Zero 2 W (recommended)
- **OS:** Raspberry Pi OS (Bullseye or Bookworm)  
- **For GUI:** Desktop environment (PIXEL, XFCE, KDE, etc.) - **Perfect for TV displays!**
- **For Text Menu:** SSH access or terminal
- **Network:** Connection to Pizza Hut TV server
- **Storage:** 100MB free space
- **Memory:** 1GB RAM minimum
- **Display:** HDMI TV/monitor (for GUI mode)
- **Input:** TV remote, wireless keyboard, or USB keyboard (GUI mode)

## File Structure After Installation

```
~/pizza-hut-tv-pi/
├── pizza_hut_tv_client.py      # Text menu application (if installed)
├── pizza_hut_tv_gui_client.py  # GUI application with TV remote support (if installed)
├── run-pizza-hut-tv            # Text menu launcher (if installed)
├── run-pizza-hut-tv-gui        # GUI launcher (if installed)  
├── run-pizza-hut-tv-choose     # Universal launcher to choose interface (if both installed)
├── client_config.txt           # Your saved settings
├── README.md                   # Complete documentation
└── copy-to-pi.bat             # Windows transfer helper
```

## Troubleshooting

### Installation Issues
- Ensure you have internet connection during install
- Run as regular user (not root/sudo)
- Check disk space (need ~100MB free)

### Connection Issues  
- Use auto-discovery (option 2) to find server
- Check server IP address format: `http://192.168.1.115:5002`
- Verify Pi and server are on same network

### Video Issues
- Test with simple content first
- Check network bandwidth
- Ensure Pi has adequate cooling
- Verify VLC is working: `vlc --version`

## Support Files Included

- **📋 README.md** - Complete user guide
- **🚀 run-pizza-hut-tv** - One-click launcher  
- **💾 copy-to-pi.bat** - Windows transfer helper
- **⚙️ client_config.txt** - Auto-generated settings file

## Advanced Usage

### Configuration File
Edit `client_config.txt` directly:
```
SERVER_URL=http://192.168.1.115:5002
STORE_ID=1000  
SCREEN_ID=tv1
```

### Command Line Options
```bash
# Quick test
python3 pizza_hut_tv_client.py --test

# Auto-start (future feature)
python3 pizza_hut_tv_client.py --auto-start
```

### Integration  
- Add to Pi startup for automatic launching
- Use with multiple screens for synchronized display
- Integrate with scheduling systems

---

**Ready to install? Just download and run the installer - everything else is automatic!**