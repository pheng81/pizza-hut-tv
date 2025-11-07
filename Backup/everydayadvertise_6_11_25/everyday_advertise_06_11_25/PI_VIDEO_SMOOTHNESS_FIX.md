# Pi Video Playback Optimization - October 19, 2025

## Problem Reported
Pi video playback was **stuttering, lagging, and not smooth** - videos would freeze/stutter during playback.

## Root Causes Identified

### 1. **Insufficient Buffering**
- Cache was only 30 seconds (`cache_secs=30`)
- Buffer size was only 150MB (`demuxer_max_bytes='150M'`)
- Cache was disabled on startup (`cache_pause=False`)
- **Result:** Video would start playing before enough data was buffered, causing stutters

### 2. **Sub-Optimal Video Sync Method**
- Using `video_sync='audio'` which can cause frame drops
- **Result:** Video frames not synced smoothly to display refresh rate

### 3. **Motion Interpolation Disabled**
- `interpolation=False` was preventing smooth motion
- No temporal scaling for frame transitions
- **Result:** Choppy motion, especially in panning/fast movement scenes

### 4. **Hardware Decode Not Optimized**
- Using `hwdec='auto'` instead of `hwdec='auto-safe'`
- Not enabling all codecs for hardware decoding
- **Result:** CPU decoding fallback causing performance issues

## Solutions Implemented

### 1. **Aggressive Caching** ✅
```python
cache='yes',
demuxer_max_bytes='500M',  # Increased from 150M
demuxer_max_back_bytes='200M',  # Increased from 50M
cache_secs=120,  # Increased from 30 seconds to 2 minutes
```
**Benefits:**
- Prevents stuttering from network hiccups
- Smoother transitions between videos
- Better handling of high-bitrate content

### 2. **Cache Pre-Loading** ✅
```python
cache_pause=True,  # Pause to build cache
cache_pause_initial=True,  # Build cache before starting
cache_pause_wait=2,  # Wait 2 seconds
```
**Benefits:**
- Ensures buffer is full before playback starts
- Eliminates initial stuttering
- More stable playback throughout

### 3. **Display-Resampled Video Sync** ✅
```python
video_sync='display-resample',  # Match display refresh rate
interpolation=True,  # Enable motion interpolation
tscale='oversample',  # Smooth temporal scaling
```
**Benefits:**
- Butter-smooth motion
- Frames perfectly synced to display refresh rate
- No judder or frame drops
- Professional-quality playback

### 4. **Optimized Hardware Decoding** ✅
```python
hwdec='auto-safe',  # Hardware decode with fallback
hwdec_codecs='all',  # Enable for all codecs
```
**Benefits:**
- Maximum use of GPU/hardware decoder
- Lower CPU usage
- Cooler Pi temperature
- Better performance on high-resolution videos

## Expected Results

### Before Fix:
- ❌ Video stuttering and lag
- ❌ Choppy motion
- ❌ Initial buffering issues
- ❌ High CPU usage

### After Fix:
- ✅ Smooth, butter-like playback
- ✅ Professional motion interpolation
- ✅ No stuttering or lag
- ✅ Efficient hardware acceleration
- ✅ Stable performance

## Technical Details

### File Modified
- `seamless_video_player.py` - Lines 86-115

### MPV Configuration Changes
| Setting | Before | After | Impact |
|---------|--------|-------|--------|
| `video_sync` | `audio` | `display-resample` | Smoother motion |
| `interpolation` | `False` | `True` | Better frame blending |
| `cache_secs` | `30` | `120` | 4x buffer |
| `demuxer_max_bytes` | `150M` | `500M` | 3.3x buffer |
| `cache_pause` | `False` | `True` | Pre-load enabled |
| `hwdec` | `auto` | `auto-safe` | Better compatibility |

## Deployment
- **File Deployed:** `seamless_video_player.py`
- **Deployed To:** `raspberrypi.local:/home/everydayadvertise/`
- **Service Restart:** Successful ✅
- **Time:** October 19, 2025 10:14 (Local Time)

## Verification Steps

1. **Check Pi is playing videos:**
   ```bash
   ssh everydayadvertise@raspberrypi.local "sudo journalctl -u pizza-hut-tv -f"
   ```

2. **Look for these indicators of smooth playback:**
   - ✅ No "buffering" messages
   - ✅ Continuous playback without pauses
   - ✅ "✅ MPV player initialized" in logs
   - ✅ Videos transitioning smoothly

3. **Visual verification on TV:**
   - Watch for smooth motion (no stutter)
   - Check transitions between videos are seamless
   - Verify no "loading" or black frames

## Monitoring

Monitor for these improvements:
- **Smoother playback** - No stuttering during videos
- **Better transitions** - Seamless video-to-video changes
- **No buffering pauses** - Videos should play continuously
- **Lower CPU usage** - Hardware decoding should reduce load

## Rollback Plan

If issues occur, revert these settings:
```python
# Revert to conservative settings
video_sync='audio',
interpolation=False,
cache_secs=30,
demuxer_max_bytes='150M',
cache_pause=False,
```

## Additional Optimizations (if needed)

If still experiencing issues:

1. **Network Issues:**
   - Check WiFi signal strength
   - Use wired Ethernet if possible
   - Reduce video bitrate/resolution

2. **Pi Performance:**
   - Ensure Pi is not overheating (check `vcgencmd measure_temp`)
   - Close unnecessary background processes
   - Update Pi firmware (`sudo rpi-update`)

3. **Video Format:**
   - Use H.264 codec (best hardware support)
   - Keep resolution at 1080p or lower
   - Use reasonable bitrates (5-10 Mbps)

## Notes

- Motion interpolation may add slight latency (~50ms) but provides much smoother playback
- Larger cache uses more RAM but prevents stuttering
- Hardware decoding is essential for smooth 1080p playback on Pi 4
- Display-resample sync matches Pi's HDMI output refresh rate (typically 60Hz)
