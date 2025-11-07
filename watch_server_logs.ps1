#!/usr/bin/env pwsh
# Watch live server logs for VNC events
param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"
)

Write-Host "Watching live server logs (press Ctrl+C to stop)..." -ForegroundColor Cyan
& ssh -i $KeyPath "ubuntu@${Server}" "sudo journalctl -u pizza-hut-tv -f --no-pager"
