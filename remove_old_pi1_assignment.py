#!/usr/bin/env python3
import json

# Load test9's config
with open('store_config__test9_at_gmail.com.json', 'r') as f:
    config = json.load(f)

print("=== Removing Old Pi1 Assignment from promo1 ===\n")

# Remove raspberrypi-ce39 from promo1
if '1111' in config.get('screens', {}):
    if '1111_promo1' in config['screens']['1111']:
        if config['screens']['1111']['1111_promo1'].get('pi_id') == 'raspberrypi-ce39':
            print("❌ Removing raspberrypi-ce39 from 1111_promo1")
            config['screens']['1111']['1111_promo1']['pi_id'] = None
    
    # Also fix Pi2 if it shows wrong ID
    if '1111_screen1' in config['screens']['1111']:
        old_pi2 = config['screens']['1111']['1111_screen1'].get('pi_id')
        if old_pi2 and old_pi2 != 'raspberrypi-new-3ef9':
            print(f"❌ Fixing Pi2 ID from '{old_pi2}' to 'raspberrypi-new-3ef9'")
            config['screens']['1111']['1111_screen1']['pi_id'] = 'raspberrypi-new-3ef9'

print("\n=== Final Assignments ===")
for screen_id in ['1111_screen1', '1111_screen2', '1111_promo1', '1111_promo2']:
    if screen_id in config.get('screens', {}).get('1111', {}):
        pi_id = config['screens']['1111'][screen_id].get('pi_id')
        print(f"  {screen_id}: {pi_id}")

# Save updated config
with open('store_config__test9_at_gmail.com.json', 'w') as f:
    json.dump(config, f, indent=2)

print("\n✅ Config saved!")
