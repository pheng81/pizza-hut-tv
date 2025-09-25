#!/usr/bin/env python3
"""
Test script to verify EA TV Pi client video functionality
"""

import requests
import sys

def test_server_connectivity():
    """Test connectivity to various servers."""
    
    servers = [
        "https://everydayadvertise.com",
        "http://54.252.90.27:8082",
    ]
    
    print("🔍 Testing server connectivity...")
    
    for server in servers:
        try:
            # Test basic connectivity
            response = requests.get(f"{server}/api/sync-time", timeout=5)
            if response.status_code == 200:
                print(f"✅ {server} - Connected successfully")
                
                # Test playlist endpoint
                try:
                    playlist_response = requests.get(f"{server}/playlist/1000/1", timeout=5)
                    if playlist_response.status_code == 200:
                        print(f"   📺 Playlist endpoint working")
                    else:
                        print(f"   ⚠️ Playlist endpoint returned {playlist_response.status_code}")
                except Exception as e:
                    print(f"   ⚠️ Playlist test failed: {e}")
                    
            else:
                print(f"❌ {server} - Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {server} - Connection failed: {e}")
    
    print("\n🎬 VLC Test:")
    try:
        import subprocess
        result = subprocess.run(['vlc', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ VLC installed: {version_line}")
        else:
            print("❌ VLC not working properly")
    except Exception as e:
        print(f"❌ VLC test failed: {e}")

if __name__ == "__main__":
    test_server_connectivity()