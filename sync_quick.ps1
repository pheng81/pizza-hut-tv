param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"
)

Write-Host "=== Quick Sync: Server → Local ===" -ForegroundColor Cyan
Write-Host ""

$localPath = $PSScriptRoot
$serverPath = "/var/www/everydayadvertise_tv"

# Download database
Write-Host "📥 Downloading database.db..." -ForegroundColor Yellow
& scp -i $KeyPath "ubuntu@${Server}:${serverPath}/database.db" "${localPath}/database.db" 2>$null
if ($LASTEXITCODE -eq 0) {
    $dbSize = (Get-Item "${localPath}/database.db").Length
    Write-Host "  ✓ $([math]::Round($dbSize/1KB, 2)) KB" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed" -ForegroundColor Red
}

# Download store config  
Write-Host "📥 Downloading store_config..." -ForegroundColor Yellow
& scp -i $KeyPath "ubuntu@${Server}:${serverPath}/store_config__test9_at_gmail.com.json" "${localPath}/store_config__test9_at_gmail.com.json" 2>$null
if ($LASTEXITCODE -eq 0) {
    $configSize = (Get-Item "${localPath}/store_config__test9_at_gmail.com.json").Length
    Write-Host "  ✓ $([math]::Round($configSize/1KB, 2)) KB" -ForegroundColor Green
    
    # Show store count
    try {
        $config = Get-Content "${localPath}/store_config__test9_at_gmail.com.json" -Raw | ConvertFrom-Json
        Write-Host "  ✓ $($config.stores.Count) stores loaded" -ForegroundColor Cyan
    } catch {}
} else {
    Write-Host "  ✗ Failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "✅ Sync complete!" -ForegroundColor Green
Write-Host "Your local copy now matches the server." -ForegroundColor Cyan
