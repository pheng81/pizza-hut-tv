param(
    [string]$Server = "54.252.90.27",
    [string]$KeyPath = "C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem",
    [int]$KeepLast = 10
)

Write-Host "=== Backup Cleanup Utility ===" -ForegroundColor Cyan
Write-Host "Keeping last $KeepLast backups..." -ForegroundColor Yellow
Write-Host ""

# List all backups
Write-Host "Current backups:" -ForegroundColor Yellow
& ssh -i $KeyPath "ubuntu@${Server}" "ls -lh /var/www/everydayadvertise_tv/*.backup-* 2>/dev/null"

Write-Host ""
Write-Host "Removing old backups (keeping last $KeepLast)..." -ForegroundColor Yellow

# Remove old config backups
& ssh -i $KeyPath "ubuntu@${Server}" "cd /var/www/everydayadvertise_tv && ls -t store_config__test9_at_gmail.com.json.backup-* 2>/dev/null | tail -n +$($KeepLast + 1) | xargs rm -f 2>/dev/null; echo 'Config backups cleaned'"

# Remove old database backups
& ssh -i $KeyPath "ubuntu@${Server}" "cd /var/www/everydayadvertise_tv && ls -t database.db.backup-* 2>/dev/null | tail -n +$($KeepLast + 1) | xargs rm -f 2>/dev/null; echo 'Database backups cleaned'"

Write-Host ""
Write-Host "Remaining backups:" -ForegroundColor Green
& ssh -i $KeyPath "ubuntu@${Server}" "ls -lh /var/www/everydayadvertise_tv/*.backup-* 2>/dev/null | wc -l"
& ssh -i $KeyPath "ubuntu@${Server}" "du -sh /var/www/everydayadvertise_tv/*.backup-* 2>/dev/null | tail -5"

Write-Host ""
Write-Host "✓ Cleanup complete!" -ForegroundColor Green
