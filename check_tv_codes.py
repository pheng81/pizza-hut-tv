#!/usr/bin/env python3
import sqlite3
import os

print("===== TV CODES AVAILABLE =====")

# Check database
conn = sqlite3.connect('users.sqlite')
rows = conn.execute('SELECT username, link_code FROM users ORDER BY username').fetchall()

print(f"Total users: {len(rows)}")
print("\nAvailable TV Codes:")
for username, code in rows:
    print(f"📺 Code {code}: {username}")
    
    # Check for store configuration files with multiple naming patterns
    possible_config_files = [
        f"store_config__{username.replace('@', '_at_').replace('.', '_')}.json",
        f"store_config__{username}.json",
        f"store_config_{username}.json"
    ]
    
    config_file_found = None
    file_size = 0
    
    # Also check for files that might have slightly different naming
    for config_file in possible_config_files:
        if os.path.exists(config_file):
            config_file_found = config_file
            file_size = os.path.getsize(config_file)
            break
    
    # If not found, try a more flexible search
    if not config_file_found:
        username_variations = [
            username.replace('@', '_at_').replace('.', '_'),
            username.replace('@', '_').replace('.', '_'),
            username
        ]
        
        all_configs = [f for f in os.listdir('.') if f.startswith('store_config__') and f.endswith('.json')]
        for variation in username_variations:
            matching_configs = [f for f in all_configs if variation in f]
            if matching_configs:
                config_file_found = matching_configs[0]
                file_size = os.path.getsize(config_file_found)
                break
    
    if config_file_found:
        print(f"   ✅ Has store configuration: {config_file_found} ({file_size} bytes)")
    else:
        print(f"   ❌ No store configuration found")

conn.close()

print("\n===== TESTING RANDOM CODES =====")
import requests

# Test a few codes
test_codes = ['5301', '2212', '1234', '9999']
for code in test_codes:
    try:
        url = f'https://everydayadvertise.com/api/stores_by_code/{code}'
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get('success'):
            user = data.get('user', {}).get('username', 'Unknown')
            stores = data.get('stores', [])
            print(f"✅ Code {code}: User {user}, {len(stores)} store(s)")
        else:
            print(f"❌ Code {code}: {data.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"⚠️ Code {code}: Exception - {e}")