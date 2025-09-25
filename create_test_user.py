#!/usr/bin/env python3
import sqlite3
import os

# Create test user with TV code 1234
conn = sqlite3.connect('users.sqlite')

# Create table if it doesn't exist
conn.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    link_code TEXT UNIQUE
)''')

# Insert test user
conn.execute('INSERT OR REPLACE INTO users (username, link_code) VALUES (?, ?)', 
             ('test_user', '1234'))

conn.commit()
print("✅ Test user created with TV code 1234")

# Verify it worked
rows = conn.execute('SELECT username, link_code FROM users').fetchall()
print(f"Users in database: {rows}")

# Create store config for test_user if it doesn't exist
config_file = 'store_config__test_user.json'
if not os.path.exists(config_file):
    import json
    import shutil
    
    # Copy from main config
    if os.path.exists('store_config.json'):
        shutil.copy('store_config.json', config_file)
        print(f"✅ Created config file: {config_file}")
    else:
        # Create basic config
        basic_config = {
            "stores": [{"id": "1000", "name": "Test Store"}],
            "master_store_id": "1000",
            "screens": {
                "1000": {
                    "1000_screen1": {
                        "file": None,
                        "vertical": False,
                        "horizontal": True,
                        "rotation": 0,
                        "protected": False,
                        "playlist": [
                            {
                                "file": "test_video.mp4",
                                "enabled": True,
                                "duration": 15,
                                "url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
                            }
                        ]
                    }
                }
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(basic_config, f, indent=2)
        print(f"✅ Created basic config: {config_file}")

conn.close()
print("✅ Setup complete! Use TV code: 1234")