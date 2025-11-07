#!/bin/bash
# 🍕 Pizza Hut TV - New Pi Setup Script
# Run this on a fresh Raspberry Pi to set up the complete client

set -e  # Exit on any error

echo "🍕 Pizza Hut TV - Pi Client Setup"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Server URL
SERVER_URL="https://everydayadvertise.com"

echo -e "${BLUE}Step 1:${NC} Updating system packages..."
sudo apt-get update

echo -e "${BLUE}Step 2:${NC} Installing Python and dependencies..."
sudo apt-get install -y python3 python3-pip python3-pygame python3-vlc libvlc-dev vlc x11vnc

echo -e "${BLUE}Step 3:${NC} Installing Python libraries..."
pip3 install requests python-socketio websocket-client pillow --break-system-packages

echo -e "${BLUE}Step 4:${NC} Creating client directory..."
mkdir -p ~/pizzahut-client
cd ~/pizzahut-client

echo -e "${BLUE}Step 5:${NC} Downloading client files from server..."
wget -O complete_pi_client.py "${SERVER_URL}/static/pi/complete_pi_client.py"
wget -O seamless_video_player.py "${SERVER_URL}/static/pi/seamless_video_player.py"
wget -O pi_vnc_tunnel.py "${SERVER_URL}/static/pi/pi_vnc_tunnel.py"
wget -O pi_mobile_sync_addon.py "${SERVER_URL}/static/pi/pi_mobile_sync_addon.py"

echo -e "${BLUE}Step 6:${NC} Making client executable..."
chmod +x complete_pi_client.py

echo -e "${BLUE}Step 7:${NC} Creating systemd service for auto-start..."
sudo tee /etc/systemd/system/pizzahut-client.service > /dev/null <<EOF
[Unit]
Description=Pizza Hut TV Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pizzahut-client
Environment="DISPLAY=:0"
ExecStart=/usr/bin/python3 /home/pi/pizzahut-client/complete_pi_client.py --server ${SERVER_URL}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${BLUE}Step 8:${NC} Enabling systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable pizzahut-client.service

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "To start the client now:"
echo "  sudo systemctl start pizzahut-client.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u pizzahut-client.service -f"
echo ""
echo "To stop the client:"
echo "  sudo systemctl stop pizzahut-client.service"
echo ""
echo "Your Pi ID: $(hostname)"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Go to ${SERVER_URL}/pi-manager"
echo "2. Click 'Settings' for your Pi ($(hostname))"
echo "3. Enter your pairing code and assign to a store/screen"
echo ""
