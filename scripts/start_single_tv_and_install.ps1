param(
  [string]$AvdName = 'Television_4K_API_36',
  [string]$Pkg = 'com.pizzahut.tv',
  [int]$Port = 5554
)

Write-Host "Starting Android TV emulator and installing app..." -ForegroundColor Cyan

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { $sdk = 'C:\Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android SDK." }
  return $sdk
}

function Get-Tool([string]$sdk, [string]$rel){
  $p = Join-Path $sdk $rel
  if(-not (Test-Path $p)){ throw "$rel not found under $sdk" }
  return $p
}

function Ensure-AvdExists([string]$emulatorExe, [string]$name){
  $avds = & $emulatorExe -list-avds 2>$null
  if(($avds | Out-String) -notmatch [regex]::Escape($name)){
    Write-Warning "AVD '$name' not found. Falling back to 'TV1' if available; otherwise run scripts/run_two_android_tv_emulators.ps1 first."
    return $false
  }
  return $true
}

function Wait-Boot([string]$adb, [string]$serial){
  & $adb -s $serial wait-for-device | Out-Null
  $max=300
  for($i=0; $i -lt $max; $i++){
    try {
      $bc = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
      $dbc = (& $adb -s $serial shell getprop dev.bootcomplete 2>$null).Trim()
      if($bc -eq '1' -or $dbc -eq '1'){ return }
    } catch {}
    Start-Sleep -Seconds 2
  }
  throw "Emulator $serial did not complete boot in time"
}

try {
  $sdk = Resolve-SdkPath
  $adb = Get-Tool $sdk 'platform-tools\adb.exe'
  $emulator = Get-Tool $sdk 'emulator\emulator.exe'

  # Start server
  & $adb start-server | Out-Null

  # Kill any existing emulator on this port to avoid conflicts
  $serial = "emulator-$Port"
  $cur = (& $adb devices) -split "`n" | Where-Object { $_ -match "^$serial\s" }
  if($cur){ & $adb -s $serial emu kill 2>$null | Out-Null; Start-Sleep -Seconds 2 }

  $hasAvd = Ensure-AvdExists $emulator $AvdName
  if(-not $hasAvd){ $AvdName = 'TV1' }

  Write-Host "Starting AVD '$AvdName' on port $Port..." -ForegroundColor Yellow
  Start-Process -FilePath $emulator -ArgumentList @('-avd', $AvdName, '-port', $Port, '-no-snapshot', '-gpu', 'auto', '-no-boot-anim', '-netdelay', 'none', '-netspeed', 'full', '-no-audio') | Out-Null

  Write-Host "Waiting for $serial to boot..." -ForegroundColor Yellow
  Wait-Boot $adb $serial
  Write-Host "Emulator booted." -ForegroundColor Green

  # Build APK
  $proj = 'C:\Users\toeng\Pizza Hut TV\android_tv_app'
  $gradlew = Join-Path $proj 'gradlew.bat'
  if(-not (Test-Path $gradlew)){ throw "Gradle wrapper not found at $gradlew" }
  Write-Host 'Building :app:assembleDebug...' -ForegroundColor Cyan
  Push-Location $proj
  cmd /c "gradlew.bat :app:assembleDebug --no-daemon --console=plain" | Write-Host
  $code = $LASTEXITCODE
  Pop-Location
  if($code -ne 0){ throw "Gradle build failed with exit code $code" }

  # Install APK
  $apk = Join-Path $proj 'app\build\outputs\apk\debug\app-debug.apk'
  if(-not (Test-Path $apk)){ throw "APK not found at $apk" }
  Write-Host "Installing APK to $serial..." -ForegroundColor Cyan
  & $adb -s $serial install -r -t "$apk"

  # Launch app (Leanback)
  Write-Host "Launching $Pkg..." -ForegroundColor Cyan
  & $adb -s $serial shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
  Write-Host "Launched. If not visible, press Home and select Pizza Hut TV." -ForegroundColor Green
}
catch {
  Write-Error $_
  exit 1
}
