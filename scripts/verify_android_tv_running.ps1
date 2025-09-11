param(
  [string]$Pkg = 'com.pizzahut.tv'
)

Write-Host "Verifying Android TV app on emulators..." -ForegroundColor Cyan

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { $sdk = 'C:\Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found. Set ANDROID_SDK_ROOT or install Android SDK." }
  return $sdk
}

function Get-Adb([string]$sdk){ $p = Join-Path $sdk 'platform-tools\adb.exe'; if(-not (Test-Path $p)){ throw "adb.exe not found at $p" }; return $p }

try {
  $sdk = Resolve-SdkPath
  $adb = Get-Adb $sdk
  & $adb start-server | Out-Null
  $devLines = (& $adb devices) -split "`n"
  $devices = @($devLines | Where-Object { $_ -match 'emulator-[0-9]+\s+device' } | ForEach-Object { ($_ -split '\s+')[0] })
  if(-not $devices -or $devices.Count -eq 0){ throw "No emulator devices detected." }

  foreach($d in $devices){
    Write-Host "-- $d" -ForegroundColor Yellow
    $pm = & $adb -s $d shell pm path $Pkg 2>$null
    if([string]::IsNullOrWhiteSpace($pm)){
      Write-Host "  Package not installed: $Pkg" -ForegroundColor Red
    } else {
      Write-Host "  Package path: $pm" -ForegroundColor Green
    }
    Write-Host "  Launching (Leanback)..." -ForegroundColor DarkGray
    & $adb -s $d shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
    Start-Sleep -Seconds 2
    $pid = (& $adb -s $d shell pidof $Pkg 2>$null).Trim()
    if([string]::IsNullOrWhiteSpace($pid)){
      Write-Host "  Not running yet; trying default launcher..." -ForegroundColor DarkYellow
      & $adb -s $d shell monkey -p $Pkg -c android.intent.category.LAUNCHER 1 | Out-Null
      Start-Sleep -Seconds 2
      $pid = (& $adb -s $d shell pidof $Pkg 2>$null).Trim()
    }
    if([string]::IsNullOrWhiteSpace($pid)){
      Write-Host "  Still not running; check logs with: adb -s $d logcat" -ForegroundColor Red
    } else {
      Write-Host "  Running with PID: $pid" -ForegroundColor Cyan
    }
    Write-Host "  Top activity snippet:" -ForegroundColor DarkGray
    & $adb -s $d shell dumpsys activity activities | Select-String $Pkg -SimpleMatch | Select -First 3
  }
}
catch {
  Write-Error $_
  exit 1
}
