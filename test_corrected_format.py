#!/usr/bin/env python3
"""
Test the corrected video URL fetching
"""

import requests

def test_corrected_format():
    """Test video URL fetching with correct format"""
    store_code = '1000'
    android_tv_code = '4682'
    
    for screen_num in ['1', '2', '3']:
        # Use dynamic store ID format
        full_screen_id = f"{store_code}_screen{screen_num}"
        
        try:
            url = f"https://everydayadvertise.com/playlist/{store_code}/{full_screen_id}"
            headers = {'X-User-Code': android_tv_code}
            
            print(f"🔍 Testing Screen {screen_num}: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                playlist = response.json()
                items = playlist.get('playlist', [])
                print(f"📋 Found {len(items)} playlist items")
                
                if items:
                    first_item = items[0]
                    if 'preferred_url' in first_item:
                        print(f"✅ Video URL available: {first_item['preferred_url'][:80]}...")
                    elif 'slice_url' in first_item:
                        print(f"✅ Video URL available: {first_item['slice_url'][:80]}...")
                    elif 'url' in first_item:
                        print(f"✅ Video URL available: {first_item['url'][:80]}...")
                else:
                    print("❌ No playlist items")
            else:
                print(f"❌ HTTP {response.status_code}")
            
            print()
                
        except Exception as e:
            print(f"❌ Error: {e}")
            print()

if __name__ == "__main__":
    test_corrected_format()