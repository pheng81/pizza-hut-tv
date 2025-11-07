#!/usr/bin/env python3
import json
import os

print("\n" + "=" * 80)
print("CHECKING USER CONFIG FILES:")
print("=" * 80)

# Check mom.toeng config
mom_config = "store_config__mom.toeng_at_gmail.com.json"
if os.path.exists(mom_config):
    with open(mom_config, 'r') as f:
        mom_data = json.load(f)
    print(f"\n✓ {mom_config}")
    print(f"  Stores: {len(mom_data.get('stores', []))}")
    for store in mom_data.get('stores', []):
        print(f"    Store {store.get('store_id')}: {store.get('store_name')} - {len(store.get('screens', []))} screens")
        for screen in store.get('screens', []):
            print(f"      - {screen.get('screen_id')}: {screen.get('name')}")
else:
    print(f"\n✗ {mom_config} - NOT FOUND")

# Check toengpheng config
toeng_config = "store_config__toengpheng_at_gmail.com.json"
if os.path.exists(toeng_config):
    with open(toeng_config, 'r') as f:
        toeng_data = json.load(f)
    print(f"\n✓ {toeng_config}")
    print(f"  Stores: {len(toeng_data.get('stores', []))}")
    for store in toeng_data.get('stores', []):
        print(f"    Store {store.get('store_id')}: {store.get('store_name')} - {len(store.get('screens', []))} screens")
        for screen in store.get('screens', []):
            print(f"      - {screen.get('screen_id')}: {screen.get('name')}")
else:
    print(f"\n✗ {toeng_config} - NOT FOUND")

# Check global config
global_config = "store_config.json"
if os.path.exists(global_config):
    with open(global_config, 'r') as f:
        global_data = json.load(f)
    print(f"\n✓ {global_config} (FALLBACK)")
    print(f"  Stores: {len(global_data.get('stores', []))}")
    for store in global_data.get('stores', []):
        print(f"    Store {store.get('store_id')}: {store.get('store_name')} - {len(store.get('screens', []))} screens")
        for screen in store.get('screens', []):
            print(f"      - {screen.get('screen_id')}: {screen.get('name')}")

print("\n" + "=" * 80)
