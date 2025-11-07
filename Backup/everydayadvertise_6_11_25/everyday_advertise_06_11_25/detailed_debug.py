#!/usr/bin/env python3
"""
Debug script - detailed playlist inspection
"""

import requests
import json

def detailed_playlist_check():
    print("🔍 Detailed Playlist Analysis...")
    
    tv_code = "4682"
    store_code = "1000"
    screen_id = "1000_screen1"
    
    try:
        url = f"https://everydayadvertise.com/playlist/{store_code}/{screen_id}"
        headers = {
            'User-Agent': 'PizzaHutTV-Debug/1.0',
            'X-User-Code': tv_code
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            playlist = data.get('playlist', [])
            
            print(f"📋 Found {len(playlist)} playlist items")
            
            for i, item in enumerate(playlist):
                print(f"\n🎬 Item {i+1} - Full Structure:")
                print(json.dumps(item, indent=2))
                
                # Test different URL patterns
                file_path = item.get('file', '')
                if file_path:
                    # Try different URL constructions
                    test_urls = [
                        f"https://everydayadvertise.com/{file_path}",
                        f"https://everydayadvertise.com/api/file/{file_path}",
                        f"https://everydayadvertise.com/files/{file_path}",
                        f"https://everydayadvertise.com/media/{file_path}",
                    ]
                    
                    print(f"\n🔗 Testing URL patterns for: {file_path}")
                    for test_url in test_urls:
                        try:
                            head_response = requests.head(test_url, timeout=3)
                            status = "✅ OK" if head_response.status_code == 200 else f"❌ {head_response.status_code}"
                            print(f"   {status}: {test_url}")
                        except Exception as e:
                            print(f"   ❌ ERROR: {test_url} - {e}")
                
        else:
            print(f"❌ Playlist fetch failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    detailed_playlist_check()