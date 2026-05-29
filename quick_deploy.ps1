param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"
)

Write-Host "Quick Deploy - app.py only" -ForegroundColor Cyan
Write-Host ""

Write-Host "Uploading app.py..." -ForegroundColor Yellow
& scp -i $KeyPath "app.py" "ubuntu@${Server}:/var/www/everydayadvertise_tv/app.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Restarting service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart everydayadvertise_tv"
    Start-Sleep -Seconds 3
    
    Write-Host ""
    Write-Host "Done! Messages API is now active." -ForegroundColor Green
    Write-Host "Test at: https://everydayadvertise.com/account" -ForegroundColor Cyan
} else {
    Write-Host "Upload failed" -ForegroundColor Red
}
