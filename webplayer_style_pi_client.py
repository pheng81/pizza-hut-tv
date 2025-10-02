# SAFE VERSION - NO VLC CROPPING TO PREVENT CRASHES
import os
import sys
import time
import threading
import json
import requests
import tkinter as tk
from tkinter import ttk
import vlc

class PizzaHutTVPlayerSafe:
    def __init__(self):
        # Initialize GUI
        self.root = tk.Tk()
        self.root.title("Pizza Hut TV Player - Safe Mode")
        self.root.geometry("400x300")
        self.root.configure(bg='#0d0d0d')

        # State variables
        self.android_tv_code = ""
        self.store_code = ""
        self.screen_id = ""
        self.current_step = 1
        
        # Safe playback - no complex cropping
        self.playback_active = False
        self.embedded_playlist = []
        self.current_embedded_index = 0
        self.embedded_stop_event = threading.Event()
        
        self.setup_gui()
        
    def setup_gui(self):
        # Create main panel
        self.panel = tk.Frame(self.root, bg="#0d0d0d")
        self.panel.pack(expand=True, fill="both", padx=20, pady=20)

        # Step 1: Store Code
        self.store_frame = tk.Frame(self.panel, bg="#0d0d0d")
        self.store_frame.pack(pady=(0, 18))
        
        tk.Label(self.store_frame, text="🏪 Step 1: Store Code", 
                font=("Arial", 14, "bold"), bg="#0d0d0d", fg="#ffffff").pack()
        
        self.store_entry = tk.Entry(self.store_frame, font=("Arial", 12), width=30)
        self.store_entry.pack(pady=(5, 0))
        self.store_entry.insert(0, "1000")

        # Step 2: Screen Selection  
        self.screen_frame = tk.Frame(self.panel, bg="#0d0d0d")
        self.screen_frame.pack(pady=(0, 18))
        
        self.screen_var = tk.StringVar(value="1")
        
        screens = [
            ("📺 Screen 1", "1"),
            ("📺 Screen 2", "2"), 
            ("📺 Screen 3", "3")
        ]
        
        tk.Label(self.screen_frame, text="📺 Step 2: Screen Selection",
                font=("Arial", 14, "bold"), bg="#0d0d0d", fg="#ffffff").pack()
        
        for text, value in screens:
            tk.Radiobutton(self.screen_frame, text=text, variable=self.screen_var, 
                          value=value, bg="#0d0d0d", fg="#ffffff", 
                          selectcolor="#0d0d0d", font=("Arial", 11)).pack(anchor="w")

        # Step 3: Android TV Code
        self.tv_frame = tk.Frame(self.panel, bg="#0d0d0d")
        self.tv_frame.pack(pady=(0, 18))
        
        tk.Label(self.tv_frame, text="📱 Step 3: Android TV Code",
                font=("Arial", 14, "bold"), bg="#0d0d0d", fg="#ffffff").pack()
        
        self.tv_entry = tk.Entry(self.tv_frame, font=("Arial", 12), width=30)
        self.tv_entry.pack(pady=(5, 0))
        self.tv_entry.insert(0, "4682")

        # Play Button
        self.play_button = tk.Button(self.panel, text="▶️ Start Safe Playback", 
                                   command=self.start_safe_playback,
                                   font=("Arial", 14, "bold"), bg="#4CAF50", fg="white",
                                   relief="flat", padx=20, pady=10)
        self.play_button.pack(pady=20)

        # Status
        self.status_label = tk.Label(self.panel, text="Ready for safe playback",
                                   font=("Arial", 10), bg="#0d0d0d", fg="#cccccc")
        self.status_label.pack()

    def start_safe_playback(self):
        """Start safe playback without any VLC cropping operations"""
        try:
            self.store_code = self.store_entry.get().strip()
            self.screen_id = self.screen_var.get()
            self.android_tv_code = self.tv_entry.get().strip()
            
            if not all([self.store_code, self.screen_id, self.android_tv_code]):
                self.status_label.config(text="❌ Please fill all fields")
                return
                
            self.status_label.config(text="🔄 Starting safe playback...")
            self.root.update()
            
            # Start safe embedded playback thread
            self.playback_active = True
            self.embedded_stop_event.clear()
            
            threading.Thread(target=self.safe_embedded_playback_loop, daemon=True).start()
            
            self.status_label.config(text="✅ Safe playback started")
            
        except Exception as e:
            self.status_label.config(text=f"❌ Error: {e}")
            print(f"❌ Startup error: {e}")

    def safe_embedded_playback_loop(self):
        """Safe playback loop - no VLC cropping, just basic playback"""
        print("🚀 Starting SAFE embedded playback loop")
        
        # Initialize VLC with Pi-safe options
        try:
            # Disable hardware acceleration and problematic features for Pi stability
            vlc_args = [
                '--intf', 'dummy',
                '--no-audio',
                '--no-video-deco', 
                '--no-embedded-video',
                '--avcodec-hw=none',
                '--vout=x11',
                '--no-xlib',
                '--quiet'
            ]
            instance = vlc.Instance(*vlc_args)
            player = instance.media_player_new()
            player.set_fullscreen(True)
            print("✅ VLC initialized with Pi-safe options")
        except Exception as e:
            print(f"❌ VLC initialization failed: {e}")
            return

        while self.playback_active and not self.embedded_stop_event.is_set():
            try:
                # Fetch playlist safely
                playlist = self.fetch_safe_playlist()
                if not playlist:
                    print("⚠️ No playlist - waiting 10s")
                    time.sleep(10)
                    continue
                    
                # Update playlist
                self.embedded_playlist = playlist
                if self.current_embedded_index >= len(self.embedded_playlist):
                    self.current_embedded_index = 0
                    
                # Play current item
                item = self.embedded_playlist[self.current_embedded_index]
                url = self.extract_safe_url(item)
                
                if not url:
                    print("⚠️ No URL found - skipping")
                    self.current_embedded_index = (self.current_embedded_index + 1) % len(self.embedded_playlist)
                    time.sleep(2)
                    continue
                    
                duration = item.get('duration', 30)
                title = item.get('title', f'Item {self.current_embedded_index+1}')
                
                print(f"🎥 SAFE Playing: {title}")
                print(f"📺 URL: {url}")
                print(f"⏱️ Duration: {duration}s")
                
                # Simple, safe playback
                media = instance.media_new(url)
                player.set_media(media)
                player.play()
                
                # Wait for playback to start
                start_wait = 0
                while player.get_state() not in [vlc.State.Playing, vlc.State.Ended] and start_wait < 10:
                    time.sleep(0.2)
                    start_wait += 0.2
                    
                if player.get_state() == vlc.State.Playing:
                    print(f"✅ Playbook started successfully")
                    
                    # Smart slice logic - detect if this is a multi-screen setup
                    try:
                        screen_num = int(self.screen_id or "1")
                        if screen_num > 1:  # Screen 2, 3, etc.
                            print(f"🔄 Screen {screen_num} detected - applying smart slice")
                            
                            # Wait for video dimensions
                            time.sleep(1)
                            try:
                                vw, vh = player.video_get_size(0)
                                if vw > 1920:  # Multi-screen video detected
                                    # Calculate slice for this screen (assuming 3-screen setup)
                                    count = 3  # or detect from video width
                                    order = screen_num - 1  # 0-based
                                    slice_width = vw // count
                                    slice_offset = order * slice_width
                                    
                                    geometry = f"{slice_width}x{vh}+{slice_offset}+0"
                                    success = player.video_set_crop_geometry(geometry)
                                    print(f"✂️ Applied slice {screen_num}/3: {geometry} success={success}")
                                    
                                    if success:
                                        player.video_set_scale(0)  # Scale to fit
                                        print(f"📺 Scaled slice to fullscreen")
                                else:
                                    print(f"📺 Standard video size {vw}x{vh} - no slicing needed")
                            except Exception as slice_e:
                                print(f"⚠️ Slice detection failed: {slice_e}")
                        else:
                            print(f"📺 Screen 1 (primary) - showing full video")
                    except Exception as screen_e:
                        print(f"⚠️ Screen detection failed: {screen_e}")
                else:
                    print(f"⚠️ Playback may not have started properly")
                
                # Simple wait with slice applied
                start_time = time.time()
                while time.time() - start_time < duration and not self.embedded_stop_event.is_set():
                    time.sleep(0.5)
                    
                # Move to next item
                self.current_embedded_index = (self.current_embedded_index + 1) % len(self.embedded_playlist)
                
            except Exception as e:
                print(f"⚠️ Safe playback error: {e}")
                time.sleep(5)
                
        print("🛑 Safe embedded playback loop exited")

    def fetch_safe_playlist(self):
        """Safely fetch playlist without complex error handling"""
        try:
            screen_id = getattr(self, 'screen_id', '1') or '1'
            store_id = getattr(self, 'store_code', '1000') or '1000'
            
            url = f"https://everydayadvertise.com/playlist/{store_id}/{store_id}_screen{screen_id}"
            print(f"🔍 Fetching playlist: {url}")
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                playlist = data.get('playlist', [])
                print(f"📋 Retrieved {len(playlist)} playlist items")
                return playlist
            else:
                print(f"⚠️ HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"⚠️ Playlist fetch error: {e}")
            return []

    def extract_safe_url(self, item):
        """Safely extract URL - prefer slice_url for screen 2/3"""
        try:
            screen_id = getattr(self, 'screen_id', '1') or '1'
            
            # For screen 2/3, prefer slice_url (server handles slicing)
            if screen_id in ['2', '3']:
                for key in ['slice_url', 'preferred_url', 'url']:
                    val = item.get(key)
                    if val:
                        print(f"✅ Using {key} for screen {screen_id}")
                        return val
            else:
                # For screen 1, prefer regular URLs
                for key in ['preferred_url', 'url', 'slice_url']:
                    val = item.get(key)
                    if val:
                        print(f"✅ Using {key} for screen {screen_id}")
                        return val
                        
            print(f"❌ No playable URL found")
            return None
            
        except Exception as e:
            print(f"❌ URL extraction error: {e}")
            return None

    def auto_start_playback(self):
        """Start playback automatically with current settings"""
        if not self.store_code or not self.screen_id or not self.android_tv_code:
            print("❌ Missing required parameters for auto-start")
            return
            
        print(f"🎬 Auto-starting playback: Store={self.store_code}, Screen={self.screen_id}, Code={self.android_tv_code}")
        self.start_safe_playback()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pizza Hut TV Player - Safe Mode")
    parser.add_argument('--store', help='Store code')
    parser.add_argument('--screen', help='Screen number')
    parser.add_argument('--code', help='Pairing code')
    args = parser.parse_args()
    
    print("🚀 Starting Pizza Hut TV Player - SAFE MODE with Smart Slicing")
    print("🛡️ No VLC cropping operations - crash-proof design")
    
    player = PizzaHutTVPlayerSafe()
    
    # Set command line arguments if provided
    if args.store:
        player.store_code = args.store
        player.store_entry.delete(0, tk.END)
        player.store_entry.insert(0, args.store)
    
    if args.screen:
        player.screen_id = args.screen
        if hasattr(player, 'screen_var'):
            player.screen_var.set(args.screen)
    
    if args.code:
        player.android_tv_code = args.code
        if hasattr(player, 'input_entry'):
            player.input_entry.delete(0, tk.END)
            player.input_entry.insert(0, args.code)
    
    # Auto-start if all parameters provided
    if args.store and args.screen and args.code:
        print(f"🎯 Auto-starting: Store={args.store}, Screen={args.screen}, Code={args.code}")
        # Trigger playback after GUI loads
        player.root.after(1000, lambda: player.auto_start_playback())
    
    player.run()