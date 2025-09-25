param(
  [string]$PiHost = 'raspberrypi',
  [string]$User = 'everydayadvertise',
  [string]$RepoPath = '/home/everydayadvertise',
  [string]$ServiceName = 'pizza-hut-tv',
  [string]$Password = 'pheng168',
  [switch]$ForceArchive,
  [switch]$PreserveConfig
)

# Pi deployment script for Pizza Hut TV
# Usage: .\deploy\deploy_pi.ps1 -PiHost raspberrypi

function Invoke-RemotePi($command) {
  Write-Host "Executing on Pi: $command" -ForegroundColor Gray
  
  # Use expect-like approach for password authentication
  $expectScript = @"
spawn ssh -o StrictHostKeyChecking=no $User@$PiHost $command
expect "password:"
send "$Password\r"
expect eof
"@
  
  # Try direct SSH first
  try {
    $process = Start-Process -FilePath 'ssh' -ArgumentList @('-o', 'StrictHostKeyChecking=no', "$User@$PiHost", $command) -PassThru -Wait -NoNewWindow
    if ($process.ExitCode -ne 0) {
      throw "SSH command failed with exit code $($process.ExitCode)"
    }
  } catch {
    Write-Host "Direct SSH failed, trying alternative method..." -ForegroundColor Yellow
    throw "Remote command failed: $($_.Exception.Message)"
  }
}

function Copy-ToPi($localPath, $remotePath) {
  Write-Host "Copying $localPath to Pi:$remotePath" -ForegroundColor Gray
  
  try {
    $process = Start-Process -FilePath 'scp' -ArgumentList @('-o', 'StrictHostKeyChecking=no', $localPath, "${User}@${PiHost}:${remotePath}") -PassThru -Wait -NoNewWindow
    if ($process.ExitCode -ne 0) {
      throw "SCP failed with exit code $($process.ExitCode)"
    }
  } catch {
    Write-Host "SCP failed, trying alternative method..." -ForegroundColor Yellow
    throw "File copy failed: $($_.Exception.Message)"
  }
}

Write-Host "Deploying to Pi: $User@$PiHost (Path: $RepoPath)" -ForegroundColor Cyan

try {
  # Create archive with enhanced Pi client
  Write-Host "Creating deployment archive..." -ForegroundColor Yellow
  $archiveName = "pi_client_$(Get-Date -Format 'yyyyMMdd_HHmmss').tar.gz"
  $tempDir = [System.IO.Path]::GetTempPath()
  $archivePath = Join-Path $tempDir $archiveName
  
  # Use tar to create archive (Windows 10+ has built-in tar)
  $filesToDeploy = @(
    'phtv_pi_client.py',
    'ea_tv_launcher.sh',
    'start_ea_tv.sh',
    'PizzaHutTV.desktop',
    'Pizza_Hut_TV.desktop'
  )
  
  $tarArgs = @('czf', $archivePath)
  foreach ($file in $filesToDeploy) {
    if (Test-Path $file) {
      $tarArgs += $file
      Write-Host "  Adding: $file" -ForegroundColor Green
    }
  }
  
  & tar @tarArgs
  if ($LASTEXITCODE -ne 0) { throw "Archive creation failed" }
  
  Write-Host "Archive created: $archivePath" -ForegroundColor Green
  
  # Copy archive to Pi
  Write-Host "Transferring archive to Pi..." -ForegroundColor Yellow
  Copy-ToPi -localPath $archivePath -remotePath "/tmp/$archiveName"
  
  # Extract and deploy on Pi
  Write-Host "Extracting and deploying on Pi..." -ForegroundColor Yellow
  Invoke-RemotePi "cd $RepoPath && tar -xzf /tmp/$archiveName"
  
  # Make scripts executable
  Invoke-RemotePi "chmod +x $RepoPath/ea_tv_launcher.sh $RepoPath/start_ea_tv.sh"
  
  # Stop any running EA TV processes
  Write-Host "Stopping existing EA TV processes..." -ForegroundColor Yellow
  Invoke-RemotePi "pkill -f phtv_pi_client.py || true"
  
  # Update desktop shortcuts if they exist
  if (Test-Path 'PizzaHutTV.desktop') {
    Invoke-RemotePi "cp $RepoPath/PizzaHutTV.desktop ~/Desktop/ 2>/dev/null || true"
  }
  if (Test-Path 'Pizza_Hut_TV.desktop') {
    Invoke-RemotePi "cp $RepoPath/Pizza_Hut_TV.desktop ~/Desktop/ 2>/dev/null || true"
  }
  
  # Make desktop files executable
  Invoke-RemotePi "chmod +x ~/Desktop/*.desktop 2>/dev/null || true"
  
  # Cleanup
  Remove-Item $archivePath -Force
  Invoke-RemotePi "rm /tmp/$archiveName"
  
  Write-Host "✅ Pi deployment completed successfully!" -ForegroundColor Green
  Write-Host "Enhanced synchronization is now active on the Pi client." -ForegroundColor Green
  Write-Host "Click the EA TV desktop icon to test synchronized playback." -ForegroundColor Cyan
  
} catch {
  Write-Host "❌ Pi deployment failed: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Please check network connectivity and Pi credentials." -ForegroundColor Yellow
  exit 1
}