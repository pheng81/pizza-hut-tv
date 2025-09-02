param(
    [string]$SdkRoot = $Env:ANDROID_SDK_ROOT,
    [string]$ApiLevel = "34",
    [string]$AvdNameA = "tv${ApiLevel}a",
    [string]$AvdNameB = "tv${ApiLevel}b",
    [string]$AppPackage = "com.pizzahut.tv",
    [string]$ApkPath = "..\android_tv_app\app\build\outputs\apk\debug\app-debug.apk",
    [string]$ImageId = "" # optional explicit system image package id
)

function Resolve-SdkRoot {
    if (-not $SdkRoot -or -not (Test-Path $SdkRoot)) {
        # Try common locations
        $c1 = "$Env:USERPROFILE\AppData\Local\Android\Sdk"
        $c2 = "C:\\Android\\Sdk"
        if (Test-Path $c1) { $script:SdkRoot = $c1 }
        elseif (Test-Path $c2) { $script:SdkRoot = $c2 }
        else { throw "Android SDK not found. Set ANDROID_SDK_ROOT or pass -SdkRoot." }
    }
}

function Get-ToolPath($rel) {
    $p = Join-Path $SdkRoot $rel
    if (-not (Test-Path $p)) { throw "Missing tool: $p" }
    return $p
}

function Ensure-SystemImage {
    param([string]$Channel = "android-tv")
    # Returns the selected/installed ImageId
    $sdkmgr = Get-ToolPath "cmdline-tools\latest\bin\sdkmanager.bat"
    $candidates = @()
    if ($ImageId -and $ImageId.Trim().Length -gt 0) {
        $candidates += $ImageId
    } else {
        # Prefer Google TV (better remote), then Android TV
        $candidates += @(
            "system-images;android-36;google-tv;x86",
            "system-images;android-35;google_apis;x86_64",
            "system-images;android-34;google_apis;x86_64",
            "system-images;android-34;android-tv;x86"
        )
    }
    Write-Host "[sysimg] Trying candidates:`n  - " ($candidates -join "`n  - ") -ForegroundColor Cyan
    $accept = ("y`n" * 10)
    $accept | & $sdkmgr --licenses | Out-Null
    foreach ($pkg in $candidates) {
        Write-Host "[sysimg] Installing $pkg ..." -ForegroundColor DarkCyan
        $out = & $sdkmgr $pkg 2>&1
        if ($LASTEXITCODE -eq 0 -and -not ($out -match "Failed to find package")) {
            Write-Host "[sysimg] Using $pkg" -ForegroundColor Green
            return $pkg
        } else {
            Write-Host "[sysimg] Not available: $pkg" -ForegroundColor Yellow
        }
    }
    throw "No compatible TV system image found. Install one via SDK Manager and pass -ImageId."
}

function Ensure-Avd {
    param([string]$Name, [string]$ImagePkg)
    $avdman = Get-ToolPath "cmdline-tools\latest\bin\avdmanager.bat"
    $avdDir = "$Env:USERPROFILE\.android\avd\$Name.avd"
    if (Test-Path $avdDir) { Write-Host "[avd] $Name exists" -ForegroundColor Yellow; return }
    Write-Host "[avd] Creating $Name..." -ForegroundColor Cyan
    (echo no) | & $avdman create avd -n $Name -k $ImagePkg --device tv_1080p | Out-Null
    # Ensure DPAD + keyboard (so arrow keys act as remote) in config.ini
    try {
        $cfg = "$avdDir\config.ini"
        if (Test-Path $cfg) {
            (Get-Content $cfg) |
              ForEach-Object { $_ } | Set-Content $cfg
            Add-Content -Path $cfg -Value "hw.dPad=yes"
            Add-Content -Path $cfg -Value "hw.keyboard=yes"
            Add-Content -Path $cfg -Value "hw.trackBall=no"
            Add-Content -Path $cfg -Value "keyboard.charmap=qwerty2"
        }
    } catch {}
}

function Start-Emu {
    param([string]$Name, [int]$Port)
    $emu = Get-ToolPath "emulator\emulator.exe"
    Write-Host "[emu] Launching $Name on port $Port" -ForegroundColor Cyan
    Start-Process -FilePath $emu -ArgumentList @("-avd", $Name, "-port", $Port, "-no-boot-anim", "-no-snapshot", "-gpu", "swiftshader_indirect", "-accel", "on") -WindowStyle Minimized | Out-Null
}

function Wait-ForBoot {
    param([string]$Serial)
    $adb = Get-ToolPath "platform-tools\adb.exe"
    Write-Host "[adb] Waiting for $Serial..." -ForegroundColor Cyan
    & $adb -s $Serial wait-for-device
    for ($i=0; $i -lt 120; $i++) {
        $ok = & $adb -s $Serial shell getprop sys.boot_completed 2>$null
        if ($ok -match "1") { Write-Host "[adb] $Serial booted" -ForegroundColor Green; return }
        Start-Sleep -Seconds 2
    }
    throw "Timeout waiting for device $Serial to boot"
}

function Install-And-Launch {
    param([string]$Serial)
    $adb = Get-ToolPath "platform-tools\adb.exe"
    if (-not (Test-Path $ApkPath)) { throw "APK not found at $ApkPath. Build it first." }
    Write-Host "[adb] Installing $ApkPath on $Serial..." -ForegroundColor Cyan
    & $adb -s $Serial install -r -d "$ApkPath" | Out-Null
    Write-Host "[adb] Launching $AppPackage on $Serial" -ForegroundColor Cyan
    & $adb -s $Serial shell monkey -p $AppPackage -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
}

try {
    Resolve-SdkRoot
    Write-Host "SDK: $SdkRoot" -ForegroundColor DarkGray
    $chosenImg = Ensure-SystemImage
    Ensure-Avd -Name $AvdNameA -ImagePkg $chosenImg
    Ensure-Avd -Name $AvdNameB -ImagePkg $chosenImg

    # Start emulators on fixed ports so serials are deterministic
    Start-Emu -Name $AvdNameA -Port 5554
    Start-Emu -Name $AvdNameB -Port 5556

    # Wait for boot
    Wait-ForBoot -Serial "emulator-5554"
    Wait-ForBoot -Serial "emulator-5556"

    # Install and launch app
    Install-And-Launch -Serial "emulator-5554"
    Install-And-Launch -Serial "emulator-5556"

    Write-Host "Done. Both emulators running with app launched." -ForegroundColor Green
} catch {
    Write-Error $_
    exit 1
}
