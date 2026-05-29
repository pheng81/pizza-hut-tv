param(
    [string]$ApiKey = "cd8f971d",
    [string]$ApiSecret,
    [string]$FromNumber = "+13165308999",
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$FinalPath = "/var/www/everydayadvertise_tv"
)

if (-not $ApiSecret) {
    Write-Host "Please provide the API Secret from:" -ForegroundColor Yellow
    Write-Host "https://dashboard.nexmo.com/settings" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Look for the field labeled 'API secret' (NOT signature secret)" -ForegroundColor Yellow
    Write-Host ""
    $ApiSecret = Read-Host "Enter API Secret"
}

Write-Host "Cleaning and resetting Vonage configuration..." -ForegroundColor Cyan
Write-Host ""

# Backup and clean
Write-Host "1. Backing up .env..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && cp .env .env.backup-clean-$(date +%s)"

Write-Host "2. Removing ALL Vonage entries..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "cd ${FinalPath} && grep -v 'VONAGE\|Vonage SMS' .env > .env.clean && mv .env.clean .env"

Write-Host "3. Adding clean Vonage configuration..." -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" @"
cd ${FinalPath} && cat >> .env << 'EOFVONAGE'

# Vonage SMS Configuration
VONAGE_API_KEY=${ApiKey}
VONAGE_API_SECRET=${ApiSecret}
VONAGE_FROM_NUMBER=${FromNumber}
EOFVONAGE
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS!" -ForegroundColor Green
    Write-Host ""
    Write-Host "4. Restarting service..." -ForegroundColor Yellow
    & ssh -i $KeyPath "ubuntu@${Server}" "sudo systemctl restart everydayadvertise_tv"
    Start-Sleep -Seconds 3
    
    Write-Host ""
    Write-Host "Configuration updated with:" -ForegroundColor Cyan
    Write-Host "  API Key: $ApiKey" -ForegroundColor White
    Write-Host "  API Secret: ${ApiSecret}" -ForegroundColor White
    Write-Host "  From Number: $FromNumber" -ForegroundColor White
    Write-Host ""
    Write-Host "Test at: https://everydayadvertise.com/account" -ForegroundColor Green
} else {
    Write-Host "FAILED" -ForegroundColor Red
}
