param(
    [string]$TargetHost = "everydayadvertise@raspberrypi.local",
    [string]$Dest = "/home/everydayadvertise/pizza-hut-tv",
    [string]$PlayUrl = "",
    [switch]$Test,
    [switch]$Probe,
    [switch]$SkipRequirements
)

Write-Host "== Pizza Hut TV Deploy (PowerShell) ==" -ForegroundColor Cyan

$files = @(
    'slice_kiosk.py',
    'pizza_hut_tv.py',
    'mpv_slice_player.py',
    'standalone_player.py',
    'requirements.txt',
    'playlist_probe.py'
) | Where-Object { Test-Path $_ }

if($files.Count -eq 0){
    Write-Error "No expected files found in current directory. Run from project root."; exit 1
}

Write-Host "Uploading files to ${TargetHost}:${Dest}" -ForegroundColor Yellow
foreach($f in $files){
    Write-Host "  -> $f"
    & scp $f "${TargetHost}:${Dest}/"
    if($LASTEXITCODE -ne 0){
        Write-Error "Failed to copy $f (scp exit code $LASTEXITCODE)"
        exit 1
    }
}

if(-not $SkipRequirements){
    Write-Host "(Re)installing Python requirements on Pi (if changed)" -ForegroundColor Yellow
    & ssh $TargetHost "python3 -m pip install --user -r $Dest/requirements.txt"
    if($LASTEXITCODE -ne 0){
        Write-Warning "Requirements install failed (exit code $LASTEXITCODE, continuing)"
    }
}

if($Test){
    $diag = if($PlayUrl){
        "python3 slice_kiosk.py --play-url '" + $PlayUrl + "' --print-only"
    } else {
        "python3 slice_kiosk.py --store 1000 --screen 2 --code 4682 --print-only"
    }
    Write-Host "Running remote diagnostic: $diag" -ForegroundColor Cyan
    & ssh $TargetHost "cd $Dest; $diag"
    if($LASTEXITCODE -ne 0){
        Write-Warning "Diagnostic command failed (exit code $LASTEXITCODE)"
    }
}

if($Probe){
    $probeCmd = if($PlayUrl){
        "python3 playlist_probe.py --play-url '" + $PlayUrl + "'"
    } else {
        "python3 playlist_probe.py --store 1000 --screen 2 --code 4682"
    }
    Write-Host "Running playlist probe: $probeCmd" -ForegroundColor Cyan
    & ssh $TargetHost "cd $Dest; $probeCmd"
    if($LASTEXITCODE -ne 0){
        Write-Warning "Playlist probe failed (exit code $LASTEXITCODE)"
    }
}

Write-Host "Deploy complete." -ForegroundColor Green
