# Quick Deploy - Screen Preview Feature
# This uploads complete_pi_client.py and shows you what to do next

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Quick Deploy - Screen Preview" -ForegroundColor Cyan  
Write-Host "========================================`n" -ForegroundColor Cyan

$piHost = "everydayadvertise@raspberrypi"

# Step 1: Upload Pi Client
Write-Host "1. Uploading complete_pi_client.py to Pi..." -ForegroundColor Yellow

# Use pscp or scp with password prompt
$localFile = "c:\Users\toeng\Pizza Hut TV\complete_pi_client.py"
$result = scp $localFile "${piHost}:/home/everydayadvertise/" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ File uploaded successfully`n" -ForegroundColor Green
    
    # Step 2: Install dependencies and restart
    Write-Host "2. Installing dependencies on Pi..." -ForegroundColor Yellow
    ssh $piHost "cd ~/pizza-hut-tv && source bin/activate && pip install Pillow && sudo apt-get install -y scrot"
    
    Write-Host "`n3. Restarting Pi client..." -ForegroundColor Yellow
    ssh $piHost "pkill -f complete_pi_client.py; nohup ~/pizza-hut-tv/bin/python ~/complete_pi_client.py > /tmp/pi_test.log 2>&1 &"
    
    Write-Host "   ✓ Pi client restarted`n" -ForegroundColor Green
    
} else {
    Write-Host "   ✗ Upload failed`n" -ForegroundColor Red
}

# Step 3: Show manual server deployment instructions
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MANUAL SERVER DEPLOYMENT NEEDED" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "The following files need to be uploaded to the server:" -ForegroundColor White
Write-Host ""
Write-Host "File 1: templates/dashboard.html" -ForegroundColor Cyan
Write-Host "  Local:  c:\Users\toeng\Pizza Hut TV\templates\dashboard.html" -ForegroundColor Gray
Write-Host "  Server: /home/ubuntu/Pizza-Hut-TV/templates/dashboard.html" -ForegroundColor Gray
Write-Host ""
Write-Host "File 2: app.py" -ForegroundColor Cyan
Write-Host "  Local:  c:\Users\toeng\Pizza Hut TV\app.py" -ForegroundColor Gray
Write-Host "  Server: /home/ubuntu/Pizza-Hut-TV/app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Upload Options:" -ForegroundColor Yellow
Write-Host "  A) Use FTP client (FileZilla, WinSCP)" -ForegroundColor White
Write-Host "  B) Use cPanel File Manager" -ForegroundColor White
Write-Host "  C) Use AWS Lightsail console file upload" -ForegroundColor White
Write-Host "  D) Try SSH: ssh ubuntu@everydayadvertise.com" -ForegroundColor White
Write-Host ""
Write-Host "After uploading, restart the server service:" -ForegroundColor Yellow
Write-Host "  sudo systemctl restart pizza-hut-tv" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
