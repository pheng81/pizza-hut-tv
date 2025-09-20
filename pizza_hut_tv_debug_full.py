#!/usr/bin/env python3
"""
Pizza Hut TV - Pi Debug Client
Shows exactly what API responses we get
"""

import tkinter as tk
from tkinter import messagebox
import requests
import json
import subprocess
import os
import signal
import sys

class PizzaHutTVDebug:
    def __init__(self, root):
        self.root = root
        self.root.title("Pizza Hut TV - Debug Mode")
        self.root.geometry("900x700")
        self.root.configure(bg='#0b0b0b')
        
        self.server_url = "http://everydayadvertise.com"
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main container
        self.main_frame = tk.Frame(self.root, bg='#0b0b0b')
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(self.main_frame, 
                              text="Pizza Hut TV - Debug Mode", 
                              font=('Arial', 18, 'bold'), 
                              fg='#c8102e',
                              bg='#0b0b0b')
        title_label.pack(pady=(0, 20))
        
        # Link code input
        input_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=15, pady=15)
        input_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(input_frame, text="Enter link code:", font=('Arial', 12), 
                fg='white', bg='#0d0d0d').pack(anchor='w')
        
        entry_frame = tk.Frame(input_frame, bg='#0d0d0d')
        entry_frame.pack(fill='x', pady=(5, 10))
        
        self.link_entry = tk.Entry(entry_frame, font=('Arial', 12), width=10,
                                  bg='#333333', fg='white', insertbackground='white')
        self.link_entry.pack(side='left', padx=(0, 10))
        self.link_entry.insert(0, "2021")  # Default to your working code
        
        tk.Button(entry_frame, text="Test API", command=self.test_api,
                 font=('Arial', 10, 'bold'), bg='#c8102e', fg='white',
                 padx=20, pady=5).pack(side='left')
        
        # Debug output
        debug_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=10, pady=10)
        debug_frame.pack(fill='both', expand=True)
        
        tk.Label(debug_frame, text="Debug Output:", font=('Arial', 12, 'bold'),
                fg='white', bg='#0d0d0d').pack(anchor='w')
        
        # Text area with scrollbar
        text_frame = tk.Frame(debug_frame, bg='#0d0d0d')
        text_frame.pack(fill='both', expand=True, pady=(5, 0))
        
        self.debug_text = tk.Text(text_frame, bg='#1a1a1a', fg='#00ff00',
                                 font=('Courier', 10), wrap='word')
        scrollbar = tk.Scrollbar(text_frame, orient='vertical', command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=scrollbar.set)
        
        self.debug_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons
        button_frame = tk.Frame(self.main_frame, bg='#0b0b0b')
        button_frame.pack(fill='x', pady=(10, 0))
        
        tk.Button(button_frame, text="Clear Output", command=self.clear_output,
                 font=('Arial', 10), bg='#666666', fg='white',
                 padx=15, pady=5).pack(side='left', padx=(0, 10))
        
        tk.Button(button_frame, text="Test Video Play", command=self.test_video,
                 font=('Arial', 10, 'bold'), bg='#c8102e', fg='white',
                 padx=15, pady=5).pack(side='left')
        
        self.current_video_url = None
        
    def log(self, message):
        """Add message to debug output"""
        self.debug_text.insert('end', f"{message}\n")
        self.debug_text.see('end')
        self.root.update()
        
    def clear_output(self):
        """Clear debug output"""
        self.debug_text.delete(1.0, 'end')
        
    def test_api(self):
        """Test the full API flow and show all responses"""
        link_code = self.link_entry.get().strip()
        if not link_code:
            self.log("ERROR: Please enter a link code")
            return
            
        self.log(f"=== Testing API with link code: {link_code} ===")
        
        try:
            # Step 1: Test stores API
            self.log("Step 1: Testing stores API...")
            stores_url = f"{self.server_url}/api/stores_by_code/{link_code}"
            self.log(f"URL: {stores_url}")
            
            response = requests.get(stores_url, timeout=10)
            self.log(f"Status: {response.status_code}")
            
            if response.status_code != 200:
                self.log(f"ERROR: {response.text}")
                return
                
            stores_data = response.json()
            self.log(f"Response: {json.dumps(stores_data, indent=2)}")
            
            if not stores_data.get('success'):
                self.log("ERROR: API returned success=false")
                return
                
            stores = stores_data.get('stores', [])
            if not stores:
                self.log("ERROR: No stores in response")
                return
                
            # Step 2: Test playlist API for each store and screen
            pair_code = stores_data.get('user', {}).get('code', link_code)
            self.log(f"\nStep 2: Testing playlists with pair code: {pair_code}")
            
            for store in stores:
                store_id = store.get('id')
                store_name = store.get('name', 'Unknown')
                self.log(f"\nStore: {store_name} (ID: {store_id})")
                
                for screen_id in ['1', '2', '3']:
                    self.log(f"\n--- Screen {screen_id} ---")
                    
                    playlist_url = f"{self.server_url}/playlist/{store_id}/{screen_id}"
                    headers = {'X-User-Code': pair_code}
                    
                    self.log(f"URL: {playlist_url}")
                    self.log(f"Headers: {headers}")
                    
                    playlist_response = requests.get(playlist_url, headers=headers, timeout=10)
                    self.log(f"Status: {playlist_response.status_code}")
                    
                    if playlist_response.status_code == 200:
                        playlist_data = playlist_response.json()
                        playlist = playlist_data.get('playlist', [])
                        
                        self.log(f"Playlist items: {len(playlist)}")
                        
                        if playlist:
                            for i, item in enumerate(playlist):
                                video_file = item.get('file', 'No file')
                                self.log(f"  Item {i+1}: {video_file}")
                                
                                # Test first video
                                if i == 0 and video_file and video_file != 'No file':
                                    video_url = f"{self.server_url}/media/{video_file}"
                                    self.log(f"  Video URL: {video_url}")
                                    
                                    # Test if video is accessible
                                    try:
                                        video_response = requests.head(video_url, timeout=5)
                                        self.log(f"  Video Status: {video_response.status_code}")
                                        
                                        if video_response.status_code == 200:
                                            self.current_video_url = video_url
                                            self.log(f"  ✓ Video accessible - ready to play!")
                                    except Exception as e:
                                        self.log(f"  Video test error: {e}")
                        else:
                            self.log("  Playlist is EMPTY")
                            # Show the full playlist response for debugging
                            self.log(f"  Full response: {json.dumps(playlist_data, indent=4)}")
                    else:
                        self.log(f"  Error: {playlist_response.text}")
                        
        except Exception as e:
            self.log(f"ERROR: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
    
    def test_video(self):
        """Test playing the found video"""
        if not self.current_video_url:
            self.log("ERROR: No video URL found. Run 'Test API' first.")
            return
            
        self.log(f"\n=== Testing Video Playback ===")
        self.log(f"Video URL: {self.current_video_url}")
        
        try:
            # Test VLC command
            vlc_cmd = ['vlc', '--fullscreen', '--loop', self.current_video_url]
            self.log(f"VLC Command: {' '.join(vlc_cmd)}")
            
            process = subprocess.Popen(vlc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.log("VLC launched - check if video is playing")
            
            # Kill VLC after 5 seconds for testing
            self.root.after(5000, lambda: self.kill_vlc(process))
            
        except Exception as e:
            self.log(f"VLC Error: {e}")
    
    def kill_vlc(self, process):
        """Kill VLC process"""
        try:
            process.terminate()
            subprocess.run(['pkill', 'vlc'], capture_output=True)
            self.log("VLC stopped")
        except:
            pass

def main():
    print("Pizza Hut TV - Debug Mode")
    print("Shows all API responses to debug playlist issues")
    
    root = tk.Tk()
    app = PizzaHutTVDebug(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()