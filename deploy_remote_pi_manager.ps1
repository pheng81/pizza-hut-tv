# Deploy Remote Pi Manager to Production
# Quick deployment script for Tailscale solution

Write-Host "🍕 Pizza Hut TV - Remote Pi Manager Production Deployment" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Copy template to production
Write-Host "📋 Step 1: Copying Remote Pi Manager template..." -ForegroundColor Yellow
if (Test-Path "templates_local\remote_pi_manager.html") {
    Copy-Item "templates_local\remote_pi_manager.html" "templates\remote_pi_manager.html" -Force
    Write-Host "✅ Template copied to production templates/" -ForegroundColor Green
} else {
    Write-Host "❌ Source template not found!" -ForegroundColor Red
    exit 1
}

# Step 2: Check if route exists in app.py
Write-Host ""
Write-Host "📋 Step 2: Checking app.py for remote-pi-manager route..." -ForegroundColor Yellow
$appContent = Get-Content "app.py" -Raw
if ($appContent -match "@app\.route\('/remote-pi-manager'\)") {
    Write-Host "✅ Route already exists in app.py" -ForegroundColor Green
} else {
    Write-Host "⚠️  Route not found in app.py" -ForegroundColor Yellow
    Write-Host "   Please add this route to app.py (around line 9520):" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "@app.route('/remote-pi-manager')" -ForegroundColor White
    Write-Host "@login_required" -ForegroundColor White
    Write-Host "def remote_pi_manager():" -ForegroundColor White
    Write-Host "    return render_template('remote_pi_manager.html')" -ForegroundColor White
    Write-Host ""
    $response = Read-Host "Do you want to add this route now? (y/n)"
    if ($response -eq 'y') {
        # Find a good insertion point (after the last @app.route)
        $lines = Get-Content "app.py"
        $insertIndex = -1
        for ($i = $lines.Count - 1; $i -ge 0; $i--) {
            if ($lines[$i] -match "^if __name__ == '__main__':") {
                $insertIndex = $i
                break
            }
        }
        
        if ($insertIndex -gt 0) {
            $newRoute = @"

@app.route('/remote-pi-manager')
@login_required
def remote_pi_manager():
    ""Remote Pi Manager page - Configure Pis remotely using Pi ID""
    return render_template('remote_pi_manager.html')
"@
            $lines = @($lines[0..($insertIndex-1)]) + $newRoute + @($lines[$insertIndex..($lines.Count-1)])
            $lines | Set-Content "app.py"
            Write-Host "✅ Route added to app.py" -ForegroundColor Green
        } else {
            Write-Host "❌ Could not find insertion point. Please add manually." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "⚠️  Please add the route manually before deploying" -ForegroundColor Yellow
        exit 1
    }
}

# Step 3: Check API endpoints
Write-Host ""
Write-Host "📋 Step 3: Verifying API endpoints exist..." -ForegroundColor Yellow
$hasConfigureEndpoint = $appContent -match "@app\.route\('/api/configure-pi',"
$hasRegisterEndpoint = $appContent -match "@app\.route\('/api/register_pi',"
$hasStatusEndpoint = $appContent -match "@app\.route\('/api/pi-status/<pi_id>'\)"

if ($hasConfigureEndpoint -and $hasRegisterEndpoint -and $hasStatusEndpoint) {
    Write-Host "✅ All required API endpoints exist:" -ForegroundColor Green
    Write-Host "   - /api/configure-pi ✅" -ForegroundColor Green
    Write-Host "   - /api/register_pi ✅" -ForegroundColor Green
    Write-Host "   - /api/pi-status/<pi_id> ✅" -ForegroundColor Green
} else {
    Write-Host "❌ Missing API endpoints!" -ForegroundColor Red
    if (-not $hasConfigureEndpoint) { Write-Host "   - /api/configure-pi ❌" -ForegroundColor Red }
    if (-not $hasRegisterEndpoint) { Write-Host "   - /api/register_pi ❌" -ForegroundColor Red }
    if (-not $hasStatusEndpoint) { Write-Host "   - /api/pi-status/<pi_id> ❌" -ForegroundColor Red }
    exit 1
}

# Step 4: Check pi_id_ip_map.json
Write-Host ""
Write-Host "📋 Step 4: Checking Pi ID mapping..." -ForegroundColor Yellow
if (Test-Path "pi_id_ip_map.json") {
    $mapping = Get-Content "pi_id_ip_map.json" | ConvertFrom-Json
    Write-Host "✅ Pi ID mapping file exists" -ForegroundColor Green
    Write-Host "   Current mappings:" -ForegroundColor Cyan
    $mapping.PSObject.Properties | ForEach-Object {
        Write-Host "   - $($_.Name) → $($_.Value)" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Update these IPs to Tailscale IPs before production use!" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Pi ID mapping file not found (will be created by auto-registration)" -ForegroundColor Yellow
}

# Step 5: Deploy to production
Write-Host ""
Write-Host "📋 Step 5: Ready to deploy?" -ForegroundColor Yellow
Write-Host "   This will deploy to: ubuntu@everydayadvertise.com" -ForegroundColor Cyan
Write-Host ""
$deploy = Read-Host "Deploy to production now? (y/n)"

if ($deploy -eq 'y') {
    Write-Host ""
    Write-Host "🚀 Deploying to production..." -ForegroundColor Cyan
    
    # Run existing deploy script
    if (Test-Path "deploy_to_server.ps1") {
        & ".\deploy_to_server.ps1"
    } else {
        Write-Host "❌ deploy_to_server.ps1 not found!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "✅ Deployment prepared but not executed" -ForegroundColor Green
    Write-Host "   Run '.\deploy_to_server.ps1' when ready" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🎉 Remote Pi Manager Production Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Install Tailscale on AWS server and Raspberry Pi" -ForegroundColor White
Write-Host "   2. Update pi_id_ip_map.json with Tailscale IPs" -ForegroundColor White
Write-Host "   3. Access: https://everydayadvertise.com/remote-pi-manager" -ForegroundColor White
Write-Host ""
Write-Host "📖 Full guide: REMOTE_PI_MANAGER_PRODUCTION.md" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
