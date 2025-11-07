#!/usr/bin/env python3
"""
Pair Pi1 to the new store/screen assignment
"""
import json

# Pi1 should be assigned to whatever you configured in the dashboard
# This script will create the local config on Pi1

config = {
    "pair_code": "8329",  # Your pair code
    "store_id": "1931",   # New store ID you assigned
    "screen_id": "1931_screen1",  # New screen ID you assigned
    "pi_id": "raspberrypi-ce39",
    "last_updated": 0
}

print(json.dumps(config, indent=2))
