param(
  [string]$Pkg = 'com.pizzahut.tv',
  [string]$ProjDir = 'C:\Users\toeng\Pizza Hut TV\android_tv_app',
  [string]$ApkPath = 'C:\Users\toeng\Pizza Hut TV\android_tv_app\app\build\outputs\apk\debug\app-debug.apk'
)

Write-Host "Reinstalling $Pkg on emulators..." -ForegroundColor Cyan

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { $sdk = 'C:\Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android SDK." }
  return $sdk
}

function Get-Adb([string]$sdk){ $p = Join-Path $sdk 'platform-tools\adb.exe'; if(-not (Test-Path $p)){ throw "adb.exe not found at $p" }; return $p }

function Wait-Boot([string]$adb, [string]$serial){
  & $adb -s $serial wait-for-device | Out-Null
  for($i=0; $i -lt 180; $i++){
    $v = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
    if ($v -eq '1') { return }
    Start-Sleep -Seconds 2
  }
  Write-Warning "$serial boot wait timeout; continuing"
}

function Build-ApkIfNeeded([string]$proj, [string]$apk){
  if(Test-Path $apk){ return }
  $gradlew = Join-Path $proj 'gradlew.bat'
  if(-not (Test-Path $gradlew)){ throw "gradlew not found in $proj; open project in Android Studio to build." }
  Write-Host "Building debug APK..." -ForegroundColor Yellow
  Push-Location $proj
  try { & $gradlew assembleDebug } finally { Pop-Location }
  if(-not (Test-Path $apk)){ throw "APK still missing after build: $apk" }
}

try {
  $sdk = Resolve-SdkPath
  $adb = Get-Adb $sdk
  & $adb start-server | Out-Null

  # Ensure emulators are running
  $devLines = (& $adb devices) -split "`n"
  $devices = @($devLines | Where-Object { $_ -match 'emulator-[0-9]+\s+device' } | ForEach-Object { ($_ -split '\s+')[0] })
  if(-not $devices -or $devices.Count -eq 0){
    $launcher = "C:\Users\toeng\Pizza Hut TV\scripts\run_two_android_tv_emulators.ps1"
    if(Test-Path $launcher){
      Write-Host "No emulators detected. Launching two Android TV emulators..." -ForegroundColor Yellow
      & $launcher | Out-Null
    } else {
      throw "No emulator devices detected. Start one and rerun."
    }
    Start-Sleep -Seconds 5
    $devLines = (& $adb devices) -split "`n"
    $devices = @($devLines | Where-Object { $_ -match 'emulator-[0-9]+\s+device' } | ForEach-Object { ($_ -split '\s+')[0] })
  }

  if(-not $devices -or $devices.Count -eq 0){ throw "No emulator devices detected after start." }

  Build-ApkIfNeeded -proj $ProjDir -apk $ApkPath

  foreach($d in $devices){
    Write-Host "Processing $d" -ForegroundColor Cyan
    Wait-Boot $adb $d
    Write-Host "Uninstalling $Pkg from $d" -ForegroundColor DarkYellow
    & $adb -s $d uninstall $Pkg 2>$null | Out-Null
    Write-Host "Installing APK on $d" -ForegroundColor Yellow
    & $adb -s $d install -r "$ApkPath"
    Write-Host "Launching (Leanback) on $d" -ForegroundColor Yellow
    & $adb -s $d shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
    Start-Sleep -Seconds 2
    $pid = (& $adb -s $d shell pidof $Pkg 2>$null).Trim()
    if([string]::IsNullOrWhiteSpace($pid)){
      Write-Host "  App not running yet; trying default LAUNCHER..." -ForegroundColor DarkYellow
      & $adb -s $d shell monkey -p $Pkg -c android.intent.category.LAUNCHER 1 | Out-Null
      Start-Sleep -Seconds 1
      $pid = (& $adb -s $d shell pidof $Pkg 2>$null).Trim()
    }
    if([string]::IsNullOrWhiteSpace($pid)){
      Write-Host "  Launch may have failed; check logcat." -ForegroundColor Red
    } else {
      Write-Host "  Running with PID: $pid" -ForegroundColor Green
    }
  }
  Write-Host "Reinstall complete." -ForegroundColor Green
}
catch {
  Write-Error $_
  exit 1
}
