# 🍕 Pi Client Display & Rotation System

## Overview
The Raspberry Pi client uses **pygame** for UI and **MPV player** (via SeamlessVideoPlayer) for video playback. Content always displays **fullscreen** and handles both horizontal and vertical orientations.

---

## Display System

### 1. **Initialization** (`complete_pi_client.py`)
```python
# Lines 528-565
pygame.init()
info = pygame.display.Info()
width = info.current_w   # Usually 1920
height = info.current_h  # Usually 1080

# Fullscreen display
screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)
```

**Default Resolution:** 1920x1080 (landscape/horizontal)

---

## Orientation & Rotation System

### 2. **How Orientation Works**

The Pi receives TWO values from the server (`/playlist/` API):

1. **`orientation`**: `'vertical'` | `'horizontal'` | `'default'`
2. **`rotation`**: `0` | `90` | `180` | `270` degrees

### 3. **Rotation Calculation** (`complete_pi_client.py` line 1925-1930)

```python
# Base rotation from orientation
base = 90 if orientation == 'vertical' else 0

# Total rotation = base + manual rotation
total = ((base + rotation) % 360 + 360) % 360

# Apply to media player
media_player.set_display_rotation(total)
```

**Examples:**
- **Horizontal (default)**: `base=0°`, `rotation=0°` → `total=0°` (landscape)
- **Vertical**: `base=90°`, `rotation=0°` → `total=90°` (portrait)
- **Vertical + 90° rotation**: `base=90°`, `rotation=90°` → `total=180°` (upside-down)
- **Horizontal + 90° rotation**: `base=0°`, `rotation=90°` → `total=90°` (portrait)

---

## Display Rotation Implementation

### 4. **For Videos** (`seamless_video_player.py` line 161-196)

Uses **MPV player** with `video-rotate` property:

```python
def set_display_rotation(self, angle: int):
    """Update MPV video rotation."""
    self.display_rotation = angle
    
    # Try multiple methods to set MPV rotation
    try:
        self.player.set_property('video-rotate', angle)
    except:
        try:
            self.player['video_rotate'] = angle
        except:
            self.player.command('set', 'video-rotate', str(angle))
```

**MPV handles video rotation natively** - no performance impact.

---

### 5. **For Images** (`seamless_video_player.py` line 626-650)

Uses **pygame.transform.rotate()** on image surfaces:

```python
def _prepare_surface_for_display(self, surface):
    """Scale and rotate image according to display rotation."""
    angle = self.display_rotation % 360
    
    # Swap width/height for 90° or 270° rotations
    rotated_axis = bool(angle % 180)
    if rotated_axis:
        target_size = (window_height, window_width)
    else:
        target_size = (window_width, window_height)
    
    # Scale image to target size
    surface = pygame.transform.scale(surface, target_size)
    
    # Rotate image (pygame uses negative angles)
    if angle:
        surface = pygame.transform.rotate(surface, -angle)
    
    # Final scale to window size
    surface = pygame.transform.scale(surface, window_size)
    
    return surface
```

**Key points:**
- Images are **rotated counter-clockwise** (`-angle`)
- **Width/height swapped** for 90°/270° rotations
- **Scaled to fill screen** (no letterboxing)
- Images are **cached** with rotation applied

---

## Horizontal vs Vertical Display

### 6. **Horizontal (Default)**

```
┌─────────────────────────────────────┐
│                                     │  Screen: 1920x1080
│         Content fills screen        │  Base rotation: 0°
│         (landscape orientation)     │  Content: stretched horizontally
│                                     │
└─────────────────────────────────────┘
```

- **Base rotation**: `0°`
- **Content**: Displays in landscape (wide)
- **Use case**: Standard TV displays, menu boards

---

### 7. **Vertical Mode**

```
┌───────────┐
│           │  Screen: 1920x1080 (physical)
│           │  Base rotation: 90°
│  Content  │  Display: 1080x1920 (logical)
│  rotated  │  Content: stretched vertically
│    90°    │
│           │
│           │
└───────────┘
```

- **Base rotation**: `90°` (clockwise)
- **Content**: Rotated 90° to create portrait effect
- **Screen stays landscape**, content rotates inside
- **Use case**: Vertical menu boards, door displays

---

## Rotation Change Detection

### 8. **Real-time Updates** (`complete_pi_client.py` line 1900-1975)

```python
# Fetch playlist every 10 seconds
def fetch_playlist():
    # Get orientation and rotation from server
    new_orientation = data.get('orientation', 'default')
    new_rotation = int(data.get('rotation', 0))
    
    # Detect changes
    old_orientation = self.screen_orientation
    old_rotation = self._last_rotation_seen
    
    orientation_changed = (new_orientation != old_orientation)
    rotation_changed = (new_rotation != old_rotation)
    
    # If rotation changed, restart playback
    if rotation_changed or orientation_changed:
        # Apply new rotation
        base = 90 if new_orientation == 'vertical' else 0
        total = (base + new_rotation) % 360
        media_player.set_display_rotation(total)
        
        # Clear image cache (images need re-rotation)
        media_player.image_cache.clear()
        
        # Stop current media
        media_player.stop()
        
        # Restart from beginning
        self.current_index = 0
        self.advance_to_next_item()
```

**When dashboard rotation changes:**
1. ✅ Detected within **10 seconds** (playlist refresh)
2. ✅ Rotation applied immediately
3. ✅ Image cache cleared (images re-rendered with new rotation)
4. ✅ Playback restarted to apply rotation
5. ✅ Videos use MPV native rotation (instant)
6. ✅ Images use pygame rotation (cached)

---

## Key Differences: Pi vs Android TV

| Feature | **Pi Client** | **Android TV App** |
|---------|---------------|-------------------|
| **Display Engine** | pygame + MPV player | ImageView + SurfaceView |
| **Video Rotation** | MPV `video-rotate` property | View.rotation (Android) |
| **Image Rotation** | pygame.transform.rotate() | View.rotation (Android) |
| **Rotation Detection** | 10s polling | 5s polling |
| **Orientation Base** | 90° for vertical | Must be manual |
| **Cache Handling** | Clear image cache on change | No cache |
| **Restart on Change** | Yes (full playback restart) | No (live rotation) |

---

## Summary

### **How Pi Displays Content:**

✅ **Fullscreen pygame** window (1920x1080)  
✅ **MPV player** for videos (hardware-accelerated)  
✅ **Pygame surfaces** for images (software-rendered)  
✅ **Rotation** applied via transform (0°/90°/180°/270°)  
✅ **Orientation** adds base 90° for vertical mode  
✅ **Content fills screen** (scaled, no letterboxing)  
✅ **Updates detected** every 10 seconds via playlist API  
✅ **Playback restarts** when rotation changes (ensures clean transition)

### **How Rotation Works:**

1. **Dashboard** sets `orientation` ('vertical'/'horizontal') and `rotation` (0°-270°)
2. **Server** returns both values in `/playlist/` API
3. **Pi client** calculates total rotation: `base + rotation`
4. **MPV** rotates videos natively (instant)
5. **Pygame** rotates images via transform (cached)
6. **Screen** always stays landscape (1920x1080), content rotates inside

---

## Testing Rotation

To test rotation changes:

1. **Open dashboard** for your Pi screen
2. **Click Rotate button** (0° → 90° → 180° → 270°)
3. **Wait 10 seconds** (Pi polls playlist)
4. **Observe** content rotation changes
5. **Check logs:** `🔍 ROTATION CHECK: old=X° new=Y° changed=True`

**Expected behavior:**
- Content rotates smoothly
- Videos use MPV rotation (instant)
- Images reload with new rotation (brief pause)
- No black bars or letterboxing
- Fills entire screen

---

**Created:** October 25, 2025  
**Pi Client:** `complete_pi_client.py` + `seamless_video_player.py`  
**Display:** pygame 1920x1080 fullscreen  
**Rotation:** MPV (videos) + pygame.transform (images)
