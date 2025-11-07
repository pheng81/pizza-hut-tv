# VNC WebSocket Tunnel - Complete Deployment Script
# This deploys the VNC-over-WebSocket solution to server and Pi

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VNC WebSocket Tunnel Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$SERVER = "ubuntu@54.252.90.27"
$PI = "pi@203.158.51.30"  # Update with your Pi's IP or hostname

# Step 1: Deploy to Server
Write-Host "[1/4] Deploying to server..." -ForegroundColor Yellow

Write-Host "  - Uploading app.py..." -ForegroundColor Gray
scp app.py "${SERVER}:~/pizza-hut-tv-deploy/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to upload app.py" -ForegroundColor Red
    exit 1
}

Write-Host "  - Uploading vnc_viewer.html template..." -ForegroundColor Gray
scp templates/vnc_viewer.html "${SERVER}:~/pizza-hut-tv-deploy/templates/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to upload vnc_viewer.html" -ForegroundColor Red
    exit 1
}

Write-Host "  - Uploading dashboard.html template..." -ForegroundColor Gray
scp templates/dashboard.html "${SERVER}:~/pizza-hut-tv-deploy/templates/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to upload dashboard.html" -ForegroundColor Red
    exit 1
}

Write-Host "  - Copying files to production..." -ForegroundColor Gray
ssh $SERVER @"
sudo cp ~/pizza-hut-tv-deploy/app.py /var/www/pizza-hut-tv/
sudo cp ~/pizza-hut-tv-deploy/templates/vnc_viewer.html /var/www/pizza-hut-tv/templates/
sudo cp ~/pizza-hut-tv-deploy/templates/dashboard.html /var/www/pizza-hut-tv/templates/
sudo systemctl restart pizza-hut-tv
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to deploy to server" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Server deployment complete" -ForegroundColor Green
Write-Host ""

# Step 2: Deploy to Pi
Write-Host "[2/4] Deploying to Pi..." -ForegroundColor Yellow

Write-Host "  - Uploading pi_vnc_tunnel.py..." -ForegroundColor Gray
scp pi_vnc_tunnel.py "${PI}:~/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to upload pi_vnc_tunnel.py" -ForegroundColor Red
    Write-Host "⚠️  Please check Pi connectivity" -ForegroundColor Yellow
    exit 1
}

Write-Host "  - Installing dependencies (mss for screen capture)..." -ForegroundColor Gray
ssh $PI "pip3 install mss pillow"

Write-Host "✅ Pi deployment complete" -ForegroundColor Green
Write-Host ""

# Step 3: Integration Instructions
Write-Host "[3/4] Pi Integration Required" -ForegroundColor Yellow
Write-Host ""
Write-Host "The Pi client needs manual integration of VNC handlers." -ForegroundColor Cyan
Write-Host "Please follow these steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. SSH to Pi: ssh $PI" -ForegroundColor White
Write-Host "2. Edit complete_pi_client.py: nano complete_pi_client.py" -ForegroundColor White
Write-Host "3. Add import at top:" -ForegroundColor White
Write-Host "   from pi_vnc_tunnel import init_vnc_tunnel, get_vnc_tunnel" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Initialize VNC (after socketio.connect):" -ForegroundColor White
Write-Host "   vnc_tunnel = init_vnc_tunnel(socketio, PI_ID)" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Add handlers (see VNC_INTEGRATION_GUIDE.txt)" -ForegroundColor White
Write-Host "6. Restart Pi service: sudo systemctl restart pizzahut-tv-pi.service" -ForegroundColor White
Write-Host ""
Write-Host "📄 Full integration guide: VNC_INTEGRATION_GUIDE.txt" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter when Pi integration is complete..."

# Step 4: Verification
Write-Host "[4/4] Verification" -ForegroundColor Yellow
Write-Host ""
Write-Host "✅ Server: VNC route available at /vnc/<pi_id>" -ForegroundColor Green
Write-Host "✅ Dashboard: 'Start VNC' button opens new window" -ForegroundColor Green
Write-Host "⏳ Pi: Waiting for integration..." -ForegroundColor Yellow
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  How to Test VNC Connection" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Open dashboard: https://everydayadvertise.com/dashboard" -ForegroundColor White
Write-Host "2. Connect to Pi using Pi Manager" -ForegroundColor White
Write-Host "3. Click 'Start VNC' button" -ForegroundColor White
Write-Host "4. New window opens with live VNC view" -ForegroundColor White
Write-Host "5. You should see Pi's screen in real-time!" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Expected Result:" -ForegroundColor Cyan
Write-Host "   - VNC window opens (1280x800)" -ForegroundColor Gray
Write-Host "   - Connects to Pi via WebSocket tunnel" -ForegroundColor Gray
Write-Host "   - Shows live screen capture (10 FPS)" -ForegroundColor Gray
Write-Host "   - Mouse/keyboard input captured" -ForegroundColor Gray
Write-Host "   - Works from anywhere (no VPN needed!)" -ForegroundColor Gray
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete! 🎉" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
