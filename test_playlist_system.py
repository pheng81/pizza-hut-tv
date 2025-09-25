#!/usr/bin/env python3
"""
Test the playlist functionality
"""

import requests
import json

def test_playlist_system():
    """Test the complete playlist system"""
    store_code = '1000'
    android_tv_code = '4682'
    
    print("🔍 Testing playlist system for all screens...")
    
    for screen_num in ['1', '2', '3']:
        full_screen_id = f"{store_code}_screen{screen_num}"
        
        try:
            url = f"https://everydayadvertise.com/playlist/{store_code}/{full_screen_id}"
            headers = {'X-User-Code': android_tv_code}
            
            print(f"\n📺 Screen {screen_num} ({full_screen_id}):")
            print(f"   URL: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                playlist_data = response.json()
                playlist_items = playlist_data.get('playlist', [])
                
                print(f"   ✅ {len(playlist_items)} playlist items found")
                
                for i, item in enumerate(playlist_items):
                    duration = item.get('duration', 10)
                    media_type = item.get('media_type', 'unknown')
                    
                    # Check available URLs
                    url_info = []
                    if 'preferred_url' in item:
                        url_info.append('preferred_url')
                    if 'slice_url' in item:
                        url_info.append('slice_url')
                    if 'url' in item:
                        url_info.append('url')
                    
                    print(f"      Item {i+1}: {media_type}, {duration}s, URLs: {', '.join(url_info)}")
                    
                    # Show the actual URL that would be used
                    if 'preferred_url' in item:
                        actual_url = item['preferred_url'][:60] + "..."
                        print(f"         🎬 Will play: {actual_url}")
                
            else:
                print(f"   ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_playlist_system()