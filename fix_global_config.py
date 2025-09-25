import json
import uuid

# Load global config and user config
with open('global_config.json', 'r') as f:
    global_config = json.load(f)

with open('temp_config_fixed.json', 'r') as f:
    user_config = json.load(f)

# Get sync groups from user config
sync_groups = user_config.get('sync_groups', {})
user_screens = user_config.get('screens', {}).get('1000', {})

# Add sync groups to global config
global_config['sync_groups'] = sync_groups

# Copy playlist items from user config to global config
global_screens = global_config.setdefault('screens', {}).setdefault('1000', {})

for screen_id in ['1000_screen1', '1000_screen2', '1000_screen3']:
    if screen_id in user_screens:
        user_screen = user_screens[screen_id]
        global_screen = global_screens.get(screen_id, {})
        
        # Copy essential fields
        global_screen['file'] = user_screen.get('file')
        global_screen['vertical'] = user_screen.get('vertical', False)
        global_screen['horizontal'] = user_screen.get('horizontal', True)
        global_screen['rotation'] = user_screen.get('rotation', 0)
        global_screen['protected'] = user_screen.get('protected', False)
        global_screen['playlist'] = user_screen.get('playlist', [])
        
        global_screens[screen_id] = global_screen
        print(f'Copied {screen_id}: {len(global_screen.get("playlist", []))} playlist items')

# Save updated global config
with open('global_config_fixed.json', 'w') as f:
    json.dump(global_config, f, indent=2)

print('Global config updated with sync video data!')