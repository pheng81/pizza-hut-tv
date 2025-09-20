#!/usr/bin/env python3
"""
Pizza Hut TV - Simple Test Client for Pi
Tests the authentication flow without GUI complications
"""

import requests

def test_authentication():
    server_url = "http://everydayadvertise.com:5002"
    
    print("=== Pizza Hut TV Authentication Test ===")
    
    # Test 1: Link code validation
    print("\n1. Testing link code 1769...")
    try:
        url = f'{server_url}/api/stores_by_code/1769'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Link code response: {data}")
            
            if data.get('success'):
                username = data.get('user', {}).get('username', '')
                print(f"✓ Authentication successful for user: {username}")
                
                # Test 2: Store validation
                print("\n2. Testing store list...")
                stores_url = f'{server_url}/api/stores'
                stores_response = requests.get(stores_url, timeout=10)
                
                if stores_response.status_code == 200:
                    stores = stores_response.json()
                    print(f"✓ Available stores: {stores}")
                    
                    # Test 3: Playlist URL
                    print("\n3. Testing playlist URL for store 1000, screen 1...")
                    playlist_url = f'{server_url}/playlist/1000/1'
                    print(f"✓ Playlist URL: {playlist_url}")
                    
                    # Test playlist access
                    playlist_response = requests.get(playlist_url, timeout=10)
                    if playlist_response.status_code == 200:
                        print(f"✓ Playlist accessible, content length: {len(playlist_response.text)}")
                    else:
                        print(f"✗ Playlist error: {playlist_response.status_code}")
                else:
                    print(f"✗ Store list error: {stores_response.status_code}")
            else:
                print(f"✗ Authentication failed: {data.get('error', 'Unknown error')}")
        else:
            print(f"✗ Link code validation failed: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Connection error: {str(e)}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_authentication()