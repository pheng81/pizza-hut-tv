# Schedule Filtering - Complete Implementation

## Overview
Both **Pi client** (custom_player.py) and **webplayer** (via server app.py) now fully respect ALL scheduling features configured in the dashboard.

## ✅ Supported Schedule Features

### 1. **Multiple Schedule Windows**
- Items can have multiple time windows in `item.schedule` array
- Each window can have its own start/end times and repeat days
- Item plays if **ANY** enabled window is currently active

### 2. **Per-Window Enabled/Disabled Toggle**
- Each schedule window has an `enabled` field
- Disabled windows are ignored (grayed out in dashboard)
- Only enabled windows are checked for active time

### 3. **Days of Week (Repeat Days)**
```json
{
  "days": ["mon", "tue", "wed", "thu", "fri"]
}
```
- Full day codes: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`
- If days array is empty or missing → plays every day
- If days specified → only plays on those days

### 4. **Date/Time Formats Supported**

#### ISO Format (Dashboard uses this):
- `2025-10-02T14:30:00` - Full date and time
- `2025-10-02T14:30` - Date and time without seconds

#### Space-Separated Format:
- `2025-10-02 14:30:00` - Full date and time
- `2025-10-02 14:30` - Date and time without seconds

#### Date Only:
- `2025-10-02` - Entire day (00:00:00 to 23:59:59)

#### Time Only:
- `14:30:00` - Specific time (applies to current date)
- `14:30` - Time without seconds

### 5. **Time Window Logic**

#### Normal Range:
```json
{
  "start": "09:00:00",
  "end": "17:00:00"
}
```
Plays between 9 AM and 5 PM

#### Overnight Range:
```json
{
  "start": "22:00:00",
  "end": "02:00:00"
}
```
Plays from 10 PM to 2 AM (crosses midnight)

#### Open-Ended:
```json
{
  "start": "09:00:00",
  "end": null
}
```
Plays from 9 AM onwards (no end time)

### 6. **Item-Level Enabled Toggle**
- `item.enabled` must be `true` (default)
- If item is disabled, it never plays regardless of schedule

### 7. **Legacy Single Window Format**
For backward compatibility, supports:
```json
{
  "start": "2025-10-02T09:00:00",
  "end": "2025-10-02T17:00:00",
  "days": ["mon", "tue", "wed", "thu", "fri"]
}
```

## 🔄 How It Works

### Pi Client (custom_player.py)
1. Fetches playlist from server
2. Filters items client-side using `is_item_active_now()`
3. Only plays items that match current time and schedule

### Webplayer (player.html)
1. Fetches playlist from `/playlist/<store_id>/<screen_id>`
2. Server filters items using `is_item_active_now()` BEFORE sending
3. Webplayer receives only currently-active items
4. No client-side filtering needed

### Server Logic (app.py)
```python
def is_item_active_now(item):
    # 1. Check item enabled
    if not item.get('enabled', True):
        return False
    
    # 2. Check schedule windows (priority)
    schedule_windows = item.get('schedule', [])
    if schedule_windows:
        for window in schedule_windows:
            if not window.get('enabled', True):
                continue  # Skip disabled windows
            if is_in_time_window(now, window['start'], window['end'], window['days']):
                return True  # Active in at least one enabled window
        return False  # No enabled windows are active
    
    # 3. Check legacy format
    if item.get('start') or item.get('end') or item.get('days'):
        return is_in_time_window(now, item['start'], item['end'], item['days'])
    
    # 4. No schedule = always active
    return True
```

## 📊 Example Scenarios

### Scenario 1: Friday-Only Content
**Dashboard Setup:**
- Repeat: Friday only (✓ F)
- Start: 00:00:00
- End: 23:59:59

**Result:**
- Pi client: Shows on Friday, hidden on Thursday ✅
- Webplayer: Shows on Friday, hidden on Thursday ✅

### Scenario 2: Lunch Special (11 AM - 2 PM, Mon-Fri)
**Dashboard Setup:**
- Repeat: Mon, Tue, Wed, Thu, Fri
- Start: 11:00:00
- End: 14:00:00

**Result:**
- Both clients show content:
  - Monday-Friday between 11 AM - 2 PM ✅
  - Hidden on weekends ✅
  - Hidden outside 11 AM - 2 PM window ✅

### Scenario 3: Late Night (10 PM - 2 AM)
**Dashboard Setup:**
- Start: 22:00:00
- End: 02:00:00

**Result:**
- Shows from 10 PM until 2 AM next day ✅
- Handles midnight crossover correctly ✅

### Scenario 4: Multiple Windows (Breakfast + Dinner)
**Dashboard Setup:**
Window 1:
- Start: 07:00:00, End: 10:00:00

Window 2:
- Start: 17:00:00, End: 21:00:00

**Result:**
- Shows 7-10 AM and 5-9 PM ✅
- Hidden during 10 AM - 5 PM and 9 PM - 7 AM ✅

## 🐛 Testing

### Manual Test:
1. Open dashboard: https://api.everydayadvertise.com/dashboard
2. Add content to Screen 1
3. Click "Schedule" → Add schedule window
4. Set repeat to Friday only
5. Check today (Thursday):
   - Webplayer should NOT show content ✅
   - Pi client should NOT show content ✅
6. Wait until Friday:
   - Both should show content ✅

### Debug Logging:
Server logs show filtering decisions:
```
DEBUG: Skipping item 'my-video.mp4' - not active based on schedule
```

## 📝 Code Locations

### Schedule Filtering Functions:
- **Server:** `app.py` lines 5194-5310
  - `parse_time_string()` - Parse datetime formats
  - `is_in_time_window()` - Check if time in window
  - `is_item_active_now()` - Main filtering logic

- **Pi Client:** `custom_player.py` lines 150-260
  - Same functions, identical logic

### Filtering Application:
- **Server:** `app.py` line 5546 (in `get_playlist()`)
  ```python
  if not is_item_active_now(item):
      print(f"DEBUG: Skipping item '{item.get('file')}' - not active based on schedule")
      continue
  ```

- **Pi Client:** `custom_player.py` line 632 (in `fetch_playlist()`)
  ```python
  active = [item for item in items if is_item_active_now(item)]
  ```

### Dashboard UI:
- **Template:** `templates/dashboard.html`
  - `renderScheduleWindows()` - Renders schedule UI
  - Window editing: date inputs, time pickers, day buttons

## ✅ Verification Checklist

- [x] Multiple schedule windows supported
- [x] Per-window enabled/disabled toggle
- [x] Days of week filtering (mon-sun)
- [x] ISO datetime format (YYYY-MM-DDTHH:MM:SS)
- [x] Space-separated format (YYYY-MM-DD HH:MM:SS)
- [x] Date-only ranges
- [x] Time-only ranges
- [x] Overnight time windows
- [x] Item-level enabled toggle
- [x] Legacy single window format
- [x] Server-side filtering (webplayer)
- [x] Client-side filtering (Pi client)
- [x] Both match dashboard scheduling exactly

## 🎯 Result

**The webplayer now respects and works with ALL scheduling functions** - exactly matching the Pi client behavior. No content will show outside its scheduled time windows on either platform.
