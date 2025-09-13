#!/usr/bin/env python3
"""
Generate thumbnail images for all video files in the uploads directory.
This ensures the Android TV app can show static fallbacks for ultra-wide videos.
"""

import os
import subprocess
import sys
from pathlib import Path

def find_ffmpeg():
    """Find ffmpeg executable."""
    # Check common locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\ffmpeg.exe", 
        "ffmpeg",
        "ffmpeg.exe"
    ]
    
    for path in common_paths:
        try:
            result = subprocess.run([path, "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Found ffmpeg: {path}")
                return path
        except:
            continue
    
    return None

def generate_thumbnail(video_path, thumb_path, ffmpeg_exe):
    """Generate a thumbnail from a video file."""
    try:
        # Extract a frame at 1 second, scale to 1920x1080, center crop if needed
        cmd = [
            ffmpeg_exe,
            "-i", str(video_path),
            "-ss", "00:00:01.000",  # Seek to 1 second to avoid black frames
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=rgb24",
            "-frames:v", "1",
            "-q:v", "2",  # High quality
            "-y",  # Overwrite existing
            str(thumb_path)
        ]
        
        print(f"Generating: {thumb_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Success: {thumb_path.name}")
            return True
        else:
            print(f"❌ Failed: {thumb_path.name}")
            print(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Exception for {video_path.name}: {e}")
        return False

def main():
    # Find ffmpeg
    ffmpeg_exe = find_ffmpeg()
    if not ffmpeg_exe:
        print("❌ FFmpeg not found. Please install FFmpeg and ensure it's in PATH.")
        print("Download from: https://ffmpeg.org/download.html")
        return 1
    
    # Find all video files in static/uploads
    base_dir = Path("static/uploads")
    if not base_dir.exists():
        print(f"❌ Upload directory not found: {base_dir}")
        return 1
    
    video_files = list(base_dir.rglob("*.mp4"))
    print(f"Found {len(video_files)} video files")
    
    if not video_files:
        print("No video files found")
        return 0
    
    success = 0
    failed = 0
    skipped = 0
    
    for video_path in video_files:
        # Check for existing thumbnail (.jpg first, then .png)
        jpg_path = video_path.with_suffix('.jpg')
        png_path = video_path.with_suffix('.png')
        
        if jpg_path.exists():
            print(f"⏭️  Skipped (exists): {jpg_path.name}")
            skipped += 1
            continue
        
        # Generate JPG thumbnail
        if generate_thumbnail(video_path, jpg_path, ffmpeg_exe):
            success += 1
        else:
            failed += 1
    
    print(f"\n=== Summary ===")
    print(f"✅ Generated: {success}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📁 Total videos: {len(video_files)}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())