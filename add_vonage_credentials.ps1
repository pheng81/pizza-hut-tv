param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$FinalPath = "/var/www/everydayadvertise_tv"
)

Write-Host "Adding Vonage SMS Credentials to Server" -ForegroundColor Cyan
Write-Host ""

Write-Host "Adding credentials..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "echo '' >> ${FinalPath}/.env ; echo '# Vonage SMS Configuration' >> ${FinalPath}/.env ; echo 'VONAGE_API_KEY=cd8f971d' >> ${FinalPath}/.env ; echo 'VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m' >> ${FinalPath}/.env ; echo 'VONAGE_FROM_NUMBER=+13165308999' >> ${FinalPath}/.env"

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Credentials added" -ForegroundColor Green
    Write-Host ""
    Write-Host "Restarting service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart everydayadvertise_tv"
    Start-Sleep -Seconds 3
    
    Write-Host "DONE!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Phone verification is now active at:" -ForegroundColor Cyan
    Write-Host "https://everydayadvertise.com/account" -ForegroundColor White
} else {
    Write-Host "FAILED to add credentials" -ForegroundColor Red
}
