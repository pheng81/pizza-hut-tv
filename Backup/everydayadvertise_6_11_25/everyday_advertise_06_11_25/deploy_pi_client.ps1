param(
    [string]$PiUser = "everydayadvertise",
    [string]$PiHost = "raspberrypi",  # Using hostname instead of IP
    # IMPORTANT: Updated to pizzahut-client directory
    [string]$RemoteDir = "/home/everydayadvertise/pizzahut-client",
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
$files = @('complete_pi_client.py','pi_mobile_sync_addon.py','seamless_video_player.py','pi_vnc_tunnel.py','transition_engine.py')
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

# Ensure capture dependencies are installed (mss, pillow)
Write-Host "Installing/ensuring capture dependencies (mss, pillow)..." -ForegroundColor Yellow
# Try pip first (user scope); if blocked (PEP 668), apt installs will cover
& ssh @sshArgs $sshTarget "pip3 install --user -q mss pillow || true"
# Ensure system packages available for capture backends
& ssh @sshArgs $sshTarget "sudo apt-get update -y && sudo apt-get install -y python3-pil || true"
# Try installing mss despite PEP 668 restrictions (user site, allow break-system-packages)
& ssh @sshArgs $sshTarget "pip3 install --user --break-system-packages -q mss || true"

# Restart the service (try multiple common names)
Write-Host "Restarting Pi client..." -ForegroundColor Yellow

# First, try to kill any running instances
Write-Host "  -> Stopping existing client processes..." -ForegroundColor Gray
& ssh @sshArgs $sshTarget "pkill -f complete_pi_client || true" 2>$null

# Wait a moment for processes to stop
Start-Sleep -Seconds 2

# Check if client auto-restarts (from bashrc or systemd)
Write-Host "  -> Checking if client auto-restarts..." -ForegroundColor Gray
Start-Sleep -Seconds 3
& ssh @sshArgs $sshTarget "pgrep -f complete_pi_client" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Client auto-restarted successfully!" -ForegroundColor Green
    $restartOk = $true
} else {
    # Try systemd service restart
    Write-Host "  -> No auto-restart detected, trying systemd services..." -ForegroundColor Gray
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
}

if (-not $restartOk) {
    Write-Host "Client restart method not detected - client should auto-start from bashrc" -ForegroundColor Yellow
    Write-Host "Check if client is running below..." -ForegroundColor Yellow
} else {
    Write-Host "Client restarted successfully!" -ForegroundColor Green
}

# Check if client is running
Write-Host ""
Write-Host "Client Status:" -ForegroundColor Cyan
& ssh @sshArgs $sshTarget "ps aux | grep complete_pi_client | grep -v grep || echo 'Client not running'"

# Show recent logs
Write-Host ""
Write-Host "Recent client logs (last 50 lines):" -ForegroundColor Cyan
& ssh @sshArgs $sshTarget "test -f ~/pi_client_debug.log && tail -n 50 ~/pi_client_debug.log || echo 'No pi_client_debug.log found'"

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "The Pi client has been updated with the video looping fix." -ForegroundColor White
Write-Host "Videos should now loop properly until the timer advances!" -ForegroundColor Cyan
