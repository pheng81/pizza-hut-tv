param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$TempPath = "pizza-hut-tv-deploy",
    [string]$FinalPath = "/var/www/pizza-hut-tv",
    [switch]$PreserveConfig
)

Write-Host "== Pizza Hut TV Server Deploy ==" -ForegroundColor Cyan
Write-Host ""

# Check if local database exists and is recent
$localDbAge = $null
if (Test-Path "database.db") {
    $localDbAge = (Get-Date) - (Get-Item "database.db").LastWriteTime
    Write-Host "Local database found (last updated: $([math]::Round($localDbAge.TotalHours, 1)) hours ago)" -ForegroundColor Cyan
    
    if ($localDbAge.TotalDays -gt 1) {
        Write-Host "  ⚠ Local database is over 1 day old" -ForegroundColor Yellow
        $syncFirst = Read-Host "Sync from server first? (yes/no)"
        if ($syncFirst -eq "yes") {
            Write-Host "Running sync..." -ForegroundColor Yellow
            & "$PSScriptRoot\sync_from_server.ps1" -AutoSync
            Write-Host ""
        }
    }
} else {
    Write-Host "⚠ No local database found!" -ForegroundColor Yellow
    Write-Host "  Run .\sync_from_server.ps1 to download server data for local testing" -ForegroundColor Cyan
    Write-Host ""
}

# Create temp directory on server
Write-Host "Creating temp deploy directory..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "rm -rf ~/${TempPath} && mkdir -p ~/${TempPath}/templates/webplayer ~/${TempPath}/templates/webplayer_1 ~/${TempPath}/static && sudo mkdir -p ${FinalPath}/templates ${FinalPath}/static"

# Core server files to deploy (NEVER include database files!)
$coreFiles = @(
    'app.py',
    'requirements.txt'
)

# Template files (explicit list for known templates; full folder upload happens below)
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

Write-Host "Uploading core server files to ubuntu@${Server}:~/${TempPath}" -ForegroundColor Yellow

foreach($file in $coreFiles) {
    if(Test-Path $file) {
        Write-Host "  -> $file"
        & scp -i $KeyPath $file "ubuntu@${Server}:~/${TempPath}/"
        if($LASTEXITCODE -ne 0) {
            Write-Error "Failed to copy $file (scp exit code $LASTEXITCODE)"
            exit 1
        }
    } else {
        Write-Warning "File not found: $file"
    }
}

Write-Host "Uploading template files..." -ForegroundColor Yellow
foreach($file in $templateFiles) {
    if(Test-Path $file) {
        Write-Host "  -> $file"
        & scp -i $KeyPath $file "ubuntu@${Server}:~/${TempPath}/${file}"
        if($LASTEXITCODE -ne 0) {
            Write-Error "Failed to copy $file (scp exit code $LASTEXITCODE)"
            exit 1
        }
    } else {
        Write-Warning "File not found: $file"
    }
}

# Upload entire templates directory (recursive) to capture any new files
if (Test-Path 'templates') {
    Write-Host "Uploading full templates directory (recursive)..." -ForegroundColor Yellow
    & scp -i $KeyPath -r 'templates' "ubuntu@${Server}:~/${TempPath}/" | Out-Null
}

# Upload static assets (recursive)
if (Test-Path 'static') {
    Write-Host "Uploading static assets (recursive)..." -ForegroundColor Yellow
    & scp -i $KeyPath -r 'static' "ubuntu@${Server}:~/${TempPath}/" | Out-Null
}

Write-Host "Creating automatic backup before deployment..." -ForegroundColor Cyan
$timestamp = [int][double]::Parse((Get-Date -UFormat %s))
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && if [ -f database.db ]; then cp database.db database.db.backup-${timestamp}; echo 'Database backup: database.db.backup-${timestamp}'; fi; if [ -f store_config__test9_at_gmail.com.json ]; then cp store_config__test9_at_gmail.com.json store_config__test9_at_gmail.com.json.backup-${timestamp}; echo 'Config backup: store_config__test9_at_gmail.com.json.backup-${timestamp}'; fi"

Write-Host "Moving files to production directory..." -ForegroundColor Yellow
# Use single-line remote command to avoid CRLF issues on Linux
& ssh -i $KeyPath "ubuntu@${Server}" "sudo mkdir -p ${FinalPath}/templates ${FinalPath}/static; if ls ~/${TempPath}/*.py 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.py ${FinalPath}/; fi; if ls ~/${TempPath}/*.txt 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.txt ${FinalPath}/; fi; if [ -d ~/${TempPath}/templates ]; then sudo cp -r ~/${TempPath}/templates/* ${FinalPath}/templates/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/templates/templates ]; then sudo cp -r ~/${TempPath}/templates/templates/* ${FinalPath}/templates/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/static ]; then sudo cp -r ~/${TempPath}/static/* ${FinalPath}/static/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/static/static ]; then sudo cp -r ~/${TempPath}/static/static/* ${FinalPath}/static/ 2>/dev/null || true; fi; sudo chown -R ubuntu:ubuntu ${FinalPath}/templates ${FinalPath}/static; sudo find ${FinalPath}/templates -type d -exec chmod 755 {} \; ; sudo find ${FinalPath}/templates -type f -exec chmod 644 {} \; ; sudo find ${FinalPath}/static -type d -exec chmod 755 {} \; ; sudo find ${FinalPath}/static -type f -exec chmod 644 {} \; ; rm -rf ~/${TempPath}"
if($LASTEXITCODE -ne 0) {
    Write-Warning "Some files may not have been copied (exit code $LASTEXITCODE)"
}

if(-not $PreserveConfig) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && source venv/bin/activate && pip install -q -r requirements.txt"
    if($LASTEXITCODE -ne 0) {
        Write-Warning "Pip install had issues (exit code $LASTEXITCODE), continuing anyway..."
    }
    
    Write-Host "Restarting Pizza Hut TV service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart pizza-hut-tv"
    if($LASTEXITCODE -ne 0) {
        Write-Warning "Service restart failed (exit code $LASTEXITCODE)"
    } else {
        Write-Host "Service restarted successfully" -ForegroundColor Green
    }
    
    Start-Sleep -Seconds 3
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl status pizza-hut-tv --no-pager"
} else {
    Write-Host "Skipping service restart (PreserveConfig specified)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Syncing Server Data Back to Local ===" -ForegroundColor Cyan
Write-Host "Downloading latest database and config from server..." -ForegroundColor Yellow

# Download database
& scp -i $KeyPath "ubuntu@${Server}:${FinalPath}/database.db" "${PSScriptRoot}/database.db"
if ($LASTEXITCODE -eq 0) {
    $dbSize = (Get-Item "${PSScriptRoot}/database.db").Length
    Write-Host "  ✓ Database synced ($([math]::Round($dbSize/1KB, 2)) KB)" -ForegroundColor Green
}

# Download store config
& scp -i $KeyPath "ubuntu@${Server}:${FinalPath}/store_config__test9_at_gmail.com.json" "${PSScriptRoot}/store_config__test9_at_gmail.com.json"
if ($LASTEXITCODE -eq 0) {
    $configSize = (Get-Item "${PSScriptRoot}/store_config__test9_at_gmail.com.json").Length
    Write-Host "  ✓ Store config synced ($([math]::Round($configSize/1KB, 2)) KB)" -ForegroundColor Green
}

Write-Host ""
Write-Host "✅ Server deployment complete!" -ForegroundColor Green
Write-Host "✅ Local data synced with server!" -ForegroundColor Green