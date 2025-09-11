param(
  [string]$Pkg = 'com.pizzahut.tv',
  [string]$Activity = '',  # optional fully-qualified or .ActivityName
  [string]$StoreId = '1000',
  [string]$ScreenId = 'screen4',
  [string]$PairCode = '1340',
  [string]$BaseUrl = '',
  [switch]$TailLogs,
  [switch]$Rebuild,
  [int]$Port1 = 5554,
  [int]$Port2 = 5556,
  [string[]]$AvdNames = @('Television_4K_API_36'),   # preferred TV AVD(s)
  [switch]$NoAccel                                     # force software if host GPU unstable
)

Write-Host "Running app on emulators..." -ForegroundColor Cyan

# Project paths used for Gradle operations
$projDir = "C:\Users\toeng\Pizza Hut TV\android_tv_app"
$gradlew = Join-Path $projDir 'gradlew.bat'

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { $sdk = 'C:\Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android SDK." }
  return $sdk
}

function Get-Adb([string]$sdk){ $p = Join-Path $sdk 'platform-tools\adb.exe'; if(-not (Test-Path $p)){ throw "adb.exe not found at $p" }; return $p }
function Get-Emu([string]$sdk){ $p = Join-Path $sdk 'emulator\emulator.exe'; if(-not (Test-Path $p)){ throw "emulator.exe not found at $p" }; return $p }

function Start-Avd([string]$emu, [string]$name, [int]$port, [switch]$NoAccel){
  $gpu = 'host'
  if($NoAccel){ $gpu = 'swiftshader_indirect' }
  $args = @(
    '-avd', $name,
    '-port', $port,
    '-no-snapshot','-no-boot-anim','-no-audio',
    '-gpu', $gpu
  )
  if($NoAccel){ $args += @('-accel','off') }
  Start-Process -FilePath $emu -ArgumentList $args | Out-Null
  Start-Sleep 3
}

function Wait-Boot([string]$adb, [string]$serial){
  # recover from "offline"
  for($t=0;$t -lt 5;$t++){
    & $adb -s $serial wait-for-device | Out-Null
    $state = ((& $adb -s $serial get-state 2>$null) | Out-String).Trim()
    if($state -eq 'device'){ break }
    Start-Sleep 2
  }
  # wait for sys.boot_completed
  for($i=0; $i -lt 240; $i++){
    $v = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
    if ($v -eq '1') { return }
    Start-Sleep -Seconds 2
  }
  Write-Warning "$serial boot wait timeout; continuing"
}

function Build-ApkIfMissing {
  $projDir = "C:\Users\toeng\Pizza Hut TV\android_tv_app"
  $gradlew = Join-Path $projDir 'gradlew.bat'
  # Try to locate an existing debug APK first
  $apkDir = Join-Path $projDir 'app\build\outputs\apk'
  $apk = $null
  try {
    if (Test-Path $apkDir) {
      $apk = Get-ChildItem -Path $apkDir -Recurse -Filter *.apk -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { $_.FullName }
    }
  } catch {}
  if($apk -and (Test-Path $apk) -and -not $Rebuild){ return $apk }
  if(-not (Test-Path $gradlew)){ throw "gradlew not found; open project in Android Studio to build." }
  $msg = "Building debug APK..."
  if($Rebuild){ $msg += " (forced)" }
  if(-not [string]::IsNullOrWhiteSpace($BaseUrl)){ $msg += " (BaseUrl=$BaseUrl)" }
  Write-Host $msg -ForegroundColor Yellow
  Push-Location $projDir
  try {
    if($Rebuild){ & $gradlew clean | Out-Null }
    if(-not [string]::IsNullOrWhiteSpace($BaseUrl)){
      & $gradlew assembleDebug -P "PHTV_BASE_URL=$BaseUrl"
    } else {
      & $gradlew assembleDebug
    }
  } finally { Pop-Location }
  # Re-scan for the newest APK after build
  try {
    if (Test-Path $apkDir) {
      $apk = Get-ChildItem -Path $apkDir -Recurse -Filter *.apk -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { $_.FullName }
    }
  } catch {}
  if(-not $apk -or -not (Test-Path $apk)){ throw "APK not found under $apkDir after build." }
  return $apk
}

try {
  $sdk = Resolve-SdkPath
  $adb = Get-Adb $sdk
  $emu = Get-Emu $sdk
  & $adb kill-server | Out-Null
  & $adb start-server | Out-Null

  # Start emulators if none are running
  $devLines = (& $adb devices) -split "`n"
  $devices = @($devLines | Where-Object { $_ -match 'emulator-[0-9]+\s+(device|offline)' } | ForEach-Object { ($_ -split '\s+')[0] })
  if(-not $devices -or $devices.Count -eq 0){
    Write-Host "No emulators detected. Starting AVD '$($AvdNames[0])' on port $Port1 ..." -ForegroundColor Yellow
    Start-Avd $emu $AvdNames[0] $Port1 $NoAccel
    Start-Sleep -Seconds 5
    # Re-enumerate after start
    $devLines = (& $adb devices) -split "`n"
    $devices = @($devLines | Where-Object { $_ -match 'emulator-[0-9]+\s+(device|offline)' } | ForEach-Object { ($_ -split '\s+')[0] })
  }

  if(-not $devices -or $devices.Count -eq 0){ throw "No emulator devices detected after start." }

  $apkPath = Build-ApkIfMissing
  # sanitize
  if($apkPath){ $apkPath = $apkPath.Trim() }
  Write-Host "Devices: $($devices -join ', ')" -ForegroundColor Green
  if([string]::IsNullOrWhiteSpace($apkPath) -or ($apkPath -notmatch '\.apk$')){
    Write-Warning "APK path invalid or empty after build. Will try Gradle installDebug."
    $apkPath = ''
  } else {
    Write-Host "Using APK: $apkPath" -ForegroundColor DarkGray
    if(-not (Test-Path -LiteralPath $apkPath)){
      Write-Warning "APK not found at $apkPath. Falling back to Gradle :app:installDebug."
      $apkPath = ''
    }
  }

  foreach($d in $devices){
    Write-Host "Processing $d" -ForegroundColor Cyan
    Wait-Boot $adb $d
    # keep screen on + unlock
    & $adb -s $d shell svc power stayon true | Out-Null
    & $adb -s $d shell input keyevent 82 | Out-Null
    if([string]::IsNullOrWhiteSpace($apkPath)){
      Write-Host "Gradle installing on $d (:app:installDebug)" -ForegroundColor Yellow
      Push-Location $projDir
      try { & $gradlew ":app:installDebug" } finally { Pop-Location }
    } else {
      Write-Host "Installing APK on $d" -ForegroundColor Yellow
      & $adb -s $d install -r -t "$apkPath" | Out-Null
    }
    Write-Host "Launching app on $d" -ForegroundColor Yellow
    # Clear logs prior to launch if tailing later
    if($TailLogs){ & $adb -s $d logcat -c | Out-Null }
    $useExtras = -not [string]::IsNullOrWhiteSpace($StoreId) -or -not [string]::IsNullOrWhiteSpace($ScreenId) -or -not [string]::IsNullOrWhiteSpace($PairCode)
    if([string]::IsNullOrWhiteSpace($Activity)){
      if(-not [string]::IsNullOrWhiteSpace($PairCode)){
        $Activity = '.SetupActivity'
      } elseif(-not [string]::IsNullOrWhiteSpace($StoreId) -or -not [string]::IsNullOrWhiteSpace($ScreenId)){
        $Activity = '.TvDisplayActivity'
      }
    }
    if(-not [string]::IsNullOrWhiteSpace($Activity)){
      # If $Activity starts with '.', prefix with package name
      $act = if($Activity.StartsWith('.')){ "$Pkg$Activity" } else { $Activity }
      $args = @('shell','am','start','-n',"$Pkg/$act")
      if($useExtras){
        if(-not [string]::IsNullOrWhiteSpace($StoreId)){ $args += @('--es','storeId',$StoreId) }
        if(-not [string]::IsNullOrWhiteSpace($ScreenId)){ $args += @('--es','screenId',$ScreenId) }
        if(-not [string]::IsNullOrWhiteSpace($PairCode)){ $args += @('--es','pairCode',$PairCode) }
      }
      & $adb -s $d @args | Out-Null
    } else {
      & $adb -s $d shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
    }
    Write-Host "Top activity (snippet):" -ForegroundColor DarkGray
    & $adb -s $d shell dumpsys activity activities | Select-String $Pkg -SimpleMatch | Select -First 3
    if($TailLogs){
      # Wait a bit longer so the app can fetch playlist and start playback
      Start-Sleep -Seconds 8
      Write-Host "Recent logs (PHTV/ExoPlayer/AndroidRuntime):" -ForegroundColor DarkGray
      & $adb -s $d logcat -d | Select-String -Pattern 'PHTV|ExoPlayer|AndroidRuntime|FATAL EXCEPTION' | Select-Object -Last 200
      # One more pass a few seconds later
      Start-Sleep -Seconds 5
      Write-Host "More logs:" -ForegroundColor DarkGray
      & $adb -s $d logcat -d | Select-String -Pattern 'PHTV|ExoPlayer|AndroidRuntime|FATAL EXCEPTION' | Select-Object -Last 200
  Write-Host "Raw tail (last 200 lines):" -ForegroundColor DarkGray
  & $adb -s $d logcat -d | Select-Object -Last 200
    }
  }
  Write-Host "Done." -ForegroundColor Green
}
catch {
  Write-Error $_
  exit 1
}
