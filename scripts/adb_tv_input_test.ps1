param(
  [string]$Pkg = 'com.pizzahut.tv',
  [string]$Text = '1126'
)

Write-Host "ADB TV input test..." -ForegroundColor Cyan

function Resolve-SdkPath {
  $sdk = $env:ANDROID_SDK_ROOT
  if (-not $sdk -or -not (Test-Path $sdk)) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
  if (-not (Test-Path $sdk)) { $sdk = 'C:\Android\Sdk' }
  if (-not (Test-Path $sdk)) { throw "Android SDK not found." }
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
    # Bring app to foreground via Leanback
    & $adb -s $d shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
    Start-Sleep -Seconds 1
    # Dump focused window/activity
    Write-Host "Focused window:" -ForegroundColor DarkGray
    & $adb -s $d shell dumpsys window | Select-String mCurrentFocus -SimpleMatch | Select -First 1
    # Send text and ENTER
    Write-Host "Sending text '$Text' and ENTER" -ForegroundColor DarkGray
    & $adb -s $d shell input text $Text
    & $adb -s $d shell input keyevent KEYCODE_ENTER
  }
}
catch {
  Write-Error $_
  exit 1
}
