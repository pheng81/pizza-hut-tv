# Deploy updated Pi client with public IP auto-registration

$PI_IP = "192.168.1.131"
$PI_USER = "pi"

Write-Host "🚀 Deploying updated Pi client..." -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green

# Copy updated client
Write-Host "📤 Uploading complete_pi_client.py..." -ForegroundColor Cyan
scp "complete_pi_client.py" "${PI_USER}@${PI_IP}:~/"

# Restart service
Write-Host "🔄 Restarting Pi service..." -ForegroundColor Cyan
ssh "${PI_USER}@${PI_IP}" "sudo systemctl restart pizza-hut-tv"

# Wait for service to start
Start-Sleep -Seconds 3

# Check status
Write-Host "✅ Checking service status..." -ForegroundColor Cyan
ssh "${PI_USER}@${PI_IP}" "sudo systemctl status pizza-hut-tv --no-pager | head -20"

Write-Host ""
Write-Host "====================================" -ForegroundColor Green
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Yellow
Write-Host "1. Set up port forwarding on your router (port 8080 → 192.168.1.131:8080)"
Write-Host "2. Check Pi registered its public IP:"
Write-Host '   ssh -i "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem" ubuntu@54.252.90.27 "cat /var/www/pizza-hut-tv/pi_id_ip_map.json"'
Write-Host "3. Test from dashboard: https://everydayadvertise.com/dashboard"
Write-Host ""
