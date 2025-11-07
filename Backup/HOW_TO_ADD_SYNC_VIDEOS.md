# 📚 How to Add Synchronized Videos - Code Explanation

## 🎯 Understanding the Sync Video System

### **What Makes Videos Synchronized?**

Videos sync across multiple screens because they all:
1. **Share the same `start_epoch` timestamp** - tells all screens when the video "started" in absolute time
2. **Calculate their position based on current time** - each screen figures out where it should be in the video
3. **Use modulo math** - loops the video infinitely: `(current_time - start_epoch) % video_duration`

---

## 📁 Config File Structure

Your screens are stored in: `/var/www/pizza-hut-tv/store_config__test22_at_gmail.com.json`

### **Basic Structure:**
```json
{
    "stores": [
        {"id": "1000", "name": "My First Store"}
    ],
    "master_store_id": "1000",
    "screens": {
        "1000": {
            "1000_screen1": {
                "file": "https://cdn.../video.mp4",     // ← Dashboard display
                "playlist": [                            // ← Actual playback
                    {
                        "type": "video",
                        "url": "https://cdn.../video.mp4",
                        "duration": 30,
                        "sync_ref": {                    // ← THE MAGIC!
                            "start_epoch": 1728129600,   // Unix timestamp
                            "group": "sync_group_1000"   // Sync group ID
                        }
                    }
                ],
                "horizontal": true,
                "vertical": false,
                "rotation": 0
            }
        }
    }
}
```

### **Key Properties Explained:**

#### 1. **`file`** (Legacy, for Dashboard Display)
- The dashboard checks this property to show preview thumbnails
- Should point to the video URL
- **Important**: Dashboard shows "No content" if this is `null` or missing

#### 2. **`playlist`** (Modern, for Actual Playback)
- Array of media items (videos, images)
- Screens actually play content from here, NOT from `file`
- Each item has `type`, `url`, `duration`

#### 3. **`sync_ref`** (The Synchronization Magic)
- **`start_epoch`**: Unix timestamp (seconds since Jan 1, 1970)
  - Example: `1728129600` = October 6, 2025, 00:00:00 UTC
  - Get current time: `date +%s` (Linux) or `int(time.time())` (Python)
  
- **`group`**: Sync group identifier
  - All screens with same group ID sync together
  - Example: `"sync_group_1000"`, `"industrial_sync_floor_1"`
  - Can have multiple sync groups for different video walls

---

## 🔧 How to Manually Add Sync Videos (Python Script)

### **Method 1: Using Python Script (Recommended)**

```python
#!/usr/bin/env python3
"""Add synchronized industrial video to 4 screens"""
import json
import time

# Configuration
CONFIG_FILE = '/var/www/pizza-hut-tv/store_config__test22_at_gmail.com.json'
STORE_ID = "1000"

# Your 4 sliced videos (from Auto-Slice feature)
VIDEOS = {
    1: "https://cdn.everydayadvertise.com/users/test22.../industrial-screen1.mp4",
    2: "https://cdn.everydayadvertise.com/users/test22.../industrial-screen2.mp4",
    3: "https://cdn.everydayadvertise.com/users/test22.../industrial-screen3.mp4",
    4: "https://cdn.everydayadvertise.com/users/test22.../industrial-screen4.mp4"
}

VIDEO_DURATION = 45  # seconds
SYNC_GROUP = "industrial_sync_1000"

# Load config
print("[SYNC] Loading config...")
with open(CONFIG_FILE, 'r') as f:
    cfg = json.load(f)

# Get current timestamp for sync
current_epoch = int(time.time())
print(f"[SYNC] Using start_epoch: {current_epoch}")

# Update each screen
for screen_num, video_url in VIDEOS.items():
    screen_id = f"{STORE_ID}_screen{screen_num}"
    
    # Ensure screen exists
    if screen_id not in cfg['screens'][STORE_ID]:
        print(f"[SYNC] ⚠️  Screen {screen_id} doesn't exist, skipping...")
        continue
    
    # Create playlist item with sync_ref
    playlist_item = {
        "type": "video",
        "url": video_url,
        "duration": VIDEO_DURATION,
        "sync_ref": {
            "start_epoch": current_epoch,    # Same for all screens!
            "group": SYNC_GROUP              # Same for all screens!
        }
    }
    
    # Update screen
    cfg['screens'][STORE_ID][screen_id]['file'] = video_url  # For dashboard
    cfg['screens'][STORE_ID][screen_id]['playlist'] = [playlist_item]  # For playback
    
    print(f"[SYNC] ✅ Updated {screen_id}")

# Save config
with open(CONFIG_FILE, 'w') as f:
    json.dump(cfg, f, indent=4)

print(f"\n[SYNC] === SUCCESS ===")
print(f"[SYNC] All 4 screens now have synchronized industrial video!")
print(f"[SYNC] Sync group: {SYNC_GROUP}")
print(f"[SYNC] Start epoch: {current_epoch}")
```

### **How to Run:**
```bash
# Upload script to server
scp script.py ubuntu@server:~/add_industrial_sync.py

# SSH to server
ssh ubuntu@server

# Run script
cd /var/www/pizza-hut-tv
sudo python3 ~/add_industrial_sync.py

# Verify
cat store_config__test22_at_gmail.com.json | grep -A5 sync_ref
```

---

## 🎬 How to Use Auto-Slice Feature (Easiest Way)

### **Step 1: Prepare Your Video**
- **Resolution**: 7680×1080 (for 4 horizontal screens) or 1920×4320 (for 4 vertical screens)
- **Format**: MP4 (H.264 codec)
- **Duration**: Any length (10-60 seconds recommended)
- **Example**: `industrial_factory_tour_7680x1080.mp4`

### **Step 2: Upload via Dashboard**
1. Go to Dashboard → **Add Sync Screen** button (top right)
2. Click **"✂️ Auto-Slice Multi-Screen Upload"**
3. Select your video file
4. Click **"Upload & Auto-Slice"**
5. **Wait 1-2 minutes** (watch the water flow animation!)
6. **Dashboard refreshes** showing 4 new screens with videos

### **Step 3: Verify Sync**
Open 4 tabs with:
- `https://everydayadvertise.com/webplayer?store_id=1000&screen_id=1000_screen1`
- `https://everydayadvertise.com/webplayer?store_id=1000&screen_id=1000_screen2`
- `https://everydayadvertise.com/webplayer?store_id=1000&screen_id=1000_screen3`
- `https://everydayadvertise.com/webplayer?store_id=1000&screen_id=1000_screen4`

Arrange side-by-side → Videos play perfectly synchronized! 🎉

---

## 🔍 Understanding the Sync Code (JavaScript)

### **Where Sync Happens: `templates/webplayer/player.html`**

#### **1. Get Server Time (Line 79)**
```javascript
async getServerTime() {
    const response = await fetch('/api/sync-time');
    const data = await response.json();
    window.serverTimestamp = data.timestamp;  // Global sync time
    return data.timestamp;
}
```
- All screens fetch the same global server timestamp
- Server aligns to 2-second intervals for consistency

#### **2. Calculate Video Position (Line 592)**
```javascript
function calculateSyncedVideoTime(item) {
    const startEpochSec = item.sync_ref.start_epoch;  // From config
    const duration = item.duration;                   // Video length
    const now = getServerSyncedTime();                // Current server time
    
    // Calculate elapsed time since video "started"
    const elapsed = now - (startEpochSec * 1000);
    
    // Loop video infinitely using modulo
    const videoTime = (elapsed / 1000) % duration;
    
    return videoTime;  // Example: 12.456 seconds into video
}
```

**Example:**
- `start_epoch`: 1728129600 (Oct 6, 2025 00:00:00)
- `duration`: 30 seconds
- `current time`: 1728129645 (Oct 6, 2025 00:00:45)
- `elapsed`: 45 seconds
- `videoTime`: 45 % 30 = **15 seconds** ← All screens jump to this position!

#### **3. Set Video Position & Play (Line 1625)**
```javascript
// Jump to calculated position
node.currentTime = syncedTime;  // Example: 15.234 seconds

// Wait for seek to complete
await new Promise((resolve) => {
    node.addEventListener('seeked', () => resolve());
});

// Start playing
await node.play();
```

#### **4. Continuous Drift Correction (Line 640)**
```javascript
function startSyncMonitoring(videoElement, item) {
    setInterval(() => {
        const actualTime = videoElement.currentTime;      // Where video is
        const expectedTime = calculateSyncedVideoTime(item);  // Where it should be
        
        // If drifted more than 0.5 seconds, correct it
        if (Math.abs(actualTime - expectedTime) > 0.5) {
            console.log('🔄 SYNC CORRECTION:', actualTime, '→', expectedTime);
            videoElement.currentTime = expectedTime;
        }
    }, 5000);  // Check every 5 seconds
}
```

---

## 📊 Sync Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         SERVER                              │
│  /api/sync-time → Returns: {timestamp: 1728129645000}      │
│  (All screens use this as master clock)                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                     ↓                     ↓
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Screen 1    │      │  Screen 2    │      │  Screen 3    │
│              │      │              │      │              │
│ sync_ref: {  │      │ sync_ref: {  │      │ sync_ref: {  │
│   start: 100 │      │   start: 100 │      │   start: 100 │ ← Same!
│   group: A   │      │   group: A   │      │   group: A   │ ← Same!
│ }            │      │ }            │      │ }            │
│              │      │              │      │              │
│ Calculation: │      │ Calculation: │      │ Calculation: │
│ elapsed=45s  │      │ elapsed=45s  │      │ elapsed=45s  │ ← Same!
│ 45s % 30s    │      │ 45s % 30s    │      │ 45s % 30s    │ ← Same!
│ = 15.0s      │      │ = 15.0s      │      │ = 15.0s      │ ← Same!
│              │      │              │      │              │
│ [Frame 450]  │      │ [Frame 450]  │      │ [Frame 450]  │ ← Synced!
└──────────────┘      └──────────────┘      └──────────────┘
```

---

## 🐛 Common Issues & Solutions

### **Issue 1: "No content uploaded" in Dashboard**
**Cause**: `file` property is `null`  
**Solution**: Set `screen.file` to the video URL

```python
cfg['screens']['1000']['1000_screen1']['file'] = video_url
```

### **Issue 2: Screens show content but not synced**
**Cause**: Different `start_epoch` values  
**Solution**: Use same timestamp for all screens

```python
# DO THIS (all screens use same time):
current_time = int(time.time())
for screen in screens:
    screen['playlist'][0]['sync_ref']['start_epoch'] = current_time

# DON'T DO THIS (each screen gets different time):
for screen in screens:
    screen['playlist'][0]['sync_ref']['start_epoch'] = int(time.time())  # ❌ Wrong!
```

### **Issue 3: Videos drift out of sync over time**
**Cause**: Slow network, browser performance issues  
**Solution**: Drift correction (already built-in!)  
- Code checks every 5 seconds
- Auto-corrects if drift > 0.5 seconds
- See `startSyncMonitoring()` function

### **Issue 4: "pair code required" error**
**Cause**: Screen not paired with user account  
**Solution**: Click "Schedule" button in dashboard once for each screen

---

## 💡 Advanced: Multiple Sync Groups

You can have different video walls playing different videos:

```json
{
    "screens": {
        "1000": {
            "1000_floor1_screen1": {
                "playlist": [{
                    "sync_ref": {
                        "start_epoch": 1728129600,
                        "group": "floor1_industrial"  // ← Group A
                    }
                }]
            },
            "1000_floor2_screen1": {
                "playlist": [{
                    "sync_ref": {
                        "start_epoch": 1728129700,
                        "group": "floor2_safety"      // ← Group B (different!)
                    }
                }]
            }
        }
    }
}
```

- **Floor 1 screens** (Group A): Synced together, play industrial video
- **Floor 2 screens** (Group B): Synced together, play safety video
- **No cross-sync**: Floor 1 doesn't sync with Floor 2

---

## 📝 Quick Reference

### **Get Current Unix Timestamp:**
```bash
# Linux/Mac
date +%s

# Python
python3 -c "import time; print(int(time.time()))"

# JavaScript (Browser Console)
Math.floor(Date.now() / 1000)
```

### **Config File Location:**
```
/var/www/pizza-hut-tv/store_config__test22_at_gmail.com.json
```

### **Reload Config (No Restart Needed):**
Screens poll the server every few seconds - config changes apply automatically!

### **View Logs:**
```bash
sudo journalctl -u pizza-hut-tv -f
```

### **Test Single Screen:**
```bash
curl 'http://127.0.0.1:5002/playlist?store_id=1000&screen_id=1000_screen1' | jq
```

---

## 🎓 Summary: What You Learned

1. **Sync videos use `sync_ref` with `start_epoch` and `group`**
2. **All screens calculate position: `(current_time - start_epoch) % duration`**
3. **Server provides global time via `/api/sync-time`**
4. **Dashboard needs `file` property to show preview**
5. **Screens play from `playlist` array, not `file`**
6. **Drift correction runs every 5 seconds automatically**
7. **Can have multiple sync groups for different video walls**

---

## 🚀 Next Steps for Industrial Video

Now that you understand the code, you can:

1. **Upload your industrial video** (7680×1080 resolution)
2. **Use Auto-Slice** to create 4 sliced videos
3. **Wait for completion** (watch water animation)
4. **Verify 4 screens created** with synchronized videos
5. **Open 4 webplayer tabs** to test the sync
6. **Deploy to actual TVs/displays**

**Need help?** Check these files:
- Sync calculation: `templates/webplayer/player.html` (line 592)
- Server time endpoint: `app.py` (line 1844)
- Config structure: `store_config__test22_at_gmail.com.json`

Good luck with your industrial video wall! 🏭✨
