#!/usr/bin/env python3
"""
Quick Pi Client Test - Bypasses TV code for direct playlist testing
"""
import requests
import subprocess
import time
import signal
import sys
import os
from datetime import datetime

class QuickPiTest:
    def __init__(self):
        self.server_url = "https://everydayadvertise.com"
        self.vlc_process = None
        
    def test_direct_playlist_access(self):
        """Test accessing playlists directly without TV codes"""
        print("===== DIRECT PLAYLIST ACCESS TEST =====")
        
        # Try to access playlist directly for store 1000
        store_id = "1000"
        screen_id = "1000_screen1"
        
        # Try different approaches to access playlist
        test_urls = [
            f"{self.server_url}/playlist/{store_id}/{screen_id}",
            f"{self.server_url}/api/playlist/{store_id}/{screen_id}",
        ]
        
        test_headers = [
            {},  # No headers
            {'X-User-Code': '1000'},  # Use store ID as code
            {'X-User-Code': '0000'},  # Default code
            {'Authorization': 'Bearer test'},  # Bearer token
        ]
        
        for url in test_urls:
            print(f"\nTesting URL: {url}")
            
            for headers in test_headers:
                try:
                    print(f"  Headers: {headers}")
                    response = requests.get(url, headers=headers, timeout=5)
                    print(f"  Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        playlist = data.get('playlist', [])
                        print(f"  ✅ SUCCESS! Got {len(playlist)} playlist items")
                        
                        if playlist:
                            for i, item in enumerate(playlist):
                                print(f"    Item {i+1}: {item.get('file')} ({item.get('duration', 0)}s)")
                                
                            # Test playing the first video
                            self.play_test_video(playlist[0])
                            return True
                    else:
                        print(f"  ❌ Error: {response.text}")
                        
                except Exception as e:
                    print(f"  ⚠️ Exception: {e}")
                    
        print("\n❌ Could not access any playlists")
        return False
        
    def play_test_video(self, video_item):
        """Play a test video for a short duration"""
        print(f"\n🎬 Testing video playback: {video_item.get('file')}")
        
        video_file = video_item.get('file')
        if not video_file:
            print("❌ No video file")
            return
            
        # Try different video URL formats
        possible_urls = [
            video_item.get('slice_url'),
            video_item.get('url'), 
            f"{self.server_url}/media/{video_file}",
            f"{self.server_url}/static/media/{video_file}",
        ]
        
        for video_url in possible_urls:
            if not video_url:
                continue
                
            print(f"Trying URL: {video_url}")
            
            # Test if URL is accessible
            try:
                response = requests.head(video_url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ Video URL accessible: {video_url}")
                    
                    # Play for 10 seconds only
                    vlc_args = [
                        'vlc',
                        '--intf', 'dummy',
                        '--fullscreen',
                        '--play-and-exit',
                        '--run-time=10',  # Run for 10 seconds only
                        video_url
                    ]
                    
                    print(f"🎬 Starting VLC: {' '.join(vlc_args)}")
                    self.vlc_process = subprocess.Popen(vlc_args)
                    
                    # Wait for it to finish or timeout
                    try:
                        self.vlc_process.wait(timeout=15)
                        print("✅ Video test completed successfully")
                        return True
                    except subprocess.TimeoutExpired:
                        print("⏰ Video test timeout - killing VLC")
                        self.vlc_process.terminate()
                        return True
                        
                else:
                    print(f"❌ Video URL not accessible: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ Error testing URL: {e}")
                
        print("❌ No accessible video URLs found")
        return False
        
    def emergency_stop(self):
        """Stop any running VLC"""
        if self.vlc_process:
            try:
                self.vlc_process.terminate()
                self.vlc_process.wait(timeout=5)
            except:
                try:
                    self.vlc_process.kill()
                except:
                    pass
                    
        # System-wide VLC cleanup
        try:
            subprocess.run(['pkill', '-9', 'vlc'], timeout=3)
        except:
            pass

def main():
    print("Quick Pi Client Test - Direct Playlist Access")
    print("=" * 50)
    
    tester = QuickPiTest()
    
    def signal_handler(signum, frame):
        print("\n🛑 Stopping test...")
        tester.emergency_stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        success = tester.test_direct_playlist_access()
        if success:
            print("\n✅ Test completed successfully!")
        else:
            print("\n❌ Test failed - check server configuration")
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"\n💥 Test error: {e}")
        tester.emergency_stop()

if __name__ == "__main__":
    main()