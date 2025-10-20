# Quick VNC Deployment to Raspberry Pi
# Fixed version - Simple and working

$PI_IP = "192.168.1.131"  # UPDATE THIS with your Pi's IP address
$PI_USER = "everydayadvertise"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VNC Tunnel - Pi Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Pi is reachable
Write-Host "[1/4] Checking Pi connectivity at $PI_IP..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $PI_IP -Count 1 -Quiet
if (-not $ping) {
    Write-Host "ERROR: Cannot reach Pi at $PI_IP" -ForegroundColor Red
    Write-Host "Please update the PI_IP variable in this script" -ForegroundColor Yellow
    exit 1
}
Write-Host "SUCCESS: Pi is reachable" -ForegroundColor Green
Write-Host ""

# Upload VNC tunnel module
Write-Host "[2/4] Uploading pi_vnc_tunnel.py..." -ForegroundColor Yellow
scp "pi_vnc_tunnel.py" "${PI_USER}@${PI_IP}:~/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload file" -ForegroundColor Red
    exit 1
}
Write-Host "SUCCESS: File uploaded" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "[3/4] Installing Python dependencies..." -ForegroundColor Yellow
ssh "${PI_USER}@${PI_IP}" "pip3 install mss pillow --quiet"
Write-Host "SUCCESS: Dependencies installed" -ForegroundColor Green
Write-Host ""

# Show integration instructions
Write-Host "[4/4] Manual Integration Required" -ForegroundColor Yellow
Write-Host ""
Write-Host "Now SSH to your Pi and integrate the VNC handlers:" -ForegroundColor Cyan
Write-Host ""
Write-Host "Step 1: SSH to Pi" -ForegroundColor White
Write-Host "  ssh ${PI_USER}@${PI_IP}" -ForegroundColor Gray
Write-Host ""
Write-Host "Step 2: Edit Pi client" -ForegroundColor White
Write-Host "  nano complete_pi_client.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Step 3: Add import at TOP" -ForegroundColor White
Write-Host "  from pi_vnc_tunnel import init_vnc_tunnel, get_vnc_tunnel" -ForegroundColor Gray
Write-Host ""
Write-Host "Step 4: After socketio.connect(), add:" -ForegroundColor White
Write-Host "  vnc_tunnel = init_vnc_tunnel(socketio, PI_ID)" -ForegroundColor Gray
Write-Host ""
Write-Host "Step 5: Add 3 handlers (see VNC_INTEGRATION_GUIDE.txt)" -ForegroundColor White
Write-Host "  @socketio.on('vnc_connect')" -ForegroundColor Gray
Write-Host "  @socketio.on('vnc_data')" -ForegroundColor Gray
Write-Host "  @socketio.on('vnc_disconnect')" -ForegroundColor Gray
Write-Host ""
Write-Host "Step 6: Restart service" -ForegroundColor White
Write-Host "  sudo systemctl restart pizzahut-tv-pi.service" -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "See VNC_INTEGRATION_GUIDE.txt for full handler code" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
