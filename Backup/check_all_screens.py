import json

with open('store_config.json') as f:
    cfg = json.load(f)

screens = cfg['screens']['1000']

for screen_id in ['1000_screen1', '1000_screen2', '1000_screen3', '1000_screen4']:
    if screen_id in screens:
        pl = screens[screen_id]['playlist']
        print(f"\n{'='*60}")
        print(f"Screen: {screen_id}")
        print(f"{'='*60}")
        print(f"Total playlist items: {len(pl)}")
        
        for i, item in enumerate(pl, 1):
            print(f"\n  Item {i}:")
            print(f"    File: {item.get('file', 'N/A')}")
            print(f"    Duration: {item.get('duration', 'N/A')}s")
            print(f"    Has sync_ref: {'sync_ref' in item}")
            if 'sync_ref' in item:
                print(f"    Sync group: {item['sync_ref'].get('group', 'N/A')}")
