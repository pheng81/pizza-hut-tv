# Stops any process listening on port 5002, then starts the Flask server via start_server.bat
param(
    [int]$Port = 5002,
    [switch]$UseUserBat
)

$ErrorActionPreference = 'SilentlyContinue'

function Stop-PortListeners {
    param([int]$P)
    try {
        $pids = netstat -ano | Select-String ":$P" | ForEach-Object {
            ($_ -split "\s+")[-1]
        } | Where-Object { $_ -match "^\d+$" } | Sort-Object -Unique
        if ($pids) {
            foreach ($pid in $pids) {
                try { Stop-Process -Id $pid -Force -ErrorAction Stop; Write-Host "Stopped PID $pid on port $P" } catch {}
            }
        }
    } catch {}
}

function Start-Server {
    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
    $root = Split-Path -Parent $root  # up to repo root
    Set-Location $root

    $bat = if ($UseUserBat) { Join-Path $root 'start_server_user.bat' } else { Join-Path $root 'start_server.bat' }
    if (-Not (Test-Path $bat)) { Write-Error "Cannot find $bat"; exit 1 }

    Write-Host "Starting server using $(Split-Path -Leaf $bat) ..."
    Start-Process -FilePath $bat -WorkingDirectory $root | Out-Null
}

Stop-PortListeners -P $Port
Start-Server

Write-Host "Done. Tail log with: Get-Content -Path (Join-Path (Get-Location) 'server.log') -Wait"