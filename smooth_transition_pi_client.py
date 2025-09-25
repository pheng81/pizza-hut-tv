#!/usr/bin/env python3
"""
🍕 EA TV Pi Client - Smooth Transitions & Effects (No Black Screens)
Professional playlist system with seamless transitions like webplayer
Supports transition effects: fade, slide-l, slide-r, zoom-in, zoom-out, cut
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import subprocess
import sys
import threading
import time
import os
import tempfile
import json
import random
import json

class SmoothTransitionEATVClient:
    def __init__(self):
        try:
            # Check if we have display access
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
                print("🖥️ Setting DISPLAY to :0 for Pi screen")
            
            self.root = tk.Tk()
            self.root.title("🍕 EA TV - Smooth Transitions")
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
            print("💡 Make sure you're running this on the Pi's local display")
            raise

    def setup_gui(self):
        """Setup the webplayer-style GUI."""
        
        # Main container
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
            text="Link Android TV",
            font=("Arial", 20, "bold"),
            fg="#ffffff",
            bg="#0d0d0d"
        )
        self.title_label.pack(pady=(0, 8))
        
        # Subtitle
        self.subtitle_label = tk.Label(
            self.panel,
            text="Enter the 4-digit code from your Android TV.",
            font=("Arial", 12),
            fg="#9a9a9a",
            bg="#0d0d0d"
        )
        self.subtitle_label.pack(pady=(0, 32))
        
        # Input section
        self.input_label = tk.Label(
            self.panel,
            text="4-digit code",
            font=("Arial", 11, "bold"),
            fg="#ffffff",
            bg="#0d0d0d"
        )
        self.input_label.pack(anchor="w", pady=(0, 8))
        
        self.input_field = tk.Entry(
            self.panel,
            font=("Arial", 14),
            bg="#1a1a1a",
            fg="#ffffff",
            insertbackground="#ffffff",
            bd=1,
            relief="solid",
            width=25
        )
        self.input_field.pack(pady=(0, 18))
        
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
        close_button.pack(side='right')
        
        # Initialize with default values and focus
        self.show_link_step()
    
    def next_step(self):
        """Move to next step in the process."""
        if self.current_step == 1:
            # Step 1: Link code
            self.android_tv_code = self.input_field.get().strip()
            if not self.android_tv_code:
                messagebox.showerror("Error", "Please enter the Android TV code")
                return
            
            self.show_store_step()
            
        elif self.current_step == 2:
            # Step 2: Store code
            self.store_code = self.input_field.get().strip()
            if not self.store_code:
                messagebox.showerror("Error", "Please enter the store code")
                return
            
            self.show_screen_step()
            
        elif self.current_step == 3:
            # Step 3: Start smooth playback
            self.start_smooth_playback()
    
    def previous_step(self):
        """Go back to previous step."""
        if self.current_step == 2:
            self.show_link_step()
        elif self.current_step == 3:
            self.show_store_step()
    
    def show_link_step(self):
        """Show Android TV code entry step."""
        self.current_step = 1
        self.title_label.config(text="Link Android TV")
        self.subtitle_label.config(text="Enter the 4-digit code from your Android TV.")
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
        self.title_label.config(text="Select Screen & Effects")
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
                bg="#0d0d0d",
                fg="#ffffff",
                selectcolor="#1a1a1a",
                activebackground="#0d0d0d",
                activeforeground="#ffffff"
            )
            rb.pack(anchor="w", pady=2)
        
        # Effect selection frame
        effect_frame = tk.Frame(self.panel, bg="#0d0d0d")
        effect_frame.pack(pady=(10, 18))
        
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
                selectcolor="#1a1a1a",
                activebackground="#0d0d0d",
                activeforeground="#ffffff",
                width=15,
                anchor="w"
            )
            rb.grid(row=row, column=col, sticky="w", padx=5, pady=2)
        
        self.main_button.config(text="🎬 Start Smooth Playback")
        self.note_label.config(text="Professional transitions with effects - synced across all screens.")
        self.back_button.pack(side='left')

    def start_smooth_playback(self):
        """Start smooth playlist playback with seamless transitions."""
        self.screen_id = self.screen_var.get()
        
        # Capture selected effect
        if hasattr(self, 'effect_var'):
            self.current_effect = self.effect_var.get()
            effect_name = self.vlc_effects.get(self.current_effect, {}).get("name", "fade")
            print(f"🎨 Selected effect: {effect_name} (#{self.current_effect})")
            
            # Sync effect choice to server for all screens
            self.sync_effect_to_all_screens()
        
        # Show loading message
        messagebox.showinfo("Starting EA TV", f"Loading smooth playlist for Store {self.store_code}, Screen {self.screen_id} with {effect_name} transitions...")
        
        # Start smooth playback system
        self.start_professional_playback()
    
    def start_professional_playback(self):
        """Start professional playlist playback with smooth transitions."""
        try:
            # Close the setup window
            self.root.withdraw()
            
            # Create control window
            self.create_smooth_control_window()
            
            # Start smooth playlist system
            self.initialize_smooth_playlist()
            
        except Exception as e:
            messagebox.showerror("Playback Error", f"Failed to start smooth playback: {e}")
            self.root.deiconify()
    
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
                    
                    print(f"🔍 Fetching smooth playlist: {url}")
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        playlist_data = response.json()
                        playlist_items = playlist_data.get('playlist', [])
                        print(f"📋 Retrieved {len(playlist_items)} items for smooth playback")
                        
                        if playlist_items:
                            return playlist_items
                    
                except Exception as e:
                    print(f"❌ Failed to fetch from {server_url}: {e}")
                    continue
            
            return []
            
        except Exception as e:
            print(f"❌ Error getting playlist: {e}")
            return []

    def create_vlc_playlist_file(self, playlist_items):
        """Create VLC playlist file for smooth continuous playback."""
        try:
            # Create temporary playlist file
            if self.vlc_playlist_file:
                try:
                    os.unlink(self.vlc_playlist_file)
                except:
                    pass
            
            fd, self.vlc_playlist_file = tempfile.mkstemp(suffix='.m3u', text=True)
            
            valid_items = 0
            with os.fdopen(fd, 'w') as f:
                f.write("#EXTM3U\n")
                
                for i, item in enumerate(playlist_items):
                    duration = int(item.get('duration', 10))
                    media_type = item.get('media_type', 'unknown')
                    
                    # Get video URL with priority order
                    media_url = None
                    if 'preferred_url' in item:
                        media_url = item['preferred_url']
                    elif 'slice_url' in item:
                        media_url = item['slice_url']
                    elif 'url' in item:
                        media_url = item['url']
                    
                    if media_url:
                        f.write(f"#EXTINF:{duration},{media_type}\n")
                        f.write(f"{media_url}\n")
                        valid_items += 1
                        print(f"   Added to playlist: {media_type} ({duration}s)")
            
            print(f"✅ Created smooth VLC playlist with {valid_items} items: {self.vlc_playlist_file}")
            return valid_items > 0
            
        except Exception as e:
            print(f"❌ Error creating VLC playlist: {e}")
            return False

    def initialize_smooth_playlist(self):
        """Initialize smooth playlist playback system."""
        self.playback_active = True
        self.smooth_playlist_loop()
    
    def smooth_playlist_loop(self):
        """Main smooth playlist loop - no black screens, perfect sync."""
        if not self.playback_active:
            return
        
        try:
            # Get fresh playlist
            self.current_playlist = self.get_full_playlist()
            
            if not self.current_playlist:
                print("⏰ No playlist items, retrying in 10 seconds...")
                self.playlist_refresh_timer = threading.Timer(10.0, self.smooth_playlist_loop)
                self.playlist_refresh_timer.start()
                return
            
            print(f"🎬 Starting smooth playlist with {len(self.current_playlist)} items")
            
            # Create VLC playlist for continuous playback
            if self.create_vlc_playlist_file(self.current_playlist):
                self.launch_smooth_vlc_playback()
                
                # Calculate total playlist duration
                total_duration = sum(int(item.get('duration', 10)) for item in self.current_playlist)
                print(f"⏰ Full playlist cycle: {total_duration}s")
                
                # Schedule seamless refresh - restart VLC with fresh playlist before current ends
                # This ensures continuous playback with updated content
                refresh_delay = max(total_duration - 3, 20)  # Refresh 3s before end, min 20s
                print(f"⏰ Seamless refresh scheduled in {refresh_delay}s")
                
                self.playlist_refresh_timer = threading.Timer(refresh_delay, self.smooth_playlist_loop)
                self.playlist_refresh_timer.start()
            else:
                print("❌ Failed to create playlist, retrying...")
                self.playlist_refresh_timer = threading.Timer(5.0, self.smooth_playlist_loop)
                self.playlist_refresh_timer.start()
                
        except Exception as e:
            print(f"❌ Error in smooth playlist loop: {e}")
            self.playlist_refresh_timer = threading.Timer(10.0, self.smooth_playlist_loop)
            self.playlist_refresh_timer.start()
    
    def launch_smooth_vlc_playback(self):
        """Launch VLC with smooth continuous playlist playback - professional transitions."""
        try:
            # Gentle VLC transition - minimize black screen time
            if self.vlc_process:
                try:
                    # Send quit signal first for graceful exit
                    self.vlc_process.terminate()
                    time.sleep(0.5)  # Brief transition pause
                    
                    # Force kill if still running
                    subprocess.run(['pkill', 'vlc'], check=False)
                    time.sleep(0.2)  # Minimal cleanup pause
                except:
                    pass
            
            # Set display
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
            
            # Professional VLC command for enterprise-grade smooth playback with effects
            vlc_cmd = [
                'vlc',
                self.vlc_playlist_file,
                '--fullscreen',
                '--no-video-title-show',
                '--no-osd',
                '--quiet',
                '--intf', 'dummy',
                '--loop',  # Loop the entire playlist smoothly
                '--no-random',
                '--playlist-autostart',
                '--video-filter', 'deinterlace',  # Professional video smoothing
                '--deinterlace-mode', 'linear',   # Best quality transitions
                '--avcodec-hw', 'any',            # Hardware acceleration for smooth playback
                '--file-caching', '2000',         # Larger cache for smoother transitions
                '--network-caching', '3000',      # Network buffer for streaming content
                '--cr-average', '1000',           # Clock reference for sync
                '--clock-jitter', '0'             # Minimize timing jitter
            ]
            
            # Add effect filters if enabled
            if hasattr(self, 'current_effect') and self.current_effect in self.vlc_effects:
                effect_config = self.vlc_effects[self.current_effect]
                if effect_config.get("filter"):
                    # Add effect filter to video chain
                    vlc_cmd.extend(effect_config["filter"].split())
                    print(f"🎨 Effect applied: {effect_config['name']}")
            
            # Add transition duration
            vlc_cmd.extend([
                '--video-filter-event', f'duration={self.vlc_effects.get(self.current_effect, {}).get("duration", "0.7")}'
            ])
            
            print(f"🎬 Launching professional smooth VLC playback...")
            
            # Start VLC process with optimized environment
            vlc_env = os.environ.copy()
            vlc_env['VLC_VERBOSE'] = '0'  # Suppress verbose output
            
            self.vlc_process = subprocess.Popen(vlc_cmd, env=vlc_env)
            print(f"✅ VLC started with PID: {self.vlc_process.pid}")
            
        except Exception as e:
            print(f"❌ Failed to start smooth VLC: {e}")
            self.vlc_process = None

    def create_smooth_control_window(self):
        """Create control window for smooth playback."""
        control_window = tk.Toplevel()
        control_window.title("EA TV - Smooth Playback")
        control_window.geometry("450x200")
        control_window.configure(bg='#0d0d0d')
        control_window.attributes('-topmost', True)
        
        # Position in top-right corner
        control_window.geometry("+{}+10".format(control_window.winfo_screenwidth() - 470))
        
        # Status label
        self.status_label = tk.Label(
            control_window,
            text=f"🍕 EA TV - Professional Smooth Transitions\nStore: {self.store_code} | Screen: {self.screen_id}\nNo Black Screens • Seamless Playback",
            font=("Arial", 10, "bold"),
            fg="white",
            bg="#0d0d0d"
        )
        self.status_label.pack(pady=15)
        
        button_frame = tk.Frame(control_window, bg="#0d0d0d")
        button_frame.pack(pady=10)
        
        # Stop button
        tk.Button(
            button_frame,
            text="⏹ Stop Smooth Playback",
            font=("Arial", 10),
            bg="#c8102e",
            fg="white",
            command=lambda: self.stop_smooth_playback(control_window),
            width=18
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
        
        return control_window

    def stop_smooth_playback(self, control_window):
        """Stop smooth playback."""
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
        
        # Clean up playlist file
        if self.vlc_playlist_file:
            try:
                os.unlink(self.vlc_playlist_file)
            except:
                pass
        
        try:
            control_window.destroy()
        except:
            pass
        
        self.root.deiconify()
    
    def show_setup(self, control_window):
        """Show setup window again."""
        self.stop_smooth_playback(control_window)
    
    def on_closing(self):
        """Handle window closing."""
        self.running = False
        self.playback_active = False
        
        # Stop timers
        if hasattr(self, 'playlist_refresh_timer') and self.playlist_refresh_timer:
            self.playlist_refresh_timer.cancel()
        
        # Clean up
        if self.vlc_playlist_file:
            try:
                os.unlink(self.vlc_playlist_file)
            except:
                pass
        
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
    
    def run(self):
        """Run the application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()

if __name__ == "__main__":
    try:
        app = SmoothTransitionEATVClient()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)