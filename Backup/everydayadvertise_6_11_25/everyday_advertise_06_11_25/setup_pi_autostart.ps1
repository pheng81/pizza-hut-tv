#!/usr/bin/env pwsh
# Setup Pi auto-start service

$PiUser = "everydayadvertise"
$PiHost = "192.168.1.131"
$Target = "${PiUser}@${PiHost}"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Pi Auto-Start Service" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Upload the setup script
Write-Host "📤 Uploading setup script to Pi..." -ForegroundColor Yellow
scp setup_pi_service.sh "${Target}:~/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to upload setup script" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Setup script uploaded" -ForegroundColor Green
Write-Host ""

# Make it executable and run it
Write-Host "🚀 Running setup script on Pi..." -ForegroundColor Yellow
ssh $Target "chmod +x ~/setup_pi_service.sh; ~/setup_pi_service.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to run setup script" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "The Pi client will now:" -ForegroundColor Cyan
Write-Host "  ✅ Auto-start on boot" -ForegroundColor White
Write-Host "  ✅ Restart automatically if it crashes" -ForegroundColor White
Write-Host "  ✅ Run even when no user is logged in" -ForegroundColor White
Write-Host ""
