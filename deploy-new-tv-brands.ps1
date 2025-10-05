# PowerShell script to upload Amazon Fire TV and Kogan TV configurations
# Run this script when server connection is available

$server = "toeng@101.98.51.155"
$remoteBase = "/var/www/html/pizza-hut-tv/static/tv-brands"
$localBase = "c:\Users\toeng\Pizza Hut TV\static\tv-brands"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "TV Brand Configuration Deployment" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Create remote directories first
Write-Host "Creating remote directories..." -ForegroundColor Yellow
ssh $server "mkdir -p $remoteBase/amazon"
ssh $server "mkdir -p $remoteBase/kogan"
Write-Host "✓ Directories created" -ForegroundColor Green
Write-Host ""

# Upload Amazon Fire TV files
Write-Host "Uploading Amazon Fire TV files..." -ForegroundColor Yellow
scp "$localBase\amazon\config.js" "${server}:${remoteBase}/amazon/"
scp "$localBase\amazon\style.css" "${server}:${remoteBase}/amazon/"
Write-Host "✓ Amazon Fire TV files uploaded" -ForegroundColor Green
Write-Host ""

# Upload Kogan TV files
Write-Host "Uploading Kogan TV files..." -ForegroundColor Yellow
scp "$localBase\kogan\config.js" "${server}:${remoteBase}/kogan/"
scp "$localBase\kogan\style.css" "${server}:${remoteBase}/kogan/"
Write-Host "✓ Kogan TV files uploaded" -ForegroundColor Green
Write-Host ""

# Upload updated Sony config (fixed)
Write-Host "Uploading updated Sony config..." -ForegroundColor Yellow
scp "$localBase\sony\config.js" "${server}:${remoteBase}/sony/"
Write-Host "✓ Sony config updated" -ForegroundColor Green
Write-Host ""

# Upload updated Panasonic config
Write-Host "Uploading updated Panasonic config..." -ForegroundColor Yellow
scp "$localBase\panasonic\config.js" "${server}:${remoteBase}/panasonic/"
Write-Host "✓ Panasonic config updated" -ForegroundColor Green
Write-Host ""

# Upload updated tv-detector.js
Write-Host "Uploading updated TV detector..." -ForegroundColor Yellow
scp "$localBase\tv-detector.js" "${server}:${remoteBase}/"
Write-Host "✓ TV detector updated" -ForegroundColor Green
Write-Host ""

# Upload documentation files
Write-Host "Uploading documentation..." -ForegroundColor Yellow
scp "$localBase\BROWSER_COMPATIBILITY.md" "${server}:${remoteBase}/"
scp "$localBase\BRAND_SUMMARY.md" "${server}:${remoteBase}/"
Write-Host "✓ Documentation uploaded" -ForegroundColor Green
Write-Host ""

# Set permissions
Write-Host "Setting file permissions..." -ForegroundColor Yellow
ssh $server "chmod -R 755 $remoteBase"
ssh $server "chown -R www-data:www-data $remoteBase"
Write-Host "✓ Permissions set" -ForegroundColor Green
Write-Host ""

# Restart services if needed
Write-Host "Restarting web server..." -ForegroundColor Yellow
ssh $server "sudo systemctl reload nginx"
Write-Host "✓ Web server reloaded" -ForegroundColor Green
Write-Host ""

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "✓ DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "New TV Brands Deployed:" -ForegroundColor White
Write-Host "  🔥 Amazon Fire TV" -ForegroundColor Yellow
Write-Host "  🇦🇺 Kogan TV" -ForegroundColor Yellow
Write-Host ""
Write-Host "Total brands supported: 11" -ForegroundColor White
Write-Host ""
Write-Host "Test the detection at:" -ForegroundColor White
Write-Host "  http://101.98.51.155/webplayer" -ForegroundColor Cyan
Write-Host ""
