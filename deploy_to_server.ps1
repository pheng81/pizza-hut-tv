param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$TempPath = "everydayadvertise_tv-deploy",
    [string]$FinalPath = "/var/www/everydayadvertise_tv",
    [string]$LegacyPath = "/var/www/pizza-hut-tv",
    [string]$ServiceName = "everydayadvertise_tv",
    [string]$LegacyServiceName = "pizza-hut-tv",
    [switch]$PreserveConfig
)

Write-Host "== EverydayAdvertise TV Server Deploy ==" -ForegroundColor Cyan
Write-Host ""

$serviceUnitFile = 'everydayadvertise_tv.service'
$LegacySessionSecret = 'pizza-hut-tv-oauth-session-key-2025-production'

# Check if local database exists and is recent
$localDbAge = $null
if (Test-Path "database.db") {
    $localDbAge = (Get-Date) - (Get-Item "database.db").LastWriteTime
    Write-Host "Local database found (last updated: $([math]::Round($localDbAge.TotalHours, 1)) hours ago)" -ForegroundColor Cyan
    
    if ($localDbAge.TotalDays -gt 1) {
        Write-Host "  âš  Local database is over 1 day old" -ForegroundColor Yellow
        $syncFirst = Read-Host "Sync from server first? (yes/no)"
        if ($syncFirst -eq "yes") {
            Write-Host "Running sync..." -ForegroundColor Yellow
            & "$PSScriptRoot\sync_from_server.ps1" -AutoSync
            Write-Host ""
        }
    }
} else {
    Write-Host "âš  No local database found!" -ForegroundColor Yellow
    Write-Host "  Run .\sync_from_server.ps1 to download server data for local testing" -ForegroundColor Cyan
    Write-Host ""
}

# Create temp directory on server
Write-Host "Creating temp deploy directory..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "rm -rf ~/${TempPath} && mkdir -p ~/${TempPath}/templates/webplayer ~/${TempPath}/templates/webplayer_1 ~/${TempPath}/static ~/${TempPath}/pi_deployment && sudo mkdir -p ${FinalPath}/templates ${FinalPath}/static ${FinalPath}/pi_deployment"

Write-Host "Preparing production directory migration..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "sudo mkdir -p ${FinalPath}/templates ${FinalPath}/static ${FinalPath}/pi_deployment; if [ -d ${LegacyPath} ] && { [ ! -f ${FinalPath}/database.db ] || [ ! -x ${FinalPath}/venv/bin/python ]; }; then sudo cp -a ${LegacyPath}/. ${FinalPath}/; fi"

# Core server files to deploy (NEVER include database files!)
$coreFiles = @(
    'app.py',
    'requirements.txt'
)

# Pi bootstrap files served by /api/pi-bootstrap/file/*
$bootstrapFiles = @(
    @{ Source = 'complete_pi_client.py'; Target = 'complete_pi_client.py' },
    @{ Source = 'pi_mobile_sync_addon.py'; Target = 'pi_mobile_sync_addon.py' },
    @{ Source = 'pi_vnc_tunnel.py'; Target = 'pi_vnc_tunnel.py' },
    @{ Source = 'transition_engine.py'; Target = 'transition_engine.py' },
    @{ Source = 'pi_deployment/seamless_video_player.py'; Target = 'pi_deployment/seamless_video_player.py' }
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

if (Test-Path $serviceUnitFile) {
    Write-Host "Uploading service unit..." -ForegroundColor Yellow
    & scp -i $KeyPath $serviceUnitFile "ubuntu@${Server}:~/${TempPath}/"
    if($LASTEXITCODE -ne 0) {
        Write-Error "Failed to copy $serviceUnitFile (scp exit code $LASTEXITCODE)"
        exit 1
    }
} else {
    Write-Warning "Service unit not found: $serviceUnitFile"
}

Write-Host "Uploading Pi bootstrap files..." -ForegroundColor Yellow
foreach($file in $bootstrapFiles) {
    if(Test-Path $file.Source) {
        Write-Host "  -> $($file.Source)"
        & scp -i $KeyPath $file.Source "ubuntu@${Server}:~/${TempPath}/$($file.Target)"
        if($LASTEXITCODE -ne 0) {
            Write-Error "Failed to copy $($file.Source) (scp exit code $LASTEXITCODE)"
            exit 1
        }
    } else {
        Write-Warning "File not found: $($file.Source)"
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
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Preserving server-side uploaded media under static/uploads..." -ForegroundColor Yellow
        & ssh -i $KeyPath "ubuntu@${Server}" "rm -rf ~/${TempPath}/static/uploads"
    }
}

Write-Host "Creating automatic backup before deployment..." -ForegroundColor Cyan
$timestamp = [int][double]::Parse((Get-Date -UFormat %s))
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && if [ -f database.db ]; then cp database.db database.db.backup-${timestamp}; echo 'Database backup: database.db.backup-${timestamp}'; fi; if [ -f store_config__test9_at_gmail.com.json ]; then cp store_config__test9_at_gmail.com.json store_config__test9_at_gmail.com.json.backup-${timestamp}; echo 'Config backup: store_config__test9_at_gmail.com.json.backup-${timestamp}'; fi"

Write-Host "Moving files to production directory..." -ForegroundColor Yellow
# Keep the remote copy command on one line to avoid CRLF and shell parsing issues.
$remoteCopyCmd = "set -e; sudo mkdir -p ${FinalPath}/templates ${FinalPath}/static ${FinalPath}/pi_deployment; if ls ~/${TempPath}/*.py 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.py ${FinalPath}/; fi; if ls ~/${TempPath}/*.txt 1>/dev/null 2>&1; then sudo cp ~/${TempPath}/*.txt ${FinalPath}/; fi; if [ -f ~/${TempPath}/${serviceUnitFile} ]; then sudo cp ~/${TempPath}/${serviceUnitFile} /etc/systemd/system/${ServiceName}.service; sudo chown root:root /etc/systemd/system/${ServiceName}.service; sudo chmod 644 /etc/systemd/system/${ServiceName}.service; fi; if [ -d ~/${TempPath}/pi_deployment ]; then sudo cp -r ~/${TempPath}/pi_deployment/* ${FinalPath}/pi_deployment/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/templates ]; then sudo cp -r ~/${TempPath}/templates/* ${FinalPath}/templates/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/templates/templates ]; then sudo cp -r ~/${TempPath}/templates/templates/* ${FinalPath}/templates/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/static ]; then sudo cp -r ~/${TempPath}/static/* ${FinalPath}/static/ 2>/dev/null || true; fi; if [ -d ~/${TempPath}/static/static ]; then sudo cp -r ~/${TempPath}/static/static/* ${FinalPath}/static/ 2>/dev/null || true; fi; sudo chown -R ubuntu:ubuntu ${FinalPath}; sudo chmod -R u=rwX,go=rX ${FinalPath}; rm -rf ~/${TempPath}"
& ssh -i $KeyPath "ubuntu@${Server}" $remoteCopyCmd
if($LASTEXITCODE -ne 0) {
    Write-Warning "Some files may not have been copied (exit code $LASTEXITCODE)"
}

if(-not $PreserveConfig) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && if [ ! -x venv/bin/python ]; then python3 -m venv venv; fi && venv/bin/python -m pip install -q -r requirements.txt"
    if($LASTEXITCODE -ne 0) {
        Write-Warning "Pip install had issues (exit code $LASTEXITCODE), continuing anyway..."
    }
    
    Write-Host "Updating systemd service registration..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl daemon-reload && sudo systemctl enable ${ServiceName}"

    Write-Host "Cleaning up zombie processes before restart..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl stop ${LegacyServiceName} 2>/dev/null || true; sudo pkill -f 'gunicorn.*/var/www/pizza-hut-tv' || true; sudo pkill -f 'gunicorn.*/var/www/everydayadvertise_tv' || true; sleep 1"
    
    Write-Host "Restarting EverydayAdvertise TV service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart ${ServiceName}"
    if($LASTEXITCODE -ne 0) {
        Write-Warning "Service restart failed (exit code $LASTEXITCODE)"
    } else {
        Write-Host "Service restarted successfully" -ForegroundColor Green
        & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl disable ${LegacyServiceName} 2>/dev/null || true"
    }
    
    Start-Sleep -Seconds 3
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl status ${ServiceName} --no-pager"
} else {
    Write-Host "Skipping service restart (PreserveConfig specified)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Configuring Vonage SMS ===" -ForegroundColor Cyan

$secretKeyCheck = & ssh -i $KeyPath "ubuntu@${Server}" "if [ -f ${FinalPath}/.env ] && grep -q '^SECRET_KEY=' ${FinalPath}/.env 2>/dev/null; then echo 1; else echo 0; fi"
if (($secretKeyCheck | Out-String).Trim() -eq "0") {
    Write-Host "Adding SECRET_KEY to .env..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "touch ${FinalPath}/.env && echo '' >> ${FinalPath}/.env && echo '# Session signing key' >> ${FinalPath}/.env && echo 'SECRET_KEY=${LegacySessionSecret}' >> ${FinalPath}/.env"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "SECRET_KEY added" -ForegroundColor Green
    } else {
        Write-Warning "Failed to add SECRET_KEY to .env (exit code $LASTEXITCODE)"
    }
} else {
    Write-Host "SECRET_KEY already configured" -ForegroundColor Green
}

# Check if Vonage is already configured
$vonageCheck = & ssh -i $KeyPath "ubuntu@${Server}" "if [ -f ${FinalPath}/.env ] && grep -q '^VONAGE_API_KEY=' ${FinalPath}/.env 2>/dev/null; then echo 1; else echo 0; fi"
if (($vonageCheck | Out-String).Trim() -eq "0") {
    Write-Host "Adding Vonage credentials to .env..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "echo '' >> ${FinalPath}/.env ; echo '# Vonage SMS Configuration' >> ${FinalPath}/.env ; echo 'VONAGE_API_KEY=cd8f971d' >> ${FinalPath}/.env ; echo 'VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m' >> ${FinalPath}/.env ; echo 'VONAGE_FROM_NUMBER=+13165308999' >> ${FinalPath}/.env"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Vonage credentials added" -ForegroundColor Green
        Write-Host "Restarting service to load credentials..." -ForegroundColor Yellow
        & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart ${ServiceName}"
        Start-Sleep -Seconds 2
    }
} else {
    Write-Host "Vonage credentials already configured" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Syncing Server Data Back to Local ===" -ForegroundColor Cyan
Write-Host "Downloading latest database and config from server..." -ForegroundColor Yellow

# Download database
& scp -i $KeyPath "ubuntu@${Server}:${FinalPath}/database.db" "${PSScriptRoot}/database.db"
if ($LASTEXITCODE -eq 0) {
    $dbSize = (Get-Item "${PSScriptRoot}/database.db").Length
    $dbSizeKB = [math]::Round($dbSize/1024, 2)
    Write-Host ('  âœ“ Database synced (' + $dbSizeKB + ' KB)') -ForegroundColor Green
}

# Download store config
& scp -i $KeyPath "ubuntu@${Server}:${FinalPath}/store_config__test9_at_gmail.com.json" "${PSScriptRoot}/store_config__test9_at_gmail.com.json"
if ($LASTEXITCODE -eq 0) {
    $configSize = (Get-Item "${PSScriptRoot}/store_config__test9_at_gmail.com.json").Length
    $configSizeKB = [math]::Round($configSize/1024, 2)
    Write-Host ('  âœ“ Store config synced (' + $configSizeKB + ' KB)') -ForegroundColor Green
}

Write-Host ""
Write-Host "âœ… Server deployment complete!" -ForegroundColor Green
Write-Host "âœ… Local data synced with server!" -ForegroundColor Green
