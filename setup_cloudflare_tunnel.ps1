#requires -Version 5.1
param(
  [string]$TunnelName = "phtv-tunnel",
  [string]$Domain = "everydayadvertise.com",
  [string]$Subdomain = "tv",
  [int]$LocalPort = 5002
)

$ErrorActionPreference = 'Stop'

Write-Host "Installing cloudflared..." -ForegroundColor Cyan
$cfDir = Join-Path $env:ProgramFiles 'cloudflared'
if (!(Test-Path $cfDir)) { New-Item -ItemType Directory -Path $cfDir | Out-Null }
$exe = Join-Path $cfDir 'cloudflared.exe'
Invoke-WebRequest -Uri https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile $exe
$env:Path += ";$cfDir"

Write-Host "Logging in to Cloudflare (browser will open)..." -ForegroundColor Cyan
& $exe tunnel login

Write-Host "Creating tunnel $TunnelName..." -ForegroundColor Cyan
& $exe tunnel create $TunnelName

Write-Host "Creating DNS route $Subdomain.$Domain..." -ForegroundColor Cyan
& $exe tunnel route dns $TunnelName "$Subdomain.$Domain"

Write-Host "Writing config.yml..." -ForegroundColor Cyan
$config = @"
tunnel: $TunnelName
credentials-file: $cfDir\$TunnelName.json

ingress:
  - hostname: $Subdomain.$Domain
    service: http://localhost:$LocalPort
  - service: http_status:404
"@
$config | Out-File -Encoding utf8 (Join-Path $cfDir 'config.yml')

Write-Host "Installing and starting cloudflared service..." -ForegroundColor Cyan
& $exe service install
Start-Service cloudflared

Write-Host "Done. Visit: https://$Subdomain.$Domain/" -ForegroundColor Green
