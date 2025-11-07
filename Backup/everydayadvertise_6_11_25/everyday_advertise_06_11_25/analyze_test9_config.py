#!/usr/bin/env python3
import json

# Load test9 config
with open('store_config__test9_at_gmail.com.json', 'r') as f:
    cfg = json.load(f)

stores = cfg.get('stores', [])
screens = cfg.get('screens', {})

print('='*60)
print('TEST9 CONFIG ANALYSIS')
print('='*60)
print(f'Number of stores: {len(stores)}')
print(f'Store IDs: {[s["id"] for s in stores]}')
print(f'Store names: {[s.get("name", "NO NAME") for s in stores]}')
print()

total_screens = 0
for store_id, store_screens in screens.items():
    screen_count = len(store_screens)
    total_screens += screen_count
    print(f'  Store {store_id}: {screen_count} screens')
    for screen_id in list(store_screens.keys())[:3]:  # Show first 3
        print(f'    - {screen_id}')
    if len(store_screens) > 3:
        print(f'    ... and {len(store_screens) - 3} more screens')

print()
print(f'TOTAL SCREENS: {total_screens}')
print('='*60)
