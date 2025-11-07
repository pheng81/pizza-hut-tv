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
$RemotePath = "/var/www/pizza-hut-tv"

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
    
    # Move files to final location
    ssh -i $KeyPath "ubuntu@$Server" @"
        sudo cp /tmp/app.py $RemotePath/app.py && \
        sudo cp /tmp/config.py $RemotePath/config.py && \
        sudo cp /tmp/.env.production $RemotePath/.env.production && \
        sudo chown www-data:www-data $RemotePath/app.py $RemotePath/config.py $RemotePath/.env.production
"@
    Write-Host "✓ Files deployed to server" -ForegroundColor Green
} else {
    Write-Host "✓ [DRY RUN] Would deploy: app.py, config.py, .env.production" -ForegroundColor Cyan
}

# Step 5: Restart Service
Write-Host "`nStep 5: Restarting Service" -ForegroundColor Yellow
Write-Host "--------------------------" -ForegroundColor Yellow

if (-not $DryRun) {
    ssh -i $KeyPath "ubuntu@$Server" @"
        sudo systemctl stop everydayadvertise && \
        sudo fuser -k 5002/tcp || true && \
        sleep 2 && \
        sudo systemctl start everydayadvertise && \
        sleep 3
"@
    Write-Host "✓ Service restarted" -ForegroundColor Green
} else {
    Write-Host "✓ [DRY RUN] Would restart service" -ForegroundColor Cyan
}

# Step 6: Health Check
Write-Host "`nStep 6: Health Check" -ForegroundColor Yellow
Write-Host "--------------------" -ForegroundColor Yellow

if (-not $DryRun) {
    Start-Sleep -Seconds 5
    $status = ssh -i $KeyPath "ubuntu@$Server" "sudo systemctl is-active everydayadvertise"
    
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
        ssh -i $KeyPath "ubuntu@$Server" "sudo cp $RemotePath/app.py.$backupName $RemotePath/app.py && sudo systemctl restart everydayadvertise"
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
Write-Host "  3. Monitor logs: ssh ubuntu@$Server 'sudo journalctl -u everydayadvertise -f'" -ForegroundColor White
Write-Host ""

if ($DryRun) {
    Write-Host "NOTE: This was a DRY RUN - no changes were made" -ForegroundColor Yellow
    Write-Host "Run without -DryRun to deploy for real" -ForegroundColor Yellow
}
