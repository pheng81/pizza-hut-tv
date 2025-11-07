# Deploy Fixed Pi Client Script
# This script deploys the corrected pi_client_ui.py with proper server IP to the Pi

Write-Host "Pizza Hut TV - Deploy Fixed Pi Client" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green

# Check if Pi is accessible
Write-Host "Checking Pi connectivity..." -ForegroundColor Yellow
$pingResult = Test-NetConnection -ComputerName raspberrypi -Port 22 -InformationLevel Quiet

if ($pingResult) {
    Write-Host "Pi is accessible! Deploying updated files..." -ForegroundColor Green
    
    # Deploy the corrected pi_client_ui.py
    Write-Host "Deploying pi_client_ui.py with correct server IP..." -ForegroundColor Yellow
    scp "pi_client_ui.py" everydayadvertise@raspberrypi:~/
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ pi_client_ui.py deployed successfully!" -ForegroundColor Green
        
        # SSH into Pi and restart the client
        Write-Host "Restarting Pi client service..." -ForegroundColor Yellow
        ssh everydayadvertise@raspberrypi "sudo systemctl restart pizza-hut-tv"
        
        Write-Host "✅ Pi client service restarted!" -ForegroundColor Green
        Write-Host ""
        Write-Host "NETWORK FIX APPLIED:" -ForegroundColor Cyan
        Write-Host "- Server URL changed to online server: https://everydayadvertise.com" -ForegroundColor White
        Write-Host "- Pi client should now be able to validate 4-digit TV codes from online server" -ForegroundColor White
        Write-Host ""
        Write-Host "To test: Run the Pi client and try entering a 4-digit code!" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Failed to deploy pi_client_ui.py" -ForegroundColor Red
    }
} else {
    Write-Host "❌ Pi is not accessible at raspberrypi" -ForegroundColor Red
    Write-Host ""
    Write-Host "MANUAL DEPLOYMENT INSTRUCTIONS:" -ForegroundColor Yellow
    Write-Host "1. Ensure Pi is powered on and connected to network" -ForegroundColor White
    Write-Host "2. Run this script again when Pi is accessible" -ForegroundColor White
    Write-Host "3. Or manually copy pi_client_ui.py to Pi using:" -ForegroundColor White
    Write-Host "   scp pi_client_ui.py everydayadvertise@raspberrypi:~/" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")