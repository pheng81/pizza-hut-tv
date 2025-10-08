# Schedule Feature Implementation Analysis

## Dashboard Schedule Features (from screenshot):

### 1. **Time-based Scheduling**
- ✅ START date/time: `mm/dd/yyyy HH:MM:SS`
- ✅ END date/time: `mm/dd/yyyy HH:MM:SS`
- Item only plays between start and end times

### 2. **Days of Week Repeat**
- ✅ M T W T F S S checkboxes
- Item only plays on selected days
- Example: M-F selected = plays Monday through Friday only

### 3. **Duration Control**
- ✅ Slider to set playback duration (10s, 30s shown)
- How long each item plays before advancing

### 4. **Enable/Disable Toggle**
- ✅ `tick` checkbox
- When unchecked, item is skipped entirely

### 5. **Playlist Order**
- ✅ Numbered bubbles (1, 2, 3, 4, 5, 6...)
- Current playing item is highlighted (blue circle)
- Shows rotation order

## Current Pi Client Implementation Status:

### ❌ **NOT IMPLEMENTED**:

1. **No Schedule Filtering**
   ```python
   # Missing: Check if current time is within schedule window
   def is_item_scheduled(item, server_time):
       # Check start/end times
       # Check days_of_week
       # Check enabled flag
       return False  # NOT IMPLEMENTED!
   ```

2. **No Days of Week Checking**
   ```python
   # Missing: Filter by day of week
   # Item has: schedule[{days: [1,2,3,4,5]}]
   # Need: Check if current day is in allowed days
   ```

3. **Doesn't Respect `enabled` Flag**
   ```python
   # Missing: Skip disabled items
   # Item has: enabled: true/false
   # Need: Filter out enabled=false items
   ```

4. **Doesn't Handle Multiple Schedule Windows**
   ```python
   # Missing: Handle multiple time windows
   # Item has: schedule: [{start, end, days}, {start, end, days}, ...]
   # Need: Check if ANY schedule window matches
   ```

## What Needs to Be Added:

### 1. **Schedule Filter Function**
```python
def filter_playlist_by_schedule(self, playlist, server_time_ms):
    """Filter playlist items based on schedule"""
    filtered = []
    
    for item in playlist:
        # Check enabled flag
        if not item.get('enabled', True):
            continue
            
        # Check if within ANY schedule window
        if self.is_within_schedule(item, server_time_ms):
            filtered.append(item)
    
    return filtered

def is_within_schedule(self, item, server_time_ms):
    """Check if item should play at this time"""
    # Convert server time to local datetime
    dt = datetime.fromtimestamp(server_time_ms / 1000)
    current_day = dt.weekday() + 1  # 1=Mon, 7=Sun
    current_time = dt.time()
    
    # Get schedule windows
    schedules = item.get('schedule', [])
    
    # If no schedule, check legacy start/end
    if not schedules:
        return self.check_legacy_schedule(item, current_time)
    
    # Check if ANY schedule window matches
    for sched in schedules:
        # Check days of week
        if 'days' in sched:
            if current_day not in sched['days']:
                continue
        
        # Check start time
        if 'start' in sched:
            start_time = self.parse_time(sched['start'])
            if current_time < start_time:
                continue
        
        # Check end time
        if 'end' in sched:
            end_time = self.parse_time(sched['end'])
            if current_time > end_time:
                continue
        
        # This window matches!
        return True
    
    # No windows matched
    return False
```

### 2. **Integration into Playlist Fetch**
```python
def fetch_playlist(self):
    """Fetch and filter playlist"""
    # Get raw playlist from API
    raw_playlist = self.api_fetch_playlist()
    
    # Get current server time
    server_time_ms = self.time_sync.get_server_time()
    
    # Filter by schedule
    filtered_playlist = self.filter_playlist_by_schedule(
        raw_playlist, 
        server_time_ms
    )
    
    # Show message if nothing scheduled
    if not filtered_playlist:
        logger.info("⏰ No items scheduled for current time")
        self.show_waiting_screen()
    
    return filtered_playlist
```

### 3. **Periodic Schedule Re-check**
```python
# Re-check schedule every 60 seconds
# In case items become scheduled/unscheduled

def start_schedule_checker(self):
    """Periodically re-check schedule"""
    def checker():
        while self.running:
            time.sleep(60)  # Check every minute
            
            # Re-fetch and filter playlist
            self.fetch_and_update_playlist()
            
            # If playlist became empty, show waiting screen
            if not self.playlist:
                self.show_waiting_screen()
    
    thread = threading.Thread(target=checker, daemon=True)
    thread.start()
```

## Implementation Priority:

### 🔴 **CRITICAL** (Breaks Dashboard Features):
1. ✅ Schedule filtering by start/end times
2. ✅ Days of week checking
3. ✅ `enabled` flag respect
4. ✅ Show "Waiting for schedule..." when nothing scheduled

### 🟡 **IMPORTANT** (Nice to Have):
5. ✅ Multiple schedule windows support
6. ✅ Periodic re-check (every 60s)
7. ✅ Event reporting when schedule changes
8. ✅ Cache schedule metadata

### 🟢 **ENHANCEMENT** (Future):
9. ⏰ Predict next scheduled time
10. ⏰ Pre-load content before schedule starts
11. ⏰ Smooth transition when schedule activates

## Testing Checklist:

- [ ] Item with start=09:00, end=17:00 only plays during work hours
- [ ] Item with days=[1,2,3,4,5] only plays Monday-Friday
- [ ] Item with enabled=false never plays
- [ ] Item with multiple schedule windows works correctly
- [ ] Shows "Waiting for schedule..." when nothing scheduled
- [ ] Auto-refreshes when schedule becomes active
- [ ] Handles timezone correctly with server time
- [ ] Respects duration slider value from dashboard

## Current Code Location:

**File**: `complete_pi_client.py`
**Line**: ~700 (in `fetch_and_update_playlist`)
**Action**: Add `filter_playlist_by_schedule()` call after fetching

---

## Recommendation:

**IMPLEMENT NOW** - Schedule filtering is a core feature that the dashboard expects. Without it, the schedule settings in the dashboard have no effect on the Pi client.
