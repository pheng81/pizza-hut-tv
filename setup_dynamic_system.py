#!/usr/bin/env python3
import sqlite3
import os
import json

print("===== DYNAMIC TV SYSTEM SETUP =====")
print("Making system work for ALL users with store configurations...")

# Get all existing store config files
config_files = [f for f in os.listdir('.') if f.startswith('store_config__') and f.endswith('.json') and 'new' not in f]

print(f"\nFound {len(config_files)} store configuration files:")

# Connect to database
conn = sqlite3.connect('users.sqlite')

users_updated = 0
users_created = 0

for config_file in config_files:
    # Extract username from filename
    username = config_file.replace('store_config__', '').replace('.json', '').replace('_at_', '@').replace('_', '.')
    
    # Skip if it's a malformed name
    if '@' not in username or len(username) < 5:
        continue
        
    print(f"\n📁 Processing: {config_file}")
    print(f"   👤 Extracted username: {username}")
    
    # Check if user exists in database
    existing = conn.execute('SELECT link_code, username FROM users WHERE username = ?', (username,)).fetchone()
    
    if existing:
        code, db_username = existing
        print(f"   ✅ User exists with TV code: {code}")
    else:
        # Generate a unique TV code
        import random
        while True:
            code = str(random.randint(1000, 9999))
            if not conn.execute('SELECT 1 FROM users WHERE link_code = ?', (code,)).fetchone():
                break
        
        # Create user entry
        conn.execute('INSERT INTO users (username, link_code) VALUES (?, ?)', (username, code))
        print(f"   🆕 Created new user with TV code: {code}")
        users_created += 1
    
    # Load and verify config file
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        store_count = len(config.get('stores', []))
        print(f"   📋 Config has {store_count} store(s)")
        users_updated += 1
    except Exception as e:
        print(f"   ❌ Error reading config: {e}")

# Commit changes
conn.commit()

print(f"\n===== RESULTS =====")
print(f"✅ Users with working configs: {users_updated}")
print(f"🆕 New users created: {users_created}")

# Show all working TV codes
print(f"\n===== ALL WORKING TV CODES =====")
rows = conn.execute('''
    SELECT u.username, u.link_code 
    FROM users u 
    WHERE EXISTS (
        SELECT 1 FROM (
            SELECT 'store_config__' || REPLACE(REPLACE(u.username, '@', '_at_'), '.', '_') || '.json' as filename
        ) WHERE filename IN ({})
    )
    ORDER BY u.link_code
'''.format(','.join(['?' for _ in config_files])), config_files).fetchall()

for username, code in rows:
    config_file = f"store_config__{username.replace('@', '_at_').replace('.', '_')}.json"
    if os.path.exists(config_file):
        file_size = os.path.getsize(config_file)
        print(f"📺 Code {code}: {username} ({file_size} bytes)")

conn.close()

print(f"\n🎉 System is now ready for {len(rows)} users!")
print("Any user with a store configuration can now:")
print("1. Use their TV code on the dashboard at https://everydayadvertise.com")
print("2. Run the Pi client with their TV code")
print("3. View and manage their playlists")