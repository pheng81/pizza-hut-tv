param(
    [string]$PiUser = "everydayadvertise",
    [string]$PiHost = "everydayadvertise",
    [string]$RemoteStageDir = "",
    [string]$KeyFile = "",
    [string]$ServerUrl = "https://api.everydayadvertise.com",
    [switch]$StartNow,
    [switch]$FinalizeImage
)

Write-Host "EverydayAdvertise TV - Golden Image Prep" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

if ([string]::IsNullOrWhiteSpace($RemoteStageDir)) {
    $RemoteStageDir = "/home/${PiUser}/everydayadvertise_tv-image"
}

$sshArgs = @('-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null')
$scpArgs = @('-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null')

if ($KeyFile -and (Test-Path $KeyFile)) {
    $sshArgs = @('-i', $KeyFile) + $sshArgs
    $scpArgs = @('-i', $KeyFile) + $scpArgs
}

$sshTarget = "${PiUser}@${PiHost}"

Write-Host "Testing SSH connection to $sshTarget ..." -ForegroundColor Yellow
& ssh @sshArgs $sshTarget "echo connected"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cannot connect to $sshTarget" -ForegroundColor Red
    exit 1
}

Write-Host "Creating remote staging directory..." -ForegroundColor Yellow
& ssh @sshArgs $sshTarget "mkdir -p ${RemoteStageDir}/pi_deployment"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create remote stage directory" -ForegroundColor Red
    exit 1
}

$files = @(
    @{ Source = 'complete_pi_client.py'; Target = 'complete_pi_client.py' },
    @{ Source = 'pi_mobile_sync_addon.py'; Target = 'pi_mobile_sync_addon.py' },
    @{ Source = 'pi_vnc_tunnel.py'; Target = 'pi_vnc_tunnel.py' },
    @{ Source = 'transition_engine.py'; Target = 'transition_engine.py' },
    @{ Source = 'pi_deployment/seamless_video_player.py'; Target = 'pi_deployment/seamless_video_player.py' },
    @{ Source = 'pi_deployment/prepare_golden_image.sh'; Target = 'pi_deployment/prepare_golden_image.sh' }
)

foreach ($file in $files) {
    if (-not (Test-Path $file.Source)) {
        Write-Host "Missing file: $($file.Source)" -ForegroundColor Red
        exit 1
    }

    Write-Host "Uploading $($file.Source) ..." -ForegroundColor Yellow
    & scp @scpArgs $file.Source "${sshTarget}:${RemoteStageDir}/$($file.Target)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to upload $($file.Source)" -ForegroundColor Red
        exit 1
    }
}

$remoteCommand = @(
    "chmod +x ${RemoteStageDir}/pi_deployment/prepare_golden_image.sh",
    "bash ${RemoteStageDir}/pi_deployment/prepare_golden_image.sh --server ${ServerUrl} --user ${PiUser}"
)

if ($StartNow) {
    $remoteCommand[-1] += " --start-now"
}

if ($FinalizeImage) {
    $remoteCommand[-1] = "bash ${RemoteStageDir}/pi_deployment/prepare_golden_image.sh --finalize-image --service-name everydayadvertise_tv"
}

Write-Host "Running remote golden image preparation..." -ForegroundColor Yellow
& ssh @sshArgs $sshTarget ($remoteCommand -join ' && ')
if ($LASTEXITCODE -ne 0) {
    Write-Host "Remote preparation failed" -ForegroundColor Red
    exit 1
}

Write-Host "" 
Write-Host "Golden image task completed." -ForegroundColor Green
if ($FinalizeImage) {
    Write-Host "The SD card is ready to clone." -ForegroundColor Green
} elseif ($StartNow) {
    Write-Host "The Pi is running the claim-screen client for testing." -ForegroundColor Green
    Write-Host "Run this script again with -FinalizeImage before cloning the SD card." -ForegroundColor Yellow
} else {
    Write-Host "The Pi is prepared but not started, which is the safest state before cloning." -ForegroundColor Green
}