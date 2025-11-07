# Pizza Hut TV Pi Client - Required Features

## Dashboard Features That Must Be Supported

### 1. **Commands System** (`/api/commands`)
- **reload**: Reload playlist immediately
- **retry_item**: Retry a specific failed item
- **flush_cache**: Clear all cached media
- Client polls every 1.5 seconds
- Commands are queued and popped on retrieval

### 2. **Global Effects** (`/api/sync-effect`, `/api/get-effect`)
- Synchronized transition effects across all screens in a store
- Effects: fade, slide, zoom, etc.
- All screens must use the same effect at the same time
- Poll for effect changes

### 3. **Heartbeat** (`/api/screen_heartbeat`)
- POST every ~30 seconds with store_id and screen_id
- Confirms screen is online and playing
- Dashboard shows green/red status based on heartbeat

### 4. **Playlist Scheduling**
Each item has:
- `schedule`: Array of time windows `[{start: "09:00", end: "17:00", days: [1,2,3,4,5]}]`
- `start`: Legacy single start time
- `end`: Legacy single end time  
- `enabled`: Boolean to show/hide item
- `repeat`: If false, plays once then stops
- `duration`: Playback duration in seconds
- `link_next`: Chain multiple items together

### 5. **Screen Rotation**
- Duration-based sequential rotation
- Tracks `rotation_meta`: `{last_index: 0, last_ts: timestamp}`
- Ensures fair rotation across items
- Prevents time modulo drift

### 6. **Screen Orientation**
Each screen has:
- `vertical`: Boolean for portrait support
- `horizontal`: Boolean for landscape support
- `rotation`: Degrees (0, 90, 180, 270)

### 7. **Event Reporting** (`/api/event`)
Client should report:
- `load_ok`: Item loaded successfully
- `load_fail`: Item failed to load
- `playlist_reload`: Playlist was reloaded
- Include: store_id, screen_id, item_id, file, error message

### 8. **Media Types**
- Video: MP4, WebM, MOV
- Image: JPG, PNG, GIF, WebP
- Each has different playback logic
- Support for transitions between items

### 9. **Caching System**
- Memory cache for images
- Download cache for videos
- Preload next 4 items
- Report cache size and status

### 10. **Time Synchronization**
- Sync with server time via `/api/server_time`
- Compensate for network latency
- Use median offset from multiple samples
- Required for accurate schedule filtering

## Current Implementation Gaps

### ❌ Missing in `complete_pi_client.py`:
1. **No actual video playback** - just shows placeholder
2. **No transition effects** - fade/slide not implemented
3. **No event reporting** - doesn't report load_ok/fail
4. **No rotation tracking** - doesn't track last_index/last_ts
5. **No orientation support** - doesn't check vertical/horizontal flags
6. **No schedule filtering** - doesn't evaluate time windows
7. **Limited caching** - basic preload but no size tracking

### ⚠️ Partially Implemented:
1. **Commands** - polls but only handles reload
2. **Heartbeat** - has thread but may not send correctly
3. **Global effects** - fetches but doesn't apply
4. **Time sync** - works but may not use for scheduling

## Recommended Solution

Create a **custom integrated player** specifically for Raspberry Pi that:

### Architecture:
```
complete_pi_client.py (Main UI & Orchestration)
    ↓
pi_video_player.py (Custom Video/Image Player)
    ↓
Uses: python-vlc or mpv for actual video playback
      PIL/Pygame for image display
      Pygame for transition effects
```

### Key Components:

1. **VideoPlayer Class**
   - Hardware-accelerated video with VLC/MPV
   - Pygame overlay for transitions
   - Smooth crossfading between items
   - Event callbacks for completion

2. **TransitionEngine Class**
   - Fade: Alpha blend between frames
   - Slide: Position animation
   - Zoom: Scale animation  
   - Wipe: Directional reveal

3. **ScheduleFilter Class**
   - Evaluate time windows against server time
   - Handle legacy start/end times
   - Filter by days_of_week
   - Respect repeat flag

4. **RotationTracker Class**
   - Track last_index and last_ts
   - Duration-based advancement
   - Persist metadata to local file
   - Sync with server on changes

5. **EventReporter Class**
   - Queue events for batch reporting
   - Retry on network failure
   - Include all required metadata

## Next Steps

1. ✅ Create `pi_video_player.py` with proper VLC/MPV integration
2. ✅ Add transition effects using Pygame surfaces
3. ✅ Implement schedule filtering with server time
4. ✅ Add event reporting for all playback events
5. ✅ Track rotation metadata properly
6. ✅ Support orientation flags
7. ✅ Test all dashboard commands work correctly
