param(
    [string]$ApiKey = "cd8f971d",
    [string]$ApiSecret,
    [string]$FromNumber = "+13165308999",
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$FinalPath = "/var/www/everydayadvertise_tv"
)

if (-not $ApiSecret) {
    Write-Host "ERROR: Please provide the API Secret" -ForegroundColor Red
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\fix_vonage_credentials.ps1 -ApiSecret 'your_secret_here'" -ForegroundColor White
    Write-Host ""
    Write-Host "Get your API Secret from:" -ForegroundColor Cyan
    Write-Host "  https://dashboard.nexmo.com/settings" -ForegroundColor White
    exit 1
}

Write-Host "Updating Vonage Credentials" -ForegroundColor Cyan
Write-Host ""

Write-Host "Removing old credentials..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && cp .env .env.backup-fix && grep -v 'VONAGE' .env > .env.tmp && mv .env.tmp .env"

Write-Host "Adding new credentials..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "echo '' >> ${FinalPath}/.env ; echo '# Vonage SMS Configuration' >> ${FinalPath}/.env ; echo 'VONAGE_API_KEY=${ApiKey}' >> ${FinalPath}/.env ; echo 'VONAGE_API_SECRET=${ApiSecret}' >> ${FinalPath}/.env ; echo 'VONAGE_FROM_NUMBER=${FromNumber}' >> ${FinalPath}/.env"

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Credentials updated" -ForegroundColor Green
    Write-Host ""
    Write-Host "Restarting service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart everydayadvertise_tv"
    Start-Sleep -Seconds 3
    
    Write-Host "DONE!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Test phone verification at:" -ForegroundColor Cyan
    Write-Host "https://everydayadvertise.com/account" -ForegroundColor White
} else {
    Write-Host "FAILED to update credentials" -ForegroundColor Red
}
