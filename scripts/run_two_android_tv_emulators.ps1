param(
  [string]$StoreId = "",
  [string]$Code = "",
  [switch]$OpenWebplayer,
  # Android TV for API 34 ships x86 only; prefer that by default
  [string]$SystemImage = "system-images;android-34;android-tv;x86",
  [string]$Device = "tv_1080p",
  [int]$Port1 = 5554,
  [int]$Port2 = 5556,
  [switch]$NoAccel
)

Write-Host "Launching two Android TV emulators..." -ForegroundColor Cyan

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) {
    $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
  }
  if (-not (Test-Path $sdk)) {
    $sdk = 'C:\Android\Sdk'
  }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android Studio/SDK." }
  return $sdk
}

function Resolve-Tool([string]$sdk, [string]$rel){
  $p = Join-Path $sdk $rel
  if (Test-Path $p) { return $p }
  return $null
}

function Get-SdkManager([string]$sdk){
  $paths = @(
    'cmdline-tools\latest\bin\sdkmanager.bat',
    'cmdline-tools\bin\sdkmanager.bat'
  )
  foreach($rel in $paths){ $p = Resolve-Tool $sdk $rel; if($p){ return $p } }
  throw "sdkmanager.bat not found under $sdk. Install Android SDK cmdline-tools."
}

function Get-AvdManager([string]$sdk){
  $paths = @(
    'cmdline-tools\latest\bin\avdmanager.bat',
    'cmdline-tools\bin\avdmanager.bat'
  )
  foreach($rel in $paths){ $p = Resolve-Tool $sdk $rel; if($p){ return $p } }
  throw "avdmanager.bat not found under $sdk."
}

function Get-Emulator([string]$sdk){
  $p = Resolve-Tool $sdk 'emulator\emulator.exe'
  if(-not $p){ throw "emulator.exe not found under $sdk\emulator" }
  return $p
}

function Get-Adb([string]$sdk){
  $p = Resolve-Tool $sdk 'platform-tools\adb.exe'
  if(-not $p){ throw "adb.exe not found under $sdk\platform-tools" }
  return $p
}

function Ensure-SdkComponents($sdkmanager, $SystemImage){
  Write-Host "Ensuring SDK components are installed... (accepting licenses)" -ForegroundColor Yellow
  try {
    # Accept licenses non-interactively
    'y' * 200 | & $sdkmanager --licenses | Out-Null
  } catch { }
  & $sdkmanager --install "platform-tools" "emulator" "platforms;android-34" "$SystemImage" | Out-Null
}

function Ensure-Avd($avdmanager, [string]$name, [string]$SystemImage, [string]$Device){
  $avdDir = Join-Path $HOME ".android\avd\$name.avd"
  if (Test-Path $avdDir) { return }
  Write-Host "Creating AVD $name..." -ForegroundColor Yellow
  $ok = $true
  try {
    # Avoid interactive hardware profile question by piping 'no'
    echo no | & $avdmanager create avd -n $name -k $SystemImage --device $Device | Out-Null
  } catch {
    $ok = $false
  }
  if(-not $ok){
    Write-Host "Retrying AVD creation with fallback device id..." -ForegroundColor DarkYellow
  try { echo no | & $avdmanager create avd -n $name -k $SystemImage --device "Android TV (1080p)" | Out-Null } catch {}
  }
  # Ensure hardware keyboard input is enabled to allow PC keyboard to send DPAD/ENTER
  try {
    $cfg = Join-Path $HOME ".android\avd\$name.avd\config.ini"
    if (Test-Path $cfg) {
      $txt = Get-Content $cfg -Raw
      if ($txt -notmatch 'hw.keyboard=') { Add-Content -Path $cfg -Value "hw.keyboard=yes" }
      else { (Get-Content $cfg) | ForEach-Object { $_ -replace '^hw\.keyboard=.*$', 'hw.keyboard=yes' } | Set-Content $cfg }
    }
  } catch {}
}

function Start-Emu($emulator, [string]$avd, [int]$port){
  $accel = if($NoAccel){ '-accel off' } else { '' }
  $args = "-avd $avd -port $port -no-snapshot -gpu auto -no-audio -no-boot-anim -netdelay none -netspeed full $accel"
  Write-Host "Starting $avd on port $port" -ForegroundColor Yellow
  Start-Process -FilePath $emulator -ArgumentList $args | Out-Null
  return "emulator-$port"
}

function Wait-Emu([string]$adb, [string]$serial){
  Write-Host "Waiting for $serial..." -ForegroundColor DarkGray
  & $adb -s $serial wait-for-device | Out-Null
  $max = 120
  for($i=0; $i -lt $max; $i++){
    $v = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
    if ($v -eq '1') { return }
    Start-Sleep -Seconds 2
  }
  Write-Warning "$serial boot wait timeout (continuing)"
}

function KeepAwake([string]$adb, [string]$serial){
  & $adb -s $serial shell svc power stayon true | Out-Null
}

function Open-WebPlayer([string]$adb, [string]$serial, [string]$StoreId, [string]$Code){
  if([string]::IsNullOrWhiteSpace($StoreId)){ return }
  $base = "https://api.everydayadvertise.com/webplayer/play"
  $sid  = "${StoreId}_screen" + ($(if($serial -match '5554'){ '1' } else { '2' }))
  $url  = "$base?store_id=$StoreId&screen_id=$sid" + ($(if([string]::IsNullOrWhiteSpace($Code)){ '' } else { "&code=$Code" }))
  & $adb -s $serial shell am start -a android.intent.action.VIEW -d $url | Out-Null
}

try {
  $sdk = Resolve-SdkPath
  $sdkmanager = Get-SdkManager $sdk
  $avdmanager = Get-AvdManager $sdk
  $emulator   = Get-Emulator   $sdk
  $adb        = Get-Adb        $sdk

  Ensure-SdkComponents $sdkmanager $SystemImage
  Ensure-Avd $avdmanager 'TV1' $SystemImage $Device
  Ensure-Avd $avdmanager 'TV2' $SystemImage $Device

  $s1 = Start-Emu $emulator 'TV1' $Port1
  $s2 = Start-Emu $emulator 'TV2' $Port2

  Wait-Emu $adb $s1; Wait-Emu $adb $s2
  KeepAwake $adb $s1; KeepAwake $adb $s2

  if($OpenWebplayer){
    Open-WebPlayer $adb $s1 $StoreId $Code
    Open-WebPlayer $adb $s2 $StoreId $Code
  }

  Write-Host "Emulators ready: $s1, $s2" -ForegroundColor Green
  Write-Host "Stop with: `n  adb -s $s1 emu kill`n  adb -s $s2 emu kill" -ForegroundColor DarkGray
}
catch {
  Write-Error $_
  exit 1
}
