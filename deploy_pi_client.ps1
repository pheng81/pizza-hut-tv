param(
    [string]$PiUser = "everydayadvertise",
    [string]$PiHost = "raspberrypi",  # Using hostname instead of IP
    [string]$RemoteDir = "",
    [string]$KeyFile = "",
    [string]$ServiceName = "complete_pi_client"
)

Write-Host "Pizza Hut TV - Pi Client Deployment" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

if ([string]::IsNullOrWhiteSpace($RemoteDir)) {
    $RemoteDir = "/home/${PiUser}/pizzahut-client"
}
$remoteDirWasDefault = $true
if (-not [string]::IsNullOrWhiteSpace($PSBoundParameters['RemoteDir'])) {
    $remoteDirWasDefault = $false
}

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
$targetCandidates = @()
$explicitPiUser = $PSBoundParameters.ContainsKey('PiUser')
$explicitPiHost = $PSBoundParameters.ContainsKey('PiHost')

function Add-TargetCandidate {
    param(
        [string]$User,
        [string]$HostName
    )

    if ([string]::IsNullOrWhiteSpace($User) -or [string]::IsNullOrWhiteSpace($HostName)) {
        return
    }

    $script:targetCandidates += [PSCustomObject]@{
        User = $User.Trim()
        Host = $HostName.Trim()
    }
}

Add-TargetCandidate -User $PiUser -HostName $PiHost
if ($PiHost -and -not $PiHost.ToLower().EndsWith('.local')) {
    Add-TargetCandidate -User $PiUser -HostName "$PiHost.local"
}

if (-not ($explicitPiUser -or $explicitPiHost)) {
    Add-TargetCandidate -User 'everydayadvertise' -HostName 'everydayadvertise'
    Add-TargetCandidate -User 'everydayadvertise' -HostName 'everydayadvertise.local'
    Add-TargetCandidate -User 'everydayadvertise0002' -HostName 'everydayadvertise'
    Add-TargetCandidate -User 'everydayadvertise0002' -HostName 'everydayadvertise.local'
    Add-TargetCandidate -User $PiUser -HostName 'raspberrypi'
    Add-TargetCandidate -User $PiUser -HostName 'raspberrypi.local'
}

$targetCandidates = $targetCandidates | Group-Object User, Host | ForEach-Object { $_.Group[0] }

$connected = $false
$sshTarget = ""
foreach($target in $targetCandidates) {
    $candidate = "$($target.User)@$($target.Host)"
    Write-Host " - Trying $candidate" -ForegroundColor Gray
    $null = & ssh @sshArgs $candidate "echo connected" 2>$null
    if ($LASTEXITCODE -eq 0) { $connected = $true; $sshTarget = $candidate; break }
}

if ($connected) {
    $resolvedPiUser = ($sshTarget -split '@', 2)[0]
    $PiUser = $resolvedPiUser
    if ($remoteDirWasDefault) {
        $RemoteDir = "/home/${PiUser}/pizzahut-client"
    }
}

if (-not $connected) {
    # Prompt for manual host/IP
    $manual = Read-Host "Cannot connect via defaults. Enter Pi Host/IP or user@host (or press Enter to cancel)"
    if ([string]::IsNullOrWhiteSpace($manual)) {
        Write-Host "Cannot connect to Pi. Please check network connection and SSH access" -ForegroundColor Yellow
        exit 1
    }
    if ($manual.Contains('@')) {
        $sshTarget = $manual.Trim()
        $PiUser = ($sshTarget -split '@', 2)[0]
    } else {
        $sshTarget = "$PiUser@$manual"
    }
    if ($remoteDirWasDefault) {
        $RemoteDir = "/home/${PiUser}/pizzahut-client"
    }
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

$uploadDirs = New-Object System.Collections.Generic.List[string]

function Add-UploadDir {
    param([string]$DirPath)

    if ([string]::IsNullOrWhiteSpace($DirPath)) {
        return
    }

    $normalized = $DirPath.Trim().TrimEnd('/')
    if (-not $normalized) {
        return
    }

    if (-not $script:uploadDirs.Contains($normalized)) {
        $script:uploadDirs.Add($normalized)
    }
}

Add-UploadDir -DirPath $RemoteDir
Add-UploadDir -DirPath "/home/${PiUser}"

Write-Host "Inspecting active Pi client runtime paths..." -ForegroundColor Yellow
$runtimeProcessLines = @(& ssh @sshArgs $sshTarget "ps -eo args | grep complete_pi_client.py | grep -v grep" 2>$null)
foreach ($line in $runtimeProcessLines) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }

    $matches = [regex]::Matches($line, '/home/[^\s"'']+/complete_pi_client\.py|/home/[^\s"'']+/pizzahut-client/complete_pi_client\.py')
    foreach ($match in $matches) {
        $runtimeFile = $match.Value
        if ([string]::IsNullOrWhiteSpace($runtimeFile)) {
            continue
        }
        $runtimeDir = Split-Path -Path $runtimeFile -Parent
        if ($runtimeDir) {
            Add-UploadDir -DirPath ($runtimeDir -replace '\\', '/')
        }
    }
}

if ($uploadDirs.Count -gt 0) {
    Write-Host "Upload targets:" -ForegroundColor Yellow
    foreach ($dir in $uploadDirs) {
        Write-Host "  -> $dir" -ForegroundColor Gray
        & ssh @sshArgs $sshTarget "mkdir -p $dir" 2>$null
    }
}

$stageDir = "/home/${PiUser}"
$requiredUploadDirs = @($RemoteDir, "/home/${PiUser}") | Select-Object -Unique

# Upload required files
$files = @(
    @{ Source = 'complete_pi_client.py'; Target = 'complete_pi_client.py' },
    @{ Source = 'pi_mobile_sync_addon.py'; Target = 'pi_mobile_sync_addon.py' },
    @{ Source = 'pi_deployment/seamless_video_player.py'; Target = 'seamless_video_player.py' },
    @{ Source = 'pi_vnc_tunnel.py'; Target = 'pi_vnc_tunnel.py' },
    @{ Source = 'transition_engine.py'; Target = 'transition_engine.py' }
)
foreach($file in $files){
    $source = $file.Source
    $target = $file.Target
    if(-not (Test-Path $source)){
        Write-Host "Skipping missing file: $source" -ForegroundColor DarkYellow
        continue
    }
    foreach ($dir in $uploadDirs) {
        Write-Host "Uploading $source as $target -> $dir" -ForegroundColor Yellow
        & scp @scpArgs $source "${sshTarget}:${dir}/${target}"
        if ($LASTEXITCODE -ne 0) {
            if ($dir -ne $stageDir -and -not $dir.StartsWith($stageDir + '/')) {
                Write-Host "Direct upload failed for $dir, trying staged sudo copy..." -ForegroundColor DarkYellow
                & ssh @sshArgs $sshTarget "sudo mkdir -p $dir && sudo cp ${stageDir}/${target} ${dir}/${target}" 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "Staged sudo copy succeeded for $dir" -ForegroundColor Green
                    continue
                }
            }

            if ($requiredUploadDirs -notcontains $dir) {
                Write-Host "Skipping optional runtime path $dir after upload failure" -ForegroundColor DarkYellow
                continue
            }

            Write-Host "Failed to upload $source to $dir" -ForegroundColor Red
            exit 1
        }
    }
}
Write-Host "Files uploaded successfully!" -ForegroundColor Green
Write-Host "Runtime path files updated." -ForegroundColor Green

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
