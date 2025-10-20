# Deploy Dashboard Only
# Use this when Pi is working fine but dashboard needs updates

Write-Host "Deploying Dashboard to Server..." -ForegroundColor Cyan
Write-Host ""

$SERVER_USER = "everydayadvertise"
$SERVER_HOST = "everydayadvertise.com"
$SERVER_PATH = "/home/everydayadvertise/pizza-hut-tv"
$DASHBOARD_FILE = "templates\dashboard.html"

Write-Host "Method: Git Pull (Recommended)" -ForegroundColor Green
Write-Host ""
Write-Host "Run these commands on your server:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ssh $SERVER_USER@$SERVER_HOST" -ForegroundColor White
Write-Host "  cd $SERVER_PATH" -ForegroundColor White
Write-Host "  git pull origin main" -ForegroundColor White
Write-Host "  sudo systemctl restart pizza-hut-tv" -ForegroundColor White
Write-Host ""
Write-Host "-----------------------------------------------------------" -ForegroundColor Gray
Write-Host ""
Write-Host "Alternative Method: Direct SCP Upload" -ForegroundColor Green
Write-Host ""
Write-Host "If Git pull doesn't work, try:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  scp templates\dashboard.html ${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/templates/" -ForegroundColor White
Write-Host "  ssh ${SERVER_USER}@${SERVER_HOST} 'sudo systemctl restart pizza-hut-tv'" -ForegroundColor White
Write-Host ""
Write-Host "-----------------------------------------------------------" -ForegroundColor Gray
Write-Host ""
Write-Host "What the fix does:" -ForegroundColor Cyan
Write-Host "  - Removes hardcoded screen list (Screen 1-4, Promo 1-3)" -ForegroundColor White
Write-Host "  - Fetches actual stores from /api/stores_by_code/{pairCode}" -ForegroundColor White
Write-Host "  - Shows only YOUR screens for selected store" -ForegroundColor White
Write-Host "  - Prevents seeing other users' screens" -ForegroundColor White
Write-Host ""
