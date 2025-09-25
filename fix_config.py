import json
import uuid

# Load the config file
with open('temp_config.json', 'r') as f:
    config = json.load(f)

screens = config.setdefault('screens', {}).setdefault('1000', {})

# Get the playlist item from screen3
screen3 = screens.get('1000_screen3', {})
template = None
if screen3.get('playlist'):
    template = screen3['playlist'][0]

if template:
    # Create playlist items for screen1 and screen2
    for screen_name, order in [('1000_screen1', 0), ('1000_screen2', 1)]:
        # Ensure screen exists
        screen = screens.setdefault(screen_name, {
            'file': template['file'],
            'vertical': False,
            'horizontal': True, 
            'rotation': 0,
            'protected': False,
            'playlist': []
        })
        
        # Create new playlist item
        new_item = template.copy()
        new_item['id'] = str(uuid.uuid4())
        
        # Update sync_ref order
        if 'sync_ref' in new_item:
            new_item['sync_ref']['order'] = order
            new_item['sync_ref']['role'] = 'master' if order == 0 else 'follower'
        
        screen['playlist'] = [new_item]
        print(f'Added playlist to {screen_name} with order {order}')

# Save the updated config
with open('temp_config_fixed.json', 'w') as f:
    json.dump(config, f, indent=2)

print('Config file updated!')