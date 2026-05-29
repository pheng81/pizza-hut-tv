param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [switch]$AutoSync = $false
)

Write-Host "=== Sync Server Data to Local ===" -ForegroundColor Cyan
Write-Host ""

$localPath = $PSScriptRoot
$serverPath = "/var/www/everydayadvertise_tv"

# Download database
Write-Host "Downloading database.db from server..." -ForegroundColor Yellow
& scp -i $KeyPath "ubuntu@${Server}:${serverPath}/database.db" "${localPath}/database.db"
if ($LASTEXITCODE -eq 0) {
    $dbSize = (Get-Item "${localPath}/database.db").Length
    Write-Host "  ✓ Database downloaded ($([math]::Round($dbSize/1KB, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to download database" -ForegroundColor Red
}

# Download store config
Write-Host "Downloading store_config__test9_at_gmail.com.json from server..." -ForegroundColor Yellow
& scp -i $KeyPath "ubuntu@${Server}:${serverPath}/store_config__test9_at_gmail.com.json" "${localPath}/store_config__test9_at_gmail.com.json"
if ($LASTEXITCODE -eq 0) {
    $configSize = (Get-Item "${localPath}/store_config__test9_at_gmail.com.json").Length
    Write-Host "  ✓ Store config downloaded ($([math]::Round($configSize/1KB, 2)) KB)" -ForegroundColor Green
    
    # Parse and show store count
    try {
        $config = Get-Content "${localPath}/store_config__test9_at_gmail.com.json" -Raw | ConvertFrom-Json
        $storeCount = $config.stores.Count
        Write-Host "  ✓ Contains $storeCount stores" -ForegroundColor Cyan
    } catch {
        Write-Host "  ⚠ Could not parse config file" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ Failed to download store config" -ForegroundColor Red
}

# Download static uploads directory (optional - can be large)
if (-not $AutoSync) {
    Write-Host ""
    $downloadMedia = Read-Host "Download media files from /static/uploads? (yes/no) [This can be large]"
    if ($downloadMedia -eq "yes") {
        Write-Host "Downloading media files..." -ForegroundColor Yellow
        New-Item -Path "${localPath}/static/uploads" -ItemType Directory -Force | Out-Null
        & scp -i $KeyPath -r "ubuntu@${Server}:${serverPath}/static/uploads/*" "${localPath}/static/uploads/"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Media files downloaded" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ Some media files may not have been downloaded" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "=== Local Backup Created ===" -ForegroundColor Green
Write-Host "Location: $localPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files synced:" -ForegroundColor Yellow
Get-ChildItem -Path $localPath -Filter "database.db" | Format-Table Name, Length, LastWriteTime -AutoSize
Get-ChildItem -Path $localPath -Filter "store_config__test9_at_gmail.com.json" | Format-Table Name, Length, LastWriteTime -AutoSize

Write-Host ""
Write-Host "✓ You can now run local dev server with this data!" -ForegroundColor Green
Write-Host "  Run: .\start_local_server.ps1" -ForegroundColor Cyan
