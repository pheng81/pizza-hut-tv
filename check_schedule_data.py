#!/usr/bin/env python3
"""Check what schedule data is actually stored for test9's items"""
import json

# Load test9's config
with open('/var/www/pizza-hut-tv/store_config__test9_at_gmail.com.json', 'r') as f:
    config = json.load(f)

store_id = '1111'
screen_id = '1111_screen1'

print('='*70)
print(f'SCHEDULE DATA CHECK - Store {store_id}, Screen {screen_id}')
print('='*70)

# First check what keys exist in config
print(f'\nConfig keys: {list(config.keys())}')
print(f'\nScreens: {list(config.get("screens", {}).keys())}')

# Get the playlist for this screen - try different locations
playlist = config.get('playlists', {}).get(store_id, {}).get(screen_id, [])
if not playlist:
    # Try screens -> store -> screen -> files or playlist
    screen_data = config.get('screens', {}).get(store_id, {}).get(screen_id, {})
    playlist = screen_data.get('playlist', screen_data.get('files', []))

print(f'\nTotal items in playlist: {len(playlist)}')

for idx, item in enumerate(playlist, 1):
    print(f'\n--- Item {idx} ---')
    print(f'File: {item.get("file", "N/A")}')
    print(f'Enabled: {item.get("enabled", True)}')
    
    # Check for schedule array (new format)
    schedule = item.get('schedule', [])
    if schedule:
        print(f'Schedule windows: {len(schedule)}')
        for sched_idx, sched in enumerate(schedule, 1):
            print(f'  Window {sched_idx}:')
            print(f'    Days: {sched.get("days", [])}')
            print(f'    Start: {sched.get("start", "none")}')
            print(f'    End: {sched.get("end", "none")}')
            print(f'    Duration: {sched.get("duration", "none")}')
    
    # Check for legacy days field
    days = item.get('days', None)
    if days is not None:
        print(f'Legacy days field: {days}')
    
    # Check legacy start/end
    start = item.get('start', None)
    end = item.get('end', None)
    if start or end:
        print(f'Legacy start: {start}')
        print(f'Legacy end: {end}')

print('\n' + '='*70)
