# Restart Pizza Hut TV Service on Raspberry Pi
# This script restarts the service to load the new Pi ID display

Write-Host "=== Restarting Pizza Hut TV Service on Raspberry Pi ===" -ForegroundColor Cyan

# Restart the service
Write-Host "`nRestarting service..." -ForegroundColor Yellow
ssh everydayadvertise@raspberrypi "sudo systemctl restart pizza-hut-tv"

Start-Sleep -Seconds 2

# Check service status
Write-Host "`nChecking service status..." -ForegroundColor Yellow
ssh everydayadvertise@raspberrypi "sudo systemctl status pizza-hut-tv --no-pager | head -15"

Write-Host "`n=== Service Restart Complete ===" -ForegroundColor Green
Write-Host "The Pi ID should now be visible on the screen!" -ForegroundColor Green
Write-Host "Look for: 'Pi ID: raspberrypi-db39' at the bottom center" -ForegroundColor Cyan
