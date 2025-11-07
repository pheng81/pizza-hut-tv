import json

with open('store_config.json') as f:
    cfg = json.load(f)

playlist = cfg['screens']['1000']['1000_screen1']['playlist']

print(f"Screen 1 - Total Items: {len(playlist)}")
print("=" * 70)

for i, item in enumerate(playlist, 1):
    print(f"\n{'='*70}")
    print(f"ITEM {i}:")
    print(f"{'='*70}")
    print(json.dumps(item, indent=2))
