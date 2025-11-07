#!/usr/bin/env python3
"""
Create proper config file for mom.toeng@gmail.com with only her 5 screens
"""
import json

config = {
    "stores": [
        {
            "id": "1000",
            "store_name": "Mom's Store"
        }
    ],
    "screens": {
        "1000": {
            "1000_screen1": {"name": "Screen 1"},
            "1000_screen2": {"name": "Screen 2"},
            "1000_screen3": {"name": "Screen 3"},
            "1000_promo1": {"name": "Promo 1"},
            "1000_promo2": {"name": "Promo 2"}
        }
    },
    "master_store_id": "1000"
}

filename = "store_config__mom.toeng_at_gmail.com.json"
with open(filename, 'w') as f:
    json.dump(config, f, indent=4)

print(f"✓ Created {filename} with 5 screens for Store 1000")
print(f"  Screens: 1000_screen1, 1000_screen2, 1000_screen3, 1000_promo1, 1000_promo2")
