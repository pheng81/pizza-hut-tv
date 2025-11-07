# Pi Video Playback - Final Diagnosis & Fix

## Current Status ✅
- **No more crashes** - X11 errors fixed
- **Video IS playing** - logs show continuous playback
- **Sync monitoring active** - drift corrections happening

## Why Video May Still Appear "Not Smooth"

### 1. **Sync Drift Issues** 🎯
Your logs show constant micro-adjustments:
```
⚡ Micro-adjustment: rate=1.050, drift=497ms
⚡ Micro-adjustment: rate=1.057, drift=566ms
```

**This means:** The Pi is constantly trying to catch up with the server time, causing **playback speed variations** (plays at 1.05x speed to catch up).

**Solution:** Disable sync monitoring for smoother playback.

### 2. **Video File Quality** 📹
Check your video file properties:
- **Codec:** Should be H.264 (not H.265/HEVC)
- **Resolution:** Max 1080p for smooth Pi playback
- **Bitrate:** 5-8 Mbps recommended (not 20-30 Mbps)
- **Frame Rate:** 30fps or 60fps (constant, not variable)

**Test:** Play a simple low-bitrate video to see if it's smooth.

### 3. **Network Caching** 🌐
The cached file `fd3068ff4e17c12ac588723200c38c58.mp4` is being reused.
- Is the original video high-quality/large?
- Is it downloading completely before playing?

## Quick Tests

### Test 1: Check Video File Properties
```bash
ssh everydayadvertise@192.168.1.131 "ffprobe cache/fd3068ff4e17c12ac588723200c38c58.mp4 2>&1 | grep -E '(Video|Duration|bitrate)'"
```

### Test 2: Disable Sync for Smooth Test
Edit `complete_pi_client.py` and temporarily disable sync monitoring.

### Test 3: Test with Different Video
Upload a known-good video:
- H.264 codec
- 720p or 1080p
- 5 Mbps bitrate
- 30fps constant

## Current MPV Settings (Optimized for Pi)

```python
vo='x11',  # Reliable X11 output
hwdec='no',  # Software decode (stable)
video_sync='audio',  # Audio-based sync (reliable)
interpolation=False,  # No interpolation (Pi can't handle it)
cache_secs=20,  # Moderate 20-second cache
demuxer_max_bytes='100M',  # 100MB buffer
```

## What "Smooth" Should Look Like

✅ **Good Signs:**
- No visible stuttering or frame skips
- Constant playback speed
- No "loading" pauses
- Transitions without black screens

❌ **Bad Signs (what you might be seeing):**
- **Speed-up/slow-down** - from sync adjustments
- **Frame drops** - from CPU overload
- **Buffering pauses** - from network/disk issues
- **Judder** - from mismatched frame rates

## Recommended Next Steps

### Option A: Disable Sync (Simplest)
This will give you the smoothest playback but lose multi-screen synchronization.

### Option B: Optimize Video Files
Re-encode videos with these settings:
```bash
ffmpeg -i input.mp4 -c:v libx264 -preset medium -crf 23 -maxrate 5M -bufsize 10M -pix_fmt yuv420p -r 30 -c:a aac -b:a 128k output.mp4
```

### Option C: Hardware Upgrade
- Use Pi 5 (much more powerful)
- Use wired Ethernet (not WiFi)
- Use better quality SD card (Class 10 or UHS-1)

## Testing Commands

### Check if MPV is actually running smoothly:
```bash
ssh everydayadvertise@192.168.1.131 "top -bn1 | grep -E '(python3|mpv)'"
```

### Check CPU temperature (throttling if >80°C):
```bash
ssh everydayadvertise@192.168.1.131 "vcgencmd measure_temp"
```

### Check actual video properties:
```bash
ssh everydayadvertise@192.168.1.131 "ls -lh cache/*.mp4"
```

## Quick Fix to Try NOW

**Increase video cache for smoother buffering:**

In `seamless_video_player.py`, change:
```python
cache_secs=20,  # Change to 30 or 40
demuxer_max_bytes='100M',  # Change to '200M'
```

This gives MPV more breathing room before playback.

## My Assessment

Based on the logs, **the video IS playing successfully**. The "not smooth" you're experiencing is likely:

1. **Sync drift corrections** (speed variations to catch up)
2. **Variable bitrate video file** (inconsistent frame delivery)
3. **Network delays** causing buffer underruns

**Most Likely Culprit:** The constant sync adjustments (`rate=1.050` etc) mean the video is playing at slightly faster/slower speeds to stay in sync, which **feels jerky/not smooth**.

**Quick Win:** Try disabling sync monitoring temporarily to see if playback becomes smooth.
