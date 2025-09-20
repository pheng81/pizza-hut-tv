#!/usr/bin/env python3

import requests
import json

def test_full_flow():
    print("Testing with link code 2021")
    print("=" * 30)
    
    # Step 1: Test link code
    try:
        response = requests.get("http://everydayadvertise.com/api/stores_by_code/2021", timeout=10)
        print(f"Link code 2021: Status {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return
            
        data = response.json()
        print(f"Stores response: {json.dumps(data, indent=2)}")
        
        if not data.get('success'):
            print("Link code not successful")
            return
            
        stores = data.get('stores', [])
        if not stores:
            print("No stores found")
            return
            
        # Step 2: Test playlist for first store
        store_id = stores[0].get('id')
        pair_code = data.get('user', {}).get('code', '2021')
        
        print(f"\nTesting playlist for store {store_id}")
        
        headers = {'X-User-Code': pair_code}
        
        for screen_id in ['1', '2', '3']:
            url = f"http://everydayadvertise.com/playlist/{store_id}/{screen_id}"
            print(f"\nTesting: {url}")
            print(f"Headers: {headers}")
            
            playlist_response = requests.get(url, headers=headers, timeout=10)
            print(f"Playlist Status: {playlist_response.status_code}")
            
            if playlist_response.status_code == 200:
                playlist_data = playlist_response.json()
                playlist = playlist_data.get('playlist', [])
                print(f"Playlist items for screen {screen_id}: {len(playlist)}")
                
                if playlist:
                    first_item = playlist[0]
                    video_file = first_item.get('file', 'No file')
                    print(f"First video file: {video_file}")
                    
                    # Test video URL
                    if video_file and video_file != 'No file':
                        video_url = f"http://everydayadvertise.com/media/{video_file}"
                        print(f"Testing video URL: {video_url}")
                        
                        video_response = requests.head(video_url, timeout=10)
                        print(f"Video URL Status: {video_response.status_code}")
                else:
                    print("Playlist is empty")
            else:
                print(f"Playlist error: {playlist_response.text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_full_flow()