#!/usr/bin/env python3
"""
Debug script to test Pizza Hut TV playlist API
"""

import requests
import json

def test_api():
    print("🍕 Testing Pizza Hut TV API...")
    
    # Test 1: Validate TV code
    tv_code = "4682"
    print(f"\n1. Testing TV code validation: {tv_code}")
    
    try:
        response = requests.get(
            f"https://everydayadvertise.com/api/stores_by_code/{tv_code}",
            timeout=10,
            headers={'User-Agent': 'PizzaHutTV-Debug/1.0'}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success', False)}")
            stores = data.get('stores', [])
            print(f"   Stores found: {len(stores)}")
            if stores:
                print(f"   First store: {stores[0]}")
        else:
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Get playlist
    store_code = "1000"
    screen_id = "1000_screen1"
    print(f"\n2. Testing playlist fetch: store={store_code}, screen={screen_id}")
    
    try:
        url = f"https://everydayadvertise.com/playlist/{store_code}/{screen_id}"
        headers = {
            'User-Agent': 'PizzaHutTV-Debug/1.0',
            'X-User-Code': tv_code
        }
        
        print(f"   URL: {url}")
        print(f"   Headers: {headers}")
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            playlist = data.get('playlist', [])
            print(f"   Playlist items: {len(playlist)}")
            
            for i, item in enumerate(playlist[:3]):  # Show first 3 items
                print(f"   Item {i+1}:")
                print(f"     File: {item.get('file', 'N/A')}")
                print(f"     Duration: {item.get('duration', 'N/A')}")
                print(f"     Media Type: {item.get('media_type', 'N/A')}")
                
                # Test if file URL is accessible
                file_url = item.get('file', '')
                if file_url:
                    full_url = f"https://everydayadvertise.com/{file_url}"
                    print(f"     Full URL: {full_url}")
                    
                    try:
                        head_response = requests.head(full_url, timeout=5)
                        print(f"     File accessible: {head_response.status_code == 200}")
                        if head_response.status_code == 200:
                            print(f"     File size: {head_response.headers.get('content-length', 'Unknown')}")
                    except Exception as fe:
                        print(f"     File check failed: {fe}")
        else:
            print(f"   Error: {response.text[:200]}")
            
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 3: Check VLC
    print(f"\n3. Testing VLC availability...")
    import subprocess
    try:
        result = subprocess.run(['vlc', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   VLC found: {version_line}")
        else:
            print(f"   VLC error: {result.stderr}")
    except Exception as e:
        print(f"   VLC check failed: {e}")
    
    print("\n✅ Debug test complete!")

if __name__ == "__main__":
    test_api()