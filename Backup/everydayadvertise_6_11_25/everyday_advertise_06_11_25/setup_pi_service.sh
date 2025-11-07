#!/bin/bash
# Setup complete_pi_client as a systemd service
# This makes it auto-start on boot and allows remote restart via systemctl

echo "=========================================="
echo "  Setup Complete Pi Client Service"
echo "=========================================="
echo ""

# Service file path
SERVICE_FILE=~/.config/systemd/user/complete_pi_client.service

# Create systemd user directory if it doesn't exist
mkdir -p ~/.config/systemd/user

# Create the service file
cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=Pizza Hut TV Complete Pi Client
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/everydayadvertise/.Xauthority
ExecStart=/usr/bin/python3 /home/everydayadvertise/complete_pi_client.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

echo "✅ Service file created at: $SERVICE_FILE"
echo ""

# Reload systemd to recognize new service
systemctl --user daemon-reload
echo "✅ Systemd reloaded"
echo ""

# Enable service to start on boot
systemctl --user enable complete_pi_client.service
echo "✅ Service enabled (will auto-start on boot)"
echo ""

# Start the service now
systemctl --user start complete_pi_client.service
echo "✅ Service started"
echo ""

# Show status
echo "=========================================="
echo "  Service Status"
echo "=========================================="
systemctl --user status complete_pi_client.service --no-pager
echo ""

# Enable linger so service runs even when user not logged in
sudo loginctl enable-linger $USER
echo "✅ Linger enabled (service runs without login)"
echo ""

echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Service commands:"
echo "  Start:   systemctl --user start complete_pi_client"
echo "  Stop:    systemctl --user stop complete_pi_client"
echo "  Restart: systemctl --user restart complete_pi_client"
echo "  Status:  systemctl --user status complete_pi_client"
echo "  Logs:    journalctl --user -u complete_pi_client -f"
echo ""
echo "Service will now auto-start on boot!"
echo "You can restart it remotely via dashboard or:"
echo "  ssh everydayadvertise@raspberrypi-ce39 'systemctl --user restart complete_pi_client'"
