import json

with open('store_config.json') as f:
    cfg = json.load(f)

# Check if there's a different config file being used
print("=== Checking store_config.json ===")
playlist = cfg['screens']['1000']['1000_screen1']['playlist']
print(f"Items in store_config.json: {len(playlist)}\n")

for i, item in enumerate(playlist, 1):
    print(f"Item {i}:")
    print(f"  File: {item.get('file', 'N/A')[:70]}")
    print(f"  Duration: {item.get('duration', 'N/A')}")
    print(f"  Days: {item.get('days', 'N/A')}")
    print(f"  Start: {item.get('start', 'N/A')}")
    print(f"  End: {item.get('end', 'N/A')}")
    print(f"  Enabled: {item.get('enabled', 'N/A')}")
    print(f"  Has sync_ref: {'sync_ref' in item}")
    print()

# Check for user-specific config
import os
import glob

print("\n=== Checking for user-specific configs ===")
user_configs = glob.glob('user_configs/**/*1000*.json', recursive=True)
if user_configs:
    print(f"Found {len(user_configs)} user config files")
    for uc in user_configs[:5]:
        print(f"  - {uc}")
        try:
            with open(uc) as f:
                ucfg = json.load(f)
            upl = ucfg.get('screens', {}).get('1000', {}).get('1000_screen1', {}).get('playlist', [])
            print(f"    Items: {len(upl)}")
        except:
            pass
else:
    print("No user-specific configs found")
