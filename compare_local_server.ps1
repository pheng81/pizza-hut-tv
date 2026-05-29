param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"
)

Write-Host "=== Compare Local vs Server Data ===" -ForegroundColor Cyan
Write-Host ""

$localPath = $PSScriptRoot
$serverPath = "/var/www/everydayadvertise_tv"

# Check local database
Write-Host "Local Database:" -ForegroundColor Yellow
if (Test-Path "${localPath}/database.db") {
    $localDbSize = (Get-Item "${localPath}/database.db").Length
    $localDbDate = (Get-Item "${localPath}/database.db").LastWriteTime
    Write-Host "  Size: $([math]::Round($localDbSize/1KB, 2)) KB" -ForegroundColor Cyan
    Write-Host "  Modified: $localDbDate" -ForegroundColor Cyan
} else {
    Write-Host "  ✗ NOT FOUND" -ForegroundColor Red
}

Write-Host ""
Write-Host "Server Database:" -ForegroundColor Yellow
$serverDbInfo = & ssh -i $KeyPath "ubuntu@${Server}" "ls -lh ${serverPath}/database.db 2>/dev/null | awk '{print \`$5, \`$6, \`$7, \`$8}'"
if ($serverDbInfo) {
    Write-Host "  $serverDbInfo" -ForegroundColor Cyan
} else {
    Write-Host "  ✗ NOT FOUND" -ForegroundColor Red
}

Write-Host ""
Write-Host "─────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# Check local config
Write-Host "Local Store Config:" -ForegroundColor Yellow
if (Test-Path "${localPath}/store_config__test9_at_gmail.com.json") {
    $localConfigSize = (Get-Item "${localPath}/store_config__test9_at_gmail.com.json").Length
    $localConfigDate = (Get-Item "${localPath}/store_config__test9_at_gmail.com.json").LastWriteTime
    Write-Host "  Size: $([math]::Round($localConfigSize/1KB, 2)) KB" -ForegroundColor Cyan
    Write-Host "  Modified: $localConfigDate" -ForegroundColor Cyan
    
    # Count stores
    try {
        $config = Get-Content "${localPath}/store_config__test9_at_gmail.com.json" -Raw | ConvertFrom-Json
        Write-Host "  Stores: $($config.stores.Count)" -ForegroundColor Cyan
    } catch {
        Write-Host "  ⚠ Could not parse" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ NOT FOUND" -ForegroundColor Red
}

Write-Host ""
Write-Host "Server Store Config:" -ForegroundColor Yellow
$serverConfigInfo = & ssh -i $KeyPath "ubuntu@${Server}" "ls -lh ${serverPath}/store_config__test9_at_gmail.com.json 2>/dev/null | awk '{print \`$5, \`$6, \`$7, \`$8}'"
if ($serverConfigInfo) {
    Write-Host "  $serverConfigInfo" -ForegroundColor Cyan
    
    # Count stores on server
    $serverStoreCount = & ssh -i $KeyPath "ubuntu@${Server}" "python3 -c 'import json; data=json.load(open(\"${serverPath}/store_config__test9_at_gmail.com.json\")); print(len(data.get(\"stores\", [])))' 2>/dev/null"
    if ($serverStoreCount) {
        Write-Host "  Stores: $serverStoreCount" -ForegroundColor Cyan
    }
} else {
    Write-Host "  ✗ NOT FOUND" -ForegroundColor Red
}

Write-Host ""
Write-Host "─────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# Check for recent backups on server
Write-Host "Recent Server Backups:" -ForegroundColor Yellow
$backupCount = & ssh -i $KeyPath "ubuntu@${Server}" "ls -1 ${serverPath}/*.backup-* 2>/dev/null | wc -l"
if ($backupCount -gt 0) {
    Write-Host "  Found $backupCount backup files" -ForegroundColor Green
    & ssh -i $KeyPath "ubuntu@${Server}" "ls -lht ${serverPath}/*.backup-* 2>/dev/null | head -3 | awk '{print \"  \", \`$9, \`$5}'"
} else {
    Write-Host "  ⚠ No backups found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Recommendations ===" -ForegroundColor Cyan

if (-not (Test-Path "${localPath}/database.db")) {
    Write-Host "  → Run .\sync_from_server.ps1 to download server data" -ForegroundColor Yellow
}

if (Test-Path "${localPath}/database.db") {
    $age = (Get-Date) - (Get-Item "${localPath}/database.db").LastWriteTime
    if ($age.TotalDays -gt 1) {
        Write-Host "  → Your local data is $([math]::Round($age.TotalDays, 1)) days old - consider syncing" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ Local data is recent" -ForegroundColor Green
    }
}

if ($backupCount -eq 0) {
    Write-Host "  → Run .\deploy_to_server.ps1 to create automatic backups" -ForegroundColor Yellow
}

Write-Host ""
