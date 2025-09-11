# Simple Android TV App Test Script
$adbPath = "C:\Users\toeng\AppData\Local\Android\Sdk\platform-tools\adb.exe"

Write-Host "=== Android TV App Test ==="
Write-Host "Date: $(Get-Date)"

# Test 1: API Endpoint
Write-Host "`n1. Testing API endpoint..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5002/api/playlist/1000" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ API Status: $($response.StatusCode)"
    
    $json = $response.Content | ConvertFrom-Json
    if ($json.items) {
        Write-Host "✅ Items: $($json.items.Count)"
        $firstItem = $json.items[0]
        Write-Host "✅ First item: $($firstItem.file)"
        if ($firstItem.sync_ref) {
            Write-Host "✅ Sync ref: count=$($firstItem.sync_ref.count)"
        }
    }
} catch {
    Write-Host "❌ API failed: $($_.Exception.Message)"
}

# Test 2: Start Android App
Write-Host "`n2. Starting Android app..."
try {
    & $adbPath -s emulator-5640 shell am start -n com.pizzahut.tv/.TvDisplayActivity
    Write-Host "✅ App start command sent"
    
    Start-Sleep 8
    
    # Check if app is running
    $ps = & $adbPath -s emulator-5640 shell "ps | grep pizzahut"
    if ($ps) {
        Write-Host "✅ App is running: $($ps -split '\s+' | Select -Last 1)"
    } else {
        Write-Host "❌ App not found in process list"
    }
} catch {
    Write-Host "❌ App start failed: $($_.Exception.Message)"
}

# Test 3: Check logs
Write-Host "`n3. Recent app logs:"
try {
    $logs = & $adbPath -s emulator-5640 logcat -d | Select-String "PHTV" | Select -Last 5
    if ($logs) {
        $logs | ForEach-Object { Write-Host "   $_" }
    } else {
        Write-Host "   No PHTV logs found"
    }
} catch {
    Write-Host "❌ Log check failed: $($_.Exception.Message)"
}

Write-Host "`n=== Test Complete ==="
