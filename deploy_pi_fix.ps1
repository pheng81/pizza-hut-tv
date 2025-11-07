# Deploy video looping fix to Raspberry Pi
# This fixes the issue where videos play once and stop (black screen)

$PI_HOST = "192.168.1.113"
$PI_USER = "everydayadvertise"
$PI_PASSWORD = "pizza"
$LOCAL_FILE = "seamless_video_player.py"
$REMOTE_PATH = "~/pizzahut-client/seamless_video_player.py"

Write-Host "🚀 Deploying video looping fix to Pi..." -ForegroundColor Cyan
Write-Host ""

# Check if file exists
if (-not (Test-Path $LOCAL_FILE)) {
    Write-Host "❌ Error: $LOCAL_FILE not found" -ForegroundColor Red
    exit 1
}

Write-Host "📁 File to deploy: $LOCAL_FILE" -ForegroundColor Green
Write-Host "🎯 Target: $PI_USER@$PI_HOST" -ForegroundColor Green
Write-Host ""

# Try using plink/pscp if available (PuTTY tools)
$pscp = Get-Command pscp -ErrorAction SilentlyContinue

if ($pscp) {
    Write-Host "Using PSCP (PuTTY)..." -ForegroundColor Yellow
    echo y | pscp -pw $PI_PASSWORD $LOCAL_FILE "${PI_USER}@${PI_HOST}:${REMOTE_PATH}"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ File deployed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "🔄 Restarting Pi client..." -ForegroundColor Yellow
        
        # Restart the client
        echo $PI_PASSWORD | plink -pw $PI_PASSWORD "${PI_USER}@${PI_HOST}" "pkill -f complete_pi_client"
        
        Start-Sleep -Seconds 3
        Write-Host "✅ Pi client restarted (will auto-start from bashrc)" -ForegroundColor Green
        Write-Host ""
        Write-Host "🎬 Videos should now loop properly!" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Deployment failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "⚠️  PSCP not found. Please install PuTTY or use one of these methods:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Method 1: Manual SCP (if you have SSH client)" -ForegroundColor Cyan
    Write-Host "  scp seamless_video_player.py ${PI_USER}@${PI_HOST}:~/pizzahut-client/" -ForegroundColor White
    Write-Host ""
    Write-Host "Method 2: Using WinSCP GUI" -ForegroundColor Cyan
    Write-Host "  1. Open WinSCP" -ForegroundColor White
    Write-Host "  2. Connect to $PI_HOST with user: $PI_USER password: $PI_PASSWORD" -ForegroundColor White
    Write-Host "  3. Upload seamless_video_player.py to /home/everydayadvertise/pizzahut-client/" -ForegroundColor White
    Write-Host "  4. SSH to Pi and run: pkill -f complete_pi_client" -ForegroundColor White
    Write-Host ""
    Write-Host "Method 3: Install PuTTY tools" -ForegroundColor Cyan
    Write-Host "  Download from: https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html" -ForegroundColor White
    Write-Host "  Install and run this script again" -ForegroundColor White
}
