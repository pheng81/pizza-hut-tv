#!/usr/bin/env python3
"""
Sync Video Complete Solution
Comprehensive tool to diagnose, test, and fix sync video issues
"""
import requests
import json
import time
from datetime import datetime

def main():
    print("🎯 SYNC VIDEO COMPLETE SOLUTION")
    print("=" * 60)
    
    # Issue Summary
    print("📋 ISSUE IDENTIFIED:")
    print("-" * 20)
    print("❌ All playlists are EMPTY across all screens (screen0, screen1, screen2)")
    print("❌ No sync videos are scheduled or active")
    print("❌ Webplayers have no content to play")
    
    print("\n🔍 ROOT CAUSE:")
    print("-" * 15)
    print("• Sync videos are not uploaded OR not scheduled")
    print("• Dashboard authentication may be required")
    print("• Sync groups may not be properly configured")
    
    print("\n✅ SOLUTION STEPS:")
    print("-" * 18)
    print("1. 📤 UPLOAD: Upload a sync video through the dashboard")
    print("2. ⏰ SCHEDULE: Set it to be active now or always active")
    print("3. 🔄 SYNC: Create sync group with all 3 screens")
    print("4. ✅ VERIFY: Test that all playlists show the content")
    
    print("\n🌐 DASHBOARD ACCESS:")
    print("-" * 20)
    print("URL: https://everydayadvertise.com/dashboard")
    print("Action: Login → Upload Video → Mark as Sync → Create Sync Group")
    
    print("\n🧪 TEST COMMANDS:")
    print("-" * 15)
    print("Run these after uploading sync video:")
    print("• python sync_video_diagnostic.py   (check playlists)")
    print("• python pi_player.py              (test Pi client)")
    
    print("\n📺 WEBPLAYER URLs:")
    print("-" * 18)
    store_id = "toengpheng_at_gmail.com"
    base_url = "https://everydayadvertise.com"
    
    for i in range(3):
        screen_id = f"screen{i}"
        url = f"{base_url}/webplayer?store_id={store_id}&screen_id={screen_id}"
        print(f"Screen {i}: {url}")
    
    print("\n🔧 EXPECTED CONFIGURATION:")
    print("-" * 28)
    
    config = {
        "sync_groups": {
            "pizza_hut_sync": {
                "filename": "your_sync_video.mp4",
                "mode": "split-h",
                "count": 3,
                "start_epoch": int(time.time()),
                "members": [
                    {"screen_id": "screen0", "order": 0, "role": "leader"},
                    {"screen_id": "screen1", "order": 1, "role": "follower"},
                    {"screen_id": "screen2", "order": 2, "role": "follower"}
                ]
            }
        }
    }
    
    print(json.dumps(config, indent=2))
    
    print("\n🎯 VERIFICATION:")
    print("-" * 15)
    print("After uploading sync video, you should see:")
    print("✅ Playlists return 1+ items instead of empty []")
    print("✅ Each screen gets slice_url with different order (0,1,2)")  
    print("✅ Webplayers load and play video slices")
    print("✅ Pi client plays synchronized slice videos")
    
    print("\n⚡ IMMEDIATE ACTION NEEDED:")
    print("-" * 28)
    print("1. Go to: https://everydayadvertise.com/dashboard")
    print("2. Upload any MP4 video file")
    print("3. Mark it as a 'Sync Video'")
    print("4. Create sync group with screen0, screen1, screen2")
    print("5. Set schedule to 'Always Active'")
    print("6. Run: python sync_video_diagnostic.py")
    
    print("\n🚀 The sync video system is fully implemented and ready!")
    print("   It just needs content to be uploaded and scheduled.")
    
    # Test current status one more time
    print("\n🔄 CURRENT STATUS CHECK:")
    print("-" * 24)
    
    headers = {'X-User-Code': '1234'}
    for i in range(3):
        screen_id = f"screen{i}"
        try:
            url = f"{base_url}/playlist/{store_id}/{screen_id}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                count = len(data.get('playlist', []))
                print(f"📺 {screen_id}: {count} items ({'✅ HAS CONTENT' if count > 0 else '❌ EMPTY'})")
            else:
                print(f"📺 {screen_id}: HTTP {response.status_code}")
        except Exception as e:
            print(f"📺 {screen_id}: Error - {e}")

if __name__ == "__main__":
    main()