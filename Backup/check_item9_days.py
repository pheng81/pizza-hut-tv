#!/usr/bin/env python3
import json
import sys

# Check test9@gmail.com user config for item 9 days-of-week data
def check_item9_days():
    try:
        with open('/var/www/everydayadvertise/user_configs/test9@gmail.com_config.json', 'r') as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    
    screens = cfg.get('screens', {}).get('1111', {})
    print(f"Store 1111 has {len(screens)} screens")
    
    for screen_id, screen_data in screens.items():
        print(f"\n=== Screen: {screen_id} ===")
        playlist = screen_data.get('playlist', [])
        print(f"Playlist has {len(playlist)} items")
        
        for item in playlist:
            item_id = item.get('id', 'N/A')
            file = item.get('file', 'N/A')
            enabled = item.get('enabled', False)
            days = item.get('days', [])
            
            # Show item 9 details
            if item_id == '9' or item.get('file', '').endswith('9.mp4'):
                print(f"\n  🎯 Item {item_id}:")
                print(f"     File: {file}")
                print(f"     Enabled: {enabled}")
                print(f"     Days: {days}")
                print(f"     Days type: {type(days)}")
                if days:
                    for day in days:
                        print(f"       - '{day}' (type: {type(day).__name__})")

if __name__ == '__main__':
    check_item9_days()
