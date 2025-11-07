#!/usr/bin/env pwsh
# Deploy Pizza Hut TV Client to New Raspberry Pi

$PI_IP = "192.168.1.113"
$PI_USER = "everydayadvertise0002"
$SERVER_URL = "https://everydayadvertise.com"

Write-Host "🍕 Deploying Pizza Hut TV Client to Pi at $PI_IP" -ForegroundColor Green
Write-Host ""

# Files to deploy
$files = @(
    "complete_pi_client.py",
    "seamless_video_player.py",
    "pi_vnc_tunnel.py",
    "pi_mobile_sync_addon.py"
)

# Step 1: Create directory on Pi
Write-Host "📁 Creating directory on Pi..." -ForegroundColor Cyan
ssh ${PI_USER}@${PI_IP} "mkdir -p ~/pizzahut-client"

# Step 2: Copy files to Pi
Write-Host "📤 Copying client files to Pi..." -ForegroundColor Cyan
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  → $file"
        scp $file ${PI_USER}@${PI_IP}:~/pizzahut-client/
    } else {
        Write-Host "  ⚠️  Warning: $file not found, skipping..." -ForegroundColor Yellow
    }
}

# Step 3: Make main script executable
Write-Host "🔧 Setting permissions..." -ForegroundColor Cyan
ssh ${PI_USER}@${PI_IP} "chmod +x ~/pizzahut-client/complete_pi_client.py"

# Step 4: Install dependencies on Pi
Write-Host "📦 Installing dependencies on Pi..." -ForegroundColor Cyan
ssh ${PI_USER}@${PI_IP} @"
sudo apt-get update && \
sudo apt-get install -y python3 python3-pip python3-pygame python3-vlc libvlc-dev vlc x11vnc && \
pip3 install requests python-socketio websocket-client pillow --break-system-packages
"@

# Step 5: Create systemd service
Write-Host "⚙️  Creating systemd service..." -ForegroundColor Cyan
ssh ${PI_USER}@${PI_IP} @"
sudo tee /etc/systemd/system/pizzahut-client.service > /dev/null <<'EOF'
[Unit]
Description=Pizza Hut TV Client
After=network.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=/home/${PI_USER}/pizzahut-client
Environment="DISPLAY=:0"
ExecStart=/usr/bin/python3 /home/${PI_USER}/pizzahut-client/complete_pi_client.py --server ${SERVER_URL}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
"@

# Step 6: Enable and start service
Write-Host "🚀 Enabling and starting service..." -ForegroundColor Cyan
ssh ${PI_USER}@${PI_IP} @"
sudo systemctl daemon-reload && \
sudo systemctl enable pizzahut-client.service && \
sudo systemctl restart pizzahut-client.service
"@

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Pi Information:" -ForegroundColor Yellow
ssh ${PI_USER}@${PI_IP} "hostname"
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  ssh ${PI_USER}@${PI_IP} 'sudo journalctl -u pizzahut-client.service -f'"
Write-Host ""
Write-Host "To check status:" -ForegroundColor Cyan
Write-Host "  ssh ${PI_USER}@${PI_IP} 'sudo systemctl status pizzahut-client.service'"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to https://everydayadvertise.com/pi-manager"
Write-Host "2. Find your Pi (raspberrypi) in the list"
Write-Host "3. Click 'Settings' and assign it to a store/screen"
Write-Host ""
