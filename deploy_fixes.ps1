# Deploy Pi Client and Dashboard Fixes
# This script deploys the latest changes to both Pi and Server

Write-Host "Starting deployment..." -ForegroundColor Cyan
Write-Host ""

# Configuration
$PI_HOST = "192.168.1.131"
$PI_USER = "everydayadvertise"
$PI_PATH = "/home/everydayadvertise/pizza-hut-tv"

$SERVER_HOST = "142.93.249.238"
$SERVER_USER = "everydayadvertise"
$SERVER_PATH = "/home/everydayadvertise/pizza-hut-tv"

# File paths
$PI_CLIENT = "complete_pi_client.py"
$DASHBOARD = "templates\dashboard.html"

Write-Host "Deploying Pi Client..." -ForegroundColor Yellow
Write-Host "Target: $PI_USER@$PI_HOST" -ForegroundColor Gray
Write-Host ""

# Deploy to Pi
Write-Host "1. Copying $PI_CLIENT to Pi..." -ForegroundColor Green
scp "$PI_CLIENT" "${PI_USER}@${PI_HOST}:${PI_PATH}/"

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Pi client deployed" -ForegroundColor Green
    
    Write-Host "2. Restarting Pi service..." -ForegroundColor Green
    ssh "${PI_USER}@${PI_HOST}" "sudo systemctl restart pizza-hut-tv"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "SUCCESS: Pi service restarted" -ForegroundColor Green
        Write-Host ""
        Write-Host "Checking Pi logs..." -ForegroundColor Cyan
        ssh "${PI_USER}@${PI_HOST}" "sudo journalctl -u pizza-hut-tv -n 20 --no-pager"
    } else {
        Write-Host "ERROR: Failed to restart Pi service" -ForegroundColor Red
    }
} else {
    Write-Host "ERROR: Failed to deploy Pi client" -ForegroundColor Red
}

Write-Host ""
Write-Host "-----------------------------------------------------------" -ForegroundColor Gray
Write-Host ""

Write-Host "Deploying Dashboard..." -ForegroundColor Yellow
Write-Host "Target: $SERVER_USER@$SERVER_HOST" -ForegroundColor Gray
Write-Host ""

# Deploy to Server
Write-Host "1. Copying $DASHBOARD to server..." -ForegroundColor Green
scp "$DASHBOARD" "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/templates/"

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Dashboard deployed" -ForegroundColor Green
    
    Write-Host "2. Restarting server service..." -ForegroundColor Green
    ssh "${SERVER_USER}@${SERVER_HOST}" "sudo systemctl restart pizza-hut-tv"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "SUCCESS: Server service restarted" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to restart server service" -ForegroundColor Red
    }
} else {
    Write-Host "ERROR: Failed to deploy dashboard" -ForegroundColor Red
}

Write-Host ""
Write-Host "-----------------------------------------------------------" -ForegroundColor Gray
Write-Host ""
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test Steps:" -ForegroundColor Yellow
Write-Host "  1. Open Dashboard Remote Pi Manager" -ForegroundColor White
Write-Host "  2. Enter Pi ID: raspberrypi-ce39" -ForegroundColor White
Write-Host "  3. Enter Pairing Code: 6640" -ForegroundColor White
Write-Host "  4. Select YOUR store from dropdown" -ForegroundColor White
Write-Host "  5. Select YOUR screen from dropdown" -ForegroundColor White
Write-Host "  6. Click Configure Pi button" -ForegroundColor White
Write-Host "  7. Video should start playing immediately" -ForegroundColor White
Write-Host ""
