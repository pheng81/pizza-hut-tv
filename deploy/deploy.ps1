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

$updateCmd = @"
set -e
if [ ! -d "$RepoPath/.git" ]; then
  echo "ERROR: Repo not found at $RepoPath (.git missing). Run with -Bootstrap first or fix RepoPath." >&2
  exit 1
fi
cd "$RepoPath"
PRESERVE=$([bool]::Parse('$(if($PreserveConfig){"True"}else{"False"})'))
if [ "$PRESERVE" = "True" ]; then
  # Safely preserve local store_config.json if present to avoid git conflicts
  if [ -f store_config.json ]; then cp store_config.json /tmp/store_config.json.local.bak; fi
  # If tracked, allow index to change and remove working copy to prevent conflict
  if git ls-files --error-unmatch store_config.json >/dev/null 2>&1; then
    git update-index --no-skip-worktree store_config.json || true
  fi
  rm -f store_config.json || true
fi

# Update code: prefer fast-forward pull, fallback to fetch/reset to origin/main
git pull --ff-only || { git fetch origin main && git checkout -f main && git reset --hard origin/main; }

# Restore preserved config if we saved it
if [ "$PRESERVE" = "True" ]; then
  if [ -f /tmp/store_config.json.local.bak ]; then cp /tmp/store_config.json.local.bak store_config.json; fi
  # If the file is tracked in git, mark skip-worktree so future pulls ignore local edits
  if git ls-files --error-unmatch store_config.json >/dev/null 2>&1; then
    git update-index --skip-worktree store_config.json || true
  fi
fi
"$RepoPath/.venv/bin/pip" install -r requirements.txt

# Prefer everydayadvertise, fallback to tv-api
for svc in $services; do
  if systemctl list-unit-files | grep -q "^${svc}\.service"; then
    sudo systemctl restart "$svc"
    sudo systemctl status "$svc" --no-pager -l || true
    exit 0
  fi
done

echo "WARNING: No known service found to restart: $services" >&2
exit 2
"@

Invoke-Remote "bash -lc '$updateCmd'"

Write-Host "Done." -ForegroundColor Green
