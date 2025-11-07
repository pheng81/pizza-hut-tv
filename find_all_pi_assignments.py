import json

config_file = '/var/www/pizza-hut-tv/store_config.json'

with open(config_file, 'r') as f:
    data = json.load(f)

screens = data.get('screens', {})

print("Looking for all Pi assignments:")
for store_id, screens_dict in screens.items():
    for screen_id, screen_data in screens_dict.items():
        pi_id = screen_data.get('pi_id')
        if pi_id and 'raspberrypi' in str(pi_id):
            store_name = "UNKNOWN"
            for store in data.get('stores', []):
                if store.get('id') == store_id:
                    store_name = store.get('name', 'UNKNOWN')
                    break
            print(f"\nStore: {store_name} (ID: {store_id})")
            print(f"  Screen: {screen_id}")
            print(f"  Pi ID: {pi_id}")
