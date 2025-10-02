# 📋 Dashboard Feature Parity Analysis for Pi Client

## Current Status: ⚠️ MISSING CRITICAL FEATURES

---

## ✅ Currently Supported Features

| Feature | Status | Implementation |
|---------|--------|----------------|
| **Basic Playback** | ✅ Working | OpenCV video/image display |
| **Duration** | ✅ Working | `item.get('duration', 10)` |
| **Slice Videos** | ✅ Working | `slice_url` detection + crop |
| **Server Time Sync** | ✅ Working | 2-second aligned timestamps |
| **Playlist Loop** | ✅ Working | Cycles through items |
| **Auto Refresh** | ✅ Working | Fetches playlist every 15s |

---

## ❌ MISSING Critical Features

### **1. ⏰ Time-Based Scheduling** (HIGH PRIORITY)
**Dashboard Feature:**
```python
item = {
    'enabled': True,
    'start': '08:00',      # Start time
    'end': '22:00',        # End time
    'days': ['mon','tue','wed','thu','fri']  # Weekdays only
}
```

**Problem:** Pi client **ignores** `start`, `end`, and `days` fields!
- Dashboard shows: "Play Mon-Fri 8am-10pm"
- Pi client shows: **Always plays** (24/7)

**Impact:** ⚠️ HIGH - Users can't schedule content

**Fix Required:**
```python
def is_item_active_now(item):
    """Check if item should play based on schedule"""
    now = datetime.now()
    
    # Check weekday
    days = item.get('days', [])
    if days:
        wd = ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]
        if wd not in days:
            return False
    
    # Check time window
    start = item.get('start')
    end = item.get('end')
    if start or end:
        # Parse HH:MM or YYYY-MM-DDTHH:MM:SS
        if not is_in_time_window(now, start, end):
            return False
    
    return True

# Use in playback loop:
active_items = [i for i in playlist if is_item_active_now(i)]
```

---

### **2. 📅 Multiple Schedule Windows** (HIGH PRIORITY)
**Dashboard Feature:**
```python
item = {
    'schedule': [
        {'start': '08:00', 'end': '12:00', 'days': ['mon','tue','wed','thu','fri']},
        {'start': '17:00', 'end': '22:00', 'days': ['mon','tue','wed','thu','fri']},
        {'start': '09:00', 'end': '23:00', 'days': ['sat','sun']}
    ]
}
```

**Problem:** Pi client **doesn't check** `schedule` array!
- Dashboard: "Play weekdays 8am-12pm AND 5pm-10pm, weekends 9am-11pm"
- Pi client: **Plays 24/7**

**Impact:** ⚠️ HIGH - Advanced scheduling doesn't work

---

### **3. 🔄 Repeat vs Play-Once** (MEDIUM PRIORITY)
**Dashboard Feature:**
```python
item = {
    'repeat': True   # Loop this item
}
item2 = {
    'repeat': False  # Play once, then skip
}
```

**Problem:** Pi client always loops all items
- Dashboard: "Play promo once per hour"
- Pi client: **Plays every cycle**

**Impact:** ⚠️ MEDIUM - Can't do one-time announcements

---

### **4. 🎬 Transition Effects** (LOW PRIORITY - Already Working?)
**Dashboard Feature:**
```python
item = {
    'effect': 'fade'  # fade, slide-l, slide-r, zoom-in, zoom-out, cut
}
```

**Current:** Pi client has fade transitions hardcoded
**Status:** ✅ Partially working (fade only)

**Enhancement Needed:** Support all effect types

---

### **5. 🔗 Link Next (MEDIUM PRIORITY)
**Dashboard Feature:**
```python
item = {
    'link_next': True  # Chain to next item without gap
}
```

**Problem:** Pi client doesn't respect `link_next`
- Dashboard: "Play video 1 → video 2 seamlessly"
- Pi client: **Waits for sync moment between each**

**Impact:** ⚠️ MEDIUM - Breaks sequential storytelling

---

### **6. 🚫 Enabled Toggle** (CRITICAL)
**Dashboard Feature:**
```python
item = {
    'enabled': False  # User disabled this item
}
```

**Problem:** Need to verify if Pi client filters disabled items!

**Check Required:**
```python
# Does current code do this?
active_playlist = [i for i in playlist if i.get('enabled', True)]
```

**Impact:** ⚠️ CRITICAL - Disabled items might still play!

---

### **7. 🔄 Sync Group Metadata** (MEDIUM PRIORITY)
**Dashboard Feature:**
```python
item = {
    'sync_ref': {
        'group': 'group_abc123',
        'role': 'base',  # or 'follower'
        'order': 0,
        'count': 3,
        'mode': 'split-h',
        'start_epoch': 1696161234
    }
}
```

**Current:** Pi uses server time sync but **ignores** sync_ref metadata

**Enhancement:** Use `start_epoch` for perfect alignment across screens

---

## 🔧 Implementation Priority

### **Phase 1: Critical (Do Now!)**
1. ✅ Filter `enabled: false` items
2. ❌ Implement `start`/`end` time windows
3. ❌ Implement `schedule` multiple windows
4. ❌ Implement `days` weekday filtering

### **Phase 2: Important (Next)**
1. ❌ Implement `repeat: false` (play-once)
2. ❌ Implement `link_next` seamless chaining
3. ❌ Use `sync_ref.start_epoch` for sync

### **Phase 3: Nice-to-Have**
1. ❌ Support all transition `effect` types
2. ❌ Image scaling modes (`image_fit`, `image_scale`)

---

## 📝 Code Changes Required

### **File: `custom_player.py`**

#### **1. Add time parsing function:**
```python
from datetime import datetime, timedelta

def parse_time_string(time_str, now):
    """Parse HH:MM or ISO datetime string"""
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # ISO format: YYYY-MM-DDTHH:MM:SS
    if 'T' in time_str or len(time_str) > 10:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    
    # Date only: YYYY-MM-DD
    if len(time_str) == 10 and '-' in time_str:
        return datetime.strptime(time_str, '%Y-%m-%d')
    
    # Time only: HH:MM or HH:MM:SS
    if ':' in time_str:
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    
    return None
```

#### **2. Add schedule checker:**
```python
def is_item_active_now(item):
    """Check if item should play based on schedule - MATCHES DASHBOARD LOGIC"""
    now = datetime.now()
    
    # Check if enabled
    if not item.get('enabled', True):
        return False
    
    # Check multiple schedule windows first
    schedule_windows = item.get('schedule', [])
    if schedule_windows:
        for window in schedule_windows:
            if is_in_time_window(now, window.get('start'), window.get('end'), window.get('days')):
                return True  # Active in at least one window
        return False  # No windows are active
    
    # Check single start/end window
    start = item.get('start')
    end = item.get('end')
    days = item.get('days', [])
    
    if start or end or days:
        return is_in_time_window(now, start, end, days)
    
    # No schedule restrictions = always active
    return True

def is_in_time_window(now, start_str, end_str, days=None):
    """Check if now is within time window"""
    # Check weekday
    if days:
        weekday = ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]
        if weekday not in days:
            return False
    
    # Parse times
    start_time = parse_time_string(start_str, now) if start_str else None
    end_time = parse_time_string(end_str, now) if end_str else None
    
    # Handle overnight wrap (e.g., 22:00 - 02:00)
    if start_time and end_time:
        if end_time < start_time:
            # Overnight: active if after start OR before end
            return now >= start_time or now <= end_time
        else:
            # Normal: active if between start and end
            return start_time <= now <= end_time
    
    # Single boundary
    if start_time and now < start_time:
        return False
    if end_time and now > end_time:
        return False
    
    return True
```

#### **3. Update playback loop:**
```python
def playback_loop(self):
    last = None
    while self.running:
        if not self.current_playlist:
            # Show "waiting" screen
            continue
        
        # FILTER ACTIVE ITEMS BASED ON SCHEDULE
        active_items = [i for i in self.current_playlist if is_item_active_now(i)]
        
        if not active_items:
            # No items active right now - show "waiting" screen
            black = np.zeros((self.screen_height, self.screen_width, 3), dtype=np.uint8)
            cv2.putText(black, "No scheduled content", (650, 540), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
            cv2.imshow(self.window_name, black)
            time.sleep(1)
            continue
        
        # Filter out non-repeating items that have already played
        playable_items = [i for i in active_items if i.get('repeat', True) or not self.has_played(i)]
        
        if not playable_items:
            playable_items = active_items  # Reset play history
        
        # Get current item from playable set
        item = playable_items[self.current_index % len(playable_items)]
        
        # ... rest of playback logic ...
```

---

## 🎯 Recommended Action Plan

1. **VERIFY** if `enabled: false` items are currently filtered
2. **IMPLEMENT** time-based scheduling (start/end/days/schedule)
3. **TEST** with dashboard schedule settings
4. **IMPLEMENT** repeat flag
5. **IMPLEMENT** link_next chaining
6. **DOCUMENT** feature parity

---

## 🧪 Test Cases Needed

### **Test 1: Weekday Scheduling**
```json
{
  "enabled": true,
  "start": "08:00",
  "end": "18:00",
  "days": ["mon","tue","wed","thu","fri"]
}
```
**Expected:** Plays Mon-Fri 8am-6pm only

### **Test 2: Weekend Override**
```json
{
  "schedule": [
    {"start": "08:00", "end": "18:00", "days": ["mon","tue","wed","thu","fri"]},
    {"start": "10:00", "end": "22:00", "days": ["sat","sun"]}
  ]
}
```
**Expected:** Different hours on weekends

### **Test 3: Overnight Window**
```json
{
  "start": "22:00",
  "end": "06:00"
}
```
**Expected:** Plays 10pm-6am (crosses midnight)

### **Test 4: Play Once**
```json
{
  "repeat": false
}
```
**Expected:** Plays once per playlist cycle, then skips

---

## 📊 Feature Parity Score

**Current:** 3/10 (30%)  
**Target:** 10/10 (100%)

**Missing Features:**
- ❌ Time scheduling (start/end)
- ❌ Multiple schedule windows
- ❌ Weekday filtering (days)
- ❌ Repeat flag
- ❌ Link next
- ❌ All transition effects
- ❌ Enabled filter verification needed

---

## 🚨 URGENT ACTION REQUIRED

The Pi client currently **IGNORES** most dashboard schedule settings! Users expect:
- "Play Mon-Fri 8am-6pm" → **Pi plays 24/7**
- "Skip item" (enabled=false) → **Pi might still play it**
- "Play once" (repeat=false) → **Pi loops it**

**This breaks the entire scheduling system!** 🔥

Recommend implementing Phase 1 features IMMEDIATELY.
