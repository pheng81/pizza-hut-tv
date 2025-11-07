# Simple Pi Deployment Script
Write-Host "`nDeploying to Pi...`n" -ForegroundColor Cyan

# Upload file
Write-Host "1. Uploading complete_pi_client.py..." -ForegroundColor Yellow
scp "c:\Users\toeng\Pizza Hut TV\complete_pi_client.py" everydayadvertise@raspberrypi:~/

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Uploaded`n" -ForegroundColor Green
    
    # Install Pillow
    Write-Host "2. Installing Pillow..." -ForegroundColor Yellow
    ssh everydayadvertise@raspberrypi "cd ~/pizza-hut-tv; source bin/activate; pip install Pillow"
    
    # Install scrot
    Write-Host "`n3. Installing scrot..." -ForegroundColor Yellow
    ssh everydayadvertise@raspberrypi "sudo apt-get install -y scrot"
    
    # Restart client
    Write-Host "`n4. Restarting Pi client..." -ForegroundColor Yellow
    ssh everydayadvertise@raspberrypi "pkill -f complete_pi_client.py"
    Start-Sleep -Seconds 2
    ssh everydayadvertise@raspberrypi 'nohup ~/pizza-hut-tv/bin/python ~/complete_pi_client.py > /tmp/pi_test.log 2>&1 &'
    
    Write-Host "`n✓ Pi deployment complete!`n" -ForegroundColor Green
    
} else {
    Write-Host "   ✗ Upload failed`n" -ForegroundColor Red
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NEXT: Upload these to SERVER manually:" -ForegroundColor Yellow
Write-Host "  1. templates/dashboard.html" -ForegroundColor White
Write-Host "  2. app.py" -ForegroundColor White
Write-Host "Then restart: sudo systemctl restart pizza-hut-tv" -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor Cyan
