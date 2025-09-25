#!/usr/bin/env python3
"""
Sync Video Diagnostic Tool
Test sync video detection and playback across screens
"""
import requests
import json
from datetime import datetime

def test_sync_video_system():
    print("🔄 Sync Video Diagnostic Tool")
    print("=" * 50)
    
    base_url = "https://everydayadvertise.com"
    headers = {'X-User-Code': '1234'}
    store_id = "toengpheng_at_gmail.com"
    
    print(f"📋 Testing store: {store_id}")
    print(f"🌐 Server: {base_url}")
    
    # Test all three screens
    for screen_num in range(3):
        screen_id = f"screen{screen_num}"
        print(f"\n📺 Testing {screen_id}:")
        print("-" * 30)
        
        try:
            # Get playlist for this screen
            playlist_url = f"{base_url}/playlist/{store_id}/{screen_id}"
            response = requests.get(playlist_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                playlist = data.get('playlist', [])
                
                print(f"✅ Playlist loaded: {len(playlist)} items")
                print(f"📊 Queue length: {data.get('queue_len', 0)}")
                print(f"📐 Orientation: {data.get('orientation', 'unknown')}")
                
                if playlist:
                    # Check for sync videos
                    sync_videos = []
                    regular_videos = []
                    
                    for item in playlist:
                        sync_ref = item.get('sync_ref')
                        if sync_ref:
                            sync_videos.append({
                                'file': item.get('file', 'unknown'),
                                'sync_ref': sync_ref,
                                'slice_url': item.get('slice_url', 'none'),
                                'url': item.get('url', 'none')
                            })
                        elif item.get('file', '').endswith('.mp4'):
                            regular_videos.append(item.get('file', 'unknown'))
                    
                    print(f"🔄 Sync videos found: {len(sync_videos)}")
                    for sv in sync_videos:
                        print(f"  📹 {sv['file']}")
                        print(f"     Mode: {sv['sync_ref'].get('mode', 'unknown')}")
                        print(f"     Count: {sv['sync_ref'].get('count', 'unknown')}")
                        print(f"     Order: {sv['sync_ref'].get('order', 'unknown')}")
                        print(f"     Slice URL: {'✅ Yes' if sv['slice_url'] != 'none' else '❌ No'}")
                    
                    print(f"📼 Regular videos: {len(regular_videos)}")
                    for rv in regular_videos:
                        print(f"  📹 {rv}")
                        
                else:
                    print("⚠️  No items in playlist")
                    
            else:
                print(f"❌ HTTP {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test if any sync videos exist in the dashboard
    print(f"\n🔍 Dashboard Analysis:")
    print("-" * 30)
    
    # Test the main playlist endpoint
    try:
        main_url = f"{base_url}/api/playlist/{store_id}"
        response = requests.get(main_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            print(f"📦 Total items in dashboard: {len(items)}")
            
            sync_count = 0
            for item in items:
                if item.get('sync_ref') or ('sync' in item.get('file', '').lower()):
                    sync_count += 1
                    print(f"🔄 Sync item: {item.get('file', 'unknown')}")
            
            if sync_count == 0:
                print("⚠️  No sync videos found in dashboard")
                print("💡 Upload a sync video to test functionality")
            else:
                print(f"✅ Found {sync_count} sync video(s)")
                
        else:
            print(f"❌ Dashboard API error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Dashboard check error: {e}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    print("-" * 30)
    print("1. Upload a sync video through the dashboard")
    print("2. Make sure it's scheduled for the current time")
    print("3. Check that all 3 screen URLs are accessible:")
    print(f"   - {base_url}/webplayer?store_id={store_id}&screen_id=screen0")
    print(f"   - {base_url}/webplayer?store_id={store_id}&screen_id=screen1") 
    print(f"   - {base_url}/webplayer?store_id={store_id}&screen_id=screen2")
    print("4. Open browser developer tools to check for JavaScript errors")

if __name__ == "__main__":
    test_sync_video_system()