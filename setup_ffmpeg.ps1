# Simple FFmpeg Installation for Pizza Hut TV
# Downloads FFmpeg and sets up for video slicing

Write-Host "Installing FFmpeg for Pizza Hut TV..." -ForegroundColor Cyan

# Common FFmpeg installation locations to check
$ffmpegLocations = @(
    "C:\ffmpeg\bin\ffmpeg.exe",
    "C:\FFmpeg\bin\ffmpeg.exe", 
    "ffmpeg.exe"  # PATH
)

# Check if FFmpeg is already available
$ffmpegFound = $false
foreach ($location in $ffmpegLocations) {
    try {
        if ($location -eq "ffmpeg.exe") {
            $null = Get-Command ffmpeg -ErrorAction Stop
            Write-Host "FFmpeg found in PATH" -ForegroundColor Green
            $ffmpegFound = $true
            break
        } elseif (Test-Path $location) {
            Write-Host "FFmpeg found at: $location" -ForegroundColor Green
            $ffmpegFound = $true
            break
        }
    } catch {
        continue
    }
}

if ($ffmpegFound) {
    Write-Host "FFmpeg is already installed!" -ForegroundColor Green
    exit 0
}

# Create directory and download
$installDir = "C:\ffmpeg"
New-Item -ItemType Directory -Path $installDir -Force | Out-Null

Write-Host "Downloading FFmpeg..." -ForegroundColor Yellow

# Download portable FFmpeg
$downloadUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$zipFile = "$installDir\ffmpeg.zip"

try {
    $ProgressPreference = 'SilentlyContinue'  # Hide progress bars
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile -UseBasicParsing
    Write-Host "Downloaded FFmpeg" -ForegroundColor Green
} catch {
    Write-Host "Download failed: $_" -ForegroundColor Red
    Write-Host "You can manually download from: $downloadUrl" -ForegroundColor Yellow
    exit 1
}

# Extract
Write-Host "Extracting FFmpeg..." -ForegroundColor Yellow
try {
    Expand-Archive -Path $zipFile -DestinationPath $installDir -Force
    
    # Find and move bin contents
    $extractedDir = Get-ChildItem -Path $installDir -Directory | Where-Object { $_.Name -like "ffmpeg-*" } | Select-Object -First 1
    
    if ($extractedDir) {
        $binSource = Join-Path $extractedDir.FullName "bin"
        $binDest = Join-Path $installDir "bin"
        
        if (Test-Path $binSource) {
            New-Item -ItemType Directory -Path $binDest -Force | Out-Null
            Copy-Item -Path "$binSource\*" -Destination $binDest -Force
            Write-Host "Extracted FFmpeg to: $binDest" -ForegroundColor Green
            
            # Cleanup
            Remove-Item -Path $extractedDir.FullName -Recurse -Force
            Remove-Item -Path $zipFile -Force
        }
    }
} catch {
    Write-Host "Extraction failed: $_" -ForegroundColor Red
    exit 1
}

# Test installation
$ffmpegExe = Join-Path $installDir "bin\ffmpeg.exe"
if (Test-Path $ffmpegExe) {
    Write-Host "FFmpeg installed successfully!" -ForegroundColor Green
    Write-Host "Location: $ffmpegExe" -ForegroundColor Yellow
    
    # Test it works
    try {
        $version = & $ffmpegExe -version 2>&1 | Select-Object -First 1
        Write-Host "Version: $($version -replace 'ffmpeg version ', '')" -ForegroundColor Green
    } catch {
        Write-Host "FFmpeg installed but may not work properly" -ForegroundColor Yellow
    }
} else {
    Write-Host "Installation failed - FFmpeg not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================" -ForegroundColor Cyan
Write-Host "INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Cyan
Write-Host "FFmpeg location: $ffmpegExe" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart your Flask server" -ForegroundColor White
Write-Host "2. FFmpeg will be automatically detected" -ForegroundColor White
Write-Host "3. Test video slicing with Android TV" -ForegroundColor White
