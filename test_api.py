#!/usr/bin/env python3

import requests
import json

def test_link_code(code):
    try:
        response = requests.get(f"http://everydayadvertise.com/api/stores_by_code/{code}", timeout=10)
        print(f"Link code {code}: Status {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            return data
    except Exception as e:
        print(f"Error testing {code}: {e}")
    return None

def test_playlist(store_id, screen_id, pair_code=None):
    try:
        headers = {}
        if pair_code:
            headers['X-User-Code'] = pair_code
        
        url = f"http://everydayadvertise.com/playlist/{store_id}/{screen_id}"
        print(f"Testing playlist: {url}")
        print(f"Headers: {headers}")
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Playlist Status: {response.status_code}")
        print(f"Playlist Response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            playlist = data.get('playlist', [])
            print(f"Playlist items: {len(playlist)}")
            if playlist:
                print(f"First item: {playlist[0]}")
        
    except Exception as e:
        print(f"Error testing playlist: {e}")

if __name__ == "__main__":
    print("Testing Pizza Hut TV API")
    print("=" * 30)
    
    # Test different link codes
    codes_to_test = ['1769', '1000', '1234', '0000']
    working_data = None
    
    for code in codes_to_test:
        result = test_link_code(code)
        if result and result.get('success'):
            working_data = result
            break
    
    if working_data:
        stores = working_data.get('stores', [])
        if stores:
            store_id = stores[0].get('id')
            pair_code = working_data.get('user', {}).get('code', code)
            
            print(f"\nTesting playlist for store {store_id}, screen 1")
            test_playlist(store_id, '1', pair_code)
    else:
        print("No working link codes found")