# Deploy enhanced Pi client to Raspberry Pi
param(
    [Parameter(Mandatory=$true)]
    [string]$PiPassword
)

Write-Host "Deploying enhanced Pi client to Raspberry Pi..." -ForegroundColor Green

$PI_USER = "everydayadvertise"
$PI_HOST = "raspberrypi"
$SOURCE_FILE = "phtv_pi_client.py"

# Check if source file exists
if (-not (Test-Path $SOURCE_FILE)) {
    Write-Host "❌ Source file $SOURCE_FILE not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Transferring enhanced Pi client..." -ForegroundColor Yellow

# Use SCP to transfer the file
try {
    # First, try to copy the file
    $scpCommand = "scp"
    $scpArgs = @($SOURCE_FILE, "${PI_USER}@${PI_HOST}:/home/everydayadvertise/")
    
    Write-Host "Running: $scpCommand $($scpArgs -join ' ')" -ForegroundColor Cyan
    
    # Note: This will prompt for password
    & $scpCommand @scpArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Pi client updated successfully!" -ForegroundColor Green
        Write-Host "The EA TV icon on desktop will now use enhanced synchronization" -ForegroundColor Green
        
        # Try to restart any running EA TV process
        Write-Host "Attempting to restart EA TV process if running..." -ForegroundColor Yellow
        ssh "${PI_USER}@${PI_HOST}" "pkill -f phtv_pi_client.py || true"
        
        Write-Host "✅ Deployment complete! You can now click the EA TV icon to test synchronized playback." -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to transfer files to Raspberry Pi" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Error during deployment: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}