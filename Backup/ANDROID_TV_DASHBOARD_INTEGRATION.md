# Android TV App Dashboard Integration Status

## ✅ DASHBOARD FUNCTIONS NOW SUPPORTED

### Playlist & Schedule Controls
- **refresh playlist** ✅ WebView polls `/playlist` every 15s + gets server orientation/rotation
- **TV (Force Reload)** ✅ Enhanced command polling handles `reload` commands from dashboard 
- **Schedule editing** ✅ WebView respects all schedule windows (primary + extra) with day/time logic
- **Item enable/disable** ✅ WebView filters to only show enabled items within active schedule windows
- **Duration controls** ✅ WebView uses `item.duration` for display timing (1-120s range)
- **Time/date scheduling** ✅ Supports both ISO datetime and time-only formats with midnight crossing
- **Repeat days** ✅ Evaluates `item.days` array against current day-of-week

### Media & Effects
- **Effects (1-10)** ✅ All transition effects mapped: cut, fade, dissolve, slides, zooms, wipes
- **Rotation** ✅ Respects server `orientation` + `rotation` with smart auto-orientation per media
- **Video looping** ✅ Honors `item.repeat` flag (default true unless explicitly disabled)
- **Link Next** ✅ When `item.link_next=true`, stays on current item instead of advancing

### Sync & Multi-Screen  
- **Sync Upload** ✅ WebView prioritizes `slice_url` for synchronized multi-screen playback
- **Auto-Slice** ✅ Handles sliced video files with proper sync group metadata logging
- **Sync groups** ✅ Recognizes `sync_ref` metadata and reports group/role/order in debug

### Commands & Status
- **Retry on TV** ✅ Enhanced command polling handles `retry_item` by item_id or filename
- **Flush cache** ✅ Handles `flush_cache` commands to clear probe/status caches
- **Status reporting** ✅ Reports `play_ok`, `play_fail`, `load_ok`, `load_fail` with timestamps
- **Heartbeat** ✅ Sends heartbeat every 30s so dashboard knows screen is online

### Apply All & Replication
- **Apply to ALL stores** ✅ Android TV will receive updated playlists when master replicates
- **Replace All** ✅ Android TV gets the mirrored playlist structure automatically
- **Protected screens** ✅ Rotation and local changes work when protection enabled

## 🔧 TECHNICAL ENHANCEMENTS

### Smart Scheduling
- WebView now evaluates schedules CLIENT-side (matches server logic exactly)
- Handles ISO datetime (YYYY-MM-DDTHH:MM:SS) and time-only (HH:MM:SS) formats
- Supports midnight-crossing time windows
- Multiple schedule windows per item with per-window enable/disable
- Shows "no active items" debug message when outside schedule

### Improved Media Handling  
- Explicit cover sizing for Android WebView (avoids object-fit issues)
- Video overlay prevention hints for compositor 
- Auto-orientation: portrait media rotates stage 90° on landscape screens
- Fallback URL support for CDN/local file serving
- Smart preloading of next scheduled item

### Enhanced Status & Debugging
- Debug overlay with ?debug=1 shows real-time status
- Per-item status reporting with file/item_id mapping  
- Command execution logging
- Orientation and sizing debug info
- Sync group metadata logging

### Command Channel Reliability
- Polls `/api/commands` every ~40% of ticks (better responsiveness)
- Handles reload, retry_item, flush_cache command types
- Immediate playlist restart on reload commands
- Targeted item retry by ID or filename

### Visibility & Performance
- Pauses playback when browser hidden (saves resources)
- Resumes video on visibility return  
- Proper cleanup on page unload
- Resize handling with orientation recalculation

## 🧪 TESTING VALIDATION

### Schedule Functions
1. Set item start/end times → Android TV respects time windows ✅
2. Add extra schedule windows → Android TV evaluates all windows ✅  
3. Enable/disable items → Android TV only shows enabled items ✅
4. Disable schedule windows → Android TV skips disabled windows ✅
5. Set weekday restrictions → Android TV checks current day ✅

### Dashboard Controls  
1. Click "TV" button → Android TV immediately reloads playlist ✅
2. Change duration → Android TV uses new timing ✅
3. Set effects → Android TV applies transition animations ✅  
4. Rotate screen → Android TV updates orientation ✅
5. Retry failed item → Android TV immediately attempts replay ✅

### Multi-Screen Sync
1. Use "Sync Upload" → Android TVs get slice URLs and play in sync ✅
2. Use "Auto-Slice" → Android TVs receive proper sliced files ✅  
3. Add sync follower → New screen joins group with correct slice ✅

### Replication & Apply All
1. Master store "Apply to ALL" → Non-master Android TVs get updates ✅
2. "Replace All" → Android TVs receive complete mirrored playlist ✅
3. Protected screens → Android TV ignores unwanted replication ✅

## 🚀 ANDROID TV NOW FULLY DASHBOARD-COMPATIBLE

The Android TV WebView now:
- **Respects every dashboard control** (schedule, effects, rotation, commands)
- **Matches Pi behavior** (same playlist logic, same media handling)  
- **Provides real-time status** (dashboard lights show current state)
- **Handles sync groups** (multi-screen setups work seamlessly)
- **Supports all media types** (images, videos, sliced content, effects)
- **Processes commands instantly** (retry, reload, flush work immediately)

All dashboard functions will work identically on Android TV and Pi devices.