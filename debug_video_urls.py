#!/usr/bin/env python3
"""
Debug video URL fetching for Pi client
"""

import requests
import sys

def test_video_urls():
    """Test video URL fetching"""
    store_code = '1000'
    screen_id = '1'
    android_tv_code = '1126'

    servers = [
        'https://everydayadvertise.com',
        'http://54.252.90.27:8082',
        'http://localhost:5002'
    ]

    print('🔍 Testing video URL fetching...')
    print(f'Store: {store_code}, Screen: {screen_id}, Code: {android_tv_code}\n')
    
    for server_url in servers:
        try:
            url = f'{server_url}/playlist/{store_code}/{screen_id}'
            headers = {'X-User-Code': android_tv_code}
            
            print(f'Trying: {url}')
            response = requests.get(url, headers=headers, timeout=10)
            print(f'Status: {response.status_code}')
            
            if response.status_code == 200:
                playlist = response.json()
                print(f'Playlist: {playlist}')
                if playlist and 'items' in playlist and len(playlist['items']) > 0:
                    first_item = playlist['items'][0]
                    if 'url' in first_item:
                        print(f'✅ Video URL found: {first_item["url"]}')
                        return first_item["url"]
                else:
                    print('❌ No items in playlist')
            else:
                print(f'❌ HTTP Error: {response.status_code}')
                try:
                    print(f'Response: {response.text[:200]}')
                except:
                    pass
            print()
        
        except Exception as e:
            print(f'❌ Failed {server_url}: {e}')
            print()

    # Fallback test
    fallback_url = f'https://everydayadvertise.com/slice-video/test.mp4?slice_mode=split-h&slice_count=3&slice_order={int(screen_id)-1}'
    print(f'Fallback URL: {fallback_url}')
    
    # Test if fallback URL is accessible
    try:
        response = requests.head(fallback_url, timeout=10)
        print(f'Fallback status: {response.status_code}')
        if response.status_code == 200:
            print('✅ Fallback URL is accessible')
            return fallback_url
        else:
            print('❌ Fallback URL not accessible')
    except Exception as e:
        print(f'❌ Fallback test failed: {e}')
    
    return None

if __name__ == "__main__":
    video_url = test_video_urls()
    if video_url:
        print(f'\n🎬 Final video URL: {video_url}')
    else:
        print('\n❌ No video URL available')