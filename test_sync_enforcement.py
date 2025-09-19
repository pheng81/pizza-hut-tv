#!/usr/bin/env python3

import requests
import json

print('=== Complete Sync Group Count Enforcement Test ===')

# Create session and login
session = requests.Session()

print('Step 1: Authenticating...')
try:
    resp = session.get('http://127.0.0.1:5002/login')
    print(f'Login page: {resp.status_code}')
    
    login_data = {'username': 'test8@gmail.com', 'password': 'test123'}
    resp = session.post('http://127.0.0.1:5002/login', data=login_data)
    print(f'Login POST: {resp.status_code}')
    print('✓ Authentication attempted')
except Exception as e:
    print(f'Authentication error: {e}')

print('\nStep 2: Creating sync group with 3 screens...')

try:
    sync_data = {
        'store_id': '1000',
        'base_screen_id': 'screen1', 
        'count': 3,
        'filename': 'users/test8_at_gmail.com/2025-09/a8379653-492b-4cc6-982e-9afe44218ad4.mp4'
    }
    
    resp = session.post('http://127.0.0.1:5002/sync/create',
                       json=sync_data,
                       headers={'Content-Type': 'application/json'})
    
    print(f'Sync creation response: {resp.status_code}')
    if resp.status_code == 200:
        result = resp.json()
        if result.get('success'):
            print('✓ Sync group created successfully!')
            print(f'  Group ID: {result.get("group_id", "unknown")[:8]}...')
            print(f'  Used screens: {result.get("used_screens", [])}')
            print(f'  Members: {len(result.get("members", []))}')
        else:
            print(f'✗ Sync creation failed: {result.get("error")}')
    else:
        print(f'✗ HTTP error: {resp.status_code}')
        print(f'Response: {resp.text[:200]}...')
        
except Exception as e:
    print(f'Sync creation error: {e}')

print('\nStep 3: Testing add screen enforcement...')

try:
    add_data = {'store_id': '1000', 'screen_type': 'screen'}
    resp = session.post('http://127.0.0.1:5002/add_screen',
                       json=add_data,
                       headers={'Content-Type': 'application/json'})
    
    print(f'Add screen response: {resp.status_code}')
    
    if resp.status_code == 400:
        result = resp.json()
        if result.get('error') == 'sync_group_complete':
            print('✓ CORRECTLY BLOCKED!')
            print(f'  Message: {result.get("message")}')
            print(f'  Locked count: {result.get("locked_count")}')
        else:
            print(f'✗ Wrong error: {result.get("error")}')
            print(f'  Full response: {result}')
    elif resp.status_code == 200:
        result = resp.json()
        print(f'✗ PROBLEM: Screen added: {result.get("screen_id")}')
        print(f'  This means sync group enforcement is BROKEN!')
    else:
        print(f'✗ Unexpected: {resp.status_code}')
        print(f'Response: {resp.text[:200]}...')
        
except Exception as e:
    print(f'Add screen error: {e}')

print('\nStep 4: Configuration state check...')
try:
    with open('store_config.json') as f:
        cfg = json.load(f)
    
    print(f'Stores: {list(cfg.get("screens", {}).keys())}')
    if '1000' in cfg.get('screens', {}):
        screens = list(cfg['screens']['1000'].keys())
        print(f'Store 1000 screens: {screens}')
        print(f'Number of screens: {len(screens)}')
    
    sync_groups = cfg.get('sync_groups', {})
    print(f'Sync groups: {len(sync_groups)}')
    for gid, grp in sync_groups.items():
        count = grp.get('count')
        locked = grp.get('locked_count')
        members = len(grp.get('members', []))
        print(f'  Group {gid[:8]}...: count={count}, locked={locked}, members={members}')
        
except Exception as e:
    print(f'Config check error: {e}')

print('\n=== Test Complete ===')
