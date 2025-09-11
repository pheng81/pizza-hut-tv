param(
  [switch]$Clean,
  [string]$GradleProps = "",
  [string]$StoreId = "",
  [string]$Screen1 = "",
  [string]$Screen2 = "",
  [string]$Code = "",
  [int]$Port1 = 5554,
  [int]$Port2 = 5556
)

Write-Host "Building and installing Android TV app on two emulators..." -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $root 'android_tv_app'
if (-not (Test-Path $appDir)) { throw "android_tv_app not found at $appDir" }

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android Studio/SDK." }
  return $sdk
}

function Get-Adb([string]$sdk){ $p = Join-Path $sdk 'platform-tools\adb.exe'; if(-not (Test-Path $p)){ throw "adb.exe not found" }; return $p }
function Get-Emulator([string]$sdk){ $p = Join-Path $sdk 'emulator\emulator.exe'; if(-not (Test-Path $p)){ throw "emulator.exe not found" }; return $p }
function Get-Gradle([string]$dir){ $p = Join-Path $dir 'gradlew.bat'; if(-not (Test-Path $p)){ throw "gradlew.bat not found in $dir" }; return $p }

function Wait-Emu([string]$adb, [string]$serial){
  & $adb -s $serial wait-for-device | Out-Null
  for($i=0; $i -lt 120; $i++){
    $v = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
    if ($v -eq '1') { return }
    Start-Sleep -Seconds 2
  }
  Write-Warning "$serial boot wait timeout (continuing)"
}

function Ensure-Emu([string]$sdk){
  $emulator = Get-Emulator $sdk
  $adb = Get-Adb $sdk
  # If no running emulators, start two default ones using the other script
  $out = & $adb devices
  $running = ($out | Select-String 'emulator-\d+\s+device').Matches.Value
  if ($running.Count -lt 2) {
    $launcher = Join-Path $PSScriptRoot 'run_two_android_tv_emulators.ps1'
    if (Test-Path $launcher) {
      & $launcher | Out-Null
    } else {
      Write-Host "Please start two emulators (5554, 5556) before continuing." -ForegroundColor Yellow
    }
  }
  Wait-Emu $adb "emulator-$Port1"; Wait-Emu $adb "emulator-$Port2"
  return $adb
}

function Build-App([string]$gradle, [string]$dir, [switch]$Clean, [string]$GradleProps){
  Push-Location $dir
  try {
    if($Clean){ & $gradle clean }
    if([string]::IsNullOrWhiteSpace($GradleProps)){
      & $gradle assembleDebug
    } else {
      & $gradle assembleDebug $GradleProps
    }
    if ($LASTEXITCODE -ne 0) { throw "Gradle build failed" }
  } finally { Pop-Location }
}

function Find-Apk([string]$dir){
  $apk = Get-ChildItem -Path (Join-Path $dir 'app\build\outputs\apk\debug') -Filter *-debug.apk -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if(-not $apk){ throw "Debug APK not found. Check build outputs." }
  return $apk.FullName
}

function Get-AppId([string]$gradleFile){
  $txt = Get-Content $gradleFile -Raw
  $m = [regex]::Match($txt, "applicationId\s+'([^']+)'")
  if($m.Success){ return $m.Groups[1].Value }
  return 'com.pizzahut.tv'
}

function Install-And-Launch([string]$adb, [string]$serial, [string]$apk, [string]$appId, [string]$StoreId, [string]$ScreenId, [string]$Code){
  & $adb -s $serial install -r "$apk" | Out-Null
  # Build launch intent with optional extras
  $extras = @()
  if($StoreId){ $extras += "--es store_id $StoreId" }
  if($ScreenId){ $extras += "--es screen_id $ScreenId" }
  if($Code){ $extras += "--es code $Code" }
  $extraStr = ($extras -join ' ')
  # Try to launch MainActivity; if activity name unknown, use monkey as fallback
  $startCmd = "shell am start -n $appId/.MainActivity $extraStr"
  $res = & $adb -s $serial $startCmd 2>&1
  if($LASTEXITCODE -ne 0 -or ($res -join " `n") -notmatch 'Status: ok'){
    & $adb -s $serial shell monkey -p $appId -c android.intent.category.LAUNCHER 1 | Out-Null
  }
}

try {
  $sdk = Resolve-SdkPath
  $adb = Ensure-Emu $sdk
  $gradle = Get-Gradle $appDir
  Build-App $gradle $appDir $Clean $GradleProps
  $apk = Find-Apk $appDir
  $appId = Get-AppId (Join-Path $appDir 'app\build.gradle')

  if([string]::IsNullOrWhiteSpace($Screen1) -and $StoreId){ $Screen1 = "${StoreId}_screen1" }
  if([string]::IsNullOrWhiteSpace($Screen2) -and $StoreId){ $Screen2 = "${StoreId}_screen2" }

  Install-And-Launch $adb "emulator-$Port1" $apk $appId $StoreId $Screen1 $Code
  Install-And-Launch $adb "emulator-$Port2" $apk $appId $StoreId $Screen2 $Code
  Write-Host "Installed and launched on emulator-$Port1 and emulator-$Port2" -ForegroundColor Green
}
catch {
  Write-Error $_
  exit 1
}
