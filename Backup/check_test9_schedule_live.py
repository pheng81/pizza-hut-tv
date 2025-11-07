#!/usr/bin/env python3
"""Check test9's schedule from the live server"""

import requests
import json
from datetime import datetime

# Test without auth first (public access)
print("="*80)
print("Checking test9 playlist schedule from server")
print("="*80)

# Try different endpoints
endpoints = [
    "https://everydayadvertise.com/api/playlist/test9/1?debug_schedule=1",
    "https://everydayadvertise.com/api/playlist/test9/1",
    "https://everydayadvertise.com/api/config/test9",
]

for url in endpoints:
    print(f"\n🔍 Testing: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   Response type: {type(data)}")
                
                # Pretty print the response
                print(f"\n📋 Response data:")
                print(json.dumps(data, indent=2)[:2000])  # First 2000 chars
                
                # Check if it's the debug schedule endpoint
                if 'store_time' in data:
                    print(f"\n⏰ Schedule Debug Info:")
                    print(f"   Server Time UTC: {data.get('server_time_utc')}")
                    print(f"   Store Time: {data.get('store_time')}")
                    print(f"   Weekday: {data.get('store_weekday')}")
                    print(f"   Timezone: {data.get('store_timezone')} (UTC+{data.get('timezone_offset')})")
                    
                    if 'items' in data:
                        print(f"\n📋 Items ({len(data['items'])} total):")
                        for i, item in enumerate(data['items'], 1):
                            print(f"\n   Item #{i}:")
                            print(f"     file: {item.get('file')}")
                            print(f"     days: {item.get('days')}")
                            print(f"     start: {item.get('start')}")
                            print(f"     end: {item.get('end')}")
                            print(f"     enabled: {item.get('enabled')}")
                            print(f"     is_active: {item.get('is_active')} ⬅️ THIS IS THE KEY!")
                
                # Check if it's a regular playlist
                elif isinstance(data, list):
                    print(f"\n📋 Playlist has {len(data)} items")
                    for i, item in enumerate(data, 1):
                        print(f"\n   Item #{i}:")
                        print(f"     file: {item.get('file')}")
                        if 'schedule' in item:
                            print(f"     schedule: {item.get('schedule')}")
                        if 'days' in item:
                            print(f"     days: {item.get('days')}")
                        if 'start' in item:
                            print(f"     start: {item.get('start')}")
                        if 'end' in item:
                            print(f"     end: {item.get('end')}")
                
                break  # Found working endpoint
                
            except json.JSONDecodeError:
                print(f"   Response is not JSON")
                print(f"   Content: {response.text[:200]}")
        else:
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"   Exception: {e}")

print("\n" + "="*80)
print("Current local time:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print("="*80)
