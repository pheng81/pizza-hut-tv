import sqlite3
import json
import os

# 1. Add test9 user with pair_code 8329 to database
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Check if test9 exists
cursor.execute("SELECT username FROM users WHERE username = ?", ('test9@gmail.com',))
if cursor.fetchone():
    print("✅ test9@gmail.com already exists")
    # Update the link_code to 8329
    cursor.execute("UPDATE users SET link_code = ? WHERE username = ?", ('8329', 'test9@gmail.com'))
    conn.commit()
    print("✅ Updated test9@gmail.com link_code to 8329")
else:
    # Insert new user
    cursor.execute("""
        INSERT INTO users (username, password_hash, link_code, verified)
        VALUES (?, ?, ?, ?)
    """, ('test9@gmail.com', 'pbkdf2:sha256:600000$YourHashHere', '8329', 0))
    conn.commit()
    print("✅ Created test9@gmail.com with pair_code 8329")

conn.close()

# 2. Create config file with store 1111
config = {
    "stores": [
        {
            "id": "1111",
            "name": "test store",
            "time_zone": "Australia/Sydney",
            "time_zone_offset": "+10:00"
        }
    ],
    "screens": {
        "1111": {
            "1111_screen1": {
                "name": "Screen 1",
                "orientation": "horizontal",
                "file": "",
                "rotation": 0
            },
            "1111_screen2": {
                "name": "Screen 2", 
                "orientation": "horizontal",
                "file": "",
                "rotation": 0,
                "pi_id": "raspberrypi-ce39"
            }
        }
    },
    "playlists": {
        "1111": {
            "1111_screen1": [],
            "1111_screen2": []
        }
    }
}

# Save to user_configs directory (create if doesn't exist)
os.makedirs('user_configs', exist_ok=True)
config_path = 'user_configs/test9@gmail.com.json'

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print(f"✅ Created config file: {config_path}")
print(f"✅ Store 1111 'test store' created with screen2 assigned to raspberrypi-ce39")
