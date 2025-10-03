# Pizza Hut TV - Screen ID Architecture

## Critical Understanding: Screen IDs are User-Defined

**IMPORTANT:** Screen IDs can be ANY custom string chosen by users. They are NOT standardized as "screen1", "screen2", etc.

### Examples of Valid Screen IDs:
- `screen1`, `screen2`, `screen3` (common convention)
- `Left Display`, `Right Display`, `Center Display`
- `Main TV`, `Secondary TV`
- `Screen A`, `Screen B`, `Screen C`
- Any other custom name the user chooses

## How Screen IDs Work

### Storage Format
Screen IDs are stored with a store prefix for uniqueness:
```
{storeId}_{screenId}
```

Examples:
- `1000_screen1` - Store 1000, screen named "screen1"
- `1135_Left Display` - Store 1135, screen named "Left Display"
- `1931_Main TV` - Store 1931, screen named "Main TV"

### Code Handling
The codebase accepts both formats:
1. **Full format:** `{storeId}_{screenId}` - e.g., `1000_screen1`
2. **Short format:** `{screenId}` - e.g., `screen1`

When a short format is provided, the system automatically prefixes it with the store ID.

## How Slice Order is Determined

### WRONG APPROACH ❌
```python
# DON'T DO THIS - assumes screen ID format
if str(screen_id).startswith('screen'):
    screen_num_str = str(screen_id).replace('screen', '')
    screen_num = int(screen_num_str)
    crop_x_offset = (screen_num - 1) * slice_width
```

**Problem:** This assumes screen IDs follow "screenN" pattern. Fails with custom names like "Left Display".

### CORRECT APPROACH ✅
```python
# Get slice order from playlist metadata (sync_ref.order)
playlist = get_playlist_from_server()
for item in playlist:
    if item.get('media_type') == 'video':
        sync_ref = item.get('sync_ref', {})
        if isinstance(sync_ref, dict):
            slice_order = int(sync_ref.get('order', 0))
            crop_x_offset = slice_order * slice_width
            break
```

**Why it works:** Slice order comes from playlist metadata, NOT from parsing screen ID.

## Playlist Metadata Structure

When a video is assigned to multiple screens for slicing, each screen's playlist contains `sync_ref` metadata:

```json
{
  "playlist": [
    {
      "file": "video.mp4",
      "media_type": "video",
      "sync_ref": {
        "group": "sync-group-uuid",
        "role": "master",    // or "follower"
        "order": 0,          // 0 = first slice, 1 = second slice, etc.
        "count": 4,          // total number of screens
        "mode": "split-h"    // horizontal split
      }
    }
  ]
}
```

### sync_ref Fields:
- **group** - UUID of the sync group
- **role** - "master" (first screen) or "follower" (other screens)
- **order** - Slice position (0, 1, 2, 3, etc.)
- **count** - Total number of screens in the sync group
- **mode** - Slice mode ("split-h" for horizontal split)

## How Webplayer Handles It

The webplayer correctly uses metadata approach:

```javascript
// templates/webplayer/player.html lines 857-865
const sliceOrder = (syncRef.order !== undefined && syncRef.order !== null) 
    ? syncRef.order 
    : Math.max(0, screenNumber - 1);
```

It prefers `syncRef.order` from playlist metadata, only falling back to parsing screen number if metadata is unavailable.

## How custom_player.py Handles It (Fixed)

The custom player now correctly uses the same metadata-driven approach:

```python
# custom_player.py lines 891-908
if playlist and not self.is_promo:
    for item in playlist:
        if item.get('media_type') == 'video':
            sync_ref = item.get('sync_ref', {})
            if isinstance(sync_ref, dict):
                # Get slice order from metadata (0 = first slice, 1 = second slice, etc.)
                self.slice_order = int(sync_ref.get('order', 0))
                self.crop_x_offset = self.slice_order * self.slice_width
                slice_count = sync_ref.get('count', 1)
                slice_mode = sync_ref.get('mode', 'split-h')
                print(f"🎬 Slice configuration from playlist metadata:")
                print(f"   Slice order: {self.slice_order} (of {slice_count} screens)")
                print(f"   Slice mode: {slice_mode}")
                print(f"   Crop X offset: {self.crop_x_offset}px")
                break
```

## How Sync Groups are Created

When creating a sync group (multi-screen video slicing), the server:

1. Creates a sync group with unique UUID
2. Assigns the video to each screen's playlist
3. Sets `sync_ref` metadata for each screen:
   - Screen 1: `{order: 0, role: 'master', count: 4, mode: 'split-h'}`
   - Screen 2: `{order: 1, role: 'follower', count: 4, mode: 'split-h'}`
   - Screen 3: `{order: 2, role: 'follower', count: 4, mode: 'split-h'}`
   - Screen 4: `{order: 3, role: 'follower', count: 4, mode: 'split-h'}`

See `app.py` lines 7270-7320 for implementation details.

## Slice Offset Calculation

Each screen displays a horizontal slice of the full video:

```
Full video: 7680px wide (4 screens × 1920px each)

Screen with order=0: Shows pixels 0-1920 (crop_x_offset = 0 * 1920 = 0px)
Screen with order=1: Shows pixels 1920-3840 (crop_x_offset = 1 * 1920 = 1920px)
Screen with order=2: Shows pixels 3840-5760 (crop_x_offset = 2 * 1920 = 3840px)
Screen with order=3: Shows pixels 5760-7680 (crop_x_offset = 3 * 1920 = 5760px)
```

Formula:
```python
crop_x_offset = slice_order * slice_width
# where slice_width = 1920px (standard 1080p width)
```

## Dashboard Display Names

For display purposes, the dashboard extracts screen numbers from IDs using the format convention:

```javascript
// dashboard.html - getScreenDisplayName()
if (screenId.includes('_')) {
    const parts = screenId.split('_');
    const storeId = parts[0];
    const screenType = parts[1];
    
    if (screenType.startsWith('screen')) {
        const num = screenType.replace('screen', '');
        return `Screen ${num} (Store ${storeId})`;
    }
}
```

**Note:** This is ONLY for display purposes. The actual screen ID is stored and used as-is, without parsing.

## API Endpoints

### Get Playlist
```
GET /playlist/{store_id}/{full_screen_id}
```

Example:
```
GET /playlist/1000/1000_screen1
```

Returns playlist with sync_ref metadata for slice videos.

### Screen Heartbeat
```
POST /api/screen_heartbeat
Body: {"store_id": "1000", "screen_id": "screen1"}
```

Accepts both full and short screen ID formats.

## Key Takeaways

1. ✅ **Screen IDs are user-defined** - can be any string
2. ✅ **Slice order comes from playlist metadata** - `sync_ref.order`
3. ✅ **Never parse screen IDs to determine behavior** - use metadata
4. ✅ **Store IDs are numeric** - e.g., `1000`, `1135`, `1931`
5. ✅ **Full screen ID format:** `{storeId}_{screenId}`
6. ✅ **Promo screens** - identified by ID starting with "promo"
7. ✅ **Backward compatibility** - both full and short formats supported

## Testing Scenarios

### Test 1: Standard Naming
- Screens: `1000_screen1`, `1000_screen2`, `1000_screen3`, `1000_screen4`
- Expected: Each screen shows correct slice based on sync_ref.order

### Test 2: Custom Naming
- Screens: `1000_Left Display`, `1000_Center Display`, `1000_Right Display`
- Expected: Each screen shows correct slice based on sync_ref.order (NOT parsed from name)

### Test 3: Mixed Naming
- Screens: `1000_screen1`, `1000_Main TV`, `1000_Screen A`, `1000_screen4`
- Expected: Each screen shows correct slice based on sync_ref.order

### Test 4: No Sync Group
- Screen: `1000_screen1` playing non-sliced video
- Expected: No sync_ref in playlist, displays full video (crop_x_offset = 0)

## Debugging

### Check Playlist Metadata
```bash
curl -H "X-User-Code: YOUR_CODE" \
  https://everydayadvertise.com/playlist/1000/1000_screen1
```

Look for `sync_ref.order` in video items.

### Custom Player Logs
When starting custom player, check output:
```
🎬 Slice configuration from playlist metadata:
   Slice order: 1 (of 4 screens)
   Slice mode: split-h
   Crop X offset: 1920px
```

### Webplayer Console
Open browser console on webplayer:
```javascript
console.log('Slice order:', sliceOrder);
console.log('Crop offset:', cropXOffset);
```

## Related Files

- `app.py` - Server-side playlist generation and sync group management
- `custom_player.py` - Pi client player (metadata-driven slicing)
- `templates/webplayer/player.html` - Browser-based player (metadata-driven slicing)
- `templates/dashboard.html` - Admin dashboard (screen management)

## Conclusion

The key insight is that **screen IDs are labels, not instructions**. The actual behavior (which slice to show) comes from playlist metadata (`sync_ref.order`), not from parsing the screen ID string. This allows users to name their screens anything they want while maintaining correct multi-screen video slicing functionality.
