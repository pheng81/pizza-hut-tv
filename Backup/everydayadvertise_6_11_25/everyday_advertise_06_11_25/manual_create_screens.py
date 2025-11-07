#!/usr/bin/env python3
"""Manually create sync screens from the completed slice job"""

import sys
sys.path.insert(0, '/var/www/pizza-hut-tv')

from app import _load_config_for_user, _save_config_for_user
import time
import json

username = 'test22_at_gmail.com'
store_id = '1000'

# Load completed job data
job_file = '/tmp/pizza_hut_tv_jobs/slice_2dc1b50a04f2.json'
with open(job_file, 'r') as f:
    job_data = json.load(f)

sliced_files = job_data['result']
layout = job_data.get('layout', 'horizontal')

print(f"[MANUAL] Creating screens for {len(sliced_files)} sliced videos")
print(f"[MANUAL] Layout: {layout}, Store: {store_id}")

# Load user config
cfg = _load_config_for_user(username)
if not cfg:
    print("[MANUAL] ERROR: Could not load config")
    sys.exit(1)

# Ensure screens dict exists
if 'screens' not in cfg:
    cfg['screens'] = {}
if store_id not in cfg['screens']:
    cfg['screens'][store_id] = {}

created_screens = []

# Create sync screens for each sliced video
for slice_info in sliced_files:
    screen_num = slice_info['screen_number']
    filename = slice_info['filename']
    url = slice_info['url']
    size = slice_info['size']
    
    # Create screen ID
    screen_id = f"{store_id}_screen{screen_num}"
    
    print(f"[MANUAL] Creating screen: {screen_id}")
    
    # Create screen entry if doesn't exist
    if screen_id not in cfg['screens'][store_id]:
        cfg['screens'][store_id][screen_id] = {
            'name': f'Screen {screen_num} (Store {store_id})',
            'playlist': [],
            'orientation': layout  # 'horizontal' or 'vertical'
        }
    
    # Add video to playlist
    current_time = int(time.time())
    playlist_item = {
        'type': 'video',
        'url': url,
        'duration': 30,  # Default 30 seconds
        'sync_ref': {
            'start_epoch': current_time,
            'group': f'sync_group_{store_id}'
        }
    }
    
    # Clear playlist and add new video (replace any existing content)
    cfg['screens'][store_id][screen_id]['playlist'] = [playlist_item]
    
    created_screens.append(screen_id)
    print(f"[MANUAL] ✅ Created {screen_id} with video: {filename}")

# Save config
success = _save_config_for_user(username, cfg)

if success:
    print(f"\n[MANUAL] === SUCCESS === Created {len(created_screens)} screens: {created_screens}")
    print(f"[MANUAL] Screens: {', '.join(created_screens)}")
    print(f"[MANUAL] Config saved successfully!")
else:
    print(f"\n[MANUAL] ERROR: Failed to save config")
    sys.exit(1)
