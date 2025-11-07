#!/usr/bin/env python3
"""
Check current Pi WebSocket connections
"""
import requests
import sys

# Test the WebSocket status endpoint
pi_id = "raspberrypi-ce39"
url = f"https://api.everydayadvertise.com/api/pi-status-ws/{pi_id}"

print(f"Checking Pi status: {pi_id}")
print(f"URL: {url}")
print("=" * 60)

try:
    response = requests.get(url, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'online':
            print("\n✅ Pi is ONLINE")
            print(f"   IP: {data.get('ip_address')}")
            print(f"   Version: {data.get('version')}")
            print(f"   Connected since: {data.get('connected_since')}")
        else:
            print("\n❌ Pi is OFFLINE")
            print(f"   Message: {data.get('message')}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
