param(
    [string]$TargetHost = "everydayadvertise@raspberrypi.local",
    [string]$Dest = "/home/everydayadvertise",
    [switch]$Test
)

Write-Host "== Pizza Hut TV Complete Pi Client Deploy ==" -ForegroundColor Cyan

# Files to deploy
$files = @(
    'complete_pi_client.py',
    'seamless_video_player.py',
    'transition_engine.py',
    'pi_mobile_sync_addon.py'
)

Write-Host "Checking files..." -ForegroundColor Yellow
foreach($f in $files){
    if(-not (Test-Path $f)){
        Write-Error "File not found: $f"
        exit 1
    }
    Write-Host "  [OK] $f" -ForegroundColor Green
}

Write-Host "`nUploading files to ${TargetHost}:${Dest}" -ForegroundColor Yellow
foreach($f in $files){
    Write-Host "  -> $f"
    & scp $f "${TargetHost}:${Dest}/"
    if($LASTEXITCODE -ne 0){
        Write-Error "Failed to copy $f (scp exit code $LASTEXITCODE)"
        exit 1
    }
}

Write-Host "`nMaking files executable..." -ForegroundColor Yellow
& ssh $TargetHost "chmod +x ${Dest}/complete_pi_client.py"

if($Test){
    Write-Host "`nRunning test mode..." -ForegroundColor Cyan
    # Use bash -lc to safely chain commands on remote without PowerShell interpreting separators
    & ssh $TargetHost "bash -lc 'cd $Dest; timeout 5 python3 complete_pi_client.py --server https://everydayadvertise.com || true'"
} else {
    Write-Host "`nUpdating systemd service..." -ForegroundColor Yellow
    
    # Create service file content using single-quoted here-string, then substitute dest path
    $serviceContent = @'
[Unit]
Description=Pizza Hut TV - Complete Pi Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=everydayadvertise
WorkingDirectory=__DEST__
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/everydayadvertise/.Xauthority
ExecStart=/usr/bin/python3 __DEST__/complete_pi_client.py --server https://everydayadvertise.com
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
'@
    $serviceContent = $serviceContent -replace '__DEST__', $Dest

    # Write service file to temp location
    $tempService = [System.IO.Path]::GetTempFileName()
    $serviceContent | Out-File -FilePath $tempService -Encoding ASCII
    
    # Upload service file
    Write-Host "  Uploading service file" -ForegroundColor Gray
    & scp $tempService "${TargetHost}:/tmp/pizza-hut-tv.service"
    Remove-Item $tempService
    
    # Install service
    Write-Host "  Installing service" -ForegroundColor Gray
    & ssh $TargetHost "sudo mv /tmp/pizza-hut-tv.service /etc/systemd/system/pizza-hut-tv.service"
    & ssh $TargetHost "sudo systemctl daemon-reload"
    & ssh $TargetHost "sudo systemctl enable pizza-hut-tv"
    & ssh $TargetHost "sudo systemctl restart pizza-hut-tv"
    
    if($LASTEXITCODE -eq 0){
    Write-Host "`n[SUCCESS] Deployment complete!" -ForegroundColor Green
        Write-Host "`nChecking service status..." -ForegroundColor Yellow
        & ssh $TargetHost "sudo systemctl status pizza-hut-tv --no-pager"
        
    Write-Host "`nTo see Pi ID, check logs:" -ForegroundColor Cyan
        Write-Host "   ssh $TargetHost 'sudo journalctl -u pizza-hut-tv -n 50 | grep Pi ID'" -ForegroundColor Gray
    } else {
        Write-Error "Service installation failed"
        exit 1
    }
}

Write-Host "`nDeployment complete!" -ForegroundColor Green
