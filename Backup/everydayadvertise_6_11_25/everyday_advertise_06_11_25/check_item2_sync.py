import json

with open('store_config.json') as f:
    cfg = json.load(f)

pl = cfg['screens']['1000']['1000_screen1']['playlist']

print(f"Total items: {len(pl)}")
print(f"\nItem 1 has sync_ref: {'sync_ref' in pl[0]}")
if len(pl) > 1:
    print(f"Item 2 has sync_ref: {'sync_ref' in pl[1]}")
    print(f"\nItem 2 full data:")
    print(json.dumps(pl[1], indent=2))
else:
    print("Only 1 item in playlist")
