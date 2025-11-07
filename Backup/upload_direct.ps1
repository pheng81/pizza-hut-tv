# PowerShell Direct Upload Script
# Upload files to server using pure PowerShell - no external tools!

$SERVER = "https://everydayadvertise.com"
$SECRET = "pizza_hut_emergency_upload_2025"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   UPLOADING FILES TO SERVER" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Files to upload
$files = @(
    @{
        Local = "c:\Users\toeng\Pizza Hut TV\app.py"
        Destination = "app.py"
        Name = "app.py"
    },
    @{
        Local = "c:\Users\toeng\Pizza Hut TV\templates\dashboard.html"
        Destination = "templates/dashboard.html"
        Name = "dashboard.html"
    }
)

$success = 0

foreach ($file in $files) {
    Write-Host "Uploading $($file.Name)..." -ForegroundColor Yellow
    
    try {
        # Read file content
        $content = Get-Content -Path $file.Local -Raw -Encoding UTF8
        Write-Host "   Size: $($content.Length) bytes" -ForegroundColor Gray
        
        # Convert to base64
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
        $base64 = [Convert]::ToBase64String($bytes)
        
        # Prepare JSON body
        $body = @{
            filename = $file.Name
            content = $base64
            destination = $file.Destination
        } | ConvertTo-Json
        
        # Upload
        $headers = @{
            "X-Upload-Secret" = $SECRET
            "Content-Type" = "application/json"
        }
        
        $response = Invoke-RestMethod -Uri "$SERVER/api/emergency-upload" `
                                     -Method Post `
                                     -Headers $headers `
                                     -Body $body `
                                     -TimeoutSec 30
        
        if ($response.success) {
            Write-Host "   SUCCESS!" -ForegroundColor Green
            $success++
        } else {
            Write-Host "   FAILED: $($response.error)" -ForegroundColor Red
        }
        
    } catch {
        Write-Host "   ERROR: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   Results: $success/$($files.Count) uploaded" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

if ($success -eq $files.Count) {
    Write-Host "All files uploaded successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Restart server
    Write-Host "Restarting server..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "$SERVER/api/emergency-restart" `
                                     -Method Post `
                                     -Headers @{"X-Upload-Secret" = $SECRET}
        Write-Host "Server restart initiated!" -ForegroundColor Green
    } catch {
        Write-Host "Restart failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "   DEPLOYMENT COMPLETE!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Wait 10 seconds, then test:" -ForegroundColor Yellow
    Write-Host "1. Open: https://everydayadvertise.com/dashboard" -ForegroundColor White
    Write-Host "2. Press: Ctrl+Shift+R" -ForegroundColor White
    Write-Host "3. Open: Remote Pi Manager" -ForegroundColor White
    Write-Host "4. Connect to Pi" -ForegroundColor White
    Write-Host "5. See: Screen Preview section!" -ForegroundColor White
    Write-Host "6. Click: Start button" -ForegroundColor White
    Write-Host "7. Screenshots appear every 2 seconds!" -ForegroundColor White
    
} else {
    Write-Host "Some files failed to upload" -ForegroundColor Red
    Write-Host "The server may not have the upload endpoint yet." -ForegroundColor Yellow
}
