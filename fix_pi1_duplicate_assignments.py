import json

config_file = '/var/www/pizza-hut-tv/store_config.json'

with open(config_file, 'r') as f:
    data = json.load(f)

screens = data.get('screens', {})

# Remove raspberrypi-ce39 from wrong assignments
removed = []
for store_id, screens_dict in screens.items():
    for screen_id, screen_data in screens_dict.items():
        if screen_data.get('pi_id') == 'raspberrypi-ce39':
            # Keep only 1111_screen2, remove from others
            if not (store_id == '1111' and screen_id == '1111_screen2'):
                print(f"Removing raspberrypi-ce39 from {store_id}/{screen_id}")
                screen_data['pi_id'] = ''
                removed.append(f"{store_id}/{screen_id}")

# Save updated config
with open(config_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\n✅ Fixed! Removed raspberrypi-ce39 from {len(removed)} wrong locations")
print(f"✅ Kept assignment: 1111/1111_screen2")
