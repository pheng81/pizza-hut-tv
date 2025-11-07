# Auto-Slicing Multi-Screen Video Feature

## Overview

The system now automatically detects multi-screen video layouts during upload and slices them into individual screen files. This eliminates the need for on-the-fly server slicing, dramatically improving playback performance.

## Performance Impact

**Before (On-the-fly slicing):**
- Upload one 7680x1080 video (4 screens)
- Each screen requests /slice-video/ route
- Server downloads 100-200MB from CDN (10-20s)
- FFmpeg processes and crops (10-20s)
- Total first load: **30-60 seconds** ⚠️

**After (Auto-slicing during upload):**
- Upload one 7680x1080 video (4 screens)
- System detects 4-screen horizontal layout
- Auto-slices into 4 separate videos during upload
- All 4 videos uploaded to CDN
- Each screen loads directly from CDN: **2-5 seconds** ✅

## Supported Layouts

### Horizontal Layouts (height=1080, width multiplied by 1920)

| Resolution    | Screens | Example Use Case          |
|---------------|---------|---------------------------|
| 1920x1080     | 1       | Single screen             |
| 3840x1080     | 2       | Two side-by-side displays |
| 5760x1080     | 3       | Three displays            |
| 7680x1080     | 4       | Four displays             |
| 9600x1080     | 5       | Five displays             |
| 11520x1080    | 6       | Six displays              |
| 13440x1080    | 7       | Seven displays            |

### Vertical Layouts (width=1920, height multiplied by 1080)

| Resolution    | Screens | Example Use Case        |
|---------------|---------|-------------------------|
| 1920x1080     | 1       | Single screen           |
| 1920x2160     | 2       | Two stacked displays    |
| 1920x3240     | 3       | Three stacked displays  |
| 1920x4320     | 4       | Four stacked displays   |
| 1920x5400     | 5       | Five stacked displays   |
| 1920x6480     | 6       | Six stacked displays    |
| 1920x7560     | 7       | Seven stacked displays  |

## How It Works

### 1. Upload Detection

When a video is uploaded via `/upload_media`:

1. **FFprobe Detection**: System uses FFprobe to extract video metadata:
   - Resolution (width × height)
   - Frame rate (fps)
   - Audio presence
   
2. **Layout Calculation**: Based on resolution:
   ```python
   # Horizontal: width % 1920 == 0 and height == 1080
   screen_count = width // 1920
   
   # Vertical: width == 1920 and height % 1080 == 0
   screen_count = height // 1080
   ```

3. **Auto-Slicing Decision**:
   - Single screen (1920x1080): Upload original, no slicing
   - Multi-screen (2-7 screens): Auto-slice into individual files

### 2. FFmpeg Slicing Process

For each screen, FFmpeg crops the appropriate section:

**Horizontal Slicing** (crop width):
```bash
# Screen 1: crop=1920:1080:0:0
# Screen 2: crop=1920:1080:1920:0
# Screen 3: crop=1920:1080:3840:0
# Screen 4: crop=1920:1080:5760:0
```

**Vertical Slicing** (crop height):
```bash
# Screen 1: crop=1920:1080:0:0
# Screen 2: crop=1920:1080:0:1080
# Screen 3: crop=1920:1080:0:2160
# Screen 4: crop=1920:1080:0:3240
```

**Encoding Settings**:
- Codec: H.264 (libx264) with Main profile
- Pixel format: yuv420p (universal compatibility)
- Quality: CRF 23 (good balance)
- Speed: Fast preset (quicker upload processing)
- GOP: 1 second keyframes for smooth seeking
- FastStart: Enabled for web streaming

### 3. Upload to CDN

Each sliced video is uploaded to Cloudflare R2 with naming:
- Original: `{uuid}.mp4`
- Slice 1: `{uuid}-screen1.mp4`
- Slice 2: `{uuid}-screen2.mp4`
- Slice 3: `{uuid}-screen3.mp4`
- Slice 4: `{uuid}-screen4.mp4`

All files are accessible via CDN: `https://cdn.everydayadvertise.com/`

## Upload Response Format

### Single Screen Video

```json
{
  "success": true,
  "filename": "2024-12/abc123.mp4",
  "media_type": "video",
  "url": "https://cdn.everydayadvertise.com/2024-12/abc123.mp4"
}
```

### Multi-Screen Video (Auto-Sliced)

```json
{
  "success": true,
  "filename": "2024-12/abc123.mp4",
  "media_type": "video",
  "url": "https://cdn.everydayadvertise.com/2024-12/abc123.mp4",
  "screen_count": 4,
  "layout": "horizontal",
  "sliced_files": [
    {
      "screen_number": 1,
      "filename": "2024-12/abc123-screen1.mp4",
      "url": "https://cdn.everydayadvertise.com/2024-12/abc123-screen1.mp4",
      "size": 52428800
    },
    {
      "screen_number": 2,
      "filename": "2024-12/abc123-screen2.mp4",
      "url": "https://cdn.everydayadvertise.com/2024-12/abc123-screen2.mp4",
      "size": 52428800
    },
    {
      "screen_number": 3,
      "filename": "2024-12/abc123-screen3.mp4",
      "url": "https://cdn.everydayadvertise.com/2024-12/abc123-screen3.mp4",
      "size": 52428800
    },
    {
      "screen_number": 4,
      "filename": "2024-12/abc123-screen4.mp4",
      "url": "https://cdn.everydayadvertise.com/2024-12/abc123-screen4.mp4",
      "size": 52428800
    }
  ]
}
```

## User Experience

### Before

1. ❌ Manually slice 7680x1080 video into 4 files using FFmpeg
2. ❌ Upload 4 separate files individually
3. ❌ Create 4 playlist items with correct sync settings
4. ❌ Configure screen_order for each item
5. ⏱️ Time consuming and error-prone

### After

1. ✅ Upload one 7680x1080 video file
2. ✅ System automatically detects 4-screen horizontal layout
3. ✅ Auto-slices into 4 videos during upload
4. ✅ All 4 videos saved to CDN with proper naming
5. ✅ Ready to use in multi-screen playlists
6. ⚡ Fast loading (2-5s per screen vs 30-60s)

## Technical Implementation

### Helper Functions

**`detect_video_resolution(video_path)`**
- Uses FFprobe to extract metadata
- Returns: width, height, fps, has_audio

**`calculate_screen_layout(width, height)`**
- Analyzes resolution to determine layout
- Returns: screen_count, layout (horizontal/vertical/single), base dimensions

**`slice_video_for_multi_screen(...)`**
- Uses FFmpeg to crop each screen section
- Saves sliced videos to temporary directory
- Returns: list of slice info (screen_number, filename, path, size)

### Modified Routes

**`/upload_media`** (Enhanced)
- After saving uploaded video locally
- Detects if video file (not image)
- Runs resolution detection
- If multi-screen: auto-slices and uploads all files
- Returns enhanced response with slice information

## Requirements

### Server Requirements

1. **FFmpeg/FFprobe Installed**
   - Ubuntu/Debian: `sudo apt-get install ffmpeg`
   - Already installed on current server (54.252.90.27)

2. **Cloudflare R2 Configured**
   - Already configured with cdn.everydayadvertise.com
   - Auto-slicing requires R2 enabled

3. **Sufficient Disk Space**
   - Temporary slicing requires 2-3x original file size
   - Slices are cleaned up after upload

### Browser/Player Requirements

- No changes needed - player already supports multi-screen sync
- Uses direct CDN URLs for each screen slice
- Existing sync system works with sliced videos

## Monitoring & Logging

The system logs detailed information during auto-slicing:

```
[upload_media] Video detected, checking for multi-screen layout...
[detect_video_resolution] /path/to/video.mp4: 7680x1080, fps=30, audio=True
[calculate_screen_layout] Detected HORIZONTAL layout: 4 screens (7680x1080)
[upload_media] Multi-screen video detected: 4 screens (horizontal layout)
[slice_video_for_multi_screen] Slicing /path/to/video.mp4 into 4 horizontal screens
[slice_video_for_multi_screen] Screen 1: crop=1920:1080:0:0
[slice_video_for_multi_screen] Running FFmpeg for screen 1...
[slice_video_for_multi_screen] Screen 1 created: uuid-screen1.mp4 (50.00 MB)
[slice_video_for_multi_screen] Screen 2: crop=1920:1080:1920:0
...
[slice_video_for_multi_screen] Successfully created 4 slices
[upload_media] Successfully created 4 slices, uploading to R2/CDN...
[upload_media] R2 put ok: 2024-12/uuid-screen1.mp4 (50.00 MB)
[upload_media] R2 put ok: 2024-12/uuid-screen2.mp4 (50.00 MB)
[upload_media] R2 put ok: 2024-12/uuid-screen3.mp4 (50.00 MB)
[upload_media] R2 put ok: 2024-12/uuid-screen4.mp4 (50.00 MB)
[upload_media] Successfully uploaded 4 sliced files to CDN
[upload_media] Returning response with 4 sliced files
[upload_media] done file=2024-12/uuid.mp4 ms=45230
```

## Error Handling

### FFmpeg Not Available
- System falls back to uploading original video without slicing
- Logs warning: "FFmpeg not available, cannot detect resolution"
- Upload still succeeds, slicing skipped

### Resolution Detection Fails
- System uploads original video without slicing
- Logs: "Could not detect video resolution, skipping auto-slice"
- Upload still succeeds

### Slicing Process Fails
- System continues with original video upload
- Logs error and traceback
- User receives original video in response

### R2 Upload Fails for Slices
- Slices are saved locally as backup
- Error logged but doesn't fail entire upload
- User can manually verify/re-upload if needed

## Performance Considerations

### Upload Time Impact

**4-Screen Video (7680x1080, 60 seconds, ~200MB):**
- Without auto-slicing: ~30-45s upload
- With auto-slicing: ~60-90s upload (includes slicing time)
- **Trade-off**: +30s upload time, saves 25-55s per screen on first playback

**Total Time Savings:**
- First playback across 4 screens:
  - Old: 30-60s × 4 = 120-240s
  - New: 2-5s × 4 = 8-20s
  - **Savings: 112-220 seconds (1.9-3.7 minutes)**

### Storage Impact

- Original video: ~200MB
- 4 sliced videos: ~4 × 50MB = 200MB
- **Total storage: 2× original size**
- Trade-off: 2× storage for dramatically faster playback

### Server Load

- FFmpeg processing: ~15-30s CPU time per screen
- Minimal impact on server with current load (0.44)
- Processing happens during upload, not playback
- No impact on playback performance

## Future Enhancements

### Planned Features

1. **Progress Indicators**
   - Real-time slicing progress in upload UI
   - Show "Slicing screen 2 of 4..." messages
   - Estimated time remaining

2. **Async Processing**
   - Move slicing to background job queue
   - Return upload success immediately
   - Process slices asynchronously
   - Notify when ready via webhook/polling

3. **Custom Layouts**
   - Support non-standard resolutions
   - Manual screen count override
   - Mixed orientation (2 horizontal + 1 vertical)

4. **Optimization**
   - GPU-accelerated encoding (NVENC/VAAPI)
   - Parallel slicing (process multiple screens simultaneously)
   - Pre-analysis to skip identical frames

5. **Management Tools**
   - Re-slice existing videos
   - Batch re-process library
   - Cleanup orphaned slices

## Troubleshooting

### "FFmpeg not available" Warning

**Problem**: System can't find FFmpeg executable.

**Solution**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install ffmpeg

# Verify installation
ffmpeg -version
ffprobe -version

# Restart Flask server
sudo systemctl restart pizza-hut-tv
```

### Slicing Takes Too Long

**Problem**: Large videos (>500MB) take several minutes to slice.

**Symptoms**: Upload appears stuck at "Processing..."

**Solutions**:
1. Pre-compress videos before upload (reduce file size)
2. Use faster encoding preset (already using "fast")
3. Consider async processing (future enhancement)

### Slices Not Playing

**Problem**: Sliced videos exist but don't play properly.

**Diagnosis**:
1. Check server logs: `tail -100 /var/log/pizza-hut-tv/gunicorn.log`
2. Verify CDN URLs: `curl -I https://cdn.everydayadvertise.com/2024-12/uuid-screen1.mp4`
3. Test direct playback in browser

**Solutions**:
- Re-upload video if slices are corrupted
- Check Cloudflare R2 permissions
- Verify FFmpeg encoding settings

### Wrong Screen Count Detected

**Problem**: 3840x1080 video detected as 1 screen instead of 2.

**Cause**: Resolution doesn't match exact multiples of 1920×1080.

**Solution**:
- Verify video resolution: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 video.mp4`
- Re-encode to exact resolution: `ffmpeg -i input.mp4 -vf scale=3840:1080 -c:v libx264 -preset fast -crf 23 output.mp4`

## Testing

### Manual Test Procedure

1. **Prepare Test Videos**:
   ```bash
   # Create 2-screen horizontal test (3840x1080)
   ffmpeg -f lavfi -i testsrc=size=3840x1080:rate=30 -t 10 -c:v libx264 test-2h.mp4
   
   # Create 4-screen horizontal test (7680x1080)
   ffmpeg -f lavfi -i testsrc=size=7680x1080:rate=30 -t 10 -c:v libx264 test-4h.mp4
   
   # Create 3-screen vertical test (1920x3240)
   ffmpeg -f lavfi -i testsrc=size=1920x3240:rate=30 -t 10 -c:v libx264 test-3v.mp4
   ```

2. **Upload via Dashboard**:
   - Go to https://everydayadvertise.com/home
   - Click "Upload Media"
   - Select test video
   - Monitor console for slicing logs

3. **Verify Response**:
   - Check JSON response has `sliced_files` array
   - Verify `screen_count` matches expected
   - Confirm `layout` is "horizontal" or "vertical"

4. **Test Playback**:
   - Create playlist with screen_id variations
   - Load webplayer for each screen
   - Verify fast loading (2-5s)
   - Check synchronization across screens

### Automated Tests

```python
# test_auto_slicing.py
import requests

def test_horizontal_4_screen():
    """Test 7680x1080 horizontal layout detection and slicing."""
    with open('test-4h.mp4', 'rb') as f:
        response = requests.post(
            'https://api.everydayadvertise.com/upload_media',
            files={'file': f},
            cookies={'session': 'your-session-cookie'}
        )
    
    data = response.json()
    assert data['success'] == True
    assert data['screen_count'] == 4
    assert data['layout'] == 'horizontal'
    assert len(data['sliced_files']) == 4
    
    # Verify each slice exists
    for slice_info in data['sliced_files']:
        url = slice_info['url']
        head = requests.head(url)
        assert head.status_code == 200
```

## Conclusion

The auto-slicing feature dramatically improves the multi-screen video experience:

✅ **Eliminates manual slicing work**
✅ **Drastically faster playback (30-60s → 2-5s)**
✅ **Automatic layout detection**
✅ **Supports both horizontal and vertical setups**
✅ **No changes needed to existing players**
✅ **Comprehensive error handling**

Simply upload your multi-screen video, and the system handles the rest!
