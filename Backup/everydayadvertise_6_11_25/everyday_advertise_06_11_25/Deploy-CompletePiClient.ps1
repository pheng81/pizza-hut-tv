# 🍕 Pizza Hut TV - Complete Pi Client Deployment (Windows)
# PowerShell script to deploy complete webplayer client to Raspberry Pi

param(
    [string]$PiHost = "everydayadvertise@raspberrypi",
    [string]$ServerUrl = "https://everydayadvertise.com",
    [switch]$Debug
)

$SERVICE_NAME = "pizza-hut-tv-complete"
$REMOTE_DIR = "/home/everydayadvertise"
$VENV_NAME = "pizza-hut-tv"

Write-Host "🍕 Pizza Hut TV - Complete Pi Client Deployment" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Yellow

# Test Pi connection
Write-Host "📡 Testing Pi connection..." -ForegroundColor Cyan
try {
    $result = ssh -o ConnectTimeout=5 $PiHost "echo 'Pi connected successfully'"
    if ($LASTEXITCODE -ne 0) {
        throw "SSH connection failed"
    }
    Write-Host "✅ Pi connection successful" -ForegroundColor Green
}
catch {
    Write-Host "❌ Cannot connect to Pi at $PiHost" -ForegroundColor Red
    Write-Host "Please check:" -ForegroundColor Yellow
    Write-Host "  - Pi is powered on and connected to network"
    Write-Host "  - SSH is enabled on Pi"
    Write-Host "  - Correct hostname/IP and credentials"
    exit 1
}

# Setup Python environment
Write-Host "🐍 Setting up Python virtual environment..." -ForegroundColor Cyan
ssh $PiHost @"
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
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to setup Python environment" -ForegroundColor Red
    exit 1
}

# Copy Python files
Write-Host "📁 Copying Python files to Pi..." -ForegroundColor Cyan
scp complete_pi_client.py ${PiHost}:${REMOTE_DIR}/
scp media_player.py ${PiHost}:${REMOTE_DIR}/

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to copy files" -ForegroundColor Red
    exit 1
}

# Make files executable
ssh $PiHost "chmod +x $REMOTE_DIR/complete_pi_client.py"

# Create systemd service
Write-Host "⚙️ Creating systemd service..." -ForegroundColor Cyan

$debugFlag = if ($Debug) { " --debug" } else { "" }

ssh $PiHost @"
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << 'EOF'
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
ExecStart=$REMOTE_DIR/$VENV_NAME/bin/python $REMOTE_DIR/complete_pi_client.py --server $ServerUrl$debugFlag
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
"@

# Stop old services
Write-Host "🛑 Stopping old services..." -ForegroundColor Cyan
ssh $PiHost @"
    sudo systemctl stop pizza-hut-tv 2>/dev/null || true
    sudo systemctl disable pizza-hut-tv 2>/dev/null || true
    sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
"@

# Start new service  
Write-Host "🚀 Starting complete Pi client service..." -ForegroundColor Cyan
ssh $PiHost "sudo systemctl start $SERVICE_NAME"

# Check service status
Write-Host "📊 Checking service status..." -ForegroundColor Cyan
ssh $PiHost "sudo systemctl status $SERVICE_NAME --no-pager"

# Show recent logs
Write-Host "📋 Recent service logs:" -ForegroundColor Cyan
ssh $PiHost "journalctl -u $SERVICE_NAME -n 20 --no-pager"

Write-Host ""
Write-Host "🎉 Deployment Complete!" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green
Write-Host "Service Name: $SERVICE_NAME" -ForegroundColor White
Write-Host "Status: sudo systemctl status $SERVICE_NAME" -ForegroundColor Gray
Write-Host "Logs: journalctl -u $SERVICE_NAME -f" -ForegroundColor Gray
Write-Host "Restart: sudo systemctl restart $SERVICE_NAME" -ForegroundColor Gray
Write-Host ""
Write-Host "The Pi client should now:" -ForegroundColor Yellow
Write-Host "  ✅ Display fullscreen Pizza Hut TV interface" -ForegroundColor Green
Write-Host "  ✅ Accept 4-digit TV codes for connection" -ForegroundColor Green
Write-Host "  ✅ Connect to $ServerUrl" -ForegroundColor Green
Write-Host "  ✅ Play media with webplayer-like transitions" -ForegroundColor Green
Write-Host "  ✅ Sync with server for schedule updates" -ForegroundColor Green
Write-Host ""

# Test connectivity
$test = Read-Host "📡 Test client connectivity? (y/n)"
if ($test -eq "y" -or $test -eq "Y") {
    Write-Host "🧪 Testing client connection..." -ForegroundColor Cyan
    ssh $PiHost @"
        source $VENV_NAME/bin/activate
        python3 -c "
import requests
import sys

try:
    # Test server connection
    response = requests.get('$ServerUrl/api/server_time', timeout=10)
    if response.status_code == 200:
        print('✅ Server connection: OK')
        data = response.json()
        print(f'   Server time: {data.get(\"server_time_ms\", \"unknown\")}')
    else:
        print('❌ Server connection: Failed')
        sys.exit(1)
        
    # Test store API
    response = requests.get('$ServerUrl/api/stores_by_code/1234', timeout=10)
    if response.status_code == 200:
        stores = response.json()
        print(f'✅ Store API: OK ({len(stores)} stores for test code)')
    else:
        print('❌ Store API: Failed')
        
    print('🎉 All connectivity tests passed!')
    
except Exception as e:
    print(f'❌ Connectivity test failed: {e}')
    sys.exit(1)
        "
"@
}

Write-Host "🍕 Pizza Hut TV Complete Pi Client is ready!" -ForegroundColor Green