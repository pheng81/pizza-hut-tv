param(
  [string]$Device = '',
  [int]$Lines = 400,
  [string]$Pkg = 'com.pizzahut.tv'
)

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
  $devs = (& $adb devices) -split "`n" | Where-Object { $_ -match 'emulator-[0-9]+\s+device' } | ForEach-Object { ($_ -split '\s+')[0] }
  if([string]::IsNullOrWhiteSpace($Device)){
    if($devs.Count -gt 0){ $Device = $devs[0] } else { throw "No emulator devices detected." }
  }
  # Clear then capture fresh logs
  & $adb -s $Device logcat -c | Out-Null
  Start-Sleep -Seconds 1
  # Give app a nudge to generate logs
  & $adb -s $Device shell monkey -p $Pkg -c android.intent.category.LEANBACK_LAUNCHER 1 | Out-Null
  Start-Sleep -Seconds 2
  Write-Host "--- Last $Lines log lines (filtered) for $Pkg on $Device ---"
  & $adb -s $Device logcat -v time -d | Select-String -Pattern $Pkg,'OkHttp','HTTP','retrofit' | Select-Object -Last $Lines
}
catch {
  Write-Error $_
  exit 1
}
