#!/usr/bin/env python3
import json
import os

print("\n" + "=" * 80)
print("GLOBAL CONFIG (store_config.json):")
print("=" * 80)

if os.path.exists('store_config.json'):
    with open('store_config.json', 'r') as f:
        data = json.load(f)
    
    stores = data.get('stores', [])
    screens = data.get('screens', {})
    
    print(f"\nTotal Stores: {len(stores)}")
    for store in stores:
        store_id = store.get('id')
        store_name = store.get('store_name', 'Unnamed')
        screen_count = len(screens.get(str(store_id), {}))
        print(f"\n  Store {store_id}: {store_name}")
        print(f"    Screens: {screen_count}")
        for screen_id, screen_data in screens.get(str(store_id), {}).items():
            screen_name = screen_data.get('name', screen_id)
            print(f"      - {screen_id}: {screen_name}")
    
    print(f"\n{'=' * 80}")
    print(f"Total screen entries across all stores: {sum(len(v) for v in screens.values())}")
else:
    print("✗ store_config.json NOT FOUND")

print("\n" + "=" * 80)
