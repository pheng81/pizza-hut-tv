param(
  [string[]]$Avds = @('androidTv31','signageTvA','Television_4K_API_36','androidTv31b'),
  [int]$BasePort = 5640,
  [switch]$Build,
  [switch]$Install,
  [switch]$Launch,
  [switch]$NoAccel,
  [string]$SdkRoot = $env:ANDROID_SDK_ROOT
)

Write-Host "Multi Android TV runner" -ForegroundColor Cyan

function Resolve-Sdk(){
  if([string]::IsNullOrWhiteSpace($SdkRoot)){
    $SdkRoot = Join-Path $env:LOCALAPPDATA 'Android\\Sdk'
  }
  if(-not (Test-Path $SdkRoot)){ throw "Android SDK not found at $SdkRoot. Set ANDROID_SDK_ROOT or install SDK." }
  return $SdkRoot
}

function Paths($sdk){
  $o = [ordered]@{}
  $o.Emulator = Join-Path $sdk 'emulator\emulator.exe'
  $o.Adb      = Join-Path $sdk 'platform-tools\adb.exe'
  $o.SdkMgr   = Join-Path $sdk 'cmdline-tools\latest\bin\sdkmanager.bat'
  $o.AvdMgr   = Join-Path $sdk 'cmdline-tools\latest\bin\avdmanager.bat'
  foreach($k in $o.Keys){ if(-not (Test-Path $o[$k])){ Write-Warning "$k not found: $($o[$k])" } }
  return $o
}

function List-Avds($emu){
  try{ & $emu -list-avds }catch{ @() }
}

function Ensure-AvdsExist($emu, [string[]]$names){
  $existing = List-Avds $emu
  $present = @()
  foreach($n in $names){ if($existing -contains $n){ $present += $n } else { Write-Warning "AVD missing: $n (create it first)" } }
  return $present
}

function Build-Apk(){
  $appDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'android_tv_app'
  if(-not (Test-Path $appDir)){ throw "android_tv_app not found: $appDir" }
  Push-Location $appDir
  try{
    $gradle = Join-Path $appDir 'gradlew.bat'
    if(-not (Test-Path $gradle)){ throw "gradlew.bat missing in $appDir" }
    & $gradle :app:assembleDebug
    if($LASTEXITCODE -ne 0){ throw "Gradle build failed" }
    $apk = Join-Path $appDir 'app\build\outputs\apk\debug\app-debug.apk'
    if(-not (Test-Path $apk)){ throw "APK missing after build: $apk" }
    return $apk
  } finally { Pop-Location }
}

function Start-Emulators($emu, [string[]]$names, [int]$BasePort, [switch]$NoAccel){
  $ports = @()
  for($i=0;$i -lt $names.Count;$i++){
    $p = $BasePort + ($i*2)
    $ports += $p
    $accel = if($NoAccel){ '-accel off' } else { '' }
    $args = "-avd " + $names[$i] + " -port $p -no-snapshot -no-boot-anim -gpu auto -no-audio $accel"
    Write-Host ("Launching {0} on console {1} (adb emulator-{2})" -f $names[$i], $p, ($p+1)) -ForegroundColor Yellow
    Start-Process -FilePath $emu -ArgumentList $args | Out-Null
    Start-Sleep -Seconds 3
  }
  return $ports
}

function Wait-Boot($adb, [int[]]$ports, [int]$timeoutSec=600){
  foreach($p in $ports){
    $serial = "emulator-" + ($p+1)
    Write-Host "Waiting for $serial..." -ForegroundColor DarkGray
    & $adb -s $serial wait-for-device | Out-Null
    $t0 = Get-Date
    while($true){
      try{
        $v = (& $adb -s $serial shell getprop sys.boot_completed 2>$null).Trim()
        if($v -eq '1'){ break }
      }catch{}
      if(((Get-Date)-$t0).TotalSeconds -gt $timeoutSec){ Write-Warning "$serial boot timeout"; break }
      Start-Sleep -Seconds 2
    }
    Write-Host "Boot ok: $serial" -ForegroundColor Green
  }
}

function Install-Launch($adb, [int[]]$ports, [string]$apk){
  foreach($p in $ports){
    $serial = "emulator-" + ($p+1)
    if($apk){
      Write-Host "Installing on $serial..." -ForegroundColor Yellow
      & $adb -s $serial install -r "$apk" | Out-Null
    }
    Write-Host "Launching app on $serial..." -ForegroundColor Yellow
    # Try launcher first; fallback activity if needed
    & $adb -s $serial shell monkey -p com.pizzahut.tv -c android.intent.category.LAUNCHER 1 | Out-Null
  }
}

try{
  $sdk = Resolve-Sdk
  $p = Paths $sdk
  if(-not (Test-Path $p.Emulator)){ throw "emulator.exe missing at $($p.Emulator)" }
  if(-not (Test-Path $p.Adb)){ throw "adb.exe missing at $($p.Adb)" }

  $present = Ensure-AvdsExist $p.Emulator $Avds
  if($present.Count -eq 0){ throw "None of the requested AVDs exist. Create them with avdmanager or Android Studio." }

  $apk = $null
  if($Build){ $apk = Build-Apk } elseif($Install){
    $cand = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'android_tv_app') 'app\build\outputs\apk\debug\app-debug.apk'
    if(Test-Path $cand){ $apk = $cand } else { Write-Warning "APK not found; run with -Build to assemble it." }
  }

  $ports = Start-Emulators $p.Emulator $present $BasePort $NoAccel
  Wait-Boot $p.Adb $ports
  if($Install -or $Launch){ Install-Launch $p.Adb $ports $apk }

  Write-Host "Done. Devices:" -ForegroundColor Cyan
  & $p.Adb devices
}
catch{ Write-Error $_; exit 1 }
