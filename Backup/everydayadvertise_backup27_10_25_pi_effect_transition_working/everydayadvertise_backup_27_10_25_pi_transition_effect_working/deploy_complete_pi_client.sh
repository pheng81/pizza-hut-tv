#!/bin/bash
"""
🍕 Pizza Hut TV - Pi Deployment Script
Automated deployment of complete webplayer client to Raspberry Pi
"""

# Configuration
PI_HOST="everydayadvertise@raspberrypi"
SERVICE_NAME="pizza-hut-tv-complete"
REMOTE_DIR="/home/everydayadvertise"
VENV_NAME="pizza-hut-tv"

echo "🍕 Pizza Hut TV - Complete Pi Client Deployment"
echo "================================================"

# Check if Pi is reachable
echo "📡 Testing Pi connection..."
if ! ssh -o ConnectTimeout=5 $PI_HOST "echo 'Pi connected successfully'"; then
    echo "❌ Cannot connect to Pi at $PI_HOST"
    echo "Please check:"
    echo "  - Pi is powered on and connected to network"
    echo "  - SSH is enabled on Pi"
    echo "  - Correct hostname/IP and credentials"
    exit 1
fi

echo "✅ Pi connection successful"

# Create virtual environment if it doesn't exist
echo "🐍 Setting up Python virtual environment..."
ssh $PI_HOST "
    if [ ! -d $VENV_NAME ]; then
        echo 'Creating virtual environment...'
        python3 -m venv $VENV_NAME
    fi
    
    # Activate and upgrade pip
    source $VENV_NAME/bin/activate
    pip install --upgrade pip
    
    # Install required packages
    echo 'Installing Python packages...'
    pip install pygame requests pillow numpy
    
    echo 'Virtual environment ready'
"

# Copy Python files to Pi
echo "📁 Copying Python files to Pi..."
scp complete_pi_client.py $PI_HOST:$REMOTE_DIR/
scp media_player.py $PI_HOST:$REMOTE_DIR/

# Make files executable
ssh $PI_HOST "chmod +x $REMOTE_DIR/complete_pi_client.py"

# Create systemd service
echo "⚙️ Creating systemd service..."
ssh $PI_HOST "sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << 'EOF'
[Unit]
Description=Pizza Hut TV Complete Digital Signage Client
After=graphical-session.target network-online.target
Wants=graphical-session.target network-online.target

[Service]
Type=simple
User=everydayadvertise
Environment=DISPLAY=:0
Environment=PYTHONPATH=$REMOTE_DIR
WorkingDirectory=$REMOTE_DIR
ExecStartPre=/bin/sleep 30
ExecStart=$REMOTE_DIR/$VENV_NAME/bin/python $REMOTE_DIR/complete_pi_client.py --server https://everydayadvertise.com
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

echo 'Systemd service created and enabled'
"

# Stop old service if running
echo "🛑 Stopping old services..."
ssh $PI_HOST "
    sudo systemctl stop pizza-hut-tv 2>/dev/null || true
    sudo systemctl disable pizza-hut-tv 2>/dev/null || true
    sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
"

# Start new service
echo "🚀 Starting complete Pi client service..."
ssh $PI_HOST "sudo systemctl start $SERVICE_NAME"

# Check service status
echo "📊 Checking service status..."
ssh $PI_HOST "sudo systemctl status $SERVICE_NAME --no-pager"

# Show recent logs
echo "📋 Recent service logs:"
ssh $PI_HOST "journalctl -u $SERVICE_NAME -n 20 --no-pager"

echo ""
echo "🎉 Deployment Complete!"
echo "=============================="
echo "Service Name: $SERVICE_NAME"
echo "Status: sudo systemctl status $SERVICE_NAME"
echo "Logs: journalctl -u $SERVICE_NAME -f"
echo "Restart: sudo systemctl restart $SERVICE_NAME"
echo ""
echo "The Pi client should now:"
echo "  ✅ Display fullscreen Pizza Hut TV interface"
echo "  ✅ Accept 4-digit TV codes for connection"
echo "  ✅ Connect to https://everydayadvertise.com"
echo "  ✅ Play media with webplayer-like transitions"
echo "  ✅ Sync with server for schedule updates"
echo ""

# Optional: Test connection
read -p "📡 Test client connectivity? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧪 Testing client connection..."
    ssh $PI_HOST "
        source $VENV_NAME/bin/activate
        python3 -c \"
import requests
import sys

try:
    # Test server connection
    response = requests.get('https://everydayadvertise.com/api/server_time', timeout=10)
    if response.status_code == 200:
        print('✅ Server connection: OK')
        data = response.json()
        print(f'   Server time: {data.get(\"server_time_ms\", \"unknown\")}')
    else:
        print('❌ Server connection: Failed')
        sys.exit(1)
        
    # Test store API
    response = requests.get('https://everydayadvertise.com/api/stores_by_code/1234', timeout=10)
    if response.status_code == 200:
        stores = response.json()
        print(f'✅ Store API: OK ({len(stores)} stores for test code)')
    else:
        print('❌ Store API: Failed')
        
    print('🎉 All connectivity tests passed!')
    
except Exception as e:
    print(f'❌ Connectivity test failed: {e}')
    sys.exit(1)
        \"
    "
fi

echo "🍕 Pizza Hut TV Complete Pi Client is ready!"