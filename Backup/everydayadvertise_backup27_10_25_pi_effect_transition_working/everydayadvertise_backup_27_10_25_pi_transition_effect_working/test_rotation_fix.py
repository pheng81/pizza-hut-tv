#!/usr/bin/env python3
"""
🔄 Rotation Fix Verification Script
Verifies that TV client can receive real-time rotation updates from dashboard
"""

import requests
import time
import json
import sys

def test_rotation_updates():
    """Test the rotation functionality end-to-end"""
    
    print("🔄 Testing Rotation Fix Implementation")
    print("=" * 50)
    
    # Test configuration
    BASE_URL = "https://everydayadvertise.com"
    TEST_STORE = "1931"
    TEST_SCREEN = "1931_promo1"
    
    # Test the rotation update endpoint
    print(f"1. Testing rotation update endpoint...")
    
    rotation_values = [90, 180, 270, 0]  # Test all rotation angles
    
    for rotation in rotation_values:
        try:
            print(f"   📡 Sending rotation update: {rotation}°")
            
            # Simulate dashboard rotation request
            payload = {
                "store_id": TEST_STORE,
                "screen_id": TEST_SCREEN,
                "rotation": rotation
            }
            
            response = requests.post(f"{BASE_URL}/update_rotation", 
                                   json=payload,
                                   timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"   ✅ Server accepted rotation {rotation}°")
                    if data.get('pushed'):
                        print(f"   ✅ WebSocket event pushed to clients")
                    else:
                        print(f"   ⚠️  WebSocket push status unknown")
                else:
                    print(f"   ❌ Server rejected rotation: {data.get('error', 'Unknown error')}")
            else:
                print(f"   ❌ HTTP Error {response.status_code}: {response.text}")
                
            time.sleep(2)  # Wait between requests
            
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            
    # Test playlist endpoint (for polling fallback)
    print(f"\n2. Testing playlist endpoint (polling fallback)...")
    
    try:
        response = requests.get(f"{BASE_URL}/playlist/{TEST_STORE}/{TEST_SCREEN}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                rotation = data.get('rotation', 'not found')
                orientation = data.get('orientation', 'not found')
                print(f"   ✅ Playlist endpoint working")
                print(f"   📊 Current rotation: {rotation}°")
                print(f"   📊 Current orientation: {orientation}")
            else:
                print(f"   ❌ Playlist endpoint error: {data}")
        else:
            print(f"   ❌ Playlist HTTP Error {response.status_code}")
    except Exception as e:
        print(f"   ❌ Playlist request failed: {e}")
    
    # Test TV view template
    print(f"\n3. Testing TV view template...")
    
    try:
        tv_url = f"{BASE_URL}/tv_view.html?debug=1&store_id={TEST_STORE}&screen_id={TEST_SCREEN}"
        response = requests.get(tv_url, timeout=10)
        
        if response.status_code == 200:
            html_content = response.text
            
            # Check for key rotation functionality
            checks = [
                ("WebSocket connection", "connectWebSocket" in html_content),
                ("Rotation application", "applyOrientation" in html_content),
                ("Polling fallback", "pollForUpdates" in html_content),
                ("Socket.IO handling", "reload_client" in html_content),
                ("Debug controls", "rotation-controls" in html_content),
            ]
            
            print(f"   📋 TV view template analysis:")
            for check_name, passed in checks:
                status = "✅" if passed else "❌"
                print(f"   {status} {check_name}")
                
        else:
            print(f"   ❌ TV view HTTP Error {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ TV view request failed: {e}")
    
    print(f"\n🎯 Testing Complete!")
    print(f"\n📋 Next Steps:")
    print(f"   1. Open Android TV browser")
    print(f"   2. Navigate to: {BASE_URL}/tv_view.html?debug=1&store_id={TEST_STORE}&screen_id={TEST_SCREEN}")
    print(f"   3. Use dashboard to test rotation: {BASE_URL}/dashboard")
    print(f"   4. Check debug overlay for rotation messages")
    print(f"\n🔍 Look for these debug messages:")
    print(f"   - 'SOCKET: Connected to server'")
    print(f"   - 'SOCKET: Received reload_client'") 
    print(f"   - 'SOCKET: Rotation update received - XXX°'")
    print(f"   - 'ROTATION: XX° rotation applied'")

if __name__ == "__main__":
    test_rotation_updates()