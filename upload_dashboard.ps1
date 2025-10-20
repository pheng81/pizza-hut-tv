# Upload dashboard.html using WinSCP or similar
# Since SSH is timing out, here's a manual upload guide

Write-Host "================================" -ForegroundColor Cyan
Write-Host "DASHBOARD DEPLOYMENT INSTRUCTIONS" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "The issue: Server is running OLD dashboard code with hardcoded screens" -ForegroundColor Yellow
Write-Host "The fix: Upload the NEW dashboard.html file to the server" -ForegroundColor Green
Write-Host ""

Write-Host "Method 1: Use DigitalOcean Console" -ForegroundColor Cyan
Write-Host "  1. Go to: https://cloud.digitalocean.com/droplets" -ForegroundColor White
Write-Host "  2. Click your droplet -> Console" -ForegroundColor White
Write-Host "  3. Log in as: everydayadvertise" -ForegroundColor White
Write-Host "  4. Run these commands:" -ForegroundColor White
Write-Host "     cd /home/everydayadvertise/pizza-hut-tv" -ForegroundColor Gray
Write-Host "     git pull origin main" -ForegroundColor Gray
Write-Host "     sudo systemctl restart pizza-hut-tv" -ForegroundColor Gray
Write-Host ""

Write-Host "Method 2: Use WinSCP (if you have it)" -ForegroundColor Cyan
Write-Host "  1. Open WinSCP" -ForegroundColor White
Write-Host "  2. Connect to: everydayadvertise.com" -ForegroundColor White
Write-Host "  3. Upload: templates\dashboard.html" -ForegroundColor White
Write-Host "  4. To: /home/everydayadvertise/pizza-hut-tv/templates/" -ForegroundColor White
Write-Host "  5. Then SSH and run: sudo systemctl restart pizza-hut-tv" -ForegroundColor White
Write-Host ""

Write-Host "Method 3: Try SSH with verbose logging" -ForegroundColor Cyan
Write-Host "  Run: ssh -v everydayadvertise@everydayadvertise.com" -ForegroundColor Gray
Write-Host "  (This might help diagnose the timeout issue)" -ForegroundColor White
Write-Host ""

Write-Host "What the deployment fixes:" -ForegroundColor Green
Write-Host "  ❌ BEFORE: Dashboard shows hardcoded 7 screens (Screen 1-4, Promo 1-3)" -ForegroundColor Red
Write-Host "  ✅ AFTER:  Dashboard fetches YOUR actual screens from API" -ForegroundColor Green
Write-Host ""

Write-Host "Files to upload:" -ForegroundColor Yellow
Write-Host "  Local:  $PWD\templates\dashboard.html" -ForegroundColor Gray
Write-Host "  Server: /home/everydayadvertise/pizza-hut-tv/templates/dashboard.html" -ForegroundColor Gray
Write-Host ""

Write-Host "After deployment, test by:" -ForegroundColor Cyan
Write-Host "  1. Open dashboard in browser" -ForegroundColor White
Write-Host "  2. Go to Remote Pi Manager" -ForegroundColor White
Write-Host "  3. Enter pairing code: 6640" -ForegroundColor White
Write-Host "  4. Select store: 1000" -ForegroundColor White
Write-Host "  5. Check screen dropdown - should show YOUR screens only" -ForegroundColor White
Write-Host ""

Write-Host "Press any key to try SSH connection one more time..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host ""
Write-Host "Attempting SSH connection..." -ForegroundColor Cyan
ssh everydayadvertise@everydayadvertise.com "cd /home/everydayadvertise/pizza-hut-tv && pwd && ls -la templates/dashboard.html"
