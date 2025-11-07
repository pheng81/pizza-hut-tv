# Multi-Screen Video Resolution Guide

## Quick Reference

### Horizontal Layout (Landscape Orientation)
**Base screen: 1920×1080**
- Screens are side-by-side
- Height stays **1080** (fixed)
- Width multiplies by **1920**

| Screens | Resolution    | Calculation     |
|---------|---------------|-----------------|
| 1       | 1920×1080     | 1920×1 = 1920   |
| 2       | 3840×1080     | 1920×2 = 3840   |
| 3       | 5760×1080     | 1920×3 = 5760   |
| 4       | 7680×1080     | 1920×4 = 7680   |
| 5       | 9600×1080     | 1920×5 = 9600   |
| 6       | 11520×1080    | 1920×6 = 11520  |
| 7       | 13440×1080    | 1920×7 = 13440  |

### Vertical Layout (Portrait Orientation)
**Base screen: 1080×1920**
- Screens are stacked vertically
- Width stays **1080** (fixed)
- Height multiplies by **1920**

| Screens | Resolution    | Calculation     |
|---------|---------------|-----------------|
| 1       | 1080×1920     | 1920×1 = 1920   |
| 2       | 1080×3840     | 1920×2 = 3840   |
| 3       | 1080×5760     | 1920×3 = 5760   |
| 4       | 1080×7680     | 1920×4 = 7680   |
| 5       | 1080×9600     | 1920×5 = 9600   |
| 6       | 1080×11520    | 1920×6 = 11520  |
| 7       | 1080×13440    | 1920×7 = 13440  |

## Visual Examples

### Horizontal (Landscape) - 4 screens
```
┌─────────┬─────────┬─────────┬─────────┐
│Screen 1 │Screen 2 │Screen 3 │Screen 4 │
│1920×1080│1920×1080│1920×1080│1920×1080│
└─────────┴─────────┴─────────┴─────────┘
         Total: 7680×1080
```

### Vertical (Portrait) - 4 screens
```
┌───────────┐
│ Screen 1  │
│ 1080×1920 │
├───────────┤
│ Screen 2  │
│ 1080×1920 │
├───────────┤
│ Screen 3  │
│ 1080×1920 │
├───────────┤
│ Screen 4  │
│ 1080×1920 │
└───────────┘
Total: 1080×7680
```

## Detection Logic

The system automatically detects layout based on resolution:

```python
# Horizontal detection (landscape)
if height == 1080 and width % 1920 == 0:
    screens = width // 1920
    layout = 'horizontal'

# Vertical detection (portrait)
if width == 1080 and height % 1920 == 0:
    screens = height // 1920
    layout = 'vertical'
```

## Creating Multi-Screen Videos

### Using FFmpeg

**Horizontal 4-screen video (7680×1080):**
```bash
ffmpeg -f lavfi -i testsrc=size=7680x1080:rate=30 -t 60 -c:v libx264 -preset fast -crf 23 horizontal-4-screens.mp4
```

**Vertical 4-screen video (1080×7680):**
```bash
ffmpeg -f lavfi -i testsrc=size=1080x7680:rate=30 -t 60 -c:v libx264 -preset fast -crf 23 vertical-4-screens.mp4
```

### From Existing Videos

**Combine 4 landscape videos side-by-side:**
```bash
ffmpeg -i screen1.mp4 -i screen2.mp4 -i screen3.mp4 -i screen4.mp4 \
  -filter_complex "[0:v][1:v][2:v][3:v]hstack=inputs=4[v]" \
  -map "[v]" -c:v libx264 -preset fast -crf 23 combined-horizontal.mp4
```

**Stack 4 portrait videos vertically:**
```bash
ffmpeg -i screen1.mp4 -i screen2.mp4 -i screen3.mp4 -i screen4.mp4 \
  -filter_complex "[0:v][1:v][2:v][3:v]vstack=inputs=4[v]" \
  -map "[v]" -c:v libx264 -preset fast -crf 23 combined-vertical.mp4
```

## Upload Process

1. **Create your multi-screen video** with exact resolution from tables above
2. **Go to Dashboard** → Click "Sync Upload" button
3. **Set "Number of screens"** to match your video (e.g., 4)
4. **Click "Upload new..."** and select your video
5. System will:
   - Auto-detect: "This is 7680×1080 = 4 horizontal screens" ✅
   - Slice into 4 separate files
   - Upload all to CDN
   - Create synchronized playlist items

## Troubleshooting

### "Video not detected as multi-screen"

**Problem:** Uploaded 4-screen video but system treats it as single screen.

**Cause:** Resolution doesn't match exact specification.

**Solution:**
```bash
# Check your video resolution
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 video.mp4

# Re-encode to exact resolution
# For horizontal 4 screens:
ffmpeg -i input.mp4 -vf scale=7680:1080 -c:v libx264 -preset fast -crf 23 output.mp4

# For vertical 4 screens:
ffmpeg -i input.mp4 -vf scale=1080:7680 -c:v libx264 -preset fast -crf 23 output.mp4
```

### "Wrong number of screens detected"

**Problem:** Video is 3840×1080 but system says "3 screens" instead of "2".

**Diagnosis:**
- Check actual resolution: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 video.mp4`
- Verify it's exactly 3840 (not 3839 or 3841)

**Solution:** Re-encode to exact dimensions using scale filter.

## Best Practices

✅ **DO:**
- Use exact resolutions from the tables above
- Test with small videos first (10-30 seconds)
- Verify resolution before uploading: `ffprobe video.mp4`
- Use H.264 codec with yuv420p pixel format

❌ **DON'T:**
- Use approximate resolutions (e.g., 7679×1080)
- Mix orientations in one video
- Use non-standard aspect ratios
- Upload extremely large files without testing (>500MB)

## Performance Comparison

### Before Auto-Slicing
- Upload 7680×1080 video once
- Each screen requests on-the-fly slice
- Server downloads + processes + serves
- **First load: 30-60 seconds per screen** ⚠️

### After Auto-Slicing
- Upload 7680×1080 video once
- System auto-slices during upload
- All 4 slices saved to CDN
- **Playback: 2-5 seconds per screen** ✅

**Time Savings:** 25-55 seconds per screen on first playback!

## Testing Your Videos

### Quick Test Procedure

1. **Create test video:**
   ```bash
   ffmpeg -f lavfi -i testsrc=size=7680x1080:rate=30 -t 10 \
     -vf "drawtext=text='Screen %{expr\:floor((x/1920))+1}':fontsize=120:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
     -c:v libx264 -preset fast test-4h.mp4
   ```

2. **Upload through dashboard**
3. **Check server logs:**
   ```bash
   sudo tail -f /var/log/pizza-hut-tv/gunicorn.log | grep -i "calculate_screen_layout"
   ```

4. **Verify slicing:**
   - Should see: "Detected HORIZONTAL (landscape) layout: 4 screens"
   - Should see: "Successfully created 4 slices"
   - Should see: "Successfully uploaded 4 sliced files to CDN"

5. **Test playback:**
   - Load each screen in webplayer
   - Verify fast loading (2-5s)
   - Check synchronization

## Summary

- **Horizontal = Landscape** (1920×1080 base) → Width changes
- **Vertical = Portrait** (1080×1920 base) → Height changes
- System auto-detects and slices during upload
- No manual work needed!
- Dramatically faster playback

**Just upload your video with the correct resolution and the system handles everything else!** 🚀
