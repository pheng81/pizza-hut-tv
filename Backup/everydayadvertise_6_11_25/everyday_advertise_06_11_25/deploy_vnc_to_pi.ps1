# Quick VNC Deployment to Raspberry Pi
# Run this to deploy VNC tunnel to your Pi

$PI_IP = "192.168.1.131"  # UPDATE THIS with your Pi's IP address
$PI_USER = "pi"           # Update if using different username

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VNC Tunnel - Pi Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Pi is reachable
Write-Host "[1/5] Checking Pi connectivity..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $PI_IP -Count 1 -Quiet
if (-not $ping) {
    Write-Host "❌ Cannot reach Pi at $PI_IP" -ForegroundColor Red
    Write-Host "Please update the PI_IP variable in this script" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Pi is reachable at $PI_IP" -ForegroundColor Green
Write-Host ""

# Upload VNC tunnel module
Write-Host "[2/5] Uploading pi_vnc_tunnel.py..." -ForegroundColor Yellow
scp "pi_vnc_tunnel.py" "${PI_USER}@${PI_IP}:~/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to upload pi_vnc_tunnel.py" -ForegroundColor Red
    Write-Host "Make sure SSH key or password is configured" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ pi_vnc_tunnel.py uploaded" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "[3/5] Installing Python dependencies (mss, pillow)..." -ForegroundColor Yellow
ssh "${PI_USER}@${PI_IP}" "pip3 install mss pillow --quiet"
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Warning: Some dependencies may have failed to install" -ForegroundColor Yellow
}
Write-Host "✅ Dependencies installed" -ForegroundColor Green
Write-Host ""

# Show integration instructions
Write-Host "[4/5] Integration Required" -ForegroundColor Yellow
Write-Host ""
Write-Host "You need to manually add VNC handlers to complete_pi_client.py:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. SSH to Pi:" -ForegroundColor White
Write-Host "   ssh ${PI_USER}@${PI_IP}" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Edit the Pi client:" -ForegroundColor White
Write-Host "   nano complete_pi_client.py" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Add at the TOP (after other imports):" -ForegroundColor White
Write-Host "   from pi_vnc_tunnel import init_vnc_tunnel, get_vnc_tunnel" -ForegroundColor Gray
Write-Host ""
Write-Host "4. After socketio.connect(), add:" -ForegroundColor White
Write-Host "   vnc_tunnel = init_vnc_tunnel(socketio, PI_ID)" -ForegroundColor Gray
Write-Host "   logging.info('✅ VNC tunnel initialized')" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Add these SocketIO handlers (see VNC_INTEGRATION_GUIDE.txt):" -ForegroundColor White
Write-Host "   @socketio.on('vnc_connect')" -ForegroundColor Gray
Write-Host "   @socketio.on('vnc_data')" -ForegroundColor Gray
Write-Host "   @socketio.on('vnc_disconnect')" -ForegroundColor Gray
Write-Host ""
Write-Host "6. Save (Ctrl+X, Y, Enter) and restart:" -ForegroundColor White
Write-Host "   sudo systemctl restart pizzahut-tv-pi.service" -ForegroundColor Gray
Write-Host ""
Write-Host "📄 Full integration guide: VNC_INTEGRATION_GUIDE.txt" -ForegroundColor Cyan
Write-Host ""

# Test connection
Write-Host "[5/5] Testing..." -ForegroundColor Yellow
Write-Host ""
Write-Host "After integration, test by:" -ForegroundColor Cyan
Write-Host "1. Opening dashboard: https://everydayadvertise.com/dashboard" -ForegroundColor White
Write-Host "2. Click 'Remote Pi Manager'" -ForegroundColor White
Write-Host "3. Enter Pi ID: raspberrypi-ce39" -ForegroundColor White
Write-Host "4. Click 'Connect'" -ForegroundColor White
Write-Host "5. Click 'Start VNC'" -ForegroundColor White
Write-Host "6. VNC window should show live Pi screen!" -ForegroundColor White
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. SSH to Pi and edit complete_pi_client.py" -ForegroundColor White
Write-Host "2. Add the 3 imports + 3 handlers + 1 initialization line" -ForegroundColor White
Write-Host "3. Restart Pi service" -ForegroundColor White
Write-Host "4. Test VNC from dashboard" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Files uploaded to Pi:" -ForegroundColor Green
Write-Host "   ~/pi_vnc_tunnel.py" -ForegroundColor Gray
Write-Host ""
Write-Host "📚 Reference:" -ForegroundColor Green
Write-Host "   VNC_INTEGRATION_GUIDE.txt (on your computer)" -ForegroundColor Gray
Write-Host "   PI_VNC_DEPLOYMENT.txt (detailed step-by-step)" -ForegroundColor Gray
Write-Host ""
