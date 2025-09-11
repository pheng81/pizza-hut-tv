param(
  [int]$Port1 = 5554,
  [int]$Port2 = 5556,
  [string]$AppId = 'com.pizzahut.tv'
)

Write-Host "Installing APK to emulator-$Port1 and emulator-$Port2..." -ForegroundColor Cyan

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { $sdk = 'C:\Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android SDK." }
  return $sdk
}

function Get-Adb([string]$sdk){ $p = Join-Path $sdk 'platform-tools\adb.exe'; if(-not (Test-Path $p)){ throw "adb.exe not found at $p" }; return $p }

function Wait-Boot([string]$adb, [string]$serial){
  Write-Host "Waiting for $serial to boot..." -ForegroundColor DarkGray
  & $adb -s $serial wait-for-device | Out-Null
  for($i=0; $i -lt 180; $i++){
    $v = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
    if ($v -eq '1') { Write-Host "$serial booted" -ForegroundColor Green; return }
    Start-Sleep -Seconds 2
  }
  Write-Warning "$serial boot wait timeout; continuing"
}

function Find-DebugApk {
  $root = Split-Path -Parent $PSScriptRoot
  $dir = Join-Path $root 'android_tv_app\app\build\outputs\apk\debug'
  if (-not (Test-Path $dir)) { throw "APK output dir not found: $dir (build first)" }
  $apk = Get-ChildItem -Path $dir -Filter *-debug.apk -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if(-not $apk){ throw "Debug APK not found under $dir" }
  return $apk.FullName
}

try {
  $sdk = Resolve-SdkPath
  $adb = Get-Adb $sdk
  & $adb start-server | Out-Null
  Wait-Boot $adb "emulator-$Port1"; Wait-Boot $adb "emulator-$Port2"
  $apk = Find-DebugApk
  Write-Host "Installing: $apk" -ForegroundColor Yellow
  & $adb -s "emulator-$Port1" install -r "$apk"
  & $adb -s "emulator-$Port2" install -r "$apk"
  Write-Host "Launching app on both emulators..." -ForegroundColor Yellow
  & $adb -s "emulator-$Port1" shell monkey -p $AppId -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
  & $adb -s "emulator-$Port2" shell monkey -p $AppId -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
  Write-Host "Done: installed and launched on emulator-$Port1 and emulator-$Port2" -ForegroundColor Green
}
catch {
  Write-Error $_
  exit 1
}
