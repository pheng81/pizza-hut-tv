#!/usr/bin/env python3
"""
Create EMPTY config file for mom.toeng@gmail.com 
This prevents her from inheriting the global config with all screens
"""
import json

# Start with minimal config - one store, NO screens
config = {
    "stores": [
        {
            "id": "1000",
            "store_name": "Store 1000"
        }
    ],
    "screens": {
        "1000": {}  # Empty - no screens yet
    },
    "master_store_id": "1000"
}

filename = "store_config__mom.toeng_at_gmail.com.json"
with open(filename, 'w') as f:
    json.dump(config, f, indent=4)

print(f"✓ Created {filename}")
print(f"  Store 1000 with 0 screens")
print(f"  User can now add screens via the dashboard")
print(f"\nThis prevents mom.toeng from seeing toengpheng's screens!")
