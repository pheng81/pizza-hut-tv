# Simple wrapper to deploy ONLY the Flask server/web templates without attempting any Pi client actions.
# Usage: powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File ./deploy_server_only.ps1

param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$TempPath = "pizza-hut-tv-deploy",
    [string]$FinalPath = "/var/www/pizza-hut-tv",
    [switch]$PreserveConfig
)

Write-Host "== Pizza Hut TV Server-Only Deploy ==" -ForegroundColor Cyan

# Delegate to the main server deploy script
& "$PSScriptRoot\deploy_to_server.ps1" -Server $Server -KeyPath $KeyPath -TempPath $TempPath -FinalPath $FinalPath -PreserveConfig:$PreserveConfig

if ($LASTEXITCODE -ne 0) {
    Write-Error "Server-only deploy failed (exit code $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host "Server-only deployment complete!" -ForegroundColor Green
