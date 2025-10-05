# Test Video Playback - Quick Start Script
# This script starts the Flask server and opens the test page

Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host "🎬 VIDEO PLAYBACK TEST - QUICK START" -ForegroundColor Cyan
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host ""

# Check if server is already running
$pythonProcess = Get-Process -Name python -ErrorAction SilentlyContinue
if ($pythonProcess) {
    Write-Host "⚠️  Flask server appears to be running already" -ForegroundColor Yellow
    Write-Host "   Process ID: $($pythonProcess.Id)"
    Write-Host ""
    $response = Read-Host "Do you want to restart it? (y/n)"
    if ($response -eq 'y') {
        Write-Host "Stopping existing server..." -ForegroundColor Yellow
        Stop-Process -Name python -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

Write-Host "🚀 Starting Flask server..." -ForegroundColor Green
Write-Host ""

# Start Flask in background
$job = Start-Job -ScriptBlock {
    Set-Location "c:\Users\toeng\Pizza Hut TV"
    python app.py
}

Write-Host "⏳ Waiting for server to start (5 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Test if server is responding
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/healthz" -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
    Write-Host "✅ Server is running!" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Server might not be ready yet, but continuing..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host "📊 OPENING TEST PAGES" -ForegroundColor Cyan
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host ""

# Open video test page
Write-Host "🔗 Opening video test page..." -ForegroundColor Green
Start-Process "http://localhost:5000/video-test"

Start-Sleep -Seconds 2

# Open main homepage
Write-Host "🔗 Opening homepage..." -ForegroundColor Green
Start-Process "http://localhost:5000/"

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host "✅ DONE!" -ForegroundColor Green
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host ""
Write-Host "📋 What to check:" -ForegroundColor Cyan
Write-Host "   1. Video Test Page - Each video should show ✅ status"
Write-Host "   2. Homepage - All videos should autoplay"
Write-Host "   3. Browser Console (F12) - Look for video log messages"
Write-Host ""
Write-Host "🛑 To stop the server:" -ForegroundColor Yellow
Write-Host "   Press Ctrl+C or run: Get-Process python | Stop-Process"
Write-Host ""
Write-Host "Job ID: $($job.Id)" -ForegroundColor Gray
Write-Host ""

# Keep script running
Write-Host "Press Ctrl+C to stop the server and exit..." -ForegroundColor Yellow
try {
    Wait-Job -Job $job
} catch {
    # User pressed Ctrl+C
    Write-Host "`n🛑 Stopping server..." -ForegroundColor Yellow
    Stop-Job -Job $job
    Remove-Job -Job $job
    Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
}
