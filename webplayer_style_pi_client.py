#!/usr/bin/env python3
"""
🍕 EA TV Pi Client - Exact Webplayer Interface
Matches webplayer UI exactly: Android TV code → Store code → Screen selection
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import webbrowser
import subprocess
import sys
import threading
import time

class WebplayerStyleEATVClient:
    def __init__(self):
        try:
            # Check if we have display access
            import os
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
                print("🖥️ Setting DISPLAY to :0 for Pi screen")
            
            self.root = tk.Tk()
            self.root.title("🍕 EA TV - Web Player")
            self.root.geometry("600x500")
            self.root.configure(bg='#0d0d0d')
            
            # State variables
            self.android_tv_code = ""
            self.store_code = ""
            self.screen_id = ""
            self.current_step = 1
            
            # Smooth transition system
            self.playback_active = False
            self.playlist_refresh_timer = None
            self.current_playlist = []
            self.current_item_index = 0
            self.preloaded_items = {}  # Cache for smooth transitions
            self.vlc_playlist_file = None
            self.vlc_process = None
            self.current_effect = "1"  # Default to fade
            
            # VLC Effect mapping for transitions
            self.vlc_effects = {
                "1": {"name": "fade", "filter": "--video-filter=blend", "duration": "0.7"},
                "2": {"name": "slide-l", "filter": "--video-filter=transform{type=90}", "duration": "0.5"}, 
                "3": {"name": "slide-r", "filter": "--video-filter=transform{type=270}", "duration": "0.5"},
                "4": {"name": "zoom-in", "filter": "--video-filter=scale{factor=1.2}", "duration": "0.8"},
                "5": {"name": "zoom-out", "filter": "--video-filter=scale{factor=0.8}", "duration": "0.8"},
                "6": {"name": "cut", "filter": "", "duration": "0.1"}
            }
            
            # Make window closeable easily
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Bind ESC key to close
            self.root.bind('<Escape>', lambda e: self.on_closing())
            self.root.bind('<q>', lambda e: self.on_closing())
            self.root.bind('<Q>', lambda e: self.on_closing())
            
            self.setup_gui()
            self.running = True
            
        except Exception as e:
            print(f"❌ Failed to initialize GUI: {e}")
            print("💡 Make sure you're running this on the Pi's local display, not via SSH")
            print("💡 Try: DISPLAY=:0 python3 webplayer_style_pi_client.py")
            raise
        
    def setup_gui(self):
        """Setup the webplayer-style GUI."""
        
        # Main container (matches webplayer panel style)
        self.panel = tk.Frame(
            self.root, 
            bg='#0d0d0d', 
            padx=28, 
            pady=28
        )
        self.panel.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Title
        self.title_label = tk.Label(
            self.panel,
            text="Enter your Android TV pairing code",
            font=("Arial", 20, "bold"),
            fg="#f4f4f4",
            bg="#0d0d0d"
        )
        self.title_label.pack(pady=(0, 12))
        
        # Subtitle
        self.subtitle_label = tk.Label(
            self.panel,
            text="Type the 4-digit code from your TV app or profile page.",
            font=("Arial", 12),
            fg="#bbbbbb",
            bg="#0d0d0d"
        )
        self.subtitle_label.pack(pady=(0, 16))
        
        # Input label
        self.input_label = tk.Label(
            self.panel,
            text="4-digit code",
            font=("Arial", 11),
            fg="#cccccc",
            bg="#0d0d0d"
        )
        self.input_label.pack(anchor='w', pady=(12, 8))
        
        # Input field (matches webplayer style)
        self.input_field = tk.Entry(
            self.panel,
            font=("Arial", 14, "bold"),
            bg="#000000",
            fg="#ffffff",
            insertbackground="#ffffff",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightcolor="#c8102e",
            highlightbackground="#333333",
            justify='center',
            width=20
        )
        self.input_field.pack(pady=(0, 18), ipady=12)
        self.input_field.insert(0, "1126")  # Default Android TV code
        self.input_field.bind('<Return>', lambda e: self.next_step())
        
        # Main button
        self.main_button = tk.Button(
            self.panel,
            text="Link Code",
            font=("Arial", 12, "bold"),
            bg="#c8102e",
            fg="#ffffff",
            activebackground="#ac0e29",
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            command=self.next_step,
            width=25,
            pady=12
        )
        self.main_button.pack(pady=(0, 14))
        
        # Note
        self.note_label = tk.Label(
            self.panel,
            text="Next you'll enter the store code and pick a screen.",
            font=("Arial", 10),
            fg="#9a9a9a",
            bg="#0d0d0d"
        )
        self.note_label.pack(pady=(14, 20))
        
        # Control buttons at bottom
        button_frame = tk.Frame(self.panel, bg="#0d0d0d")
        button_frame.pack(side='bottom', fill='x', pady=(20, 0))
        
        # Back button (initially hidden)
        self.back_button = tk.Button(
            button_frame,
            text="← Back",
            font=("Arial", 10),
            bg="#666666",
            fg="#ffffff",
            command=self.previous_step,
            width=12
        )
        
        # Close button
        close_button = tk.Button(
            button_frame,
            text="❌ Close",
            font=("Arial", 10),
            bg="#666666",
            fg="#ffffff",
            command=self.on_closing,
            width=12
        )
        close_button.pack(side='right', padx=(10, 0))
        
        # Focus on input
        self.root.after(100, lambda: self.input_field.focus_set())
        
    def next_step(self):
        """Move to next step in webplayer flow."""
        
        if self.current_step == 1:
            # Step 1: Android TV Code
            code = self.input_field.get().strip()
            if not code:
                messagebox.showerror("Error", "Please enter a 4-digit code!")
                return
            if len(code) != 4 or not code.isdigit():
                messagebox.showerror("Error", "Please enter exactly 4 digits!")
                return
                
            self.android_tv_code = code
            self.show_store_step()
            
        elif self.current_step == 2:
            # Step 2: Store Code
            store = self.input_field.get().strip()
            if not store:
                messagebox.showerror("Error", "Please enter a store code!")
                return
                
            self.store_code = store
            self.show_screen_step()
            
        elif self.current_step == 3:
            # Step 3: Start playback
            self.start_playback()
    
    def previous_step(self):
        """Go back to previous step."""
        if self.current_step == 2:
            self.show_android_tv_step()
        elif self.current_step == 3:
            self.show_store_step()
    
    def show_android_tv_step(self):
        """Show Android TV code entry step."""
        self.current_step = 1
        self.title_label.config(text="Enter your Android TV pairing code")
        self.subtitle_label.config(text="Type the 4-digit code from your TV app or profile page.")
        self.input_label.config(text="4-digit code")
        self.input_field.delete(0, tk.END)
        self.input_field.insert(0, self.android_tv_code if self.android_tv_code else "4682")
        self.main_button.config(text="Link Code")
        self.note_label.config(text="Next you'll enter the store code and pick a screen.")
        self.back_button.pack_forget()
        self.input_field.focus_set()
    
    def show_store_step(self):
        """Show store code entry step."""
        self.current_step = 2
        self.title_label.config(text="Enter Store Code")
        self.subtitle_label.config(text="Enter your store ID or store link.")
        self.input_label.config(text="Store Code")
        self.input_field.delete(0, tk.END)
        self.input_field.insert(0, self.store_code if self.store_code else "1000")
        self.main_button.config(text="Continue")
        self.note_label.config(text="Next you'll select which screen to display.")
        self.back_button.pack(side='left')
        self.input_field.focus_set()
    
    def show_screen_step(self):
        """Show screen selection step."""
        self.current_step = 3
        
        # Update labels
        self.title_label.config(text="Select Screen")
        self.subtitle_label.config(text=f"Store: {self.store_code} | Android TV Code: {self.android_tv_code}")
        self.input_label.config(text="Choose your screen:")
        
        # Hide input field and show screen selection
        self.input_field.pack_forget()
        
        # Screen selection frame
        if hasattr(self, 'screen_frame'):
            self.screen_frame.destroy()
            
        self.screen_frame = tk.Frame(self.panel, bg="#0d0d0d")
        self.screen_frame.pack(pady=(0, 18))
        
        self.screen_var = tk.StringVar(value="1")
        
        screens = [
            ("Screen 1 (Left)", "1"),
            ("Screen 2 (Center)", "2"),
            ("Screen 3 (Right)", "3")
        ]
        
        for text, value in screens:
            rb = tk.Radiobutton(
                self.screen_frame,
                text=text,
                variable=self.screen_var,
                value=value,
                font=("Arial", 12),
                fg="#ffffff",
                bg="#0d0d0d",
                selectcolor="#000000",
                activebackground="#0d0d0d",
                activeforeground="#ffffff"
            )
            rb.pack(anchor='w', pady=4)
        
        # Effect selection frame
        effect_frame = tk.Frame(self.panel, bg="#0d0d0d")
        effect_frame.pack(pady=(15, 18))
        
        effect_label = tk.Label(
            effect_frame,
            text="Transition Effects:",
            font=("Arial", 11, "bold"),
            fg="#ffffff",
            bg="#0d0d0d"
        )
        effect_label.pack(anchor="w", pady=(0, 8))
        
        self.effect_var = tk.StringVar(value="1")
        
        effects = [
            ("1. Fade (Smooth)", "1", "fade"),
            ("2. Slide Left", "2", "slide-l"),
            ("3. Slide Right", "3", "slide-r"), 
            ("4. Zoom In", "4", "zoom-in"),
            ("5. Zoom Out", "5", "zoom-out"),
            ("6. Cut (Instant)", "6", "cut")
        ]
        
        # Create effect buttons in 2 columns
        effect_buttons_frame = tk.Frame(effect_frame, bg="#0d0d0d")
        effect_buttons_frame.pack()
        
        for i, (text, value, effect_name) in enumerate(effects):
            col = i % 2
            row = i // 2
            
            rb = tk.Radiobutton(
                effect_buttons_frame,
                text=text,
                variable=self.effect_var,
                value=value,
                font=("Arial", 10),
                bg="#0d0d0d",
                fg="#ffffff",
                selectcolor="#000000",
                activebackground="#0d0d0d",
                activeforeground="#ffffff",
                width=15,
                anchor="w"
            )
            rb.grid(row=row, column=col, sticky="w", padx=5, pady=2)
        
        self.main_button.config(text="🚀 Start EA TV with Effects")
        self.note_label.config(text="Choose effect & screen - synced across all displays!")
        
        # Update back button visibility
        self.back_button.pack(side='left')
    
    def start_playback(self):
        """Start EA TV playback with selected settings."""
        self.screen_id = self.screen_var.get()
        
        # Capture selected effect
        if hasattr(self, 'effect_var'):
            self.current_effect = self.effect_var.get()
            effect_name = self.vlc_effects.get(self.current_effect, {}).get("name", "fade")
            print(f"🎨 Selected effect: {effect_name} (#{self.current_effect})")
            
            # Sync effect choice to server for all screens
            self.sync_effect_to_all_screens()
        
        # Show loading message
        messagebox.showinfo("Starting EA TV", f"Loading videos for Store {self.store_code}, Screen {self.screen_id} with {effect_name} effects...")
        
        # Start real video playback
        self.start_real_playback()
    
    def start_real_playback(self):
        """Start real playlist playback using VLC - matches webplayer functionality."""
        try:
            # Close the setup window
            self.root.withdraw()
            
            # Create control window
            self.create_playlist_control_window()
            
            # Start playlist playback system
            self.start_playlist_playback()
            
        except Exception as e:
            messagebox.showerror("Playback Error", f"Failed to start video playback: {e}")
            self.root.deiconify()
    

    
    def start_playlist_playback(self):
        """Start playlist-based playback system - matches webplayer functionality."""
        # Initialize playlist state
        self.current_playlist = []
        self.current_item_index = 0
        self.vlc_process = None
        self.playback_active = True
        self.playlist_refresh_timer = None
        
        # Start the playlist loop
        self.playlist_loop()
    
    def get_full_playlist(self):
        """Get the complete playlist from server - matches webplayer."""
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
    
    def playlist_loop(self):
        """Main playlist loop - cycles through all items like webplayer."""
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
            duration = int(current_item.get('duration', 10))  # Default 10 seconds
            
            print(f"🎬 Playing item {self.current_item_index + 1}/{len(self.current_playlist)} for {duration}s")
            
            # Get the video URL for this item
            video_url = self.extract_video_url_from_item(current_item)
            
            if video_url:
                # Launch VLC for this item
                self.launch_vlc_for_item(video_url, duration)
                
                # Schedule next item
                self.current_item_index += 1
                if self.current_item_index >= len(self.current_playlist):
                    self.current_item_index = 0  # Loop back to start
                
                # Schedule next item after duration
                self.playlist_refresh_timer = threading.Timer(duration, self.playlist_loop)
                self.playlist_refresh_timer.start()
            else:
                print("❌ No video URL for current item, skipping...")
                self.current_item_index += 1
                # Try next item quickly
                self.playlist_refresh_timer = threading.Timer(2.0, self.playlist_loop)
                self.playlist_refresh_timer.start()
                
        except Exception as e:
            print(f"❌ Error in playlist loop: {e}")
            # Retry in 5 seconds
            self.playlist_refresh_timer = threading.Timer(5.0, self.playlist_loop)
            self.playlist_refresh_timer.start()
    
    def extract_video_url_from_item(self, item):
        """Extract video URL from playlist item - matches webplayer priority."""
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
                print(f"❌ No URL found in item: {item.keys()}")
                return None
        except Exception as e:
            print(f"❌ Error extracting URL: {e}")
            return None
    
    def launch_vlc_for_item(self, video_url, duration):
        """Launch VLC for a specific playlist item with timeout."""
        try:
            # Kill any existing VLC process
            if self.vlc_process:
                try:
                    self.vlc_process.terminate()
                    subprocess.run(['pkill', 'vlc'], check=False)
                except:
                    pass
            
            # Set display for VLC
            import os
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
            
            # VLC command for timed playback (no loop for individual items)
            vlc_cmd = [
                'vlc',
                video_url,
                '--fullscreen',
                '--no-video-title-show',
                '--no-osd',
                '--quiet',
                '--intf', 'dummy',
                '--play-and-exit',  # Exit after playing
                f'--stop-time={duration}'  # Stop after duration
            ]
            
            # Add effect filters if enabled
            if hasattr(self, 'current_effect') and self.current_effect in self.vlc_effects:
                effect_config = self.vlc_effects[self.current_effect]
                if effect_config.get("filter"):
                    # Add effect filter to video chain
                    vlc_cmd.extend(effect_config["filter"].split())
                    print(f"🎨 Effect applied: {effect_config['name']}")
            
            # Add professional video settings
            vlc_cmd.extend([
                '--avcodec-hw', 'any',       # Hardware acceleration
                '--file-caching', '2000',    # Smooth caching
                '--network-caching', '3000'  # Network buffer
            ])
            
            print(f"🎬 Starting VLC for {duration}s: {video_url[:80]}...")
            
            # Start VLC process
            self.vlc_process = subprocess.Popen(vlc_cmd, env=os.environ.copy())
            
        except Exception as e:
            print(f"❌ Failed to start VLC: {e}")
            print(f"💡 Make sure VLC is installed: sudo apt-get install vlc")
            print(f"💡 Make sure display is available: echo $DISPLAY")
            self.vlc_process = None
    
    def create_playlist_control_window(self):
        """Create a control window for playlist playback."""
        control_window = tk.Toplevel()
        control_window.title("EA TV Playlist Control")
        control_window.geometry("400x200")
        control_window.configure(bg='#0d0d0d')
        control_window.attributes('-topmost', True)
        
        # Position in top-right corner
        control_window.geometry("+{}+10".format(control_window.winfo_screenwidth() - 420))
        
        # Status label
        self.status_label = tk.Label(
            control_window,
            text=f"🍕 EA TV Playlist\nStore: {self.store_code} | Screen: {self.screen_id}\nInitializing...",
            font=("Arial", 10, "bold"),
            fg="white",
            bg="#0d0d0d"
        )
        self.status_label.pack(pady=10)
        
        button_frame = tk.Frame(control_window, bg="#0d0d0d")
        button_frame.pack(pady=10)
        
        # Stop button
        tk.Button(
            button_frame,
            text="⏹ Stop Playlist",
            font=("Arial", 10),
            bg="#c8102e",
            fg="white",
            command=lambda: self.stop_playlist_playback(control_window),
            width=12
        ).pack(side='left', padx=5)
        
        # Setup button
        tk.Button(
            button_frame,
            text="⚙ Setup",
            font=("Arial", 10),
            bg="#666666",
            fg="white",
            command=lambda: self.show_setup(control_window),
            width=8
        ).pack(side='left', padx=5)
        
        # Update status periodically
        def update_status():
            if self.playback_active and hasattr(self, 'current_playlist'):
                total_items = len(self.current_playlist) if self.current_playlist else 0
                current_pos = self.current_item_index + 1 if total_items > 0 else 0
                status_text = f"🍕 EA TV Playlist\nStore: {self.store_code} | Screen: {self.screen_id}\nItem: {current_pos}/{total_items}"
                self.status_label.config(text=status_text)
                control_window.after(2000, update_status)
        
        update_status()
        return control_window
    
    def stop_playlist_playback(self, control_window):
        """Stop playlist playback."""
        self.playback_active = False
        
        # Stop timers
        if self.playlist_refresh_timer:
            self.playlist_refresh_timer.cancel()
        
        # Kill VLC
        try:
            if self.vlc_process:
                self.vlc_process.terminate()
            subprocess.run(['pkill', 'vlc'], check=False)
        except:
            pass
        
        try:
            control_window.destroy()
        except:
            pass
        
        self.root.deiconify()
    
    def show_setup(self, control_window):
        """Show setup window again."""
        self.playback_active = False
        
        # Stop timers
        if self.playlist_refresh_timer:
            self.playlist_refresh_timer.cancel()
        
        try:
            control_window.destroy()
        except:
            pass
        
        subprocess.run(['pkill', 'vlc'], check=False)
        self.root.deiconify()
    
    def on_closing(self):
        """Handle window closing."""
        self.running = False
        self.playback_active = False
        
        # Stop timers
        if hasattr(self, 'playlist_refresh_timer') and self.playlist_refresh_timer:
            self.playlist_refresh_timer.cancel()
        
        try:
            # Kill any running processes
            subprocess.run(['pkill', '-f', 'pizza_hut_tv'], check=False)
            subprocess.run(['pkill', '-f', 'phtv_pi'], check=False)
            subprocess.run(['pkill', 'vlc'], check=False)
        except:
            pass
        
        self.root.quit()
        self.root.destroy()
        sys.exit(0)
    
    def sync_effect_to_all_screens(self):
        """Sync the selected effect to all screens (webplayer & Pi clients)."""
        try:
            effect_name = self.vlc_effects.get(self.current_effect, {}).get("name", "fade")
            
            # Send effect update to server API
            sync_data = {
                "store_code": self.store_code,
                "effect_id": self.current_effect,
                "effect_name": effect_name,
                "timestamp": time.time()
            }
            
            # Try to sync with server
            response = requests.post(
                f"https://pizza-hut-tv.fly.dev/api/sync-effect",
                json=sync_data,
                timeout=3
            )
            
            if response.status_code == 200:
                print(f"✅ Effect synced to all screens: {effect_name}")
            else:
                print(f"⚠️ Effect sync failed: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Effect sync error (continuing): {e}")
    
    def run(self):
        """Run the application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()

if __name__ == "__main__":
    try:
        app = WebplayerStyleEATVClient()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)