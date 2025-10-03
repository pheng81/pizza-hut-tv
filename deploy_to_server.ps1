param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$RemotePath = "pizza-hut-tv",
    [switch]$PreserveConfig
)

Write-Host "== Pizza Hut TV Server Deploy ==" -ForegroundColor Cyan

# Core server files to deploy (NEVER include database files!)
$coreFiles = @(
    'app.py',
    'requirements.txt'
)

# Template files
$templateFiles = @(
    'templates/home.html',
    'templates/dashboard.html',
    'templates/webplayer/browse.html',
    'templates/webplayer/index.html', 
    'templates/webplayer/store.html',
    'templates/webplayer/player.html'
)

Write-Host "Uploading core server files to ubuntu@${Server}:${RemotePath}" -ForegroundColor Yellow

foreach($file in $coreFiles) {
    if(Test-Path $file) {
        Write-Host "  -> $file"
        & scp -i $KeyPath $file "ubuntu@${Server}:${RemotePath}/"
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
        $remoteDir = Split-Path $file -Parent
        & ssh -i $KeyPath "ubuntu@${Server}" "mkdir -p ${RemotePath}/${remoteDir}"
        & scp -i $KeyPath $file "ubuntu@${Server}:${RemotePath}/${file}"
        if($LASTEXITCODE -ne 0) {
            Write-Error "Failed to copy $file (scp exit code $LASTEXITCODE)"
            exit 1
        }
    } else {
        Write-Warning "File not found: $file"
    }
}

if(-not $PreserveConfig) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "cd /var/www/${RemotePath} && source venv/bin/activate && pip install -q -r requirements.txt"
    if($LASTEXITCODE -ne 0) {
        Write-Warning "Pip install had issues (exit code $LASTEXITCODE), continuing anyway..."
    }
    
    Write-Host "Restarting Pizza Hut TV service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "cd ${RemotePath} && sudo systemctl restart pizza-hut-tv"
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

Write-Host "Server deployment complete!" -ForegroundColor Green