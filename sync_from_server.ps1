param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [string]$RemoteAppPath = "/var/www/pizza-hut-tv",
    [string]$UserSafeKey = "test9_at_gmail.com",
    [string]$SnapshotName = "live",
    [switch]$IncludeMedia = $false
)

Write-Host "=== Sync Server Data to Local ===" -ForegroundColor Cyan
Write-Host ""

$snapshotRoot = Join-Path $PSScriptRoot ".server_snapshot"
$targetDir = Join-Path $snapshotRoot $SnapshotName
New-Item -Path $targetDir -ItemType Directory -Force | Out-Null

$userConfigName = "store_config__${UserSafeKey}.json"

function Copy-RemoteFile {
    param(
        [string]$RemoteName,
        [switch]$Required = $true
    )

    $destination = Join-Path $targetDir $RemoteName
    & scp -i $KeyPath "ubuntu@${Server}:${RemoteAppPath}/${RemoteName}" $destination
    if ($LASTEXITCODE -eq 0) {
        $sizeKB = [math]::Round((Get-Item $destination).Length / 1KB, 2)
        Write-Host "  [OK] ${RemoteName} downloaded (${sizeKB} KB)" -ForegroundColor Green
        return $true
    }

    if ($Required) {
        Write-Host "  [ERR] Failed to download ${RemoteName}" -ForegroundColor Red
    } else {
        Write-Host "  [WARN] ${RemoteName} not found on server" -ForegroundColor Yellow
    }
    return $false
}

# Download database
Write-Host "Downloading database.db from server..." -ForegroundColor Yellow
[void](Copy-RemoteFile -RemoteName "database.db")

# Download store config
Write-Host "Downloading ${userConfigName} from server..." -ForegroundColor Yellow
if (Copy-RemoteFile -RemoteName $userConfigName) {
    try {
        $config = Get-Content (Join-Path $targetDir $userConfigName) -Raw | ConvertFrom-Json
        $storeCount = @($config.stores).Count
        $screenGroups = @($config.screens.PSObject.Properties).Count
        Write-Host "  [OK] Contains $storeCount stores across $screenGroups screen groups" -ForegroundColor Cyan
    } catch {
        Write-Host "  [WARN] Could not parse ${userConfigName}" -ForegroundColor Yellow
    }
}

Write-Host "Downloading shared config files..." -ForegroundColor Yellow
[void](Copy-RemoteFile -RemoteName "store_config.json" -Required:$false)
[void](Copy-RemoteFile -RemoteName "pi_id_ip_map.json" -Required:$false)

# Download static uploads directory (optional - can be large)
if ($IncludeMedia) {
    Write-Host "Downloading media files..." -ForegroundColor Yellow
    $mediaTarget = Join-Path $targetDir "static/uploads"
    New-Item -Path $mediaTarget -ItemType Directory -Force | Out-Null
    & scp -i $KeyPath -r "ubuntu@${Server}:${RemoteAppPath}/static/uploads/*" $mediaTarget
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Media files downloaded" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Some media files may not have been downloaded" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Local Backup Created ===" -ForegroundColor Green
Write-Host "Location: $targetDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files synced:" -ForegroundColor Yellow
Get-ChildItem -Path $targetDir -Filter "database.db" | Format-Table Name, Length, LastWriteTime -AutoSize
Get-ChildItem -Path $targetDir -Filter $userConfigName | Format-Table Name, Length, LastWriteTime -AutoSize

Write-Host ""
Write-Host "[OK] You can now run local dev server with this exact server snapshot." -ForegroundColor Green
Write-Host "  Run: .\start_local_server_snapshot.ps1 -SnapshotName ${SnapshotName}" -ForegroundColor Cyan
