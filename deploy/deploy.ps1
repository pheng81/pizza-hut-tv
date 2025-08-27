param(
  [Parameter(Mandatory=$true)] [string]$Server,
  [string]$User = 'ubuntu',
  [string]$RepoPath = '/home/ubuntu/pizza-hut-tv',
  [string[]]$ServiceNames = @('everydayadvertise','tv-api'),
  [string]$KeyPath = '',
  [switch]$Bootstrap,
  [switch]$PreserveConfig
)

# Simple, repeatable deploy script to update your Lightsail VM.
# Usage examples (from Windows PowerShell):
#   .\deploy\deploy.ps1 -Server 1.2.3.4
#   .\deploy\deploy.ps1 -Server your.domain -Bootstrap
#   .\deploy\deploy.ps1 -Server 1.2.3.4 -RepoPath '/opt/pizza-hut-tv' -ServiceNames tv-api

function Invoke-Remote($command) {
  $sshExe = 'ssh'
  $sshArgs = @()
  if ($KeyPath -and (Test-Path $KeyPath)) { $sshArgs += @('-i', $KeyPath) }
  $sshArgs += @('-o','StrictHostKeyChecking=no',"$User@$Server", $command)
  & $sshExe @sshArgs
  if ($LASTEXITCODE -ne 0) { throw "Remote command failed with exit code $LASTEXITCODE" }
}

function Copy-ToRemote($localPath, $remotePath) {
  $scpExe = 'scp'
  $scpArgs = @()
  if ($KeyPath -and (Test-Path $KeyPath)) { $scpArgs += @('-i', $KeyPath) }
  $scpArgs += @('-o','StrictHostKeyChecking=no', $localPath, "${User}@${Server}:${remotePath}")
  & $scpExe @scpArgs
  if ($LASTEXITCODE -ne 0) { throw "File copy failed with exit code $LASTEXITCODE" }
}

Write-Host "Deploying to $User@$Server (Repo: $RepoPath)" -ForegroundColor Cyan

if ($Bootstrap) {
  Write-Host "Running first-time bootstrap on the server..." -ForegroundColor Yellow
  $bootstrapCmd = @"
set -e
sudo apt-get update -y
sudo apt-get install -y git python3-venv ffmpeg

mkdir -p "$(Split-Path -Path $RepoPath)"
if [ ! -d "$RepoPath/.git" ]; then
  git clone https://github.com/pheng81/pizza-hut-tv.git "$RepoPath"
fi

cd "$RepoPath"
python3 -m venv .venv
"$RepoPath/.venv/bin/pip" install --upgrade pip wheel
"$RepoPath/.venv/bin/pip" install -r requirements.txt
"$RepoPath/.venv/bin/pip" install gunicorn

# Install standardized systemd unit (everydayadvertise.service)
sudo cp deploy/everydayadvertise.service /etc/systemd/system/everydayadvertise.service
sudo systemctl daemon-reload
sudo systemctl enable --now everydayadvertise
sudo systemctl status everydayadvertise --no-pager -l || true
"@
  Invoke-Remote "bash -lc '$bootstrapCmd'"
}

Write-Host "Pulling latest code and restarting service..." -ForegroundColor Yellow

$services = ($ServiceNames | ForEach-Object { $_.Trim() }) -join ' '
$preserveStr = if ($PreserveConfig.IsPresent) { 'True' } else { 'False' }

# Upload and run the robust server-side updater to avoid inline quoting issues
Copy-ToRemote -localPath (Join-Path $PSScriptRoot 'update_server.sh') -remotePath '/tmp/update_server.sh'
Invoke-Remote "bash -lc 'chmod +x /tmp/update_server.sh; REPO_PATH="$RepoPath" PRESERVE="$preserveStr" SERVICES="$services" /tmp/update_server.sh'"

Write-Host "Done." -ForegroundColor Green
