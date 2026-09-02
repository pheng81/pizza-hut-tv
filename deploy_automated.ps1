# Automated Deployment with Testing
# Deploys to server only if all checks pass

param(
    [string]$Environment = "production",
    [switch]$SkipTests,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AUTOMATED DEPLOYMENT PIPELINE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$Server = "54.252.90.27"
$KeyPath = "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-southeast-2.pem"
$RemotePath = "/var/www/everydayadvertise_tv"

# Step 1: Pre-deployment Checks
Write-Host "Step 1: Pre-deployment Checks" -ForegroundColor Yellow
Write-Host "------------------------------" -ForegroundColor Yellow

# Check critical files exist
$criticalFiles = @('app.py', 'requirements.txt', 'config.py', '.env.production')
foreach ($file in $criticalFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "✗ Critical file missing: $file" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Found: $file" -ForegroundColor Green
}

# Check Python syntax
Write-Host "`nChecking Python syntax..." -ForegroundColor Yellow
$syntaxCheck = python -m py_compile app.py 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Syntax error in app.py" -ForegroundColor Red
    Write-Host $syntaxCheck
    exit 1
}
Write-Host "✓ Python syntax OK" -ForegroundColor Green

# Step 2: Run Tests (if not skipped)
if (-not $SkipTests) {
    Write-Host "`nStep 2: Running Tests" -ForegroundColor Yellow
    Write-Host "---------------------" -ForegroundColor Yellow
    
    # Check if test file exists
    if (Test-Path "test_app.py") {
        python test_app.py
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ Tests failed" -ForegroundColor Red
            exit 1
        }
        Write-Host "✓ All tests passed" -ForegroundColor Green
    } else {
        Write-Host "⚠ No tests found (create test_app.py)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`nStep 2: Tests Skipped" -ForegroundColor Yellow
}

# Step 3: Create Backup
Write-Host "`nStep 3: Creating Server Backup" -ForegroundColor Yellow
Write-Host "------------------------------" -ForegroundColor Yellow

$backupName = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$backupCmd = "sudo cp $RemotePath/app.py $RemotePath/app.py.$backupName"

if (-not $DryRun) {
    ssh -i $KeyPath "ubuntu@$Server" $backupCmd
    Write-Host "✓ Backup created: app.py.$backupName" -ForegroundColor Green
} else {
    Write-Host "✓ [DRY RUN] Would create backup" -ForegroundColor Cyan
}

# Step 4: Deploy Files
Write-Host "`nStep 4: Deploying Files" -ForegroundColor Yellow
Write-Host "-----------------------" -ForegroundColor Yellow

if (-not $DryRun) {
    # Upload app.py
    scp -i $KeyPath app.py "ubuntu@${Server}:/tmp/app.py"
    Write-Host "✓ Uploaded app.py" -ForegroundColor Green
    
    # Upload config.py
    scp -i $KeyPath config.py "ubuntu@${Server}:/tmp/config.py"
    Write-Host "✓ Uploaded config.py" -ForegroundColor Green
    
    # Upload .env.production
    scp -i $KeyPath .env.production "ubuntu@${Server}:/tmp/.env.production"
    Write-Host "✓ Uploaded .env.production" -ForegroundColor Green
    
    # Move files to final location.
    # PowerShell here-strings use CRLF, and a CR survives the `\` line
    # continuation as a literal command - bash then reports `$'\r': command not
    # found` and, worse, treats each line as separate so a failed cp does not
    # stop the ones after it. Send LF-only and let `set -e` do the guarding.
    # The app calls load_dotenv() with no argument, which reads ".env" - NOT
    # ".env.production". Uploading only the latter meant every config change
    # deployed here was silently ignored while the app kept using the old .env,
    # with no error to notice. Write the file the app actually reads, keeping a
    # timestamped copy of the previous one because it holds SECRET_KEY: losing
    # that invalidates every user session.
    # Merge rather than replace. Secrets that only ever existed on the box -
    # APPLE_IAP_SHARED_SECRET and GOOGLE_PLAY_SERVICE_ACCOUNT_JSON - are not in
    # .env.production, and copying it over .env deleted them. That makes
    # _apple_iap_enabled() and _google_play_enabled() false, so the server
    # refuses receipts *after* the store has charged the customer - worse than
    # whatever the deploy was fixing. Keys the incoming file defines still win,
    # so config changes take effect; keys only the live file has are carried
    # across. Line-based, so a value spanning multiple lines is not supported.
    # The body is a literal here-string so the shell's own $VARs survive
    # PowerShell; the one value it needs is passed in as $REMOTE.
    $deployBody = (@'
set -e
STAMP=$(date +%Y%m%d_%H%M%S)
sudo cp /tmp/app.py $REMOTE/app.py
sudo cp /tmp/config.py $REMOTE/config.py
awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ {print $1}' /tmp/.env.production | sort -u > /tmp/.env.newkeys
if [ -f $REMOTE/.env ]; then
  sudo cp -a $REMOTE/.env $REMOTE/.env.backup_$STAMP
  sudo awk -F= 'NR==FNR {k[$1]=1; next} /^[A-Za-z_][A-Za-z0-9_]*=/ && !($1 in k)' /tmp/.env.newkeys $REMOTE/.env > /tmp/.env.keep
else
  : > /tmp/.env.keep
fi
cp /tmp/.env.production /tmp/.env.merged
if [ -s /tmp/.env.keep ]; then
  printf '\n# Preserved from the previous .env on %s - not defined in .env.production\n' "$STAMP" >> /tmp/.env.merged
  cat /tmp/.env.keep >> /tmp/.env.merged
  echo "Kept keys that exist only on the server:"
  cut -d= -f1 /tmp/.env.keep | sed 's/^/  /'
else
  echo "No server-only keys to keep."
fi
NEWCOUNT=$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' /tmp/.env.production)
MERGEDCOUNT=$(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' /tmp/.env.merged)
if [ "$MERGEDCOUNT" -lt "$NEWCOUNT" ]; then
  echo "Refusing to install a .env with fewer keys ($MERGEDCOUNT) than .env.production ($NEWCOUNT)."
  exit 1
fi
sudo cp /tmp/.env.merged $REMOTE/.env
sudo cp /tmp/.env.production $REMOTE/.env.production
sudo chown www-data:www-data $REMOTE/app.py $REMOTE/config.py $REMOTE/.env.production
sudo chown ubuntu:ubuntu $REMOTE/.env
sudo chmod 644 $REMOTE/.env
rm -f /tmp/.env.newkeys /tmp/.env.keep /tmp/.env.merged
'@) -replace "`r`n", "`n"
    $deployCmd = "REMOTE='$RemotePath'`n" + $deployBody
    ssh -i $KeyPath "ubuntu@$Server" $deployCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to move files into place on the server" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Files deployed to server" -ForegroundColor Green
} else {
    Write-Host "✓ [DRY RUN] Would deploy: app.py, config.py, .env.production" -ForegroundColor Cyan
}

# Step 5: Restart Service
Write-Host "`nStep 5: Restarting Service" -ForegroundColor Yellow
Write-Host "--------------------------" -ForegroundColor Yellow

if (-not $DryRun) {
    # LF-only for the same reason as the deploy step above.
    $restartCmd = (@"
sudo systemctl stop everydayadvertise_tv
sudo fuser -k 5002/tcp || true
sleep 2
sudo systemctl start everydayadvertise_tv
sleep 3
"@) -replace "`r`n", "`n"
    ssh -i $KeyPath "ubuntu@$Server" $restartCmd
    Write-Host "✓ Service restarted" -ForegroundColor Green
} else {
    Write-Host "✓ [DRY RUN] Would restart service" -ForegroundColor Cyan
}

# Step 6: Health Check
Write-Host "`nStep 6: Health Check" -ForegroundColor Yellow
Write-Host "--------------------" -ForegroundColor Yellow

if (-not $DryRun) {
    Start-Sleep -Seconds 5
    $status = ssh -i $KeyPath "ubuntu@$Server" "sudo systemctl is-active everydayadvertise_tv"
    
    if ($status -eq "active") {
        Write-Host "✓ Service is running" -ForegroundColor Green
        
        # Check if port is responding
        $portCheck = ssh -i $KeyPath "ubuntu@$Server" "curl -s -o /dev/null -w '%{http_code}' http://localhost:5002 || echo '000'"
        
        if ($portCheck -eq "200" -or $portCheck -eq "302") {
            Write-Host "✓ Server responding on port 5002" -ForegroundColor Green
        } else {
            Write-Host "⚠ Service running but port check returned: $portCheck" -ForegroundColor Yellow
        }
    } else {
        Write-Host "✗ Service is not running!" -ForegroundColor Red
        Write-Host "Rolling back..." -ForegroundColor Yellow
        
        # Rollback
        ssh -i $KeyPath "ubuntu@$Server" "sudo cp $RemotePath/app.py.$backupName $RemotePath/app.py && sudo systemctl restart everydayadvertise_tv"
        Write-Host "✓ Rolled back to previous version" -ForegroundColor Green
        exit 1
    }
} else {
    Write-Host "✓ [DRY RUN] Would perform health check" -ForegroundColor Cyan
}

# Step 7: Completion
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✓ DEPLOYMENT SUCCESSFUL" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Deployment Summary:" -ForegroundColor Cyan
Write-Host "  Environment: $Environment" -ForegroundColor White
Write-Host "  Server: $Server" -ForegroundColor White
Write-Host "  Backup: app.py.$backupName" -ForegroundColor White
Write-Host "  Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test the website: https://everydayadvertise.com" -ForegroundColor White
Write-Host "  2. Check dashboard functionality" -ForegroundColor White
Write-Host "  3. Monitor logs: ssh ubuntu@$Server 'sudo journalctl -u everydayadvertise_tv -f'" -ForegroundColor White
Write-Host ""

if ($DryRun) {
    Write-Host "NOTE: This was a DRY RUN - no changes were made" -ForegroundColor Yellow
    Write-Host "Run without -DryRun to deploy for real" -ForegroundColor Yellow
}
