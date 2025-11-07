# Run local development server with correct session cookie settings
Write-Host "🚀 Starting LOCAL development server..." -ForegroundColor Green
Write-Host ""

# Set environment variables for LOCAL development
$env:USERS_DB_PATH = "database_from_server.db"
$env:FLASK_ENV = "development"
$env:FLASK_DEBUG = "1"

# CRITICAL: Override production cookie settings for local development
$env:SESSION_COOKIE_SECURE = "False"  # Allow HTTP (not HTTPS)
$env:SESSION_COOKIE_DOMAIN = $null    # Don't restrict domain
$env:SESSION_COOKIE_SAMESITE = "Lax"  # Lax instead of None (doesn't require HTTPS)

Write-Host "✅ Environment configured for local development:" -ForegroundColor Yellow
Write-Host "   Database: database_from_server.db"
Write-Host "   Session cookies: HTTP allowed (not HTTPS-only)"
Write-Host "   Cookie domain: unrestricted (works on localhost/127.0.0.1)"
Write-Host ""
Write-Host "📍 Access the server at: http://127.0.0.1:5002/login" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔑 Login credentials:" -ForegroundColor Magenta
Write-Host "   Username: kayson5@gmail.com"
Write-Host "   Password: test123"
Write-Host ""

# Start Flask
python app.py
