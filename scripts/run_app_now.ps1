# Build, install, and launch the Android TV app on running emulators
param(
  [string]$Activity = '.TvDisplayActivity'
)

$Sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$Adb = Join-Path $Sdk 'platform-tools\adb.exe'
$Gradlew = 'C:\Users\toeng\Pizza Hut TV\android_tv_app\gradlew.bat'
$ProjDir = 'C:\Users\toeng\Pizza Hut TV\android_tv_app'
$Apk = 'C:\Users\toeng\Pizza Hut TV\android_tv_app\app\build\outputs\apk\debug\app-debug.apk'
$Pkg = 'com.pizzahut.tv'

if(!(Test-Path $Adb)) { Write-Host "adb not found: $Adb"; exit 1 }

# Build APK if missing
if(!(Test-Path $Apk)){
  if(Test-Path $Gradlew){
    Write-Host 'Building debug APK...'
    Push-Location $ProjDir
    & $Gradlew assembleDebug
    $code = $LASTEXITCODE
    Pop-Location
    if($code -ne 0){ Write-Error 'Gradle build failed'; exit 1 }
  } else {
    Write-Host 'gradlew not found; open project in Android Studio to build.'
    exit 1
  }
}

if(!(Test-Path $Apk)){ Write-Host "APK still missing: $Apk"; exit 1 }

Write-Host 'Devices before install:'
& $Adb devices

# Pick only emulator-* devices
$devices = (& $Adb devices) -split "`n" | Where-Object { $_ -match 'emulator-[0-9]+\s+device' } | ForEach-Object { ($_ -split '\s+')[0] }

# If none, try to start two Android TV emulators
if(-not $devices -or $devices.Count -eq 0){
  $launcher = 'C:\Users\toeng\Pizza Hut TV\scripts\run_two_android_tv_emulators.ps1'
  if(Test-Path $launcher){
    Write-Host 'No emulators detected; starting two Android TV emulators...'
    & $launcher
  } else {
    Write-Host 'No emulator devices detected. Start one and rerun.'
    exit 1
  }
  # Refresh device list after attempting launch
  Start-Sleep -Seconds 2
  & $Adb start-server | Out-Null
  $devices = (& $Adb devices) -split "`n" | Where-Object { $_ -match 'emulator-[0-9]+\s+device' } | ForEach-Object { ($_ -split '\s+')[0] }
}

if(-not $devices){ Write-Host 'No emulator devices detected after launch. Start one and rerun.'; exit 1 }

foreach($d in $devices){
  Write-Host "Processing $d"
  # Wait boot
  for($i=0;$i -lt 180;$i++){
    $bc = (& $Adb -s $d shell getprop sys.boot_completed 2>$null).Trim()
    if($bc -eq '1'){ Write-Host "$d boot complete"; break }
    Start-Sleep -Seconds 2
    if($i -eq 179){ Write-Host "$d boot timeout"; continue }
  }
  Write-Host "Installing APK on $d"
  & $Adb -s $d install -r "$Apk"
  Write-Host "Launching app on $d"
  # Prefer Leanback launcher; fallback to generic launcher
  $res = & $Adb -s $d shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 2>&1
  if($LASTEXITCODE -ne 0){ & $Adb -s $d shell monkey -p $Pkg -c android.intent.category.LAUNCHER 1 | Out-Null }
  Write-Host 'Check running activity:'
  & $Adb -s $d shell dumpsys activity activities | Select-String $Pkg -SimpleMatch | Select -First 3
}

Write-Host 'Done.'
