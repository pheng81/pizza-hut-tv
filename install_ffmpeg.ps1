# Install FFmpeg for Pizza Hut TV Video Slicing
# This script downloads and sets up FFmpeg for Windows

Write-Host "Installing FFmpeg for Pizza Hut TV Video Slicing..." -ForegroundColor Green

# Create FFmpeg directory
$ffmpegDir = "C:\ffmpeg"
$ffmpegBin = "$ffmpegDir\bin"

if (!(Test-Path $ffmpegDir)) {
    New-Item -ItemType Directory -Path $ffmpegDir -Force
    Write-Host "Created directory: $ffmpegDir" -ForegroundColor Yellow
}

# Download FFmpeg (Windows build)
$ffmpegZip = "$env:TEMP\ffmpeg.zip"
$downloadUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "Downloading FFmpeg from: $downloadUrl" -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $ffmpegZip -UseBasicParsing
    Write-Host "Downloaded FFmpeg to: $ffmpegZip" -ForegroundColor Green
} catch {
    Write-Host "Error downloading FFmpeg: $_" -ForegroundColor Red
    exit 1
}

# Extract FFmpeg
Write-Host "Extracting FFmpeg..." -ForegroundColor Yellow
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ffmpegZip, $env:TEMP)
    
    # Find the extracted folder (it has a version-specific name)
    $extractedFolder = Get-ChildItem -Path $env:TEMP -Directory | Where-Object { $_.Name -like "ffmpeg-*" } | Select-Object -First 1
    
    if ($extractedFolder) {
        # Copy bin folder contents to our target directory
        $sourceBin = Join-Path $extractedFolder.FullName "bin"
        if (Test-Path $sourceBin) {
            Copy-Item -Path "$sourceBin\*" -Destination $ffmpegBin -Recurse -Force
            Write-Host "Extracted FFmpeg to: $ffmpegBin" -ForegroundColor Green
        } else {
            Write-Host "Error: bin folder not found in extracted archive" -ForegroundColor Red
            exit 1
        }
        
        # Cleanup temp extraction
        Remove-Item -Path $extractedFolder.FullName -Recurse -Force
    } else {
        Write-Host "Error: Could not find extracted FFmpeg folder" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error extracting FFmpeg: $_" -ForegroundColor Red
    exit 1
}

# Add to PATH if not already there
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -notlike "*$ffmpegBin*") {
    Write-Host "Adding FFmpeg to system PATH..." -ForegroundColor Yellow
    try {
        [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$ffmpegBin", "Machine")
        Write-Host "Added FFmpeg to system PATH" -ForegroundColor Green
        Write-Host "You may need to restart your terminal/IDE for PATH changes to take effect" -ForegroundColor Yellow
    } catch {
        Write-Host "Error adding to PATH (try running as Administrator): $_" -ForegroundColor Red
        Write-Host "Manual step: Add '$ffmpegBin' to your system PATH" -ForegroundColor Yellow
    }
} else {
    Write-Host "FFmpeg already in system PATH" -ForegroundColor Green
}

# Test FFmpeg installation
Write-Host "Testing FFmpeg installation..." -ForegroundColor Yellow
try {
    $ffmpegExe = Join-Path $ffmpegBin "ffmpeg.exe"
    if (Test-Path $ffmpegExe) {
        $version = & $ffmpegExe -version 2>&1 | Select-Object -First 1
        Write-Host "FFmpeg installed successfully!" -ForegroundColor Green
        Write-Host "Version: $version" -ForegroundColor Green
        
        # Also test ffprobe
        $ffprobeExe = Join-Path $ffmpegBin "ffprobe.exe"
        if (Test-Path $ffprobeExe) {
            Write-Host "FFprobe also available" -ForegroundColor Green
        }
    } else {
        Write-Host "Error: FFmpeg executable not found at $ffmpegExe" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error testing FFmpeg: $_" -ForegroundColor Red
    Write-Host "You may need to restart your terminal for PATH changes to take effect" -ForegroundColor Yellow
}

# Cleanup download
if (Test-Path $ffmpegZip) {
    Remove-Item $ffmpegZip
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "FFmpeg Installation Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Location: $ffmpegBin" -ForegroundColor Yellow
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart your Flask server" -ForegroundColor White
Write-Host "2. Test video slicing with Android TV app" -ForegroundColor White
Write-Host "3. Check server logs for FFmpeg availability" -ForegroundColor White
Write-Host ""
Write-Host "If FFmpeg is still not found, restart your terminal/IDE" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
