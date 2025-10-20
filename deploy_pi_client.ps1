param(
    [string]$PiUser = "everydayadvertise",
    [string]$PiHost = "raspberrypi",
    # IMPORTANT: Match systemd WorkingDirectory (most units use /home/everydayadvertise/pizza-hut-tv)
    [string]$RemoteDir = "/home/everydayadvertise/pizza-hut-tv",
    [string]$KeyFile = "",
    [string]$ServiceName = "complete_pi_client"
)

Write-Host "Pizza Hut TV - Pi Client Deployment" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

 # Build SSH/SCP base with optional key
$sshArgs = @()
$scpArgs = @()
if ($KeyFile -and (Test-Path $KeyFile)) {
    $sshArgs += @('-i', $KeyFile)
    $scpArgs += @('-i', $KeyFile)
}
$sshArgs += @('-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null')
$scpArgs += @('-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null')

# Test Pi connection with fallbacks
Write-Host "Testing Pi connection..." -ForegroundColor Yellow
$hostCandidates = @()
if ($PiHost) { $hostCandidates += $PiHost }
if ($PiHost -and -not $PiHost.ToLower().EndsWith('.local')) { $hostCandidates += ("$PiHost.local") }
$hostCandidates += @('raspberrypi','raspberrypi.local')
$hostCandidates = $hostCandidates | Select-Object -Unique

$connected = $false
$sshTarget = ""
foreach($h in $hostCandidates) {
    $candidate = "$PiUser@$h"
    Write-Host " - Trying $candidate" -ForegroundColor Gray
    $null = & ssh @sshArgs $candidate "echo connected" 2>$null
    if ($LASTEXITCODE -eq 0) { $connected = $true; $sshTarget = $candidate; break }
}

if (-not $connected) {
    # Prompt for manual host/IP
    $manual = Read-Host "Cannot connect via defaults. Enter Pi Host/IP (or press Enter to cancel)"
    if ([string]::IsNullOrWhiteSpace($manual)) {
        Write-Host "Cannot connect to Pi. Please check network connection and SSH access" -ForegroundColor Yellow
        exit 1
    }
    $sshTarget = "$PiUser@$manual"
    Write-Host " - Trying $sshTarget" -ForegroundColor Gray
    $null = & ssh @sshArgs $sshTarget "echo connected" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Cannot connect to Pi at $sshTarget" -ForegroundColor Red
        Write-Host "Please verify the host/IP and try again" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "Pi connection successful!" -ForegroundColor Green

# Ensure remote directory exists
Write-Host "Ensuring remote directory exists: $RemoteDir" -ForegroundColor Yellow
& ssh @sshArgs $sshTarget "mkdir -p $RemoteDir"

# Upload required files
$files = @('complete_pi_client.py','pi_mobile_sync_addon.py','seamless_video_player.py')
foreach($f in $files){
    if(-not (Test-Path $f)){
        Write-Host "Skipping missing file: $f" -ForegroundColor DarkYellow
        continue
    }
    Write-Host "Uploading $f..." -ForegroundColor Yellow
    & scp @scpArgs $f "${sshTarget}:${RemoteDir}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to upload $f" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Files uploaded successfully!" -ForegroundColor Green

# Also upload directly into /home/<PiUser> because some user services ExecStart from there
Write-Host "Uploading files to /home/${PiUser} for user service ExecStart" -ForegroundColor Yellow
foreach($f in $files){
    if(-not (Test-Path $f)){ continue }
    & scp @scpArgs $f "${sshTarget}:/home/${PiUser}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Failed to upload $f to /home/${PiUser}" -ForegroundColor DarkYellow
    }
}
Write-Host "Service path files updated (best-effort)." -ForegroundColor Green

# Restart the service (try multiple common names)
Write-Host "Restarting Pi client service..." -ForegroundColor Yellow
$serviceCandidates = @($ServiceName, 'complete-pi-client', 'pizza-hut-tv', 'pizza-hut-tv-complete') | Select-Object -Unique
$restartOk = $false
$usedUserService = $false
foreach($svc in $serviceCandidates){
    Write-Host "  -> Trying: $svc" -ForegroundColor Gray
    # Try system service first
    & ssh @sshArgs $sshTarget "sudo systemctl restart $svc" 2>$null
    if ($LASTEXITCODE -eq 0) { $ServiceName = $svc; $restartOk = $true; $usedUserService = $false; break }
    # Then try user service (common when using loginctl linger)
    & ssh @sshArgs $sshTarget "systemctl --user restart $svc" 2>$null
    if ($LASTEXITCODE -eq 0) { $ServiceName = $svc; $restartOk = $true; $usedUserService = $true; break }
}

if (-not $restartOk) {
    Write-Host "Service restart failed - you may need to restart manually" -ForegroundColor Yellow
} else {
    Write-Host "Service restarted successfully: $ServiceName" -ForegroundColor Green
}

# Check service status
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
if ($usedUserService) {
    & ssh @sshArgs $sshTarget "systemctl --user status $ServiceName --no-pager -l | head -20"
} else {
    & ssh @sshArgs $sshTarget "sudo systemctl status $ServiceName --no-pager -l | head -20"
}

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "The Pi can now handle restart and close screen commands." -ForegroundColor White
