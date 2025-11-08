param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\.ssh\LightsailDefaultKey-ap-southeast-2.pem",
    [string]$TempPath = "pizza-hut-tv-deploy",
    [string]$FinalPath = "/var/www/pizza-hut-tv"
)

Write-Host "== SAFE Pizza Hut TV Deploy (Protects Config) ==" -ForegroundColor Cyan
Write-Host ""

# Check local config is clean BEFORE deploying
Write-Host "Checking local config integrity..." -ForegroundColor Yellow
$checkResult = & python fix_screen_mixup.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Local config has issues! Fix them first." -ForegroundColor Red
    exit 1
}

$cleanCheck = $checkResult | Select-String "No issues found"
if (-not $cleanCheck) {
    Write-Host "⚠️  Local config was just cleaned. Review changes before deploying." -ForegroundColor Yellow
    $continue = Read-Host "Continue with deployment? (yes/no)"
    if ($continue -ne "yes") {
        Write-Host "Deployment cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "✓ Local config is clean" -ForegroundColor Green
Write-Host ""

# Store local config size for verification
$localConfigSize = (Get-Item "store_config__test9_at_gmail.com.json").Length
Write-Host "Local config size: $([math]::Round($localConfigSize/1024, 2)) KB" -ForegroundColor Cyan

# Create temp directory
Write-Host ""
Write-Host "Creating temp deploy directory..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "rm -rf ~/${TempPath} && mkdir -p ~/${TempPath}/templates/webplayer ~/${TempPath}/templates/webplayer_1 ~/${TempPath}/static"

# Upload files
$coreFiles = @('app.py', 'requirements.txt')
$templateFiles = @(
    'templates/home.html',
    'templates/dashboard.html',
    'templates/vnc_viewer.html',
    'templates/webplayer/browse.html',
    'templates/webplayer/index.html',
    'templates/webplayer/store.html',
    'templates/webplayer/player.html',
    'templates/tv_view.html',
    'templates/webplayer_1/player.html',
    'templates/pi_manager.html'
)

Write-Host "Uploading core files..." -ForegroundColor Yellow
foreach($file in $coreFiles) {
    if(Test-Path $file) {
        Write-Host "  -> $file"
        & scp -i $KeyPath $file "ubuntu@${Server}:~/${TempPath}/"
    }
}

Write-Host "Uploading templates..." -ForegroundColor Yellow
foreach($file in $templateFiles) {
    if(Test-Path $file) {
        & scp -i $KeyPath $file "ubuntu@${Server}:~/${TempPath}/${file}" 2>&1 | Out-Null
    }
}

if (Test-Path 'templates') {
    & scp -i $KeyPath -r 'templates' "ubuntu@${Server}:~/${TempPath}/" 2>&1 | Out-Null
}
if (Test-Path 'static') {
    & scp -i $KeyPath -r 'static' "ubuntu@${Server}:~/${TempPath}/" 2>&1 | Out-Null
}

# IMPORTANT: Upload clean config BEFORE deployment
Write-Host ""
Write-Host "Uploading CLEAN local config to server..." -ForegroundColor Cyan
& scp -i $KeyPath "store_config__test9_at_gmail.com.json" "ubuntu@${Server}:~/${TempPath}/"

# Create backups on server
Write-Host ""
Write-Host "Creating server backups..." -ForegroundColor Yellow
$timestamp = [int][double]::Parse((Get-Date -UFormat %s))
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && if [ -f database.db ]; then cp database.db database.db.backup-${timestamp}; fi; if [ -f store_config__test9_at_gmail.com.json ]; then cp store_config__test9_at_gmail.com.json store_config__test9_at_gmail.com.json.backup-${timestamp}; fi"

# Deploy files (including config)
Write-Host "Deploying to production..." -ForegroundColor Yellow
$deployCmd = @"
sudo mkdir -p ${FinalPath}/templates ${FinalPath}/static
if ls ~/${TempPath}/*.py 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.py ${FinalPath}/; fi
if ls ~/${TempPath}/*.txt 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.txt ${FinalPath}/; fi
if ls ~/${TempPath}/*.json 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.json ${FinalPath}/; fi
if [ -d ~/${TempPath}/templates ]; then sudo cp -r ~/${TempPath}/templates/* ${FinalPath}/templates/ 2>/dev/null || true; fi
if [ -d ~/${TempPath}/static ]; then sudo cp -r ~/${TempPath}/static/* ${FinalPath}/static/ 2>/dev/null || true; fi
sudo chown -R ubuntu:ubuntu ${FinalPath}
rm -rf ~/${TempPath}
"@

& ssh -i $KeyPath "ubuntu@${Server}" $deployCmd

# Install dependencies and restart
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && source venv/bin/activate && pip install -q -r requirements.txt" 2>&1 | Out-Null

Write-Host "Restarting service..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "sudo pkill -f 'gunicorn.*pizza-hut-tv' 2>/dev/null || true; sleep 1; sudo systemctl restart pizza-hut-tv"
Start-Sleep -Seconds 3

& ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl status pizza-hut-tv --no-pager"

# Verify server config matches local
Write-Host ""
Write-Host "Verifying server config..." -ForegroundColor Cyan
$serverConfigSize = & ssh -i $KeyPath "ubuntu@${Server}" "stat -f%z ${FinalPath}/store_config__test9_at_gmail.com.json 2>/dev/null || stat -c%s ${FinalPath}/store_config__test9_at_gmail.com.json 2>/dev/null"
$serverConfigSize = [int]$serverConfigSize

if ($serverConfigSize -eq $localConfigSize) {
    Write-Host "✓ Server config matches local ($([math]::Round($serverConfigSize/1024, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "⚠️  Server config size mismatch!" -ForegroundColor Yellow
    Write-Host "  Local: $([math]::Round($localConfigSize/1024, 2)) KB" -ForegroundColor Yellow
    Write-Host "  Server: $([math]::Round($serverConfigSize/1024, 2)) KB" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host "✅ Your clean config is now on the server!" -ForegroundColor Green
