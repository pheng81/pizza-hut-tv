param(
  [string[]]$Avds = @('androidTv31','signageTvA','Television_4K_API_36','androidTv31b'),
  [int]$BasePort = 5640,
  [string]$SdkRoot = "$env:LOCALAPPDATA\Android\Sdk",
  [string]$ProjectRoot = "C:\Users\toeng\Pizza Hut TV\android_tv_app",
  [string]$ApkRelative = ".\app\build\outputs\apk\debug\app-debug.apk",
  [string]$Package = "com.pizzahut.tv",
  [int]$Desired = 0
)

$ErrorActionPreference = 'Stop'

function Add-ToPath([string]$p){ if(-not [string]::IsNullOrWhiteSpace($p) -and (Test-Path $p)){ $env:PATH = "$p;" + $env:PATH } }

$Emu = Join-Path $SdkRoot "emulator\emulator.exe"
$Adb = Join-Path $SdkRoot "platform-tools\adb.exe"
$Gradlew = Join-Path $ProjectRoot "gradlew.bat"

if(!(Test-Path $Emu)){ throw "Emulator not found at $Emu" }
if(!(Test-Path $Adb)){ throw "ADB not found at $Adb" }

$env:ANDROID_SDK_ROOT = $SdkRoot
$env:ANDROID_HOME = $SdkRoot
Add-ToPath (Join-Path $SdkRoot 'platform-tools')
Add-ToPath (Join-Path $SdkRoot 'emulator')
Add-ToPath (Join-Path $SdkRoot 'cmdline-tools\latest\bin')

Write-Host "Killing old emulator/adb..."
Start-Process -FilePath $Adb -ArgumentList 'kill-server' -NoNewWindow -Wait | Out-Null
Get-Process emulator -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Ensure adb daemon is running before launching emulators
& $Adb start-server | Out-Null
Start-Sleep -Seconds 1

Write-Host "Building APK (assembleDebug)..."
pushd $ProjectRoot
& $Gradlew :app:assembleDebug
if($LASTEXITCODE -ne 0){ throw "Gradle build failed ($LASTEXITCODE)" }
$Apk = Join-Path $ProjectRoot $ApkRelative
if(!(Test-Path $Apk)){ throw "APK missing at $Apk" }
popd

# Pre-compute ports
$Ports = for($i=0;$i -lt $Avds.Count; $i++){ $BasePort + ($i*2) }
if($Desired -le 0){ $Desired = [Math]::Max(1, $Avds.Count) }

Write-Host "Launching emulators..."
for($i=0;$i -lt $Avds.Count; $i++){
  $avd = $Avds[$i]
  $p = $Ports[$i]
  $console = $p
  $adbPort = [int]$p + 1
  Write-Host "$avd => console $console (adb emulator-$adbPort)"
  Start-Process -FilePath $Emu -ArgumentList @(
    '-avd',$avd,
    '-port',$console,
    '-no-snapshot-load','-no-snapshot-save','-no-boot-anim','-gpu','swiftshader_indirect','-read-only'
  ) -WindowStyle Minimized | Out-Null
  Start-Sleep -Seconds 5
}

# Re-confirm adb daemon started
& $Adb start-server | Out-Null

# Discover emulator device IDs dynamically from adb
function Get-EmulatorIds {
  try {
    $list = & $Adb devices 2>$null
    if(-not $list){ return @() }
    $ids = @()
    foreach($line in $list){
      if($line -match '^emulator-\d+\s+device'){ $ids += ($line -split '\s+')[0] }
    }
    return $ids
  } catch { return @() }
}

# Wait up to 6 minutes for desired number of emulators to be in 'device' state
$deadline = (Get-Date).AddMinutes(6)
do {
  $emulators = Get-EmulatorIds
  if($emulators.Count -ge $Desired){ break }
  Start-Sleep -Seconds 3
} while((Get-Date) -lt $deadline)

if($emulators.Count -eq 0){
  Write-Warning "No emulator devices appeared in adb in time."
} else {
  Write-Host "Detected emulator devices: $($emulators -join ', ') (count=$($emulators.Count))"
}

# For each detected emulator, wait for boot_completed then install & launch
foreach($adbId in $emulators){
  Write-Host "Waiting for $adbId to report boot_completed..."
  $bootDeadline = (Get-Date).AddMinutes(4)
  $bootOk = $false
  do {
    $state = ''
    try { $state = (& $Adb -s $adbId get-state 2>$null) } catch { $state = '' }
    if($state -ne 'device'){ Start-Sleep -Seconds 2; continue }
    $out = ''
    try { $out = (& $Adb -s $adbId shell getprop sys.boot_completed 2>$null) } catch { $out = '' }
    if($out){ $out = $out.Trim() }
    if($out -eq '1'){ $bootOk = $true; break }
    Start-Sleep -Seconds 2
  } while((Get-Date) -lt $bootDeadline)
  if(-not $bootOk){ Write-Warning "$adbId boot wait timed out"; continue }

  Write-Host "Boot complete: $adbId -> installing APK"
  try {
    & $Adb -s $adbId install -r $Apk | Write-Host
  } catch {
    Write-Warning ("Install failed on {0}: {1}" -f $adbId, $_.Exception.Message)
    continue
  }
  Write-Host "Launching $Package on $adbId"
  $launchOk = $false
  try {
    # Try explicit activity start first
    & $Adb -s $adbId shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$Package/.TvDisplayActivity" | Write-Host
    $launchOk = $true
  } catch {
    Write-Warning ("am start failed on {0}: {1}" -f $adbId, $_.Exception.Message)
  }
  if(-not $launchOk){
    try {
      # Fallback: monkey with LAUNCHER category
      & $Adb -s $adbId shell monkey -p $Package -c android.intent.category.LAUNCHER 1 | Write-Host
    } catch {
      Write-Warning ("Launch (monkey) failed on {0}: {1}" -f $adbId, $_.Exception.Message)
    }
  }
}

# Second pass: process any late-arriving emulator devices up to desired count
$late = Get-EmulatorIds | Where-Object { $emulators -notcontains $_ }
if($late.Count -gt 0){ Write-Host "Late emulator arrivals: $($late -join ', ')" }
foreach($adbId in $late){
  Write-Host "Waiting for $adbId to report boot_completed (late)..."
  $bootDeadline = (Get-Date).AddMinutes(3)
  $bootOk = $false
  do {
    $state = ''
    try { $state = (& $Adb -s $adbId get-state 2>$null) } catch { $state = '' }
    if($state -ne 'device'){ Start-Sleep -Seconds 2; continue }
    $out = ''
    try { $out = (& $Adb -s $adbId shell getprop sys.boot_completed 2>$null) } catch { $out = '' }
    if($out){ $out = $out.Trim() }
    if($out -eq '1'){ $bootOk = $true; break }
    Start-Sleep -Seconds 2
  } while((Get-Date) -lt $bootDeadline)
  if(-not $bootOk){ Write-Warning "$adbId boot wait timed out"; continue }

  Write-Host "Boot complete (late): $adbId -> installing APK"
  try {
    & $Adb -s $adbId install -r $Apk | Write-Host
  } catch {
    Write-Warning ("Install failed on {0}: {1}" -f $adbId, $_.Exception.Message)
    continue
  }
  Write-Host "Launching $Package on $adbId"
  $launchOk = $false
  try {
    & $Adb -s $adbId shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$Package/.TvDisplayActivity" | Write-Host
    $launchOk = $true
  } catch {
    Write-Warning ("am start failed on {0}: {1}" -f $adbId, $_.Exception.Message)
  }
  if(-not $launchOk){
    try {
      & $Adb -s $adbId shell monkey -p $Package -c android.intent.category.LAUNCHER 1 | Write-Host
    } catch {
      Write-Warning ("Launch (monkey) failed on {0}: {1}" -f $adbId, $_.Exception.Message)
    }
  }
}

# Connectivity test against local server (10.0.2.2 -> host)
$testId = (Get-EmulatorIds | Select-Object -First 1)
if($testId){
  Write-Host "Connectivity check from $testId to http://10.0.2.2:5002/"
  & $Adb -s $testId shell sh -c "toybox nc -z -v 10.0.2.2 5002 || (cmd -l -c 'curl -I http://10.0.2.2:5002/' 2>/dev/null)" | Write-Host
} else {
  Write-Host "Skipping connectivity test (no emulator detected)."
}

Write-Host "Done."