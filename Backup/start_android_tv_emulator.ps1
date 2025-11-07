# Pizza Hut TV - Android TV Emulator helper
# Launches the Android TV AVD, installs the APK, and tails logcat

param(
    [string]$AvdName = "Pizza_Hut_TV"
)

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Pizza Hut TV - Android TV Emulator Launcher  " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host

# Configuration
$avdName = $AvdName
$packageName = "com.pizzahut.tv"
$apkPath = "android_tv_app\app\build\outputs\apk\debug\app-debug.apk"

function Fail([string]$message) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

Write-Host "[1/6] Detecting Android SDK..." -ForegroundColor Yellow
$androidHome = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }

if (-not (Test-Path $androidHome)) {
    Fail "Android SDK not found at $androidHome. Install Android Studio or set ANDROID_HOME."
}

Write-Host "[OK] Android SDK found at $androidHome" -ForegroundColor Green

$env:ANDROID_HOME = $androidHome
$pathParts = @(
    "$androidHome\emulator",
    "$androidHome\platform-tools",
    "$androidHome\cmdline-tools\latest\bin",
    $env:PATH
) | Where-Object { $_ -and $_.Trim() }
$env:PATH = ($pathParts -join ';')

$emulatorExe = Join-Path $androidHome "emulator\emulator.exe"
$adbExe = Join-Path $androidHome "platform-tools\adb.exe"
$avdManager = Join-Path $androidHome "cmdline-tools\latest\bin\avdmanager.bat"

if (-not (Test-Path $emulatorExe)) { Fail "Emulator binary missing at $emulatorExe" }
if (-not (Test-Path $adbExe)) { Fail "ADB binary missing at $adbExe" }

Write-Host "[2/6] Checking APK..." -ForegroundColor Yellow
if (-not (Test-Path $apkPath)) {
    Write-Host "APK not found. Building debug APK via Gradle." -ForegroundColor Yellow
    Push-Location android_tv_app
    try {
        .\gradlew.bat assembleDebug | Write-Host
        if ($LASTEXITCODE -ne 0) {
            Fail "Gradle build failed"
        }
    } finally {
        Pop-Location
    }
    if (-not (Test-Path $apkPath)) {
        Fail "APK still missing after build ($apkPath)"
    }
}
Write-Host "[OK] APK ready at $apkPath" -ForegroundColor Green

Write-Host "[3/6] Verifying Android Virtual Device..." -ForegroundColor Yellow
if (Test-Path $avdManager) {
    $existingAvds = & $emulatorExe -list-avds 2>$null
    if (-not $existingAvds) {
        Fail "No Android Virtual Devices are defined. Create one in Android Studio."
    }

    $matchingAvd = $existingAvds | Where-Object { $_.ToLowerInvariant() -eq $avdName.ToLowerInvariant() } | Select-Object -First 1
    if ($matchingAvd) {
        $avdName = $matchingAvd
    } else {
        Write-Host "AVD $avdName not found." -ForegroundColor Yellow
        $fallbackAvd = $existingAvds | Select-Object -First 1
        Write-Host "Using available AVD $fallbackAvd instead." -ForegroundColor Yellow
        $avdName = $fallbackAvd
    }
} else {
    Write-Host "avdmanager not available; skipping AVD list check." -ForegroundColor Yellow
}

Write-Host "[4/6] Stopping any running emulators..." -ForegroundColor Yellow
& $adbExe devices | Select-String "emulator-" | ForEach-Object {
    $emuId = ($_ -split "\s+")[0]
    Write-Host "Stopping emulator $emuId" -ForegroundColor Gray
    & $adbExe -s $emuId emu kill 2>$null
}
Start-Sleep -Seconds 2

Write-Host "[OK] Cleanup complete." -ForegroundColor Green

Write-Host "[5/6] Starting Android TV emulator $avdName..." -ForegroundColor Yellow
$emuArgs = @(
    "-avd", $avdName,
    "-no-snapshot-load",
    "-gpu", "auto",
    "-memory", "2048",
    "-cores", "4",
    "-no-boot-anim"
)
Start-Process -FilePath $emulatorExe -ArgumentList $emuArgs -WindowStyle Normal | Out-Null

Write-Host "Waiting for emulator to boot (max 2 minutes)..." -ForegroundColor Gray
$maxWait = 120
$elapsed = 0
$deviceId = $null

while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 5
    $elapsed += 5

    $onlineDevices = & $adbExe devices 2>$null | Select-String "emulator-.*device$"
    if ($onlineDevices) {
        $deviceId = ($onlineDevices[0] -split "\s+")[0]
        $bootState = & $adbExe -s $deviceId shell getprop sys.boot_completed 2>$null
        if ($bootState.Trim() -eq "1") {
            Write-Host "Emulator is ready after $elapsed seconds." -ForegroundColor Green
            break
        }
    }

    Write-Host "Still booting... $elapsed seconds elapsed" -ForegroundColor Gray
}

if (-not $deviceId) {
    Fail "No emulator device detected."
}

if ($elapsed -ge $maxWait) {
    Write-Host "Boot took longer than expected; continuing anyway." -ForegroundColor Yellow
}

Write-Host "[6/6] Installing Pizza Hut TV app..." -ForegroundColor Yellow
Write-Host "Removing any existing install..." -ForegroundColor Gray
& $adbExe -s $deviceId uninstall $packageName 2>$null | Out-Null

Write-Host "Pushing APK..." -ForegroundColor Gray

$installOutput = & $adbExe -s $deviceId install -r $apkPath 2>&1
$installText = ($installOutput | Out-String)
if (-not ($installText -match "Success")) {
    Write-Host $installText
    Fail "ADB install failed"
}

Write-Host "APK installed successfully." -ForegroundColor Green

Write-Host "Launching application..." -ForegroundColor Yellow
& $adbExe -s $deviceId shell am start -n "$packageName/.SetupActivity" 2>&1 | Out-Null
Start-Sleep -Seconds 2
Write-Host "Launch command sent." -ForegroundColor Green

Write-Host
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Setup complete" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Emulator device: $deviceId" -ForegroundColor Cyan
Write-Host "Package name:    $packageName" -ForegroundColor Cyan
Write-Host
Write-Host "Useful ADB commands:" -ForegroundColor Yellow
Write-Host "  adb -s $deviceId logcat" -ForegroundColor Gray
Write-Host "  adb -s $deviceId shell am start -n $packageName/.SetupActivity" -ForegroundColor Gray
Write-Host "  adb -s $deviceId uninstall $packageName" -ForegroundColor Gray
Write-Host
Write-Host "Streaming logcat (Ctrl+C to stop)..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

& $adbExe -s $deviceId logcat -s PizzaHutTV:* AndroidRuntime:E
