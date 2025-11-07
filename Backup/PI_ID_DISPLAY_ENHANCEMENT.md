# Pi ID Display Enhancement

## Overview
Enhanced the Pi ID display to be **MUCH LARGER and MORE VISIBLE** in two locations:
1. **Raspberry Pi Client Screen** - Large, centered display with red border
2. **Webplayer Pairing Screen** - Fixed bottom display for easy identification

## Changes Made

### 1. Raspberry Pi Client (`complete_pi_client.py`)

#### Before:
- Small text in bottom-right corner (14px font)
- Semi-transparent, hard to read
- Single line display

#### After:
- **LARGE bold text** (36px font, centered)
- **Bottom-center positioning** for better visibility
- **Two-line display**:
  - Main line: `Pi ID: {hostname-XXXX}` (36px, white, bold)
  - Hint line: `[Press 'I' to hide]` (14px, gray)
- **Prominent background**:
  - Black semi-opaque background (200 alpha)
  - Red border (Pizza Hut red: #c8102e)
  - 8px rounded corners
  - Large padding (40px width, 20px height)
- **Better visibility**: Can be seen from across the room!

#### Display Position:
```
┌─────────────────────────────────────┐
│                                     │
│         Video Content               │
│                                     │
│                                     │
│        ┌──────────────────┐        │
│        │ Pi ID: raspberrypi-a1b2 │ │ ← Large, centered
│        │  [Press 'I' to hide]   │  │ ← Hint text
│        └──────────────────┘        │
└─────────────────────────────────────┘
```

### 2. Webplayer Pairing Screen (`templates/webplayer/index.html`)

#### New Features:
- **Fixed bottom display** showing Pi ID
- **Automatic fetching** from new API endpoint
- **Professional styling**:
  - Position: Fixed bottom, centered
  - Background: Semi-transparent black (85% opacity)
  - Border: 2px red border (Pizza Hut red)
  - Font: Large, bold (32px)
  - Labels: "Pi ID" label above the ID
  - Shadow: Subtle shadow for depth

#### Display Layout:
```
┌─────────────────────────────────────┐
│  Enter your Android TV pairing code │
│                                     │
│  [____]  4-digit code               │
│                                     │
│      [Link Code]                    │
├─────────────────────────────────────┤
│        ┌───────────────┐           │
│        │    Pi ID      │           │ ← Fixed bottom
│        │ raspberrypi-a1b2 │         │ ← Large display
│        └───────────────┘           │
└─────────────────────────────────────┘
```

### 3. New API Endpoint (`app.py`)

Added `/api/pi_id` endpoint that returns:
```json
{
  "success": true,
  "pi_id": "raspberrypi-a1b2",
  "hostname": "raspberrypi"
}
```

#### Implementation:
- Uses `socket.gethostname()` for hostname
- Uses `uuid.getnode()` for MAC address
- Generates Pi ID: `{hostname}-{last_4_mac_chars}`
- Compatible with all TV browsers (fallback to XHR)

## Visual Improvements

### Raspberry Pi Client
| Aspect | Before | After |
|--------|--------|-------|
| Font Size | 14px | **36px (2.5x larger!)** |
| Position | Bottom-right | **Bottom-center** |
| Visibility | Semi-transparent | **Bold with background** |
| Readability | Poor | **Excellent** |
| Border | None | **Red border (brand color)** |

### Webplayer
| Feature | Status |
|---------|--------|
| Pi ID Display | ✅ Added |
| Auto-fetch | ✅ Implemented |
| Fixed Position | ✅ Bottom-center |
| Professional Style | ✅ With red border |
| Cross-browser | ✅ Works on all TVs |

## Use Cases

### 1. Customer-Facing Displays
- Pi ID auto-hides after 5 minutes
- Press 'I' key to toggle visibility
- Clean display for customers

### 2. Setup & Configuration
- **Large, visible Pi ID** makes identification easy
- Can be seen from across the store
- Perfect for remote configuration

### 3. Webplayer on Fire TV / Android TV
- Pi ID always visible at bottom
- Easy to reference when configuring
- Professional appearance

## Files Modified

1. **complete_pi_client.py** (Lines 565-605)
   - Enhanced `draw_overlay_info()` method
   - Larger font (36px bold)
   - Centered positioning with red border
   - Two-line display with hint text

2. **templates/webplayer/index.html**
   - Added CSS for `.pi-id-display` class
   - Added HTML element for Pi ID
   - Added JavaScript to fetch and display Pi ID

3. **app.py** (Added after line 5180)
   - New `/api/pi_id` endpoint
   - Returns hostname and Pi ID
   - Error handling for all cases

## Testing

### On Raspberry Pi:
1. The Pi should already be running with the new code
2. You should see a **LARGE** Pi ID at the bottom-center
3. It will have:
   - White text: "Pi ID: raspberrypi-XXXX"
   - Gray hint: "[Press 'I' to hide]"
   - Black background with red border
4. Press 'I' key to toggle visibility
5. Auto-hides after 5 minutes (default)

### On Webplayer:
1. Open webplayer at: http://54.252.90.27/webplayer
2. You should see the Pi ID at the bottom of the screen
3. It will show "Loading..." then display the actual Pi ID
4. The display has:
   - "Pi ID" label
   - Actual ID below in large text
   - Red border around it

## Deployment Status

✅ **Committed to Git** (commit: 22901da)  
✅ **Deployed to Pi**: complete_pi_client.py uploaded  
✅ **Deployed to Server**: app.py + webplayer templates uploaded  
✅ **Service Restarted**: Server running with new code

## Next Steps

To see the changes:

### Raspberry Pi:
```bash
# Restart the Pi client to see large Pi ID
sudo systemctl restart pizza-hut-tv
```

### Webplayer:
1. Open: http://54.252.90.27/webplayer
2. Hard refresh if needed (Ctrl+F5)
3. Pi ID should appear at bottom

## Benefits

1. **Easy Identification**: Can identify Pis from across the room
2. **Professional**: Clean, branded appearance with red border
3. **Flexible**: Show/hide with keyboard or auto-hide timer
4. **Consistent**: Same Pi ID format across all displays
5. **User-Friendly**: Large, readable text
6. **Remote-Ready**: Perfect for Remote Pi Manager feature
