param(
  [Parameter(Mandatory=$true)] [string]$Server,
  [string]$User = 'ubuntu',
  [string]$RepoPath = '/home/ubuntu/pizza-hut-tv',
  [string[]]$ServiceNames = @('everydayadvertise','tv-api'),
  [string]$KeyPath = '',
  [switch]$Bootstrap,
  [switch]$PreserveConfig,
  [switch]$ForceArchive,
  # Optional: create /etc/pizza-hut-tv.env on the server
  [switch]$SetAdminEnv,
  [string]$AdminUsername = 'admin',
  [string]$AdminPassword = 'admin',
  [string]$CookieDomain = '.everydayadvertise.com',
  [string]$MediaBaseUrl = 'https://cdn.everydayadvertise.com',
  # Optional persistent DB path on server (outside repo)
  [string]$UsersDbPath = '/var/lib/pizza-hut-tv/users.sqlite'
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
    # Copy the prepared bootstrap script and execute it remotely.
    # Using a file avoids CRLF and quoting issues over SSH.
    Copy-ToRemote -localPath (Join-Path $PSScriptRoot 'bootstrap_server.sh') -remotePath '/tmp/bootstrap_server.sh'
    # Run via bash with CR stripped to avoid shebang/CRLF issues
    Invoke-Remote "tr -d '\r' </tmp/bootstrap_server.sh | bash"
}

Write-Host "Pulling latest code and restarting service..." -ForegroundColor Yellow

$services = ($ServiceNames | ForEach-Object { $_.Trim() }) -join ' '
$preserveStr = if ($PreserveConfig.IsPresent) { 'True' } else { 'False' }

if (-not $ForceArchive) {
  # Upload and run the robust server-side updater to avoid inline quoting issues
  Copy-ToRemote -localPath (Join-Path $PSScriptRoot 'update_server.sh') -remotePath '/tmp/update_server.sh'
  try {
    # Execute update script by piping through bash with CR stripped; pass env vars to bash
    $remoteUpdateCmd = "REPO_PATH='" + $RepoPath + "' PRESERVE='" + $preserveStr + "' SERVICES='" + $services + "' bash -s"
    Invoke-Remote ("tr -d '\r' </tmp/update_server.sh | " + $remoteUpdateCmd)
  }
  catch {
    Write-Warning "Remote git-based update failed. Falling back to archive upload and extract."
    $ForceArchive = $true
  }
}

if ($ForceArchive) {
  # 1) Build archive of current working tree (includes uncommitted changes)
  # Use a temp location to avoid archiving the archive itself and keep repo clean
  $archivePath = Join-Path $env:TEMP ("phtv_site_" + [System.Guid]::NewGuid().ToString('n') + '.tar')
  if (Test-Path $archivePath) { Remove-Item -Force $archivePath }
  $rootDir = Split-Path -Parent $PSScriptRoot
  # Prefer tar with excludes; fallback to Compress-Archive if tar is unavailable
  $tarOk = $false
  try {
    $tarCmd = @(
      'tar','-cf',"$archivePath",
  '--exclude=.git','--exclude=.venv','--exclude=__pycache__','--exclude=__pycache__/**','--exclude=*.pyc','--exclude=*.pyo',
  '--exclude=static/uploads','--exclude=static/uploads/**','--exclude=users.sqlite','--exclude=store_config__*.json',
      # exclude giant Android SDK/builds entirely
      '--exclude=android_tv_app','--exclude=android_tv_app/**',
      # avoid bundling any pre-existing archives
      '--exclude=*.zip','--exclude=*.tar','--exclude=deploy/site.tar','--exclude=deploy/site.zip',
      '-C',"$rootDir",'.'
    )
    & $tarCmd[0] $tarCmd[1..($tarCmd.Length-1)]
    if ($LASTEXITCODE -eq 0) { $tarOk = $true }
  } catch { $tarOk = $false }
  if (-not $tarOk) {
    $zipPath = Join-Path $env:TEMP ("phtv_site_" + [System.Guid]::NewGuid().ToString('n') + '.zip')
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    # Create zip of working tree excluding common folders; Compress-Archive lacks exclude, so copy to temp first
    $tempStaging = Join-Path $env:TEMP ('phtv_stage_' + [System.Guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Force -Path $tempStaging | Out-Null
    robocopy "$rootDir" "$tempStaging" /E /XF *.pyc *.pyo *.zip *.tar /XD .git .venv __pycache__ android_tv_app | Out-Null
    Compress-Archive -Path (Join-Path $tempStaging '*') -DestinationPath $zipPath -Force
    Remove-Item -Recurse -Force $tempStaging
    # Convert zip to tar on the server (we'll handle both below); prefer tar if created
    $archivePath = $zipPath
  }
  if (-not (Test-Path $archivePath)) { throw "Failed to create working tree archive at $archivePath" }

  # 2) Upload archive to server
  $remoteArchive = if ($archivePath.ToLower().EndsWith('.zip')) { '/tmp/site.zip' } else { '/tmp/site.tar' }
  Copy-ToRemote -localPath $archivePath -remotePath $remoteArchive

  # 3) Extract on server, preserve config if requested, install deps, restart service
  $cmdParts = @()
  $cmdParts += "set -e"
  $cmdParts += "mkdir -p '$RepoPath'"
  if ($PreserveConfig.IsPresent) {
  $cmdParts += "if [ -f '$RepoPath/store_config.json' ]; then cp '$RepoPath/store_config.json' /tmp/store_config.json.local.bak; fi"
  $cmdParts += "mkdir -p /tmp/phtv_cfg_bak && cp -f '$RepoPath'/store_config__*.json /tmp/phtv_cfg_bak/ 2>/dev/null || true"
  $cmdParts += "if [ -d '$RepoPath/static/uploads' ]; then mkdir -p /tmp/phtv_uploads_bak && rsync -a '$RepoPath/static/uploads/' /tmp/phtv_uploads_bak/; fi"
  $cmdParts += "if [ -f '$RepoPath/users.sqlite' ]; then cp '$RepoPath/users.sqlite' /tmp/users.sqlite.bak; fi"
  }
  if ($remoteArchive.EndsWith('.zip')) {
    $cmdParts += "unzip -o $remoteArchive -d '$RepoPath' || (sudo apt-get update -y && sudo apt-get install -y unzip && unzip -o $remoteArchive -d '$RepoPath')"
  } else {
    $cmdParts += "tar -xf $remoteArchive -C '$RepoPath'"
  }
  $cmdParts += "python3 -m venv '$RepoPath/.venv' || true"
  $cmdParts += "'$RepoPath/.venv/bin/python' -m ensurepip --upgrade || true"
  $cmdParts += "'$RepoPath/.venv/bin/python' -m pip install --upgrade pip wheel"
  $cmdParts += "'$RepoPath/.venv/bin/python' -m pip install -r '$RepoPath/requirements.txt'"
  if ($PreserveConfig.IsPresent) {
  $cmdParts += "if [ -f /tmp/store_config.json.local.bak ]; then cp /tmp/store_config.json.local.bak '$RepoPath/store_config.json'; fi"
  $cmdParts += "if ls /tmp/phtv_cfg_bak/store_config__*.json >/dev/null 2>&1; then cp -f /tmp/phtv_cfg_bak/store_config__*.json '$RepoPath' || true; fi"
  $cmdParts += "if [ -d /tmp/phtv_uploads_bak ]; then mkdir -p '$RepoPath/static/uploads' && rsync -a /tmp/phtv_uploads_bak/ '$RepoPath/static/uploads/'; fi"
  # Restore repo-local users.sqlite backup if present
  $cmdParts += "if [ -f /tmp/users.sqlite.bak ]; then cp /tmp/users.sqlite.bak '$RepoPath/users.sqlite'; fi"
  }
  $cmdParts += ('for svc in ' + $services + '; do if systemctl list-unit-files | grep -q ''^${svc}\.service''; then sudo systemctl restart "${svc}"; sudo systemctl status "${svc}" --no-pager -l || true; exit 0; fi; done')
  $cmdParts += "echo 'No known service found; installing everydayadvertise.service' >&2"
  # Install service as fallback and wire env file if present
  $cmdParts += "if [ -f '$RepoPath/deploy/everydayadvertise.service' ]; then sudo cp '$RepoPath/deploy/everydayadvertise.service' /etc/systemd/system/everydayadvertise.service; fi"
  # Ensure drop-in directory exists
  $cmdParts += "sudo mkdir -p /etc/systemd/system/everydayadvertise.service.d"
  # Write a proper override using printf|tee (safer than nested heredoc across PowerShell/SSH quoting)
  $cmdParts += "if [ -f /etc/pizza-hut-tv.env ]; then printf '%s\n' '[Service]' 'EnvironmentFile=/etc/pizza-hut-tv.env' | sudo tee /etc/systemd/system/everydayadvertise.service.d/override.conf >/dev/null; fi"
  $cmdParts += "sudo systemctl daemon-reload"
  $cmdParts += "sudo systemctl enable --now everydayadvertise || true"
  $cmdParts += "sudo systemctl restart everydayadvertise || true"
  $cmdParts += "sudo systemctl status everydayadvertise --no-pager -l || true"

  $remoteCmd = ($cmdParts -join ' && ')
  Invoke-Remote $remoteCmd
  Write-Host 'Archive deploy completed.' -ForegroundColor Green
}

# Optionally write /etc/pizza-hut-tv.env with admin credentials and cookie domain
if ($SetAdminEnv.IsPresent) {
  Write-Host "Configuring /etc/pizza-hut-tv.env (admin credentials + cookie domain)..." -ForegroundColor Yellow
  $escapedUser = $AdminUsername
  $escapedPass = $AdminPassword
  $escapedCookie = $CookieDomain
  $escapedMedia = $MediaBaseUrl

  $remoteCmd2 = @()
  $remoteCmd2 += 'set -e'
  $remoteCmd2 += 'ENV=/etc/pizza-hut-tv.env'
  $remoteCmd2 += 'sudo touch "$ENV"'
  # Remove any previous ADMIN_ lines to avoid duplicates
  $remoteCmd2 += 'sudo sed -i ''/^ADMIN_USERNAME=/d;/^ADMIN_PASSWORD=/d'' "$ENV"'
  # Append fresh values (no quotes to keep simple; values should not contain spaces)
  $remoteCmd2 += "printf '%s`n' 'ADMIN_USERNAME=$escapedUser' 'ADMIN_PASSWORD=$escapedPass' | sudo tee -a '$ENV' > /dev/null"
  $remoteCmd2 += "printf '%s`n' 'SESSION_COOKIE_DOMAIN=$escapedCookie' 'MEDIA_BASE_URL=$escapedMedia' 'USERS_DB_PATH=$UsersDbPath' | sudo tee -a '$ENV' > /dev/null"
  # Ensure everydayadvertise service references the env file via drop-in
  $remoteCmd2 += 'sudo mkdir -p /etc/systemd/system/everydayadvertise.service.d'
  $remoteCmd2 += 'printf ''%s\n'' ''[Service]'' ''EnvironmentFile=/etc/pizza-hut-tv.env'' | sudo tee /etc/systemd/system/everydayadvertise.service.d/override.conf >/dev/null'
  $remoteCmd2 += 'sudo systemctl daemon-reload'
  # Deterministic restart: try everydayadvertise, then tv-api
  $remoteCmd2 += '(sudo systemctl restart everydayadvertise || sudo systemctl restart tv-api) || true'
  $remoteCmd2 += '(sudo systemctl status everydayadvertise --no-pager -l || sudo systemctl status tv-api --no-pager -l) || true'
  Invoke-Remote ($remoteCmd2 -join ' && ')
  Write-Host "Admin env applied on server." -ForegroundColor Green
}

Write-Host "Done." -ForegroundColor Green
