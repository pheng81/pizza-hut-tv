# Pizza Hut TV - Start two Android TV emulators and install app on both
# Usage (PowerShell):
#   ./start_two_android_tv_emulators.ps1 -AvdName "Pizza_Hut_TV" -ApkPath "android_tv_app/app/build/outputs/apk/debug/app-debug.apk"
# Notes:
# - If AvdName doesn't exist, the first available AVD from `emulator -list-avds` will be used.
# - If ApkPath doesn't exist, we'll try to build it with Gradle from android_tv_app.

param(
    [string]$AvdName = "",
    [string]$AvdNames = "",
    [string]$ApkPath = "android_tv_app\app\build\outputs\apk\debug\app-debug.apk",
    [string]$PackageName = "com.pizzahut.tv",
    [int]$MaxBootWaitSeconds = 180,
    [switch]$Headless
)

$ErrorActionPreference = "Stop"

function Fail([string]$message) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

function Set-AndroidSdkEnv() {
    Write-Host "[1/6] Detecting Android SDK..." -ForegroundColor Yellow
    $androidHome = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
    if (-not (Test-Path $androidHome)) { Fail "Android SDK not found at $androidHome. Install Android Studio or set ANDROID_HOME." }
    $env:ANDROID_HOME = $androidHome
    $global:EmulatorExe = Join-Path $androidHome "emulator\emulator.exe"
    $global:AdbExe = Join-Path $androidHome "platform-tools\adb.exe"
    $global:AvdManager = Join-Path $androidHome "cmdline-tools\latest\bin\avdmanager.bat"
    if (-not (Test-Path $EmulatorExe)) { Fail "Emulator binary missing at $EmulatorExe" }
    if (-not (Test-Path $AdbExe)) { Fail "ADB binary missing at $AdbExe" }
    $pathParts = @(
        "$androidHome\emulator",
        "$androidHome\platform-tools",
        "$androidHome\cmdline-tools\latest\bin",
        $env:PATH
    ) | Where-Object { $_ -and $_.Trim() }
    $env:PATH = ($pathParts -join ';')
    Write-Host "[OK] Android SDK found at $androidHome" -ForegroundColor Green
}

function Get-ApkOrBuild([string]$apkPath) {
    Write-Host "[2/6] Checking APK..." -ForegroundColor Yellow
    if (-not (Test-Path $apkPath)) {
        Write-Host "APK not found. Building debug APK via Gradle." -ForegroundColor Yellow
        if (-not (Test-Path "android_tv_app\gradlew.bat")) { Fail "Gradle wrapper not found in android_tv_app" }
        Push-Location android_tv_app
        try {
            .\gradlew.bat assembleDebug | Write-Host
            if ($LASTEXITCODE -ne 0) { Fail "Gradle build failed" }
        } finally { Pop-Location }
        if (-not (Test-Path $apkPath)) { Fail "APK still missing after build ($apkPath)" }
    }
    Write-Host "[OK] APK ready at $apkPath" -ForegroundColor Green
}

function Get-TwoAvds([string]$preferred, [string]$pairCsv) {
    Write-Host "[3/7] Resolving two AVDs..." -ForegroundColor Yellow
    $avds = @(& $EmulatorExe -list-avds 2>$null)
    if (-not $avds -or $avds.Count -lt 1) { Fail "No Android Virtual Devices are defined. Create one in Android Studio." }

    if ($pairCsv -and $pairCsv.Trim()) {
        $wanted = ($pairCsv -split '[,;]') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        if ($wanted.Count -ge 2) {
            $first = $avds | Where-Object { $_.ToLowerInvariant() -eq $wanted[0].ToLowerInvariant() } | Select-Object -First 1
            $second = $avds | Where-Object { $_.ToLowerInvariant() -eq $wanted[1].ToLowerInvariant() } | Select-Object -First 1
            if (-not $first) { Fail "Requested AVD '$($wanted[0])' not found. Available: $($avds -join ', ')" }
            if (-not $second) { Fail "Requested AVD '$($wanted[1])' not found. Available: $($avds -join ', ')" }
            Write-Host "Using AVDs: $first, $second" -ForegroundColor Green
            return ,@($first, $second)
        }
    }

    $first = $null
    if ($preferred -and $preferred.Trim()) {
        $first = $avds | Where-Object { $_.ToLowerInvariant() -eq $preferred.ToLowerInvariant() } | Select-Object -First 1
        if (-not $first) { Write-Host "Preferred AVD '$preferred' not found; using list order" -ForegroundColor Yellow }
    }
    if (-not $first) { $first = $avds | Select-Object -First 1 }
    $second = ($avds | Where-Object { $_ -ne $first } | Select-Object -First 1)
    if (-not $second) { Fail "Need at least two Android Virtual Devices. Create more in Android Studio." }
    Write-Host "Using AVDs: $first, $second" -ForegroundColor Green
    return ,@($first, $second)
}

function Get-CurrentEmulatorIds() {
    & $AdbExe devices 2>$null | Select-String "^emulator-\d+\s+device$" | ForEach-Object { ($_ -split "\s+")[0] }
}

function Start-Emulator([string]$avdName, [int]$port = 0, [switch]$noWindow) {
    $emuArgsLocal = @(
        "-avd", $avdName,
        "-no-snapshot-load",
        "-no-snapshot-save",
        "-gpu", "host",
        "-memory", "2048",
        "-cores", "4",
        "-no-boot-anim"
    )
    if ($port -gt 0) { $emuArgsLocal += @('-port', $port) }
    if ($noWindow) { $emuArgsLocal += '-no-window' }
    Start-Process -FilePath $EmulatorExe -ArgumentList $emuArgsLocal -WindowStyle Normal | Out-Null
}

function Wait-ForBoot([string]$deviceId, [int]$timeoutSec) {
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        Start-Sleep -Seconds 5
        $elapsed += 5
        $boot = & $AdbExe -s $deviceId shell getprop sys.boot_completed 2>$null
        if ($boot.Trim() -eq "1") { return $true }
    }
    return $false
}

function Install-And-Launch([string]$deviceId, [string]$apkPath, [string]$packageName) {
    Write-Host "Installing on $deviceId..." -ForegroundColor Yellow
    & $AdbExe -s $deviceId uninstall $packageName 2>$null | Out-Null
    $out = & $AdbExe -s $deviceId install -r $apkPath 2>&1
    if (-not (($out | Out-String) -match "Success")) { Write-Host $out; Fail "ADB install failed on $deviceId" }
    Write-Host "Installed on $deviceId" -ForegroundColor Green
    Write-Host "Launching app on $deviceId..." -ForegroundColor Yellow
    & $AdbExe -s $deviceId shell am start -n "$packageName/.SetupActivity" 2>&1 | Out-Null
}

# --- Main ---
Set-AndroidSdkEnv
Get-ApkOrBuild -apkPath $ApkPath
$avdPair = Get-TwoAvds -preferred $AvdName -pairCsv $AvdNames
$avd1 = $avdPair[0]
$avd2 = $avdPair[1]

Write-Host "[4/7] Stopping any running emulators..." -ForegroundColor Yellow
& $AdbExe devices 2>$null | Select-String "^emulator-\d+\s+device$" | ForEach-Object {
    $emuId = ($_ -split "\s+")[0]
    Write-Host "Stopping $emuId" -ForegroundColor Gray
    & $AdbExe -s $emuId emu kill 2>$null
}
Start-Sleep -Seconds 2

Write-Host "[5/7] Starting two emulators '$avd1' and '$avd2'..." -ForegroundColor Yellow
$port1 = 5554
$port2 = 5556
Start-Emulator -avdName $avd1 -port $port1 -noWindow:$Headless
Start-Sleep -Seconds 2
Start-Emulator -avdName $avd2 -port $port2 -noWindow:$Headless

Write-Host "Waiting for two emulator devices to appear..." -ForegroundColor Gray
$expected = @("emulator-$port1", "emulator-$port2")
$appearElapsed = 0
while ($appearElapsed -lt $MaxBootWaitSeconds) {
    Start-Sleep -Seconds 5
    $appearElapsed += 5
    $current = @(Get-CurrentEmulatorIds)
    if (@($expected | Where-Object { $current -contains $_ }).Count -eq 2) { break }
    Write-Host "Still waiting... ($appearElapsed s) Found: $($current -join ', ')" -ForegroundColor Gray
}

Write-Host "[6/7] Waiting for boot completion..." -ForegroundColor Yellow
$readyIds = @()
foreach ($id in $expected) {
    Write-Host "Waiting for $id to boot (max $MaxBootWaitSeconds s)..." -ForegroundColor Gray
    $ok = Wait-ForBoot -deviceId $id -timeoutSec $MaxBootWaitSeconds
    if ($ok) { Write-Host "$id booted" -ForegroundColor Green; $readyIds += $id } else { Write-Host "$id did not fully boot in time" -ForegroundColor Yellow }
}

if ($readyIds.Count -eq 0) { Fail "Neither emulator finished booting in time." }

Write-Host "[7/7] Installing APK to ready devices: $($readyIds -join ', ')" -ForegroundColor Yellow
foreach ($id in $readyIds) { Install-And-Launch -deviceId $id -apkPath $ApkPath -packageName $PackageName }

Write-Host
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Two-emulator setup complete" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Devices: $($readyIds -join ', ')" -ForegroundColor Cyan
Write-Host "Package: $PackageName" -ForegroundColor Cyan
Write-Host "APK:     $ApkPath" -ForegroundColor Cyan
