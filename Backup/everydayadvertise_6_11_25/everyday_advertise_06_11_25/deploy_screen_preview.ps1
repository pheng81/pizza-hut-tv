# Deploy Screen Preview Feature
# This script uploads the necessary files to enable live screen preview in Remote Pi Manager

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Screen Preview Feature Deployment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Continue"

# Files to deploy
$serverFiles = @(
    @{
        Local = "c:\Users\toeng\Pizza Hut TV\app.py"
        Remote = "~/Pizza-Hut-TV/app.py"
        Server = "ubuntu@everydayadvertise.com"
    },
    @{
        Local = "c:\Users\toeng\Pizza Hut TV\templates\dashboard.html"
        Remote = "~/Pizza-Hut-TV/templates/dashboard.html"
        Server = "ubuntu@everydayadvertise.com"
    }
)

$piFiles = @(
    @{
        Local = "c:\Users\toeng\Pizza Hut TV\complete_pi_client.py"
        Remote = "~/complete_pi_client.py"
        Server = "everydayadvertise@raspberrypi"
    }
)

# Deploy to server
Write-Host "1. Deploying to Server..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $serverFiles) {
    Write-Host "   Uploading: $($file.Local)" -ForegroundColor White
    Write-Host "   To: $($file.Server):$($file.Remote)" -ForegroundColor Gray
    
    $result = scp $file.Local "$($file.Server):$($file.Remote)" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✓ Success" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Failed: $result" -ForegroundColor Red
    }
    Write-Host ""
}

# Restart server service
Write-Host "2. Restarting Server Service..." -ForegroundColor Yellow
ssh ubuntu@everydayadvertise.com "sudo systemctl restart pizza-hut-tv"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Server restarted successfully" -ForegroundColor Green
} else {
    Write-Host "   ✗ Server restart failed" -ForegroundColor Red
    Write-Host "   Manual restart: ssh ubuntu@everydayadvertise.com 'sudo systemctl restart pizza-hut-tv'" -ForegroundColor Yellow
}
Write-Host ""

# Deploy to Pi
Write-Host "3. Deploying to Pi..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $piFiles) {
    Write-Host "   Uploading: $($file.Local)" -ForegroundColor White
    Write-Host "   To: $($file.Server):$($file.Remote)" -ForegroundColor Gray
    
    $result = scp $file.Local "$($file.Server):$($file.Remote)" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✓ Success" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Failed: $result" -ForegroundColor Red
    }
    Write-Host ""
}

# Install dependencies and restart Pi client
Write-Host "4. Installing Pi Dependencies..." -ForegroundColor Yellow
Write-Host ""

Write-Host "   Installing Pillow..." -ForegroundColor White
ssh everydayadvertise@raspberrypi "cd ~/pizza-hut-tv && source bin/activate && pip install Pillow"

Write-Host "   Installing scrot..." -ForegroundColor White
ssh everydayadvertise@raspberrypi "sudo apt-get install -y scrot"

Write-Host ""
Write-Host "5. Restarting Pi Client..." -ForegroundColor Yellow
ssh everydayadvertise@raspberrypi "pkill -f complete_pi_client.py; nohup ~/pizza-hut-tv/bin/python ~/complete_pi_client.py > /tmp/pi_test.log 2>&1 &"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Pi client restarted" -ForegroundColor Green
} else {
    Write-Host "   ✗ Failed to restart Pi client" -ForegroundColor Red
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Deployment Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Open dashboard: https://everydayadvertise.com/dashboard" -ForegroundColor White
Write-Host "2. Go to Remote Pi Manager" -ForegroundColor White
Write-Host "3. Connect to Pi (raspberrypi-ce39)" -ForegroundColor White
Write-Host "4. You should see '📺 Screen Preview' section" -ForegroundColor White
Write-Host "5. Click '▶ Start' to begin live preview" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
