#!/usr/bin/env python3
import sqlite3
import os

print("===== DATABASE vs CONFIG FILE ANALYSIS =====")

# Check database
conn = sqlite3.connect('users.sqlite')
rows = conn.execute('SELECT username, link_code FROM users ORDER BY username').fetchall()
conn.close()

print(f"Total users in database: {len(rows)}")
print("\n--- SAMPLE DATABASE ENTRIES ---")
for username, code in rows[:5]:
    print(f"DB: '{username}' -> Code {code}")

print("\n--- SAMPLE CONFIG FILES ---")
config_files = [f for f in os.listdir('.') if f.startswith('store_config__') and f.endswith('.json')]
for config_file in config_files[:5]:
    print(f"FILE: {config_file}")

print("\n--- MATCHING ANALYSIS ---")
for username, code in rows:
    # Try different naming patterns
    patterns = [
        f"store_config__{username.replace('@', '_at_').replace('.', '_')}.json",
        f"store_config__{username}.json"
    ]
    
    found = False
    for pattern in patterns:
        if os.path.exists(pattern):
            print(f"✅ Code {code} ({username}): {pattern}")
            found = True
            break
    
    if not found:
        # Check if any config file contains similar name
        username_clean = username.replace('@', '_at_').replace('.', '_')
        matching_files = [f for f in config_files if username_clean in f or username in f]
        if matching_files:
            print(f"🔍 Code {code} ({username}): Possible match -> {matching_files[0]}")
        else:
            print(f"❌ Code {code} ({username}): No config found")