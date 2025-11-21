Write-Host "=== Setting up Vonage SMS on Production ===" -ForegroundColor Cyan
Write-Host ""

$setupScript = @'
#!/bin/bash
echo "Setting up Vonage SMS credentials..."

cd /var/www/pizza-hut-tv

cp .env .env.backup-$(date +%s) 2>/dev/null || true

if ! grep -q "VONAGE_API_KEY" .env 2>/dev/null; then
    echo "" >> .env
    echo "# Vonage SMS Configuration" >> .env
    echo "VONAGE_API_KEY=cd8f971d" >> .env
    echo "VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m" >> .env
    echo "VONAGE_FROM_NUMBER=+13165308999" >> .env
    echo "Vonage credentials added to .env"
else
    echo "Vonage credentials already exist in .env"
fi

echo ""
echo "Installing Vonage SDK..."
source venv/bin/activate
pip install 'vonage>=3.0,<4'

echo ""
echo "Restarting service..."
sudo systemctl restart pizza-hut-tv
sleep 2

echo ""
echo "Setup complete!"
echo ""
echo "Checking service status:"
sudo systemctl status pizza-hut-tv --no-pager -l | head -15

echo ""
echo "Checking for Vonage initialization:"
sudo journalctl -u pizza-hut-tv -n 50 --no-pager | grep -i vonage
'@

$tempScript = "setup_vonage_tmp.sh"
$setupScript | Out-File -FilePath $tempScript -Encoding ASCII -NoNewline

Write-Host "Uploading setup script to server..." -ForegroundColor Yellow
scp $tempScript ubuntu@54.252.90.27:~/setup_vonage.sh
if ($LASTEXITCODE -eq 0) {
    Write-Host "Script uploaded" -ForegroundColor Green
} else {
    Write-Host "Upload failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Running setup on server..." -ForegroundColor Yellow
ssh ubuntu@54.252.90.27 "chmod +x ~/setup_vonage.sh ; ~/setup_vonage.sh"

Remove-Item $tempScript -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Phone verification is now set up!" -ForegroundColor Green
Write-Host ""
Write-Host "Test at: https://everydayadvertise.com/account" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
