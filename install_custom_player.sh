#!/bin/bash
# Installation script for Custom Media Player
# Run this on Raspberry Pi

echo "====================================="
echo "Custom Media Player Installation"
echo "====================================="

# Install required Python packages
echo "📦 Installing Python packages..."
sudo apt-get update
sudo apt-get install -y python3-opencv python3-pil python3-numpy python3-requests

# Make the player executable
chmod +x /home/everydayadvertise/Desktop/custom_player.py

# Create systemd service for autostart
echo "⚙️  Creating systemd service..."
sudo tee /etc/systemd/system/custom-player.service > /dev/null <<EOF
[Unit]
Description=Custom Media Player for Multi-Screen Display
After=network.target

[Service]
Type=simple
User=everydayadvertise
Environment="DISPLAY=:0"
WorkingDirectory=/home/everydayadvertise/Desktop
ExecStart=/usr/bin/python3 /home/everydayadvertise/Desktop/custom_player.py 1000 2
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start the player manually:"
echo "  python3 /home/everydayadvertise/Desktop/custom_player.py 1000 2"
echo ""
echo "To enable autostart on boot:"
echo "  sudo systemctl enable custom-player.service"
echo "  sudo systemctl start custom-player.service"
echo ""
echo "To check status:"
echo "  sudo systemctl status custom-player.service"
echo ""
echo "To view logs:"
echo "  journalctl -u custom-player.service -f"
echo ""
