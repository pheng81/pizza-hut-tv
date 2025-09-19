#!/usr/bin/env python3
"""
Debug script to test the complete sync group enforcement flow
"""

import requests
import json
import os

BASE_URL = "http://localhost:5002"

def check_store_config():
    """Check current store configuration"""
    try:
        with open("store_config.json", "r") as f:
            config = json.load(f)
            print("=== Current Store Config ===")
            print(f"Stores: {[s['id'] + ':' + s['name'] for s in config.get('stores', [])]}")
            
            screens = config.get('screens', {})
            for store_id, store_screens in screens.items():
                print(f"Store {store_id} screens: {list(store_screens.keys())}")
            
            sync_groups = config.get('sync_groups', {})
            print(f"Sync groups: {len(sync_groups)}")
            for gid, group in sync_groups.items():
                store_id = group.get('store_id')
                count = group.get('count')
                locked_count = group.get('locked_count')
                print(f"  Group {gid}: store={store_id}, count={count}, locked_count={locked_count}")
            
            return config
    except Exception as e:
        print(f"Error reading config: {e}")
        return None

def test_add_screen(store_id, screen_type="screen"):
    """Test adding a screen"""
    print(f"\n=== Testing Add Screen: store={store_id}, type={screen_type} ===")
    
    try:
        response = requests.post(f"{BASE_URL}/add_screen", 
                               json={"store_id": store_id, "screen_type": screen_type},
                               headers={"Content-Type": "application/json"},
                               timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            data = response.json()
            print(f"Response: {data}")
            return data.get('success', False)
        else:
            print(f"Non-JSON response: {response.text[:200]}...")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False

def test_sync_workflow():
    """Test the complete sync group workflow"""
    print("=== TESTING SYNC GROUP ENFORCEMENT ===\n")
    
    # Check initial state
    config = check_store_config()
    if not config:
        return
    
    # Test with store 1200 (kippax)
    store_id = "1200"
    print(f"\nTesting with store: {store_id}")
    
    # Step 1: Add first screen
    print("\n1. Adding first screen...")
    success1 = test_add_screen(store_id, "screen")
    check_store_config()
    
    # Step 2: Add second screen  
    print("\n2. Adding second screen...")
    success2 = test_add_screen(store_id, "screen")
    check_store_config()
    
    # Step 3: Add third screen
    print("\n3. Adding third screen...")  
    success3 = test_add_screen(store_id, "screen")
    check_store_config()
    
    # At this point, we need to create a sync group to test enforcement
    # But that requires a more complex API call with file upload
    print("\n4. Now we need to create a sync group manually through the web interface")
    print("   - Go to http://localhost:5002")
    print("   - Select store 1200")
    print("   - Create a sync group with count=3")
    print("   - Then try adding more screens")
    
    # Step 4: Try adding fourth screen (should be blocked if sync group exists)
    print("\n5. Testing fourth screen (should be blocked if sync group exists)...")
    success4 = test_add_screen(store_id, "screen")
    
    # Step 5: Try adding promo screen (should also be blocked)
    print("\n6. Testing promo screen (should also be blocked if sync group exists)...")
    success5 = test_add_screen(store_id, "promo")
    
    # Final check
    check_store_config()
    
    print("\n=== SUMMARY ===")
    print(f"Screen additions: {sum([success1, success2, success3, success4, success5])}/5 succeeded")
    print("If sync group enforcement is working:")
    print("  - First 3 screens should succeed")
    print("  - 4th screen should fail (sync group complete)")
    print("  - Promo screen should fail (sync group complete)")

if __name__ == "__main__":
    test_sync_workflow()
