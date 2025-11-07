# 🍕 Update custom_player.py on Raspberry Pi
# This script updates the custom player to support 4+ screen slices

Write-Host "🍕 Pizza Hut TV - Update Custom Player on Pi" -ForegroundColor Cyan
Write-Host "=============================================="
Write-Host ""

# Configuration - you can override these
$PI_USER = if ($env:PI_USER) { $env:PI_USER } else { "pi" }
$PI_HOST = if ($env:PI_HOST) { $env:PI_HOST } else { "raspberrypi.local" }

Write-Host "📋 Update Plan:" -ForegroundColor Blue
Write-Host "   • Copy updated custom_player.py to Pi: $PI_USER@$PI_HOST"
Write-Host "   • Restart any running custom player processes"
Write-Host ""

# Check if custom_player.py exists locally
if (-not (Test-Path "custom_player.py")) {
    Write-Host "❌ custom_player.py not found in current directory" -ForegroundColor Red
    Write-Host "Please run this script from the Pizza Hut TV directory"
    exit 1
}

# Test connection
Write-Host "🌐 Testing Pi connection..." -ForegroundColor Yellow
$testConnection = ssh -o ConnectTimeout=3 "$PI_USER@$PI_HOST" "echo Connected" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Pi is reachable at $PI_USER@$PI_HOST" -ForegroundColor Green
} else {
    Write-Host "❌ Cannot reach Pi at $PI_USER@$PI_HOST" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Try one of these:" -ForegroundColor Yellow
    Write-Host "   1. Use IP address:"
    Write-Host "      `$env:PI_HOST='192.168.1.115'"
    Write-Host "      .\update_pi_custom_player.ps1"
    Write-Host ""
    Write-Host "   2. Use different username:"
    Write-Host "      `$env:PI_USER='everydayadvertise'"
    Write-Host "      .\update_pi_custom_player.ps1"
    exit 1
}

# Copy custom_player.py to Pi
Write-Host "📤 Uploading custom_player.py to Pi..." -ForegroundColor Yellow
scp custom_player.py "${PI_USER}@${PI_HOST}:/home/${PI_USER}/"
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ custom_player.py uploaded successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to copy custom_player.py" -ForegroundColor Red
    exit 1
}

# Check if custom player is running and offer to restart
Write-Host "🔍 Checking for running custom player processes..." -ForegroundColor Yellow
$runningProcs = ssh "$PI_USER@$PI_HOST" "pgrep -f custom_player.py" 2>$null

if ($runningProcs) {
    Write-Host "ℹ️  Found running custom player processes: $runningProcs" -ForegroundColor Blue
    Write-Host ""
    $response = Read-Host "Do you want to restart them? (y/N)"
    if ($response -match '^[Yy]$') {
        Write-Host "🔄 Restarting custom player..." -ForegroundColor Yellow
        ssh "$PI_USER@$PI_HOST" "pkill -f custom_player.py" 2>$null
        Start-Sleep -Seconds 2
        Write-Host "✅ Custom player processes stopped" -ForegroundColor Green
        Write-Host "ℹ️  You can now launch the custom player from the Pi desktop" -ForegroundColor Blue
    } else {
        Write-Host "⚠️  Skipping restart - changes will take effect on next launch" -ForegroundColor Yellow
    }
} else {
    Write-Host "ℹ️  No running custom player processes found" -ForegroundColor Blue
}

Write-Host ""
Write-Host "✅ Update complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 What was fixed:" -ForegroundColor Blue
Write-Host "   • Screen slice parsing now correctly handles screen4, screen5, etc."
Write-Host "   • Previously only worked for screen1, screen2, screen3"
Write-Host "   • Now supports unlimited screens"
Write-Host ""
Write-Host "🚀 Next steps:" -ForegroundColor Blue
Write-Host "   1. If you restarted the player, launch it again from the Pi desktop"
Write-Host "   2. If you didn't restart, close and reopen the custom player"
Write-Host "   3. Verify screen4 and screen5 now show different slices"
Write-Host ""
