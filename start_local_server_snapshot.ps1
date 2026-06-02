param(
    [string]$SnapshotName = "live",
    [int]$Port = 5100,
    [string]$PythonPath = ""
)

$snapshotDir = Join-Path (Join-Path $PSScriptRoot ".server_snapshot") $SnapshotName
$dbPath = Join-Path $snapshotDir "database.db"

if (-not (Test-Path $snapshotDir)) {
    Write-Error "Snapshot directory not found: $snapshotDir"
    exit 1
}

if (-not (Test-Path $dbPath)) {
    Write-Error "Snapshot database not found: $dbPath"
    exit 1
}

if (-not $PythonPath) {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    $systemPython = "C:\Users\toeng\AppData\Local\Programs\Python\Python313\python.exe"
    if (Test-Path $venvPython) {
        $PythonPath = $venvPython
    } elseif (Test-Path $systemPython) {
        $PythonPath = $systemPython
    } else {
        $PythonPath = "python"
    }
}

$env:FLASK_ENV = "development"
$env:PORT = "$Port"
$env:USERS_DB_PATH = $dbPath
$env:STORE_CONFIG_DIR = $snapshotDir
$env:SESSION_COOKIE_SECURE = "False"
$env:SESSION_COOKIE_SAMESITE = "Lax"
$env:SESSION_COOKIE_DOMAIN = "host-only"

Write-Host "Starting local server against snapshot: $snapshotDir" -ForegroundColor Cyan
Write-Host "USERS_DB_PATH=$env:USERS_DB_PATH" -ForegroundColor DarkGray
Write-Host "STORE_CONFIG_DIR=$env:STORE_CONFIG_DIR" -ForegroundColor DarkGray
Write-Host "SESSION_COOKIE_SECURE=$env:SESSION_COOKIE_SECURE" -ForegroundColor DarkGray
Write-Host "SESSION_COOKIE_SAMESITE=$env:SESSION_COOKIE_SAMESITE" -ForegroundColor DarkGray
Write-Host "SESSION_COOKIE_DOMAIN=<host-only>" -ForegroundColor DarkGray

& $PythonPath app.py