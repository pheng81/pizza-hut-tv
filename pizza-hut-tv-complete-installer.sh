#!/bin/bash
# Pizza Hut TV Pi - Complete Downloadable Package
# Version: 2.0 - Self-contained installer with all files embedded

set -e

PACKAGE_NAME="Pizza Hut TV Pi Client"
VERSION="2.0"
INSTALL_DIR="$HOME/pizza-hut-tv-pi"

echo "=============================================="
echo "🍕 $PACKAGE_NAME v$VERSION"
echo "=============================================="
echo "Complete self-contained installer package"
echo "No internet connection required after download!"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please don't run this as root. Run as regular user."
    exit 1
fi

# Get confirmation
read -p "Install Pizza Hut TV client? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo "🔧 Installing system dependencies..."
sudo apt update -qq
sudo apt install -y python3 python3-tk python3-requests vlc curl > /dev/null 2>&1

echo "📁 Creating installation directory..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "📦 Creating Pizza Hut TV client files..."

# Create the main simple client
cat > pizza_hut_tv_client.py << 'MAIN_CLIENT_EOF'
#!/usr/bin/env python3
"""
Pizza Hut TV - Raspberry Pi Client
Complete client with menu interface
"""

import threading
import time
import subprocess
import signal
import os
import requests
import json
from datetime import datetime

class PizzaHutTVClient:
    def __init__(self):
        self.server_url = "http://192.168.1.115:5002"
        self.store_id = "1000"
        self.screen_id = "tv1"
        self.running = False
        self.current_playlist = []
        self.current_index = 0
        self.video_process = None
        self.is_playing = False
        
    def print_banner(self):
        print("\n" + "="*60)
        print("🍕 PIZZA HUT TV - RASPBERRY PI CLIENT v2.0")
        print("="*60)
        
    def print_status(self):
        print(f"\n📊 Status:")
        print(f"   Server: {self.server_url}")
        print(f"   Store:  {self.store_id} | Screen: {self.screen_id}")
        print(f"   Client: {'🟢 Running' if self.running else '🔴 Stopped'}")
        
        if self.current_playlist:
            current = self.current_playlist[self.current_index]
            filename = current.get('file', 'Unknown')
            print(f"   Content: {len(self.current_playlist)} videos")
            print(f"   Playing: {filename} [{self.current_index + 1}/{len(self.current_playlist)}]")
        else:
            print(f"   Content: None available")
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def test_connection(self):
        print("\n🔍 Testing server connection...")
        
        try:
            url = f"{self.server_url}/api/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                print(f"✅ SUCCESS! Found {len(items)} videos")
                
                if items:
                    print("\n📋 Available content:")
                    for i, item in enumerate(items[:3], 1):
                        filename = item.get('file', 'Unknown')
                        duration = item.get('duration', 0)
                        print(f"   {i}. {filename} ({duration}s)")
                    if len(items) > 3:
                        print(f"   ... and {len(items) - 3} more")
                else:
                    print("⚠️ Server connected but no content configured")
                return True
                    
            elif response.status_code == 404:
                print("⚠️ Server found but no content for this store/screen")
                print("💡 Try configuring your store ID and screen ID")
                return False
            else:
                print(f"❌ Server error: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("💡 Check server IP address and network connection")
            return False
            
    def auto_discover(self):
        print("\n🔍 Scanning network for Pizza Hut TV servers...")
        
        networks = ["192.168.1.", "192.168.0.", "10.0.0.", "172.16.0."]
        ports = [5002, 5000, 8000, 3000]
        
        for network in networks:
            for i in range(100, 120):
                for port in ports:
                    try:
                        test_url = f"http://{network}{i}:{port}/api/playlist/test/tv1"
                        response = requests.get(test_url, timeout=0.5)
                        if response.status_code in [200, 404]:
                            found_server = f"http://{network}{i}:{port}"
                            print(f"✅ Found server: {found_server}")
                            return found_server
                    except:
                        continue
                        
        print("❌ No servers found automatically")
        return None
    
    def configure(self):
        print("\n⚙️ Configuration")
        print("Press Enter to keep current value:")
        
        new_server = input(f"\nServer URL [{self.server_url}]: ").strip()
        if new_server:
            if not new_server.startswith('http'):
                new_server = f"http://{new_server}"
            self.server_url = new_server
            
        new_store = input(f"Store ID [{self.store_id}]: ").strip()
        if new_store:
            self.store_id = new_store
            
        new_screen = input(f"Screen ID [{self.screen_id}]: ").strip()
        if new_screen:
            self.screen_id = new_screen
            
        print("✅ Configuration saved")
        
        # Save config to file
        with open('client_config.txt', 'w') as f:
            f.write(f"SERVER_URL={self.server_url}\n")
            f.write(f"STORE_ID={self.store_id}\n")
            f.write(f"SCREEN_ID={self.screen_id}\n")
        
    def load_config(self):
        """Load saved configuration"""
        try:
            with open('client_config.txt', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        if key == 'SERVER_URL':
                            self.server_url = value
                        elif key == 'STORE_ID':
                            self.store_id = value
                        elif key == 'SCREEN_ID':
                            self.screen_id = value
        except FileNotFoundError:
            pass  # Use defaults
            
    def fetch_playlist(self):
        try:
            url = f"{self.server_url}/api/playlist/{self.store_id}/{self.screen_id}"
            headers = {'User-Agent': 'phtv-pi/2.0 (Raspberry Pi)'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception:
            return []
            
    def get_video_url(self, item):
        url = item.get('url') or item.get('slice_url') or item.get('preferred_url')
        if url and not url.startswith('http'):
            base = self.server_url.rstrip('/')
            url = f"{base}/{url.lstrip('/')}"
        return url
        
    def play_video(self, video_url, filename):
        if not video_url:
            return False
            
        self.stop_video()
        
        try:
            cmd = [
                'cvlc', 
                '--intf', 'dummy',
                '--no-video-title-show',
                '--fullscreen',
                '--play-and-exit',
                '--no-osd',
                '--quiet',
                video_url
            ]
            
            self.video_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            
            self.is_playing = True
            self.log(f"🎥 {filename}")
            return True
            
        except Exception as e:
            self.log(f"❌ Video error: {e}")
            return False
            
    def stop_video(self):
        if self.video_process:
            try:
                os.killpg(os.getpgid(self.video_process.pid), signal.SIGTERM)
                self.video_process.wait(timeout=3)
            except:
                try:
                    os.killpg(os.getpgid(self.video_process.pid), signal.SIGKILL)
                except:
                    pass
            finally:
                self.video_process = None
                
        self.is_playing = False
        
    def run_client(self):
        if self.running:
            print("❌ Client already running")
            return
            
        print("\n🚀 Starting Pizza Hut TV client...")
        print("💡 Press Ctrl+C to stop")
        
        self.running = True
        client_thread = threading.Thread(target=self.client_loop, daemon=True)
        client_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            self.stop_video()
            print("\n🛑 Client stopped")
            
    def client_loop(self):
        self.current_playlist = self.fetch_playlist()
        item_start_time = time.time()
        last_fetch = 0
        
        while self.running:
            current_time = time.time()
            
            # Refresh playlist every 30 seconds
            if (current_time - last_fetch) > 30:
                new_playlist = self.fetch_playlist()
                if new_playlist != self.current_playlist:
                    self.current_playlist = new_playlist
                    if self.current_index >= len(self.current_playlist):
                        self.current_index = 0
                    self.log(f"📋 Updated: {len(self.current_playlist)} items")
                last_fetch = current_time
                
            if not self.current_playlist:
                self.log("⏸️ No content - waiting...")
                time.sleep(5)
                continue
                
            current_item = self.current_playlist[self.current_index]
            duration = max(int(current_item.get('duration', 10)), 1)
            elapsed = current_time - item_start_time
            filename = current_item.get('file', 'Unknown')
            
            if not self.is_playing or elapsed >= duration:
                video_url = self.get_video_url(current_item)
                if video_url:
                    if self.play_video(video_url, filename):
                        item_start_time = current_time
                    else:
                        self.advance_playlist()
                        item_start_time = current_time
                else:
                    self.log(f"❌ No URL: {filename}")
                    self.advance_playlist()
                    item_start_time = current_time
                    
            elif self.video_process and self.video_process.poll() is not None:
                self.is_playing = False
                self.advance_playlist()
                item_start_time = current_time
                
            time.sleep(1)
            
    def advance_playlist(self):
        if self.current_playlist:
            self.current_index = (self.current_index + 1) % len(self.current_playlist)
            
    def show_menu(self):
        self.load_config()
        
        while True:
            self.print_banner()
            self.print_status()
            
            print(f"\n📋 Main Menu:")
            print(f"   1. 🔍 Test connection")
            print(f"   2. 🌐 Auto-discover servers")
            print(f"   3. ⚙️  Configure settings")
            print(f"   4. ▶️  Start client")
            print(f"   5. 📊 Show current status")
            print(f"   6. 🚪 Exit")
            
            try:
                choice = input(f"\nSelect option (1-6): ").strip()
                
                if choice == '1':
                    self.test_connection()
                    input("\n⏎ Press Enter to continue...")
                    
                elif choice == '2':
                    found = self.auto_discover()
                    if found:
                        self.server_url = found
                        print(f"✅ Server updated: {found}")
                        with open('client_config.txt', 'w') as f:
                            f.write(f"SERVER_URL={self.server_url}\n")
                            f.write(f"STORE_ID={self.store_id}\n")
                            f.write(f"SCREEN_ID={self.screen_id}\n")
                    input("\n⏎ Press Enter to continue...")
                    
                elif choice == '3':
                    self.configure()
                    input("\n⏎ Press Enter to continue...")
                    
                elif choice == '4':
                    self.run_client()
                    
                elif choice == '5':
                    continue  # Just refresh display
                    
                elif choice == '6':
                    print("\n👋 Goodbye!")
                    break
                    
                else:
                    print("❌ Invalid choice")
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break

def main():
    client = PizzaHutTVClient()
    client.show_menu()

if __name__ == '__main__':
    main()
MAIN_CLIENT_EOF

# Create quick launcher
cat > run-pizza-hut-tv << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 pizza_hut_tv_client.py
LAUNCHER_EOF

# Create Windows batch helper (for copying to Pi)
cat > copy-to-pi.bat << 'BATCH_EOF'
@echo off
echo 🍕 Pizza Hut TV Pi - Windows Transfer Helper
echo ==========================================
echo.
echo This helps you copy the client to your Raspberry Pi
echo.
echo Method 1: SCP (if you have SSH access)
echo scp pizza_hut_tv_client.py pi@YOUR_PI_IP:/home/pi/
echo ssh pi@YOUR_PI_IP "chmod +x pizza_hut_tv_client.py && python3 pizza_hut_tv_client.py"
echo.
echo Method 2: USB Drive
echo 1. Copy pizza_hut_tv_client.py to USB drive
echo 2. Insert USB into Pi
echo 3. On Pi: cp /media/pi/*/pizza_hut_tv_client.py ~/
echo 4. On Pi: chmod +x pizza_hut_tv_client.py
echo 5. On Pi: python3 pizza_hut_tv_client.py
echo.
pause
BATCH_EOF

# Create README
cat > README.md << 'README_EOF'
# 🍕 Pizza Hut TV - Raspberry Pi Client

Complete client software for displaying Pizza Hut TV content on Raspberry Pi.

## Quick Start

1. **Run the client:**
   ```bash
   python3 pizza_hut_tv_client.py
   ```

2. **Configure your settings:**
   - Choose option 3 to configure server IP, store ID, and screen ID

3. **Test connection:**
   - Choose option 1 to verify server connection

4. **Start playing:**
   - Choose option 4 to begin displaying content

## Features

- ✅ **Auto-server discovery** - Finds Pizza Hut TV servers automatically
- ✅ **Easy configuration** - Simple menu-driven setup  
- ✅ **Connection testing** - Verify server connection before starting
- ✅ **Real-time updates** - Playlist refreshes automatically
- ✅ **Hardware optimized** - Uses VLC for best Pi performance
- ✅ **Error recovery** - Handles network issues gracefully

## Configuration

The client will create a `client_config.txt` file with your settings:
- `SERVER_URL` - Your Pizza Hut TV server address
- `STORE_ID` - Your store identifier  
- `SCREEN_ID` - Screen identifier (tv1, tv2, etc.)

## Requirements

- Raspberry Pi (3, 4, or Zero 2 W recommended)
- Raspberry Pi OS with desktop
- Network connection to Pizza Hut TV server

## Troubleshooting

### Connection Issues
- Use option 2 to auto-discover servers
- Check server IP address and port
- Verify network connectivity

### Video Playback Issues  
- Ensure VLC is installed: `sudo apt install vlc`
- Check video file formats are supported
- Verify sufficient bandwidth for video streaming

### Performance Issues
- Use wired network connection when possible
- Ensure Pi has adequate cooling
- Close unnecessary applications

## Support

For help with configuration or troubleshooting, check the server logs and network connectivity first.
README_EOF

# Make executable
chmod +x pizza_hut_tv_client.py
chmod +x run-pizza-hut-tv

echo ""
echo "✅ Pizza Hut TV Pi Client Package Created!"
echo ""
echo "📦 Package contents:"
echo "   • pizza_hut_tv_client.py - Main client application"
echo "   • run-pizza-hut-tv - Quick launcher script"
echo "   • README.md - Complete documentation"
echo "   • copy-to-pi.bat - Windows transfer helper"
echo ""
echo "🚀 To start immediately:"
echo "   python3 pizza_hut_tv_client.py"
echo ""
echo "📍 Installation directory: $INSTALL_DIR"
echo ""
echo "🎯 Next steps:"
echo "   1. Run the client: python3 pizza_hut_tv_client.py"
echo "   2. Choose option 2 to auto-discover your server"
echo "   3. Choose option 3 to configure store/screen settings"  
echo "   4. Choose option 1 to test connection"
echo "   5. Choose option 4 to start playing content"
echo ""
echo "💡 The client automatically saves your configuration!"
echo ""