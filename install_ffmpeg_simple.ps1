# Simple FFmpeg Installation - Just the right version for Windows
Write-Host "Installing FFmpeg for Pizza Hut TV Video Slicing..." -ForegroundColor Green

# Direct download of the correct Windows version
$downloadUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$zipFile = "C:\ffmpeg.zip"
$installDir = "C:\ffmpeg"

Write-Host "Downloading FFmpeg (Windows 64-bit GPL)..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile -UseBasicParsing
    Write-Host "Downloaded successfully" -ForegroundColor Green
} catch {
    Write-Host "Download failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "Extracting FFmpeg..." -ForegroundColor Yellow
try {
    # Create install directory
    if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    
    # Extract
    Expand-Archive -Path $zipFile -DestinationPath $installDir -Force
    
    # Find the extracted folder and move bin contents
    $extractedFolder = Get-ChildItem -Path $installDir -Directory | Select-Object -First 1
    if ($extractedFolder) {
        $binSource = Join-Path $extractedFolder.FullName "bin"
        $binDest = Join-Path $installDir "bin"
        
        if (Test-Path $binSource) {
            Move-Item -Path $binSource -Destination $binDest
            Remove-Item -Path $extractedFolder.FullName -Recurse -Force
        }
    }
    
    # Cleanup
    Remove-Item $zipFile -Force
    Write-Host "Extracted to C:\ffmpeg\bin\" -ForegroundColor Green
    
} catch {
    Write-Host "Extraction failed: $_" -ForegroundColor Red
    exit 1
}

# Test installation
$ffmpegExe = "C:\ffmpeg\bin\ffmpeg.exe"
if (Test-Path $ffmpegExe) {
    Write-Host "Testing FFmpeg..." -ForegroundColor Yellow
    try {
        $version = & $ffmpegExe -version 2>&1 | Select-Object -First 1
        Write-Host "SUCCESS! FFmpeg installed and working" -ForegroundColor Green
        Write-Host "Version: $($version -replace 'ffmpeg version ', '')" -ForegroundColor Cyan
    } catch {
        Write-Host "FFmpeg installed but test failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "Installation failed - FFmpeg not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "FFMPEG READY FOR VIDEO SLICING!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Location: C:\ffmpeg\bin\ffmpeg.exe" -ForegroundColor White
Write-Host ""
Write-Host "Next: Restart your Flask server to enable video slicing" -ForegroundColor Yellow
Write-Host "The video slicing solution is already implemented!" -ForegroundColor Green
