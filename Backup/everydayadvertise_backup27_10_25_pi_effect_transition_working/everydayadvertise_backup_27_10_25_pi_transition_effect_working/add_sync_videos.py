#!/usr/bin/env python3
"""Manually add sync videos to screens"""
import json
import time

CONFIG_FILE = '/var/www/pizza-hut-tv/store_config__test22_at_gmail.com.json'

# Load config
with open(CONFIG_FILE, 'r') as f:
    cfg = json.load(f)

# Sliced video data from completed job
sliced_videos = [
    {
        "screen_number": 1,
        "filename": "users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen1.mp4",
        "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen1.mp4",
        "size": 27550786
    },
    {
        "screen_number": 2,
        "filename": "users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen2.mp4",
        "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen2.mp4",
        "size": 38328218
    },
    {
        "screen_number": 3,
        "filename": "users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen3.mp4",
        "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen3.mp4",
        "size": 32009329
    },
    {
        "screen_number": 4,
        "filename": "users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen4.mp4",
        "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen4.mp4",
        "size": 29628018
    }
]

store_id = "1000"
current_time = int(time.time())

print(f"[MANUAL] Adding 4 sync screens with videos...")

# Ensure screens dict exists
if '1000' not in cfg['screens']:
    cfg['screens']['1000'] = {}

# Create/update all 4 screens
for video_info in sliced_videos:
    screen_num = video_info['screen_number']
    screen_id = f"1000_screen{screen_num}"
    url = video_info['url']
    
    # Create screen if doesn't exist
    if screen_id not in cfg['screens']['1000']:
        print(f"[MANUAL] Creating new screen: {screen_id}")
        cfg['screens']['1000'][screen_id] = {
            "file": None,
            "vertical": False,
            "horizontal": True,
            "rotation": 0,
            "protected": False,
            "playlist": [],
            "fresh": True,
            "rotation_meta": {
                "last_index": 0,
                "last_ts": 0
            }
        }
    else:
        print(f"[MANUAL] Updating existing screen: {screen_id}")
    
    # Add sync video to playlist
    playlist_item = {
        "type": "video",
        "url": url,
        "duration": 30,
        "sync_ref": {
            "start_epoch": current_time,
            "group": f"sync_group_1000"
        }
    }
    
    cfg['screens']['1000'][screen_id]['playlist'] = [playlist_item]
    print(f"[MANUAL] ✅ Added video to {screen_id}")

# Save config
with open(CONFIG_FILE, 'w') as f:
    json.dump(cfg, f, indent=4)

print(f"\n[MANUAL] === SUCCESS ===")
print(f"[MANUAL] Created/updated 4 screens: 1000_screen1, 1000_screen2, 1000_screen3, 1000_screen4")
print(f"[MANUAL] All screens now have synchronized videos!")
print(f"[MANUAL] Refresh your dashboard to see the screens!")
