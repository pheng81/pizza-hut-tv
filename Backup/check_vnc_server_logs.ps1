#!/usr/bin/env pwsh
# Quick diagnostic to check VNC event routing on server
param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"
)

Write-Host "Checking server logs for VNC events..." -ForegroundColor Cyan
& ssh -i $KeyPath "ubuntu@${Server}" "sudo journalctl -u pizza-hut-tv -n 100 --no-pager | grep -E 'VNC|vnc_connect|raspberrypi-ce39' | tail -50"
