#!/usr/bin/env python3
"""
EA TV Pi Client - Headless Playlist Test
Tests playlist functionality without GUI
"""

import requests
import subprocess
import threading
import time
import os
import sys

class HeadlessEATVPlaylist:
    def __init__(self, store_code="1000", screen_id="1", android_tv_code="4682"):
        self.store_code = store_code
        self.screen_id = screen_id
        self.android_tv_code = android_tv_code
        
        # Playlist system variables
        self.playback_active = False
        self.playlist_refresh_timer = None
        self.vlc_process = None
        self.current_playlist = []
        self.current_item_index = 0
        
        # Set display
        if not os.environ.get('DISPLAY'):
            os.environ['DISPLAY'] = ':0'
            print("🖥️ Setting DISPLAY to :0")
    
    def get_full_playlist(self):
        """Get the complete playlist from server."""
        try:
            # Use dynamic store ID to build proper screen ID format
            full_screen_id = f"{self.store_code}_screen{self.screen_id}"
            
            # Try different server URLs
            servers = [
                "https://everydayadvertise.com",
                "http://54.252.90.27:8082",
                "http://localhost:5002"
            ]
            
            for server_url in servers:
                try:
                    # Fetch playlist from server using correct format
                    url = f"{server_url}/playlist/{self.store_code}/{full_screen_id}"
                    headers = {}
                    if self.android_tv_code:
                        headers['X-User-Code'] = self.android_tv_code
                    
                    print(f"🔍 Fetching playlist: {url}")
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        playlist_data = response.json()
                        playlist_items = playlist_data.get('playlist', [])
                        print(f"📋 Retrieved {len(playlist_items)} playlist items")
                        
                        if playlist_items:
                            return playlist_items
                    
                except Exception as e:
                    print(f"❌ Failed to fetch playlist from {server_url}: {e}")
                    continue
            
            print("❌ No playlist items available from any server")
            return []
            
        except Exception as e:
            print(f"❌ Error getting playlist: {e}")
            return []
    
    def extract_video_url_from_item(self, item):
        """Extract video URL from playlist item."""
        try:
            # Priority order: preferred_url -> slice_url -> url
            if 'preferred_url' in item:
                print(f"✅ Using preferred_url")
                return item['preferred_url']
            elif 'slice_url' in item:
                print(f"✅ Using slice_url")
                return item['slice_url']
            elif 'url' in item:
                print(f"✅ Using url")
                return item['url']
            else:
                print(f"❌ No URL found in item: {list(item.keys())}")
                return None
        except Exception as e:
            print(f"❌ Error extracting URL: {e}")
            return None
    
    def launch_vlc_for_item(self, video_url, duration):
        """Launch VLC for a specific playlist item."""
        try:
            # Kill any existing VLC process
            if self.vlc_process:
                try:
                    self.vlc_process.terminate()
                    subprocess.run(['pkill', 'vlc'], check=False)
                except:
                    pass
            
            # VLC command for timed playback
            vlc_cmd = [
                'vlc',
                video_url,
                '--fullscreen',
                '--no-video-title-show',
                '--no-osd',
                '--quiet',
                '--intf', 'dummy',
                '--play-and-exit',
                f'--stop-time={duration}'
            ]
            
            print(f"🎬 Starting VLC for {duration}s: {video_url[:80]}...")
            
            # Start VLC process
            self.vlc_process = subprocess.Popen(vlc_cmd, env=os.environ.copy())
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start VLC: {e}")
            return False
    
    def playlist_loop(self):
        """Main playlist loop."""
        if not self.playback_active:
            return
        
        try:
            # Refresh playlist
            self.current_playlist = self.get_full_playlist()
            
            if not self.current_playlist:
                print("⏰ No playlist items, retrying in 10 seconds...")
                self.playlist_refresh_timer = threading.Timer(10.0, self.playlist_loop)
                self.playlist_refresh_timer.start()
                return
            
            # Get current item
            if self.current_item_index >= len(self.current_playlist):
                self.current_item_index = 0  # Loop back to start
            
            current_item = self.current_playlist[self.current_item_index]
            duration = int(current_item.get('duration', 10))
            
            print(f"🎬 Playing item {self.current_item_index + 1}/{len(self.current_playlist)} for {duration}s")
            
            # Get the video URL for this item
            video_url = self.extract_video_url_from_item(current_item)
            
            if video_url:
                # Launch VLC for this item
                if self.launch_vlc_for_item(video_url, duration):
                    # Schedule next item
                    self.current_item_index += 1
                    if self.current_item_index >= len(self.current_playlist):
                        self.current_item_index = 0  # Loop back to start
                    
                    # Schedule next item after duration
                    print(f"⏰ Next item in {duration} seconds...")
                    self.playlist_refresh_timer = threading.Timer(duration, self.playlist_loop)
                    self.playlist_refresh_timer.start()
                else:
                    print("❌ VLC launch failed, trying next item...")
                    self.current_item_index += 1
                    self.playlist_refresh_timer = threading.Timer(2.0, self.playlist_loop)
                    self.playlist_refresh_timer.start()
            else:
                print("❌ No video URL for current item, skipping...")
                self.current_item_index += 1
                self.playlist_refresh_timer = threading.Timer(2.0, self.playlist_loop)
                self.playlist_refresh_timer.start()
                
        except Exception as e:
            print(f"❌ Error in playlist loop: {e}")
            self.playlist_refresh_timer = threading.Timer(5.0, self.playlist_loop)
            self.playlist_refresh_timer.start()
    
    def start_playback(self):
        """Start playlist playback."""
        print(f"🚀 Starting EA TV playlist for Store {self.store_code}, Screen {self.screen_id}")
        self.playback_active = True
        self.playlist_loop()
    
    def stop_playback(self):
        """Stop playlist playback."""
        print("⏹️ Stopping playback...")
        self.playback_active = False
        
        if self.playlist_refresh_timer:
            self.playlist_refresh_timer.cancel()
        
        if self.vlc_process:
            try:
                self.vlc_process.terminate()
            except:
                pass
        
        subprocess.run(['pkill', 'vlc'], check=False)

def main():
    """Main function."""
    if len(sys.argv) > 1:
        screen_id = sys.argv[1]
    else:
        screen_id = input("Enter screen number (1, 2, or 3): ").strip()
    
    if screen_id not in ['1', '2', '3']:
        print("❌ Invalid screen number. Use 1, 2, or 3")
        sys.exit(1)
    
    client = HeadlessEATVPlaylist(screen_id=screen_id)
    
    try:
        client.start_playback()
        
        print("🎬 Playlist running... Press Ctrl+C to stop")
        while client.playback_active:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")
        client.stop_playback()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        client.stop_playback()

if __name__ == "__main__":
    main()