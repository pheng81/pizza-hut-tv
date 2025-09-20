#!/bin/bash
# Pizza Hut TV Pi - Self-Extracting Installer
# This file contains everything needed - just run it!

set -e

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${PURPLE}🍕 Pizza Hut TV - Self-Installing Package${NC}"
echo -e "${PURPLE}===========================================${NC}"
echo ""
echo -e "${CYAN}This is a complete standalone installer.${NC}"
echo -e "${CYAN}Everything is included - no internet needed!${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ Please don't run this as root/sudo. Run as regular user (pi).${NC}"
    exit 1
fi

# Get user confirmation
echo -e "${YELLOW}This will install Pizza Hut TV client on your Raspberry Pi.${NC}"
read -p "Continue with installation? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Installation cancelled.${NC}"
    exit 0
fi

echo -e "${BLUE}📦 Updating system packages...${NC}"
sudo apt update

echo -e "${BLUE}🔧 Installing system dependencies...${NC}"
sudo apt install -y python3 python3-pip python3-pygame omxplayer vlc curl unzip systemd

echo -e "${BLUE}🐍 Installing Python dependencies...${NC}"
pip3 install --user --upgrade pygame requests

INSTALL_DIR="$HOME/pizza-hut-tv-pi"
echo -e "${BLUE}📁 Creating installation directory: $INSTALL_DIR${NC}"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Extract the embedded files
echo -e "${BLUE}📦 Extracting Pizza Hut TV client...${NC}"

# Create the main client file
cat > "$INSTALL_DIR/phtv_pi_client.py" << 'PYTHON_CLIENT_EOF'
#!/usr/bin/env python3
"""
Pizza Hut TV - Raspberry Pi Client
Complete standalone client for Pizza Hut TV system
"""

import pygame
import requests
import json
import time
import sys
import argparse
import os
import threading
import logging
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any
import subprocess
import signal
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PHTVPiClient:
    """Raspberry Pi client for Pizza Hut TV system."""
    
    def __init__(self, server_url: str, store_id: str, screen_id: str):
        self.server_url = server_url.rstrip('/')
        self.store_id = store_id
        self.screen_id = screen_id
        self.user_agent = "phtv-pi/1.0 (Raspberry Pi)"
        
        # State
        self.running = True
        self.current_playlist = []
        self.current_index = 0
        self.item_start_time = 0
        self.last_playlist_fetch = 0
        
        # Video playback
        self.video_process = None
        self.is_playing = False
        
        # Settings
        self.playlist_refresh_interval = 5
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def check_dependencies(self) -> bool:
        """Check if required video players are available."""
        players = []
        
        if self.is_command_available('omxplayer'):
            players.append('omxplayer (Pi optimized)')
        if self.is_command_available('cvlc'):
            players.append('VLC')
            
        if not players:
            self.log("❌ No video players found! Run: sudo apt install omxplayer vlc", "ERROR")
            return False
            
        self.log(f"✅ Available players: {', '.join(players)}")
        return True
        
    def is_command_available(self, command: str) -> bool:
        """Check if command exists."""
        try:
            subprocess.run(['which', command], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
            
    def fetch_playlist(self) -> List[Dict[str, Any]]:
        """Fetch playlist from server."""
        try:
            url = f"{self.server_url}/api/playlist/{self.store_id}/{self.screen_id}"
            headers = {'User-Agent': self.user_agent}
            
            self.log(f"📡 Fetching playlist from {url}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            self.log(f"✅ Got {len(items)} playlist items")
            return items
            
        except Exception as e:
            self.log(f"❌ Playlist fetch failed: {e}", "ERROR")
            return []
            
    def get_video_url(self, item: Dict[str, Any]) -> str:
        """Get video URL for item."""
        url = item.get('url') or item.get('slice_url') or item.get('preferred_url')
        
        if url and not url.startswith('http'):
            url = urljoin(self.server_url + '/', url)
            
        return url
        
    def play_video(self, video_url: str, duration: int) -> bool:
        """Start video playback."""
        if not video_url:
            self.log("❌ No video URL", "ERROR")
            return False
            
        self.stop_video()
        
        if self.is_command_available('omxplayer'):
            return self.play_omx(video_url, duration)
        elif self.is_command_available('cvlc'):
            return self.play_vlc(video_url, duration)
        else:
            self.log("❌ No video player available", "ERROR")
            return False
            
    def play_omx(self, video_url: str, duration: int) -> bool:
        """Play with omxplayer."""
        try:
            cmd = [
                'omxplayer',
                '--no-osd',
                '--no-keys', 
                '--aspect-mode', 'stretch',
                video_url
            ]
            
            self.log(f"🎥 Starting omxplayer: {video_url}")
            self.video_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            
            self.is_playing = True
            return True
            
        except Exception as e:
            self.log(f"❌ omxplayer failed: {e}", "ERROR")
            return False
            
    def play_vlc(self, video_url: str, duration: int) -> bool:
        """Play with VLC."""
        try:
            cmd = [
                'cvlc',
                '--intf', 'dummy',
                '--no-video-title-show',
                '--fullscreen',
                '--play-and-exit',
                video_url
            ]
            
            self.log(f"🎥 Starting VLC: {video_url}")
            self.video_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            
            self.is_playing = True
            return True
            
        except Exception as e:
            self.log(f"❌ VLC failed: {e}", "ERROR")
            return False
            
    def stop_video(self):
        """Stop current video."""
        if self.video_process:
            try:
                os.killpg(os.getpgid(self.video_process.pid), signal.SIGTERM)
                self.video_process.wait(timeout=5)
            except:
                try:
                    os.killpg(os.getpgid(self.video_process.pid), signal.SIGKILL)
                except:
                    pass
            finally:
                self.video_process = None
                
        self.is_playing = False
        
    def advance_playlist(self):
        """Move to next item."""
        if self.current_playlist:
            self.current_index = (self.current_index + 1) % len(self.current_playlist)
            self.item_start_time = time.time()
            self.log(f"📝 Advanced to item {self.current_index + 1}/{len(self.current_playlist)}")
            
    def run(self):
        """Main client loop."""
        self.log("🚀 Starting Pizza Hut TV Pi Client")
        self.log(f"   Server: {self.server_url}")
        self.log(f"   Store:  {self.store_id}")
        self.log(f"   Screen: {self.screen_id}")
        
        if not self.check_dependencies():
            return False
            
        self.current_playlist = self.fetch_playlist()
        self.item_start_time = time.time()
        
        try:
            while self.running:
                current_time = time.time()
                
                # Update playlist periodically
                if (current_time - self.last_playlist_fetch) > self.playlist_refresh_interval:
                    new_playlist = self.fetch_playlist()
                    if new_playlist != self.current_playlist:
                        self.current_playlist = new_playlist
                        if self.current_index >= len(self.current_playlist):
                            self.current_index = 0
                    self.last_playlist_fetch = current_time
                
                if not self.current_playlist:
                    self.log("⏸️ No content available, retrying...")
                    time.sleep(5)
                    continue
                    
                current_item = self.current_playlist[self.current_index]
                duration = max(int(current_item.get('duration', 10)), 1)
                elapsed = current_time - self.item_start_time
                
                if not self.is_playing or elapsed >= duration:
                    video_url = self.get_video_url(current_item)
                    filename = current_item.get('file', 'Unknown')
                    
                    if video_url:
                        self.log(f"🎬 Playing: {filename} ({duration}s)")
                        if self.play_video(video_url, duration):
                            self.item_start_time = current_time
                        else:
                            self.advance_playlist()
                    else:
                        self.log(f"❌ No URL for: {filename}")
                        self.advance_playlist()
                        
                elif self.video_process and self.video_process.poll() is not None:
                    self.is_playing = False
                    self.advance_playlist()
                    
                elif elapsed > (duration + 10):
                    self.log("⏰ Duration exceeded, advancing")
                    self.stop_video()
                    self.advance_playlist()
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.log("🛑 Keyboard interrupt")
        except Exception as e:
            self.log(f"💥 Unexpected error: {e}", "ERROR")
            traceback.print_exc()
        finally:
            self.cleanup()
            
        return True
        
    def cleanup(self):
        """Cleanup resources."""
        self.log("🧹 Cleaning up...")
        self.running = False
        self.stop_video()

def main():
    parser = argparse.ArgumentParser(description='Pizza Hut TV Pi Client')
    parser.add_argument('--server', required=True, help='Server URL')
    parser.add_argument('--store', required=True, help='Store ID') 
    parser.add_argument('--screen', required=True, help='Screen ID')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    client = PHTVPiClient(args.server, args.store, args.screen)
    
    def signal_handler(signum, frame):
        client.running = False
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    success = client.run()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
PYTHON_CLIENT_EOF

# Create configuration file
cat > "$INSTALL_DIR/phtv-config" << 'CONFIG_EOF'
# Pizza Hut TV Pi Client Configuration
# Edit these values for your setup

# Server settings (REQUIRED - change these!)
PHTV_SERVER="http://192.168.1.115:5002"
PHTV_STORE="1000" 
PHTV_SCREEN="tv1"

# Optional settings
PHTV_DEBUG="false"
CONFIG_EOF

# Create start script
cat > "$INSTALL_DIR/phtv-start" << 'START_SCRIPT_EOF'
#!/bin/bash
# Pizza Hut TV Pi Client Startup Script

cd "$(dirname "$0")"

# Load config
if [ -f "phtv-config" ]; then
    source phtv-config
else
    echo "❌ Configuration file 'phtv-config' not found!"
    echo "   Please run: nano phtv-config"
    exit 1
fi

# Validate config
if [ -z "$PHTV_SERVER" ] || [ -z "$PHTV_STORE" ] || [ -z "$PHTV_SCREEN" ]; then
    echo "❌ Please configure PHTV_SERVER, PHTV_STORE, and PHTV_SCREEN in phtv-config"
    exit 1
fi

echo "🍕 Pizza Hut TV Pi Client Starting..."
echo "   Server: $PHTV_SERVER"
echo "   Store:  $PHTV_STORE"
echo "   Screen: $PHTV_SCREEN"
echo

# Build arguments
ARGS="--server $PHTV_SERVER --store $PHTV_STORE --screen $PHTV_SCREEN"

if [ "$PHTV_DEBUG" = "true" ]; then
    ARGS="$ARGS --debug"
fi

# Start client
exec python3 phtv_pi_client.py $ARGS
START_SCRIPT_EOF

# Create systemd service
cat > "$INSTALL_DIR/pizza-hut-tv.service" << SERVICE_EOF
[Unit]
Description=Pizza Hut TV Pi Client
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/phtv-start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
SERVICE_EOF

# Create uninstaller
cat > "$INSTALL_DIR/uninstall.sh" << 'UNINSTALL_EOF'
#!/bin/bash
echo "🗑️ Uninstalling Pizza Hut TV Pi Client..."

# Stop and disable service
sudo systemctl stop pizza-hut-tv 2>/dev/null || true
sudo systemctl disable pizza-hut-tv 2>/dev/null || true
sudo rm -f /etc/systemd/system/pizza-hut-tv.service
sudo systemctl daemon-reload

# Remove installation directory
rm -rf "$HOME/pizza-hut-tv-pi"

echo "✅ Pizza Hut TV Pi Client uninstalled successfully!"
UNINSTALL_EOF

# Make scripts executable
chmod +x "$INSTALL_DIR/phtv_pi_client.py"
chmod +x "$INSTALL_DIR/phtv-start"
chmod +x "$INSTALL_DIR/uninstall.sh"

# Install systemd service
echo -e "${BLUE}⚙️ Installing systemd service...${NC}"
sudo cp "$INSTALL_DIR/pizza-hut-tv.service" /etc/systemd/system/
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}✅ Pizza Hut TV Pi Client installed successfully!${NC}"
echo ""
echo -e "${YELLOW}📝 NEXT STEPS:${NC}"
echo -e "${CYAN}1. Configure your settings:${NC}"
echo -e "   nano $INSTALL_DIR/phtv-config"
echo ""
echo -e "${CYAN}2. Test the client manually:${NC}"
echo -e "   cd $INSTALL_DIR && ./phtv-start"
echo ""
echo -e "${CYAN}3. Enable auto-start on boot:${NC}"
echo -e "   sudo systemctl enable pizza-hut-tv"
echo ""
echo -e "${CYAN}4. Start the service:${NC}"
echo -e "   sudo systemctl start pizza-hut-tv"
echo ""
echo -e "${CYAN}5. Check service status:${NC}"
echo -e "   sudo systemctl status pizza-hut-tv"
echo ""
echo -e "${CYAN}6. View logs:${NC}"
echo -e "   journalctl -u pizza-hut-tv -f"
echo ""
echo -e "${RED}🔧 IMPORTANT: Edit $INSTALL_DIR/phtv-config with your server details!${NC}"
echo ""
echo -e "${GREEN}📍 Installation complete in: $INSTALL_DIR${NC}"

# Show current config
echo ""
echo -e "${YELLOW}📄 Current configuration (EDIT THIS):${NC}"
echo -e "${PURPLE}----------------------------------------${NC}"
cat "$INSTALL_DIR/phtv-config"
echo -e "${PURPLE}----------------------------------------${NC}"
echo ""
echo -e "${CYAN}Edit with: nano $INSTALL_DIR/phtv-config${NC}"
echo ""
echo -e "${GREEN}🎬 Ready to display Pizza Hut TV content!${NC}"