# Get Pi ID remotely
param(
    [string]$PiIP = "192.168.1.131",
    [string]$Username = "everydayadvertise"
)

Write-Host "Connecting to $Username@$PiIP..." -ForegroundColor Cyan
Write-Host ""

try {
    # Try to read from saved file
    $piId = ssh "$Username@$PiIP" "cat ~/.pizza_hut_tv_id"
    
    if ($piId -and $piId -ne "" -and $LASTEXITCODE -eq 0) {
        Write-Host "Pi ID: " -ForegroundColor Green -NoNewline
        Write-Host "$piId" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host "   Use this ID in Remote Pi Manager: " -NoNewline
        Write-Host "$piId" -ForegroundColor Yellow
        Write-Host "============================================================" -ForegroundColor Cyan
    } else {
        Write-Host "Pi ID file not found, generating from hostname..." -ForegroundColor Yellow
        Write-Host ""
        
        # Get hostname
        $hostname = ssh "$Username@$PiIP" "hostname"
        $hostname = $hostname.Trim()
        
        # Get MAC address (try eth0 first, then wlan0)
        $mac = ssh "$Username@$PiIP" "cat /sys/class/net/eth0/address"
        if ($LASTEXITCODE -ne 0) {
            $mac = ssh "$Username@$PiIP" "cat /sys/class/net/wlan0/address"
        }
        $macClean = $mac.Trim().Replace(":", "").Replace("`n", "").Replace("`r", "")
        $macSuffix = $macClean.Substring([Math]::Max(0, $macClean.Length - 4))
        
        $piId = "$hostname-$macSuffix"
        
        Write-Host "Generated Pi ID: " -ForegroundColor Green -NoNewline
        Write-Host "$piId" -ForegroundColor Yellow
        
        # Save it for future use
        ssh "$Username@$PiIP" "echo '$piId' > ~/.pizza_hut_tv_id"
        Write-Host "Saved Pi ID to ~/.pizza_hut_tv_id" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host "   Use this ID in Remote Pi Manager: " -NoNewline
        Write-Host "$piId" -ForegroundColor Yellow
        Write-Host "============================================================" -ForegroundColor Cyan
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual alternatives:" -ForegroundColor Yellow
    Write-Host "1. SSH: ssh $Username@$PiIP `"cat ~/.pizza_hut_tv_id`""
    Write-Host "2. Look at Pi screen (ID shown in corner)"
    Write-Host "3. Run: ssh $Username@$PiIP `"hostname`""
}
