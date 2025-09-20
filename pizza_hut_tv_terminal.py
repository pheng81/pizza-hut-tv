#!/usr/bin/env python3
"""
EA TV - Raspberry Pi Client (Terminal Version)
Simple command-line interface that works without GUI
"""

import sys
import subprocess
import requests
import json

class PizzaHutTVTerminal:
    def __init__(self):
        self.server_url = "https://everydayadvertise.com"
        self.code = ""
        self.store_id = ""
        self.screen_id = ""
        self.vlc_process = None
        
    def get_input(self, prompt):
        """Get user input with prompt"""
        try:
            return input(prompt).strip()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)
    
    def verify_code(self):
        """Step 1: Verify TV code"""
        print("\n🍕 Pizza Hut TV - Raspberry Pi Client")
        print("=" * 40)
        
        while True:
            self.code = self.get_input("Enter 4-digit TV code: ")
            if len(self.code) == 4 and self.code.isdigit():
                try:
                    url = f"{self.server_url}/api/stores_by_code/{self.code}"
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            print(f"✅ Code {self.code} verified!")
                            return True
                    print(f"❌ Code {self.code} not found. Try again.")
                except Exception as e:
                    print(f"❌ Error checking code: {e}")
            else:
                print("❌ Please enter exactly 4 digits.")
    
    def get_store(self):
        """Step 2: Get store code"""
        while True:
            self.store_id = self.get_input("Enter store code: ")
            if self.store_id:
                print(f"✅ Store: {self.store_id}")
                return True
            print("❌ Store code cannot be empty.")
    
    def select_screen(self):
        """Step 3: Select screen"""
        print("\n📺 Available screens:")
        print("1 - Screen 1 (Left)")
        print("2 - Screen 2 (Middle)")  
        print("3 - Screen 3 (Right)")
        
        while True:
            choice = self.get_input("Select screen (1-3): ")
            if choice in ['1', '2', '3']:
                self.screen_id = f"{self.store_id}_screen{choice}"
                print(f"✅ Selected Screen {choice}")
                return True
            print("❌ Please enter 1, 2, or 3.")
    
    def play_video(self):
        """Step 4: Play video"""
        try:
            print("\n🎬 Getting playlist...")
            
            headers = {'X-User-Code': self.code}
            playlist_url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            
            response = requests.get(playlist_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"❌ Error getting playlist: HTTP {response.status_code}")
                return False
            
            data = response.json()
            playlist = data.get('playlist', [])
            
            if not playlist:
                print("❌ No videos in playlist")
                return False
            
            video_item = playlist[0]
            
            # Use exact webplayer logic
            slice_url = video_item.get('slice_url')
            if slice_url:
                if 'localhost' not in slice_url and '127.0.0.1' not in slice_url:
                    video_url = slice_url.replace('http:', 'https:')
                else:
                    video_url = slice_url
                print(f"📺 Using server slice URL")
            else:
                video_file = video_item.get('file')
                video_url = video_item.get('url') or f"{self.server_url}/media/{video_file}"
                print(f"📺 Using fallback URL")
            
            print(f"🎥 Playing: {video_url}")
            
            # Launch VLC in fullscreen
            vlc_args = [
                'vlc',
                '--intf', 'dummy',
                '--fullscreen',
                '--loop',
                '--no-osd',
                '--no-video-title-show', 
                '--no-video-deco',
                video_url
            ]
            
            print("🚀 Starting VLC...")
            print("Press Ctrl+C to stop video")
            
            self.vlc_process = subprocess.Popen(vlc_args)
            
            try:
                self.vlc_process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Stopping video...")
                self.vlc_process.terminate()
                
            return True
            
        except Exception as e:
            print(f"❌ Error playing video: {e}")
            return False
    
    def run(self):
        """Main program flow"""
        try:
            if self.verify_code():
                if self.get_store():
                    if self.select_screen():
                        self.play_video()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
        finally:
            if self.vlc_process:
                try:
                    self.vlc_process.terminate()
                except:
                    pass

if __name__ == "__main__":
    client = PizzaHutTVTerminal()
    client.run()