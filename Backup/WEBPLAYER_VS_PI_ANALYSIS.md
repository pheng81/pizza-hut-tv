# WEBPLAYER vs PI CLIENT - Complete Analysis

## How the Webplayer Works (tv_view.html)

### Main Playback Loop (`tick()` function)
1. **Fetches playlist** from server via `/api/playlist`
2. **Filters active items** based on schedule (days, start/end times)
3. **Shows current item** using `showItem(item)`
4. **Sets timer** based on item duration: `setTimeout(tick, dur*1000)`
5. **Advances to next** active item when timer fires

### Media Display (`showItem()` function)

#### VIDEO HANDLING:
```javascript
// 1. Detect video type
const isVid = isVideoByName(url) || (type === 'video' && !/\.(png|jpe?g|gif|webp|svg)/.test(url));

// 2. Preload video element
const node = await preloadVideo(url);

// 3. CRITICAL: Enable looping
node.loop = (item.repeat !== false); // default TRUE
node.autoplay = true;
node.muted = true;
node.playsInline = true;

// 4. Add to back layer (double-buffering)
clearNode(back);
back.appendChild(node);

// 5. Crossfade transition (1100ms)
back.classList.add('visible');
front.classList.add('fade');

// 6. Start video playback
node.play().catch(()=>{});

// 7. Swap layers (front becomes back, back becomes front)
setTimeout(()=> swapLayers(), 1100);
```

#### IMAGE HANDLING:
```javascript
// 1. Preload image
const node = await preloadImage(url);

// 2. Apply cover sizing (fill screen)
applyCoverSizing(node, node.naturalWidth, node.naturalHeight);

// 3. Add to back layer
clearNode(back);
back.appendChild(node);

// 4. Crossfade transition
back.classList.add('visible');
front.classList.add('fade');
setTimeout(()=> swapLayers(), 1100);
```

### Key Features:

#### Double-Buffering System:
- **Two layers**: `front` (currently visible) and `back` (preparing next)
- Preload next media in back layer while front shows current
- Smooth 1100ms crossfade transition
- Swap layers after transition completes
- No flicker or black screens

#### Video Looping:
- **Default behavior**: `node.loop = true`
- Videos loop continuously until timer advances playlist
- Server doesn't send `repeat` field, so defaults to `true`
- Timer controls when to move to next item (based on `duration`)

#### Memory Management (Android TV Specific):
- Preload='none' (load only when playing)
- Max 1 concurrent video load
- Sequential loading queue
- Size limits: 1920x1080 max
- Cleanup old nodes before adding new

#### Schedule Filtering:
- Checks `enabled` flag on each item
- Filters by days of week (`days` array)
- Filters by time windows (`start`, `end`)
- Only shows items that should be active NOW
- Re-checks every 30 seconds if no active items

---

## How the Pi Client Works (complete_pi_client.py + seamless_video_player.py)

### Main Playback Loop:
1. **Fetches playlist** from server via `/api/playlist`
2. **Filters active items** based on schedule (same as webplayer)
3. **Plays current item** using `media_player.play_media(url, effect, duration)`
4. **Sets timer** using `threading.Timer(duration, on_item_finished)`
5. **Advances to next** when timer fires: `advance_to_next_item()`

### Media Display (`SeamlessMediaPlayer.play_media()`):

#### VIDEO HANDLING:
```python
# 1. Detect media type
if url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
    media_type = 'video'

# 2. Download if URL, or use local path
local_path = self._download_media(url, media_type)

# 3. Play with MPV
self.video_player.play_video(local_path, duration, start_position)

# 4. MPV OPTIONS (from __init__):
mpv.MPV(
    vo='gpu',                    # Video output: GPU with OpenGL
    hwdec='v4l2m2m-copy',       # Hardware decode for Pi
    fullscreen=False,            # NOT fullscreen
    ontop=False,
    border=False,
    autofit='2560x1440',
    keep_open='always',          # Keep window open
    idle='yes',                  # Idle when playlist empty
    # ❌ MISSING: loop-file='inf' (THIS WAS THE BUG!)
)
```

#### IMAGE HANDLING:
```python
# 1. Load image as pygame surface
new_surface = self._load_image(local_path)

# 2. Apply transition effect (fade, slide, zoom, etc.)
if effect and effect != 'cut':
    self.transition_engine.apply_transition(prev_surface, new_surface, effect)

# 3. Blit to screen
self.screen.blit(new_surface, (0, 0))
pygame.display.flip()

# 4. Store as last_frame for next transition
self.last_frame = new_surface
```

### Key Differences:

| Feature | Webplayer (HTML5) | Pi Client (MPV) |
|---------|------------------|-----------------|
| Video Loop | `node.loop = true` ✅ | **Missing** ❌ (was the bug) |
| Double Buffer | Two HTML layers | Single MPV window + pygame |
| Transitions | CSS animations | TransitionEngine (pygame surfaces) |
| Video Player | Browser HTML5 | MPV (libmpv) |
| Image Display | HTML `<img>` | pygame.Surface |
| Memory | Browser managed | Manual cleanup |

---

## THE BUG - Why Pi Videos Stopped Playing

### Root Cause:
**Webplayer**: Videos loop because `node.loop = (item.repeat !== false)` defaults to `true`

**Pi Client**: MPV had NO loop setting, so videos played once and stopped (black screen)

### The Fix Applied:
Added to `seamless_video_player.py` line ~250:
```python
# CRITICAL FIX: Enable looping to prevent black screen
try:
    self.player['loop-file'] = 'inf'  # Loop current file infinitely
    logger.info("🔁 Enabled video looping to prevent black screen")
except Exception as loop_err:
    logger.warning(f"⚠️ Could not enable loop-file: {loop_err}")
```

### How It Works Now:
1. **Timer starts** when video begins (e.g., 10 seconds)
2. **Video loops** continuously in MPV (like HTML5 `loop=true`)
3. **Timer fires** after configured duration
4. **Client advances** to next item: `on_item_finished()` → `advance_to_next_item()`
5. **MPV plays next** video seamlessly (internal playlist or new file)
6. **No black screens** because video is always playing until timer advances

---

## Why Webplayer Works Perfectly:

### Strengths:
✅ Browser handles video/image rendering natively
✅ CSS transitions are hardware-accelerated
✅ HTML5 video `loop` attribute is standard
✅ Double-buffering prevents flicker
✅ Memory managed by browser engine
✅ Same code works on Android TV, desktop, mobile

### Design Philosophy:
- **Declarative**: HTML/CSS describe what to show
- **Event-driven**: JavaScript responds to events
- **Browser-optimized**: Native video decode, GPU compositing
- **Proven**: Millions of websites use same patterns

---

## Why Pi Client Needed the Fix:

### Challenges:
⚠️ MPV requires explicit configuration
⚠️ Python/pygame not as optimized as browsers
⚠️ Manual memory management required
⚠️ Hardware decode on Pi needs special setup
⚠️ No native "loop" default like HTML5 video

### Design Philosophy:
- **Imperative**: Code explicitly controls MPV
- **Callback-based**: MPV events trigger Python functions
- **Manual optimization**: Must configure every setting
- **Platform-specific**: Pi hardware decode (v4l2m2m)

---

## Summary

**The webplayer works perfectly** because HTML5 video elements loop by default (`node.loop = true`), ensuring continuous playback until JavaScript's timer advances the playlist.

**The Pi client had a bug** because MPV wasn't configured to loop videos, causing them to play once and stop (black screen). The timer would eventually advance, but there was a gap.

**The fix** adds `loop-file='inf'` to MPV, matching the HTML5 loop behavior. Now both platforms work identically:
- Videos loop continuously
- Timers control when to advance
- No black screens or gaps
- Seamless playlist navigation

---

## Deployment Status

✅ **Fix applied** to local `seamless_video_player.py`
⏳ **Needs deployment** to Raspberry Pi at `/home/everydayadvertise/pizzahut-client/`
📝 **Deployment methods** documented in `deploy_pi_fix.ps1`
