# PowerShell script to download and install Android command line SDK + Android TV image
param(
    [string]$SdkRoot = "C:\Android\Sdk",
    [string]$ApiLevel = "34",
    [string]$ImageChannel = "android-tv",
    [string]$AvdName = "tv$ApiLevel"
)

Write-Host "[1] Ensuring base directories at $SdkRoot" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $SdkRoot | Out-Null
New-Item -ItemType Directory -Force -Path "$SdkRoot\cmdline-tools" | Out-Null

$Env:ANDROID_SDK_ROOT = $SdkRoot
$Env:ANDROID_HOME = $SdkRoot

# Known commandline tools release (adjust if outdated)
$toolsUrl = "https://dl.google.com/android/repository/commandlinetools-win-9477386_latest.zip"
$zipPath  = "$SdkRoot\cmdline-tools\commandlinetools.zip"

if (-not (Test-Path "$SdkRoot\cmdline-tools\latest\bin\sdkmanager.bat")) {
    Write-Host "[2] Downloading command line tools..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $toolsUrl -OutFile $zipPath -UseBasicParsing
    Write-Host "[3] Extracting..." -ForegroundColor Cyan
    Expand-Archive -Path $zipPath -DestinationPath "$SdkRoot\cmdline-tools" -Force
    if (Test-Path "$SdkRoot\cmdline-tools\cmdline-tools") {
        Rename-Item "$SdkRoot\cmdline-tools\cmdline-tools" "$SdkRoot\cmdline-tools\latest" -Force
    }
    Remove-Item $zipPath -Force
} else {
    Write-Host "[Skip] Command line tools already present" -ForegroundColor Yellow
}

$toolsBin = "$SdkRoot\cmdline-tools\latest\bin"
$Env:PATH = "$SdkRoot\platform-tools;$SdkRoot\emulator;$toolsBin;" + $Env:PATH

if (-not (Test-Path "$toolsBin\sdkmanager.bat")) { Write-Error "sdkmanager not found; aborting"; exit 1 }

Write-Host "[4] Accepting licenses (auto)" -ForegroundColor Cyan
# Auto-accept licenses
for ($i=0; $i -lt 10; $i++) { $accept += "y`n" }
$accept | & "$toolsBin\sdkmanager.bat" --licenses *> "$SdkRoot\licenses.log"

Write-Host "[5] Installing required packages" -ForegroundColor Cyan
$packages = @(
    "platform-tools",
    "emulator",
    "platforms;android-$ApiLevel",
    "build-tools;$ApiLevel.0.0",
    "system-images;android-$ApiLevel;$ImageChannel;x86_64"
)
& "$toolsBin\sdkmanager.bat" $packages *> "$SdkRoot\install.log"

Write-Host "[6] Verifying adb" -ForegroundColor Cyan
$adbPath = (Get-Command adb -ErrorAction SilentlyContinue).Source
if (-not $adbPath) { Write-Warning "adb not found on PATH yet" } else { Write-Host "adb at $adbPath" -ForegroundColor Green }

Write-Host "[7] Creating AVD $AvdName (if missing)" -ForegroundColor Cyan
$avdDir = "$Env:USERPROFILE\.android\avd\$AvdName.avd"
if (-not (Test-Path $avdDir)) {
    # Avoid interactive hardware profile question
    (echo no) | & "$toolsBin\avdmanager.bat" create avd -n $AvdName -k "system-images;android-$ApiLevel;$ImageChannel;x86_64" --device tv_1080p *> "$SdkRoot\avd_create.log"
} else {
    Write-Host "[Skip] AVD already exists" -ForegroundColor Yellow
}

Write-Host "Done. To launch emulator run:`nemulator -avd $AvdName" -ForegroundColor Green
