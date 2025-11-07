#!/usr/bin/env python3
import json

# Load test9's config
with open('store_config__test9_at_gmail.com.json', 'r') as f:
    config = json.load(f)

print("=== Current Pi Assignments for Store 1111 ===\n")
if '1111' in config.get('screens', {}):
    for screen_id, screen_data in config['screens']['1111'].items():
        if screen_id.startswith('1111'):
            pi_id = screen_data.get('pi_id', 'Not set')
            print(f"  {screen_id}: {pi_id}")

# Update assignments
print("\n=== Updating Assignments ===\n")

if 'screens' not in config:
    config['screens'] = {}
if '1111' not in config['screens']:
    config['screens']['1111'] = {}

# Ensure both screens exist
for screen_id in ['1111_screen1', '1111_screen2']:
    if screen_id not in config['screens']['1111']:
        config['screens']['1111'][screen_id] = {}

# Set correct Pi IDs
config['screens']['1111']['1111_screen2']['pi_id'] = 'raspberrypi-ce39'
config['screens']['1111']['1111_screen1']['pi_id'] = 'raspberrypi-new-3ef9'

print("✅ Set 1111_screen2 -> raspberrypi-ce39 (Pi1)")
print("✅ Set 1111_screen1 -> raspberrypi-new-3ef9 (Pi2)")

# Save updated config
with open('store_config__test9_at_gmail.com.json', 'w') as f:
    json.dump(config, f, indent=2)

print("\n✅ Config file updated!")
