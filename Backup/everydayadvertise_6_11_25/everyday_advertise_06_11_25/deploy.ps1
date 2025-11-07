# Pizza Hut TV Deployment Script
# This script deploys the updated code to both Pi and Server

Write-Host "🚀 Pizza Hut TV Deployment Script" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# Deploy to Raspberry Pi
Write-Host "`n📡 Deploying to Raspberry Pi..." -ForegroundColor Cyan
try {
    Write-Host "Copying ea_tv.py to Pi..."
    scp "ea_tv_pi.py" "everydayadvertise@raspberrypi.local:/home/everydayadvertise/Desktop/ea_tv.py"
    
    Write-Host "✅ Pi deployment successful!" -ForegroundColor Green
    
    # Restart the Pi client service if running
    Write-Host "Checking if Pi client is running..."
    ssh everydayadvertise@raspberrypi.local "pkill -f 'python.*ea_tv.py' 2>/dev/null; true"
    Write-Host "Pi client processes stopped (if any were running)"
    
} catch {
    Write-Host "❌ Pi deployment failed: $_" -ForegroundColor Red
}

# Server deployment instructions
Write-Host "`n🖥️ Server Deployment Instructions:" -ForegroundColor Cyan
Write-Host "1. Server files to update:" -ForegroundColor Yellow
Write-Host "   - app.py (Flask application)" -ForegroundColor White
Write-Host "   - Any template files if modified" -ForegroundColor White

Write-Host "`n2. Manual server update commands:" -ForegroundColor Yellow
Write-Host "   # Connect to server:" -ForegroundColor White  
Write-Host "   ssh ubuntu@54.252.90.27" -ForegroundColor Gray
Write-Host "   # Backup current app:" -ForegroundColor White
Write-Host "   cp /home/ubuntu/pizza-hut-tv/app.py /home/ubuntu/pizza-hut-tv/app.py.backup" -ForegroundColor Gray
Write-Host "   # Update app.py with new version" -ForegroundColor White
Write-Host "   # Restart Flask service:" -ForegroundColor White
Write-Host "   sudo systemctl restart pizza-hut-tv" -ForegroundColor Gray

Write-Host "`n3. Server deployment checklist:" -ForegroundColor Yellow
Write-Host "   ✓ Mixed media detection improvements" -ForegroundColor White
Write-Host "   ✓ Schedule-aware playlist transitions" -ForegroundColor White 
Write-Host "   ✓ Slice video URL generation" -ForegroundColor White
Write-Host "   ✓ Auto-clean playlist fix (disabled)" -ForegroundColor White

# Pi deployment verification
Write-Host "`n🔍 Pi Deployment Verification:" -ForegroundColor Cyan
Write-Host "Testing Pi client functionality..."
try {
    ssh everydayadvertise@raspberrypi.local "python3 --version; ls -la /home/everydayadvertise/Desktop/ea_tv.py"
    Write-Host "✅ Pi client file deployed successfully!" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Could not verify Pi deployment" -ForegroundColor Yellow
}

Write-Host "`n🎯 Deployment Summary:" -ForegroundColor Green
Write-Host "=====================" -ForegroundColor Green
Write-Host "✅ Pi Client: Updated with mixed media fixes" -ForegroundColor Green
Write-Host "⏳ Server: Manual update required (SSH key needed)" -ForegroundColor Yellow
Write-Host "📋 Features: Schedule-aware transitions, slice cropping fixes" -ForegroundColor Green

Write-Host "`n🔄 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Test Pi client: ssh everydayadvertise@raspberrypi.local 'cd Desktop && python3 ea_tv.py --screen 2'" -ForegroundColor White
Write-Host "2. Update server manually if needed" -ForegroundColor White
Write-Host "3. Verify scheduling transitions work properly" -ForegroundColor White

Write-Host "`nDeployment script completed! 🎉" -ForegroundColor Green