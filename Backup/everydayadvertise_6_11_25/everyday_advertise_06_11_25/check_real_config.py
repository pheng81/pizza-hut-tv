import json

with open('store_config__toengpheng_at_gmail.com.json') as f:
    cfg = json.load(f)

playlist = cfg['screens']['1000']['1000_screen1']['playlist']

print(f"=== REAL CONFIG (toengpheng user) ===")
print(f"Total items in Screen 1: {len(playlist)}\n")

for i, item in enumerate(playlist, 1):
    print("=" * 80)
    print(f"ITEM {i}:")
    print("=" * 80)
    print(json.dumps(item, indent=2))
    print()
