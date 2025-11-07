import json

config_file = '/var/www/pizza-hut-tv/store_config__toengpheng_at_gmail.com.json'

with open(config_file, 'r') as f:
    data = json.load(f)

screens = data.get('screens', {})
pi_id = 'raspberrypi-ce39'

print(f"Looking for {pi_id} assignments:")
for store_id, screens_dict in screens.items():
    for screen_id, screen_data in screens_dict.items():
        if screen_data.get('pi_id') == pi_id:
            print(f"  {store_id}/{screen_id}")
            print(f"    pi_id: {screen_data.get('pi_id')}")
