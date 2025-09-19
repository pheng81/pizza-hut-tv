#!/usr/bin/env python3
"""
Test script to verify sync group enforcement works correctly
"""

import requests
import json

BASE_URL = "http://localhost:5000"

# Test the add_screen endpoint
url = f"{BASE_URL}/add_screen"
data = {
    "store_id": "1000",
    "screen_type": "screen"
}
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}
cookies = {
    "user_key": "test8_at_gmail.com"
}

print("Testing add_screen endpoint...")
print(f"URL: {url}")
print(f"Data: {data}")
print(f"Headers: {headers}")
print(f"Cookies: {cookies}")

try:
    response = requests.post(url, data=data, headers=headers, cookies=cookies)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Content: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("="*50)

def test_sync_enforcement():
    print("=== Testing Sync Group Enforcement ===")
    
    # Test store
    store_id = "1200"
    
    print(f"Testing with store: {store_id}")
    
    # First, let's try to add screens and see what happens
    print("\n1. Adding first screen...")
    response = requests.post(f"{BASE_URL}/add_screen", 
                           json={"store_id": store_id, "screen_type": "screen"},
                           headers={"Content-Type": "application/json"})
    
    print(f"Response: {response.status_code}")
    if response.text:
        try:
            data = response.json()
            print(f"Data: {data}")
        except:
            print(f"Raw response: {response.text[:200]}...")
    
    print("\n2. Adding second screen...")
    response = requests.post(f"{BASE_URL}/add_screen", 
                           json={"store_id": store_id, "screen_type": "screen"},
                           headers={"Content-Type": "application/json"})
    
    print(f"Response: {response.status_code}")
    if response.text:
        try:
            data = response.json()
            print(f"Data: {data}")
        except:
            print(f"Raw response: {response.text[:200]}...")
    
    print("\n3. Adding third screen...")
    response = requests.post(f"{BASE_URL}/add_screen", 
                           json={"store_id": store_id, "screen_type": "screen"},
                           headers={"Content-Type": "application/json"})
    
    print(f"Response: {response.status_code}")
    if response.text:
        try:
            data = response.json()
            print(f"Data: {data}")
        except:
            print(f"Raw response: {response.text[:200]}...")
    
    # Now let's check the current store config
    print("\n4. Checking store configuration...")
    try:
        with open("store_config.json", "r") as f:
            config = json.load(f)
            screens = config.get("screens", {}).get(store_id, {})
            sync_groups = config.get("sync_groups", {})
            
            print(f"Current screens in store {store_id}: {list(screens.keys())}")
            print(f"Sync groups: {len(sync_groups)} groups")
            for gid, group in sync_groups.items():
                if group.get("store_id") == store_id:
                    print(f"  Group {gid}: count={group.get('count')}, locked_count={group.get('locked_count')}")
                    
    except Exception as e:
        print(f"Error reading config: {e}")
    
    print("\n5. Now let's try adding a promo screen...")
    response = requests.post(f"{BASE_URL}/add_screen", 
                           json={"store_id": store_id, "screen_type": "promo"},
                           headers={"Content-Type": "application/json"})
    
    print(f"Response: {response.status_code}")
    if response.text:
        try:
            data = response.json()
            print(f"Data: {data}")
        except:
            print(f"Raw response: {response.text[:200]}...")

if __name__ == "__main__":
    test_sync_enforcement()
