# Pizza Hut TV - FFmpeg Video Slicing Implementation Summary

## What We've Implemented

### 1. Enhanced Android TV Sync Video Support
- **Fixed critical playlist data loss bug** that was erasing playlist items when CDN files weren't found locally
- **Enhanced get_playlist endpoint** with complete sync_ref data including count, mode, and order fields
- **Added automatic backup system** for store_config.json to prevent data loss
- **Android app enhanced** with video slicing transforms and comprehensive debugging

### 2. Server-Side Video Slicing Solution
- **Complete slice-video endpoint rewrite** using FFmpeg crop filters
- **Cache system** for storing processed video slices
- **Automatic cleanup** of old cached slices
- **R2/CDN support** for downloading and processing remote videos
- **Fallback handling** when FFmpeg is not available

### 3. Video Processing Logic
- **Ultra-wide video support**: Takes 5760x1080 videos and creates 1920x1080 slices
- **Horizontal splitting**: `crop=1920:1080:0:0` for slice 0, `crop=1920:1080:1920:0` for slice 1, etc.
- **Quality optimization**: Uses h264 codec with CRF 23 for good quality/size balance
- **Audio preservation**: Copies audio streams without re-encoding

## Current Status

### ✅ Completed
- [x] Fixed playlist data loss bug with automatic backups
- [x] Enhanced Android app with video slicing transforms
- [x] Implemented complete FFmpeg-based video slicing solution
- [x] Added cache system and cleanup routines
- [x] Created FFmpeg detection with multiple path checking
- [x] Added status endpoint for monitoring FFmpeg availability

### ⚠️ Pending
- [ ] FFmpeg installation (manual step required)
- [ ] Testing with actual ultra-wide sync videos
- [ ] Android TV app testing with properly-sized video slices

## FFmpeg Installation Instructions

Since the automated installation script had issues, here's how to manually install FFmpeg:

### Option 1: Direct Download (Recommended)
1. **Download FFmpeg**:
   - Go to: https://github.com/BtbN/FFmpeg-Builds/releases/latest
   - Download: `ffmpeg-master-latest-win64-gpl.zip`

2. **Extract and Setup**:
   ```powershell
   # Create directory
   mkdir C:\ffmpeg\bin -Force
   
   # Extract the zip to C:\ffmpeg
   # Copy the contents of the 'bin' folder from the extracted archive to C:\ffmpeg\bin\
   ```

3. **Verify Installation**:
   ```powershell
   C:\ffmpeg\bin\ffmpeg.exe -version
   C:\ffmpeg\bin\ffprobe.exe -version
   ```

### Option 2: Using Chocolatey (if available)
```powershell
choco install ffmpeg
```

### Option 3: Using Winget (Windows 10+)
```powershell
winget install ffmpeg
```

## Testing the Implementation

### 1. Check FFmpeg Status
Once FFmpeg is installed, restart the Flask server and check:
```
http://localhost:5002/admin/ffmpeg-status
```

### 2. Test Video Slicing
Upload a sync video and test the slice endpoint:
```
http://localhost:5002/slice-video/uploads/your_video.mp4?slice_mode=split-h&slice_count=3&slice_order=0
```

### 3. Android TV Testing
- Load the sync playlist in Android TV app
- Check logs for slice URL generation
- Verify ExoPlayer can play the 1920x1080 sliced videos

## How the Video Slicing Works

### Input: Ultra-wide Sync Video
- Resolution: 5760x1080 (3 screens side by side)
- Format: MP4 with h264 codec

### Processing: FFmpeg Crop Filter
- Slice 0: `crop=1920:1080:0:0` (left third)
- Slice 1: `crop=1920:1080:1920:0` (middle third)  
- Slice 2: `crop=1920:1080:3840:0` (right third)

### Output: TV-Ready Slices
- Resolution: 1920x1080 (standard TV format)
- Format: MP4 with h264 codec
- Quality: CRF 23 (good balance)
- Audio: Original stream copied

## Key Files Modified

### `app.py` Changes
- **Lines 2866-2890**: Enhanced FFmpeg detection with multiple paths
- **Lines 6806-7000**: Complete slice_video endpoint rewrite
- **Lines 7007-7105**: FFmpeg video slice generation function
- **Lines 4900-5000**: Enhanced get_playlist with slice-aware URL generation

### Android App Changes
- **TvDisplayActivity.kt**: Enhanced video slicing logic with debug logging
- Video transform application for properly-sized slices

### Cache System
- **static/cache/slices/**: Stores processed video slices
- **static/cache/temp/**: Temporary storage for CDN downloads
- Automatic cleanup of old cached files

## Next Steps

1. **Install FFmpeg** using the manual instructions above
2. **Restart Flask server** to detect FFmpeg
3. **Upload a test sync video** (5760x1080 resolution)
4. **Test slice endpoint** in browser or Android TV app
5. **Verify Android ExoPlayer** can play the sliced videos without decoder errors

## Expected Results

With FFmpeg installed and working:
- Android TV app should receive 1920x1080 video slices instead of 5760x1080 ultra-wide videos
- ExoPlayer decoder should handle the properly-sized videos without issues
- Video quality should be maintained while solving the ultra-wide format problem
- Cache system should improve performance for repeated access to the same slices

This implementation matches how the webplayer works (serving appropriate video segments) but does it server-side rather than client-side, which is more reliable for Android TV hardware limitations.
