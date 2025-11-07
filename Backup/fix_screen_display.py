#!/usr/bin/env python3
"""Fix screens by adding 'file' property for dashboard display"""
import json

CONFIG_FILE = '/var/www/pizza-hut-tv/store_config__test22_at_gmail.com.json'

# Load config
with open(CONFIG_FILE, 'r') as f:
    cfg = json.load(f)

# Sliced video URLs
videos = {
    "1000_screen1": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen1.mp4",
    "1000_screen2": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen2.mp4",
    "1000_screen3": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen3.mp4",
    "1000_screen4": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/e4b7d410-8607-468d-9747-4b1a6c2d09e1-screen4.mp4"
}

print("[FIX] Setting 'file' property for dashboard display...")

for screen_id, video_url in videos.items():
    if screen_id in cfg['screens']['1000']:
        # Set the file property so dashboard shows content
        cfg['screens']['1000'][screen_id]['file'] = video_url
        print(f"[FIX] ✅ Set file for {screen_id}")
    else:
        print(f"[FIX] ⚠️ Screen {screen_id} not found")

# Save config
with open(CONFIG_FILE, 'w') as f:
    json.dump(cfg, f, indent=4)

print(f"\n[FIX] === SUCCESS ===")
print(f"[FIX] Updated all 4 screens to show content in dashboard")
print(f"[FIX] Refresh your dashboard (F5) to see the videos!")
