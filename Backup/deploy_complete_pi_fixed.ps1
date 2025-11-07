param(
    [string]$TargetHost = "everydayadvertise@raspberrypi.local",
    [string]$Dest = "/home/everydayadvertise",
    [switch]$Test
)

Write-Host "== Pizza Hut TV Complete Pi Client Deploy ==" -ForegroundColor Cyan

# Files to deploy
$files = @(
    'complete_pi_client.py',
    'seamless_video_player.py'
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
    Write-Host "  Copying $f..." -ForegroundColor Gray
    & scp $f "${TargetHost}:${Dest}/"
    if($LASTEXITCODE -ne 0){
        Write-Error "Failed to copy $f"
        exit 1
    }
}

Write-Host "`nMaking files executable..." -ForegroundColor Yellow
& ssh $TargetHost "chmod +x ${Dest}/complete_pi_client.py"

if($Test){
    Write-Host "`nRunning test mode..." -ForegroundColor Cyan
    & ssh $TargetHost "cd $Dest ; python3 complete_pi_client.py --server https://everydayadvertise.com --debug"
} else {
    Write-Host "`nUpdating systemd service..." -ForegroundColor Yellow
    
    # Create service file
    $serviceContent = "[Unit]
Description=Pizza Hut TV - Complete Pi Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=everydayadvertise
WorkingDirectory=${Dest}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/everydayadvertise/.Xauthority
ExecStart=/usr/bin/python3 ${Dest}/complete_pi_client.py --server https://everydayadvertise.com
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target"

    # Write to temp file
    $tempService = New-TemporaryFile
    $serviceContent | Out-File -FilePath $tempService.FullName -Encoding ASCII -NoNewline
    
    # Upload and install
    Write-Host "  Uploading service..." -ForegroundColor Gray
    & scp $tempService.FullName "${TargetHost}:/tmp/pizza-hut-tv.service"
    Remove-Item $tempService.FullName
    
    Write-Host "  Installing service..." -ForegroundColor Gray
    & ssh $TargetHost "sudo mv /tmp/pizza-hut-tv.service /etc/systemd/system/"
    & ssh $TargetHost "sudo systemctl daemon-reload"
    & ssh $TargetHost "sudo systemctl enable pizza-hut-tv"
    & ssh $TargetHost "sudo systemctl restart pizza-hut-tv"
    
    if($LASTEXITCODE -eq 0){
        Write-Host "`n[SUCCESS] Deployment complete!" -ForegroundColor Green
        Write-Host "`nService status:" -ForegroundColor Yellow
        & ssh $TargetHost "sudo systemctl status pizza-hut-tv --no-pager -n 10"
        
        Write-Host "`n[INFO] Pi ID will be displayed on screen" -ForegroundColor Cyan
        Write-Host "       Check logs: ssh $TargetHost 'sudo journalctl -u pizza-hut-tv -f'" -ForegroundColor Gray
    } else {
        Write-Error "Service installation failed"
        exit 1
    }
}
