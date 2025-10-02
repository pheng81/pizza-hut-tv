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
import traceback
import argparse
import json

# ------------------------------------------------------------
# Headless args parsing (added for Option B pure VLC slicing)
# ------------------------------------------------------------

def parse_headless_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--headless', action='store_true', default=False)
    parser.add_argument('--store', dest='store_code', default=None)
    parser.add_argument('--screen', dest='screen_id', default=None)
    parser.add_argument('--code', dest='android_code', default=None)
    parser.add_argument('--effect', dest='effect', default=None)
    try:
        args, _ = parser.parse_known_args()
        return args
    except SystemExit:
        return argparse.Namespace(headless=False, store_code=None, screen_id=None, android_code=None, effect=None)

_HEADLESS_ARGS = parse_headless_args()

# Try to import python-vlc for smoother, single-process playlist playback
try:
    import vlc  # python-vlc binding
    _VLC_PY_AVAILABLE = True
except Exception:
    _VLC_PY_AVAILABLE = False

class WebplayerStyleEATVClient:
    def __init__(self):
        try:
            # Check if we have display access
            import os
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
                print("🖥️ Setting DISPLAY to :0 for Pi screen")
            
            self.root = None
            if not _HEADLESS_ARGS.headless:
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
            
            # Seamless playback enhancements
            self.last_playlist_signature = None  # Signature of last launched resolved playlist
            self.resolved_playlist_cache = []    # Last resolved playable items (url,duration,title)
            self.empty_playlist_retry_seconds = 15  # Faster retry when schedule gap
            self.use_embedded_vlc = False  # Disable embedded VLC for better crop compatibility
            self.embedded_thread = None
            self.embedded_stop_event = threading.Event()
            self.current_embedded_index = 0
            
            # VLC Smooth transition settings for each effect
            self.vlc_effects = {
                "1": {"name": "fade", "crossfade": "1.0", "gap": "0.5"},      # Smooth fade
                "2": {"name": "slide-l", "crossfade": "0.8", "gap": "0.3"},   # Quick slide left
                "3": {"name": "slide-r", "crossfade": "0.8", "gap": "0.3"},   # Quick slide right
                "4": {"name": "zoom-in", "crossfade": "1.2", "gap": "0.4"},   # Slower zoom in
                "5": {"name": "zoom-out", "crossfade": "1.2", "gap": "0.4"},  # Slower zoom out
                "6": {"name": "cut", "crossfade": "0.1", "gap": "0.0"}        # Instant cut
            }
            
            # Make window closeable easily
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Bind ESC key to close
            self.root.bind('<Escape>', lambda e: self.on_closing())
            self.root.bind('<q>', lambda e: self.on_closing())
            self.root.bind('<Q>', lambda e: self.on_closing())
            
            self.running = True
            if not _HEADLESS_ARGS.headless:
                self.setup_gui()
            else:
                # Headless quick-start (Option B): require all params
                if _HEADLESS_ARGS.store_code and _HEADLESS_ARGS.android_code and _HEADLESS_ARGS.screen_id:
                    self.android_tv_code = _HEADLESS_ARGS.android_code
                    self.store_code = _HEADLESS_ARGS.store_code
                    # Accept either '2' or full id like 1000_screen2
                    if _HEADLESS_ARGS.screen_id.isdigit():
                        self.screen_id = _HEADLESS_ARGS.screen_id
                    else:
                        # Extract trailing digit
                        tail = _HEADLESS_ARGS.screen_id.split('screen')[-1]
                        self.screen_id = tail if tail.isdigit() else '1'
                    if _HEADLESS_ARGS.effect and _HEADLESS_ARGS.effect in self.vlc_effects:
                        self.current_effect = _HEADLESS_ARGS.effect
                    print(f"🔄 HEADLESS START store={self.store_code} screen={self.screen_id} code={self.android_tv_code}")
                    self.start_real_playback()
                else:
                    print("❌ Headless mode missing --store --screen --code. Exiting.")
                    self.running = False
                    return
            
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
        self.input_field.insert(0, "4682")  # Working Android TV code with content
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
            
            # Start playlist playback system (embedded if possible)
            if self.use_embedded_vlc:
                print("🎼 Using embedded python-vlc playback engine (reduced flicker)")
            else:
                print("🔁 Falling back to external VLC process (python-vlc not available)")
            self.start_playlist_playback()
            
        except Exception as e:
            messagebox.showerror("Playback Error", f"Failed to start video playback: {e}")
            self.root.deiconify()
    

    
    def start_playlist_playback(self):
        """Start playlist-based playback system - SMOOTH TRANSITIONS, NO FLICKERS."""
        # Initialize playlist state
        self.current_playlist = []
        self.current_item_index = 0
        self.vlc_process = None
        self.playback_active = True
        self.playlist_refresh_timer = None
        self.smooth_playlist_path = None
        
        # Start the SMOOTH playlist system
        self.smooth_playlist_loop()
    
    def smooth_playlist_loop(self):
        """SMOOTH playlist loop - NO FLICKERS, continuous playback like webplayer."""
        if not self.playback_active:
            return
        
        try:
            # Get fresh playlist from server
            raw_items = self.get_full_playlist()

            # Resolve playable items now (url, duration, title)
            resolved = []
            for i, item in enumerate(raw_items):
                url = self.extract_video_url_from_item(item)
                if not url:
                    continue
                if not url.startswith(('http://','https://')):
                    continue
                try:
                    duration = int(item.get('duration', 30) or 30)
                except:
                    duration = 30
                title = item.get('title') or item.get('name') or f'Item {i+1}'
                resolved.append({
                    'url': url,
                    'duration': duration,
                    'title': title
                })

            if not resolved:
                # Server returned empty - respect scheduling system, don't force repeat
                print("📅 No scheduled content available (outside schedule windows or no repeat items)")
                
                # Stop any current VLC playback since no content is scheduled
                if self.vlc_process:
                    try:
                        self.vlc_process.terminate()
                        subprocess.run(['pkill', 'vlc'], check=False)
                        print("🛑 Stopped VLC - no scheduled content")
                    except:
                        pass
                    self.vlc_process = None
                
                # Check again more frequently when no content to catch schedule changes
                print(f"⏰ No scheduled content, checking again in {self.empty_playlist_retry_seconds}s…")
                self.playlist_refresh_timer = threading.Timer(self.empty_playlist_retry_seconds, self.smooth_playlist_loop)
                self.playlist_refresh_timer.start()
                return

            # Build signature AFTER URL processing to detect real content changes
            # First, prepare URLs for actual playback (this may convert slice URLs to CDN URLs)
            has_slice_videos = any('slice-video' in item.get('url', '') for item in resolved)
            if has_slice_videos:
                # Convert slice URLs to full URLs for signature calculation
                resolved_for_signature = self.prepare_urls_for_vlc_crop(resolved)
            else:
                resolved_for_signature = resolved
            
            # Normalize URLs by removing cache-busting parameters for comparison
            def normalize_url(url):
                try:
                    import re
                    # Remove cache-busting parameters like cb=timestamp
                    return re.sub(r'[&?]cb=\d+', '', url)
                except:
                    return url
            
            signature_parts = [(normalize_url(r['url']), r['duration']) for r in resolved_for_signature]
            signature = hash(tuple(signature_parts))
            
            # Debug: Print what we're getting from server with timestamp
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"🔍 Server returned {len(resolved)} items at {current_time}:")
            for i, item in enumerate(resolved):
                print(f"   {i+1}. {item.get('title', 'Unknown')} - {item.get('url', 'No URL')[:80]}...")
            print(f"🔢 Playlist signature: {signature} (previous: {self.last_playlist_signature})")
            
            # Check if server is rotating content or always returning same items
            if len(resolved) > 1:
                print(f"📋 Multiple items detected - should be rotating between: {[item['title'] for item in resolved]}")
            else:
                print(f"📋 Single item schedule: {resolved[0].get('title', 'Unknown') if resolved else 'None'}")

            if signature == self.last_playlist_signature:
                # Same content from server - could be same schedule continuing or looping
                vlc_running = self.is_vlc_process_alive()
                
                if vlc_running:
                    # VLC still playing same schedule content
                    refresh_interval = 15  # Check every 15 seconds for schedule changes
                    print(f"🔁 Same schedule active (items={len(resolved)}). VLC running (PID: {self.vlc_process.pid if self.vlc_process else 'Unknown'}).")
                    print(f"   ⏰ Will check again in {refresh_interval}s for schedule changes from server")
                    self.playlist_refresh_timer = threading.Timer(refresh_interval, self.smooth_playlist_loop)
                    self.playlist_refresh_timer.start()
                    return
                else:
                    print(f"⚠️ VLC DIED! Same schedule still active, restarting playback...")
                    print(f"   💡 This shouldn't happen - VLC should loop with --loop flag")
                    # VLC died but schedule is the same - restart it
                    # This is NOT normal - VLC should loop forever with --loop flag

            # New playlist, changed playlist, or VLC restart needed – update playback engine
            if signature != self.last_playlist_signature:
                print(f"🎉 SCHEDULE CHANGED! Old signature: {self.last_playlist_signature}, New: {signature}")
                print(f"📋 New schedule has {len(resolved)} items. Updating playback engine…")
                # ALWAYS kill existing MPV/VLC when schedule changes
                # This ensures crop parameters are reset for new schedule
                if self.vlc_process:
                    try:
                        print("🛑 Killing existing MPV/VLC for schedule change (crop parameters need reset)...")
                        self.vlc_process.terminate()
                        subprocess.run(['pkill', 'vlc'], check=False)
                        subprocess.run(['pkill', 'mpv'], check=False)
                        time.sleep(0.5)  # Give it time to clean up
                    except Exception as e:
                        print(f"⚠️ Error killing MPV/VLC: {e}")
            else:
                print(f"🔄 Same schedule continuing ({len(resolved)} items) - restarting VLC playback...")

            if self.use_embedded_vlc:
                self.start_or_update_embedded_playlist(resolved)
            else:
                # Check for mixed media types before creating playlist
                self.resolved_playlist_cache = resolved  # Set cache first for detection methods
                has_mixed_media = self.playlist_has_mixed_media_types()
                has_slice_videos = self.playlist_has_slice_videos()
                
                # UNIFIED APPROACH: Always use VLC crop for slice videos (required for sync)
                # Handle mixed media crashes by using safer VLC parameters
                if has_slice_videos:
                    if has_mixed_media:
                        # MIXED MEDIA: Cannot use global crop (breaks images) or lua script (crop persists)
                        # TEMPORARY: Don't crop - images display correctly, slice videos show full width
                        print(f"🎭 Mixed media detected - NO CROP applied (temporary solution)")
                        print(f"   ✅ Images will display correctly (full screen)")
                        print(f"   ⚠️  Slice videos will show FULL WIDTH (5760px) - need server-side slicing fix")
                        print(f"   💡 Server slice URLs should return pre-cropped content for this screen")
                        
                        # Use original URLs (don't convert) - let server handle slicing
                        playlist_path = self.create_smooth_vlc_playlist(resolved, pre_resolved=True, apply_per_file_crop=False)
                        if not playlist_path:
                            print("❌ Failed to build playlist file; retrying in 20s")
                            self.playlist_refresh_timer = threading.Timer(20.0, self.smooth_playlist_loop)
                            self.playlist_refresh_timer.start()
                            return
                        self.launch_smooth_vlc_playlist(playlist_path, use_global_crop=False, use_lua_script=False)
                        self.smooth_playlist_path = playlist_path
                    else:
                        # PURE SLICE VIDEOS: Convert to CDN URLs and apply MPV crop
                        print(f"🎬 Pure slice videos - using CDN URLs + MPV CROP")
                        
                        # Use MPV crop on CDN URLs for reliable slicing
                        resolved_for_vlc_crop = self.prepare_urls_for_vlc_crop(resolved)
                        playlist_path = self.create_smooth_vlc_playlist(resolved_for_vlc_crop, pre_resolved=True, apply_per_file_crop=False)
                        
                        if not playlist_path:
                            print("❌ Failed to build VLC crop playlist file; retrying in 20s")
                            self.playlist_refresh_timer = threading.Timer(20.0, self.smooth_playlist_loop)
                            self.playlist_refresh_timer.start()
                            return
                        self.launch_smooth_vlc_playlist(playlist_path, use_global_crop=True, use_lua_script=False)
                        self.smooth_playlist_path = playlist_path
                else:
                    print(f"🔄 No slice videos - using direct URLs (full screen playback)")
                    playlist_path = self.create_smooth_vlc_playlist(resolved, pre_resolved=True, apply_per_file_crop=False)
                    if not playlist_path:
                        print("❌ Failed to build updated playlist file; retrying in 20s (keeping current playback if any)")
                        self.playlist_refresh_timer = threading.Timer(20.0, self.smooth_playlist_loop)
                        self.playlist_refresh_timer.start()
                        return
                    self.launch_smooth_vlc_playlist(playlist_path, use_global_crop=False, use_lua_script=False)
                    self.smooth_playlist_path = playlist_path
            self.last_playlist_signature = signature
            self.resolved_playlist_cache = resolved

            # Schedule-aware refresh timing
            total_duration = sum(r['duration'] for r in resolved)
            
            # Check frequently to catch schedule transitions properly
            # - Every 10-15 seconds to detect schedule changes quickly
            # - More frequently than playlist duration to allow mid-playlist transitions
            if total_duration <= 30:
                refresh_interval = 10  # Very short content - check every 10s
            elif total_duration <= 120:  
                refresh_interval = 15  # Medium content - check every 15s
            else:
                refresh_interval = 30  # Long content - check every 30s
            
            print(f"⏰ Next schedule check in {refresh_interval}s (current content duration: {total_duration}s)")
            self.playlist_refresh_timer = threading.Timer(refresh_interval, self.smooth_playlist_loop)
            self.playlist_refresh_timer.start()
                
        except Exception as e:
            print(f"❌ Error in smooth playlist loop: {e}")
            # Retry in 10 seconds
            self.playlist_refresh_timer = threading.Timer(10.0, self.smooth_playlist_loop)
            self.playlist_refresh_timer.start()

    def is_vlc_process_alive(self):
        """Check if the VLC process is still running"""
        try:
            if not self.vlc_process:
                return False
            
            # Check if process is still alive
            return_code = self.vlc_process.poll()
            if return_code is not None:
                print(f"⚠️ VLC process exited with code: {return_code}")
                return False
            
            return True
        except Exception as e:
            print(f"⚠️ Error checking VLC process: {e}")
            return False

    def playlist_has_mixed_media_types(self):
        """Check if playlist contains both video and image files"""
        try:
            if not hasattr(self, 'resolved_playlist_cache') or not self.resolved_playlist_cache:
                return False
            
            has_video = False
            has_image = False
            
            for item in self.resolved_playlist_cache:
                url = item.get('url', '').lower()
                if any(ext in url for ext in ['.mp4', '.webm', '.mov', '.avi', 'slice-video']):
                    has_video = True
                elif any(ext in url for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    has_image = True
                
                if has_video and has_image:
                    return True
            
            return False
        except Exception:
            return False

    def playlist_has_slice_videos(self):
        """Check if playlist contains slice videos that need cropping"""
        try:
            if not hasattr(self, 'resolved_playlist_cache') or not self.resolved_playlist_cache:
                return False
            
            for item in self.resolved_playlist_cache:
                url = item.get('url', '')
                if 'slice-video' in url and ('slice_mode=' in url or 'slice_count=' in url):
                    return True
            
            return False
        except Exception:
            return False

    def prepare_urls_for_vlc_crop(self, resolved_items):
        """Prepare URLs for VLC crop processing by converting slice URLs to full video URLs"""
        converted_items = []
        for item in resolved_items:
            new_item = item.copy()
            url = item['url']
            
            # Convert slice-video URLs to full CDN URLs since server redirects anyway
            if 'slice-video' in url:
                # Server slice URLs redirect to full videos with headers VLC can't use
                # Example: https://everydayadvertise.com/slice-video/users/user/file.mp4?slice_mode=... 
                # Convert to: https://cdn.everydayadvertise.com/users/user/file.mp4
                import re
                
                # Extract the file path after /slice-video/
                match = re.search(r'/slice-video/(.+?)(?:\?|$)', url)
                if match:
                    file_path = match.group(1)
                    # Convert to direct CDN URL for VLC crop processing
                    full_url = f"https://cdn.everydayadvertise.com/{file_path}"
                    new_item['url'] = full_url
                    print(f"🔄 Converted slice URL to full CDN URL for VLC crop: {full_url}")
                else:
                    print(f"⚠️ Could not convert slice URL, using as-is: {url}")
            else:
                print(f"🖼️ Non-slice URL, keeping as-is: {url}")
            
            converted_items.append(new_item)
        return converted_items

    def create_mixed_media_vlc_playlist(self, playlist_items, pre_resolved=False):
        """Create specialized VLC playlist for mixed media (slice videos + images)"""
        try:
            import tempfile
            import os

            playlist_fd, playlist_path = tempfile.mkstemp(suffix='.m3u8', prefix='mixed_playlist_')
            with os.fdopen(playlist_fd, 'w') as f:
                f.write('#EXTM3U\n')
                valid_count = 0

                for i, item in enumerate(playlist_items):
                    if pre_resolved:
                        url = item['url']
                        duration = item['duration']
                        title = item['title']
                    else:
                        url = self.extract_video_url_from_item(item)
                        duration = int(item.get('duration', 30) or 30)
                        title = item.get('title') or item.get('name') or f'Item {i+1}'
                    
                    if not url or not url.startswith(('http://','https://')):
                        continue
                    
                    # For slice videos, use the slice URL directly (server handles slicing)
                    # For images, use regular URL (no cropping needed)
                    is_slice_video = 'slice-video' in url and ('slice_mode=' in url or 'slice_count=' in url)
                    
                    if is_slice_video:
                        print(f"📹 Adding slice video to mixed playlist: {title}")
                    else:
                        print(f"🖼️ Adding image to mixed playlist: {title}")
                    
                    f.write(f'#EXTINF:{duration},{title}\n')
                    f.write(f'{url}\n')
                    valid_count += 1

            if valid_count == 0:
                print('❌ No valid media URLs written to mixed playlist file')
                return None

            print(f"📋 Created mixed media VLC playlist file with {valid_count} items")
            return playlist_path
        except Exception as e:
            print(f"❌ Failed to create mixed media playlist: {e}")
            return None

    def launch_mixed_media_vlc_playlist(self, playlist_path):
        """Launch VLC for mixed media playlist without global crop parameters"""
        try:
            # Kill any existing VLC first
            if self.vlc_process:
                try:
                    self.vlc_process.terminate()
                    subprocess.run(['pkill', 'vlc'], check=False)
                    time.sleep(0.3)
                except:
                    pass
            
            import os
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
            
            # Get effect transition settings
            effect_config = self.vlc_effects.get(self.current_effect, {"crossfade": "0.7", "gap": "0.3"})
            crossfade_time = effect_config.get("crossfade", "0.7")
            
            # VLC command for MIXED MEDIA PLAYLIST - no global crop parameters
            # Loop current schedule until system detects schedule change
            vlc_cmd = [
                'vlc',
                playlist_path,
                '--fullscreen',
                '--no-video-title-show',
                '--no-osd',
                '--quiet',
                '--intf', 'dummy',
                '--no-random',
                '--playlist-autostart',
                '--playlist-tree',
                '--avcodec-hw', 'any',
                '--file-caching', '4000',
                '--network-caching', '5000',
                '--clock-jitter', '0',
                '--cr-average', '1000',
                '--audio-desync', '0',
                '--loop'
            ]
            
            print(f"🎬 Launching MIXED MEDIA VLC playlist with {effect_config['name']} transitions...")
            print(f"⚠️ No global crop applied - slice videos use server-side slicing, images display normally")
            
            # Start VLC process
            self.vlc_process = subprocess.Popen(vlc_cmd, env=os.environ.copy())
            print(f"✅ Mixed media VLC playlist started (PID: {self.vlc_process.pid})")
            
        except Exception as e:
            print(f"❌ Failed to start mixed media VLC playlist: {e}")
            self.vlc_process = None

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
        """DEPRECATED: Old flickering method - replaced by smooth_playlist_loop()"""
        print("⚠️ Using deprecated playlist_loop - switch to smooth_playlist_loop!")
        # This method has been replaced by smooth_playlist_loop() for no-flicker transitions
        pass
    
    def extract_video_url_from_item(self, item):
        """Extract video URL from playlist item - matches webplayer priority."""
        try:
            # Adaptive priority: for multi-screen sliced content (screen 2/3) prefer slice_url
            screen_id = getattr(self, 'screen_id', '1') or '1'
            slice_aware = item.get('slice_aware') or item.get('is_slice') or False

            # Extended slice structures sometimes used by webplayer
            # Examples (we defensively check):
            #  - item['slices'] -> {"1": {"url": ...}, "2": {"url": ...}}
            #  - item['slice_urls'] -> {"1": "...", "2": "..."}
            #  - item['sliceVariants'] -> list/dict of per-screen entries
            #  - item['variants'][screen_id]['slice_url']
            candidate_nested_urls = []
            try:
                if isinstance(item.get('slices'), dict):
                    sdict = item['slices']
                    if screen_id in sdict:
                        url_from_slices = sdict[screen_id].get('url') if isinstance(sdict[screen_id], dict) else sdict[screen_id]
                        if url_from_slices:
                            candidate_nested_urls.append(('slices', url_from_slices))
                if isinstance(item.get('slice_urls'), dict) and screen_id in item['slice_urls']:
                    candidate_nested_urls.append(('slice_urls', item['slice_urls'][screen_id]))
                if isinstance(item.get('sliceVariants'), dict) and screen_id in item['sliceVariants']:
                    sv = item['sliceVariants'][screen_id]
                    if isinstance(sv, dict):
                        for keyname in ['slice_url','url','preferred_url']:
                            if keyname in sv and sv[keyname]:
                                candidate_nested_urls.append(('sliceVariants', sv[keyname]))
                                break
                if isinstance(item.get('variants'), dict) and screen_id in item['variants']:
                    v = item['variants'][screen_id]
                    if isinstance(v, dict):
                        for keyname in ['slice_url','url','preferred_url']:
                            if keyname in v and v[keyname]:
                                candidate_nested_urls.append(('variants', v[keyname]))
                                break
            except Exception as e_nested:
                print(f"⚠️ Nested slice parse error: {e_nested}")

            if screen_id in ['2','3'] and candidate_nested_urls:
                # Take first resolved nested slice match
                source_name, nested_url = candidate_nested_urls[0]
                if nested_url:
                    print(f"✅ Using nested slice source {source_name} for screen {screen_id}: {nested_url}")
                    return nested_url

            # Build ordered candidate keys depending on screen
            if screen_id in ['2', '3'] and slice_aware:
                # Force slice first so secondary displays show only their portion
                candidate_keys = ['slice_url', 'preferred_url', 'url']
            else:
                candidate_keys = ['preferred_url', 'slice_url', 'url']

            for key in candidate_keys:
                val = item.get(key)
                if val:
                    print(f"✅ Using {key} (screen {screen_id}, slice_aware={slice_aware}): {val}")
                    return val

            # Fallback: construct from file field if present
            file_field = item.get('file')
            if file_field:
                # Some responses include path segments; the working pattern we validated is /media/<basename>
                import os
                basename = os.path.basename(file_field)
                if basename:
                    fallback_url = f"https://everydayadvertise.com/media/{basename}"
                    print(f"🛟 Fallback constructed media URL: {fallback_url}")
                    return fallback_url

            print(f"❌ No playable URL fields in item (keys: {list(item.keys())})")
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
            
            # Add smooth transition settings based on effect
            if hasattr(self, 'current_effect') and self.current_effect in self.vlc_effects:
                effect_config = self.vlc_effects[self.current_effect]
                crossfade_duration = effect_config.get("crossfade", "0.7")
                
                # Add crossfading for smooth transitions
                vlc_cmd.extend([
                    '--audio-filter', 'normvol',
                    '--video-filter', 'blend',
                    '--sub-filter', 'blend'
                ])
                print(f"🎨 Smooth transition effect: {effect_config['name']} ({crossfade_duration}s crossfade)")
            
            # Add professional video settings for smooth playback
            vlc_cmd.extend([
                '--avcodec-hw', 'any',           # Hardware acceleration
                '--file-caching', '3000',        # Larger cache for smoother transitions
                '--network-caching', '4000',     # Network buffer
                '--clock-jitter', '0',           # Minimize timing jitter
                '--cr-average', '1000'           # Clock reference for sync
            ])
            
            # Add crop filter for slice playback if needed
            crop_filter = self._get_crop_filter_for_url(video_url)
            if crop_filter:
                # Dynamic crop calculation based on screen count
                if "slice_count" in crop_filter and "slice_order" in crop_filter:
                    slice_count = crop_filter["slice_count"]
                    slice_order = crop_filter["slice_order"]
                    screen_id = crop_filter["screen_id"]
                    
                    # For 3-screen concatenated video (5760x1080), calculate correct crop
                    if slice_count == 3:
                        # Each screen is 1920px wide in the 5760px total width
                        slice_width = 1920
                        x_offset = slice_order * 1920
                        video_height = 1080
                        
                        # VLC crop format: --crop=<width>x<height>+<x>+<y>
                        crop_param = f"{slice_width}x{video_height}+{x_offset}+0"
                        vlc_cmd.extend(['--crop', crop_param])
                        
                        print(f"🔪 External VLC crop for screen {screen_id}: {crop_param}")
                        print(f"   📊 3-screen video (5760x1080), showing slice {slice_order + 1}")
                        print(f"   📐 Slice: 1920px wide at x={x_offset}")
                    else:
                        # Generic calculation for other screen counts
                        # Assume total width based on screen count * 1920
                        total_width = slice_count * 1920
                        slice_width = 1920
                        x_offset = slice_order * slice_width
                        video_height = 1080
                        
                        crop_param = f"{slice_width}x{video_height}+{x_offset}+0"
                        vlc_cmd.extend(['--crop', crop_param])
                        
                        print(f"🔪 External VLC crop for screen {screen_id}: {crop_param}")
                        print(f"   📊 {slice_count}-screen video ({total_width}x1080), showing slice {slice_order + 1}")
                        print(f"   📐 Slice: {slice_width}px wide at x={x_offset}")
                    
                else:
                    # Legacy static crop (fallback for old format)
                    if crop_filter.get("left") == 1 and crop_filter.get("right") == 1:
                        vlc_cmd.extend(['--crop', '640x1080+640+0'])  # Middle third
                        print(f"🔪 Legacy VLC crop: 640x1080+640+0 (middle third)")
                    elif crop_filter.get("left") == 2 and crop_filter.get("right") == 0:
                        vlc_cmd.extend(['--crop', '640x1080+1280+0'])  # Right third
                        print(f"🔪 Legacy VLC crop: 640x1080+1280+0 (right third)")
                    elif crop_filter.get("left") == 0 and crop_filter.get("right") == 2:
                        vlc_cmd.extend(['--crop', '640x1080+0+0'])  # Left third
                        print(f"🔪 Legacy VLC crop: 640x1080+0+0 (left third)")
                    else:
                        print(f"🔪 Unhandled crop filter: {crop_filter}")
            
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
        
        # Clean up smooth playlist file
        if hasattr(self, 'smooth_playlist_path') and self.smooth_playlist_path:
            try:
                import os
                os.unlink(self.smooth_playlist_path)
                print("🧹 Cleaned up smooth playlist file")
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
                f"https://everydayadvertise.com/api/sync-effect",
                json=sync_data,
                timeout=3
            )
            
            if response.status_code == 200:
                print(f"✅ Effect synced to all screens: {effect_name}")
            else:
                print(f"⚠️ Effect sync failed: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Effect sync error (continuing): {e}")
    
    def create_smooth_vlc_playlist(self, playlist_items, pre_resolved=False, apply_per_file_crop=False):
        """Create VLC playlist file with smooth transitions - no flickers.

        playlist_items can be either raw server items (pre_resolved=False) or a list of
        dictionaries each containing: url, duration, title (pre_resolved=True).
        apply_per_file_crop: Ignored for MPV (kept for API compatibility)
        """
        try:
            import tempfile
            import os

            playlist_fd, playlist_path = tempfile.mkstemp(suffix='.m3u8', prefix='smooth_playlist_')
            
            with os.fdopen(playlist_fd, 'w') as f:
                f.write('#EXTM3U\n')
                valid_count = 0

                if pre_resolved:
                    # Already resolved list
                    for i, r in enumerate(playlist_items):
                        f.write(f"#EXTINF:{r['duration']},{r['title']}\n")
                        f.write(f"{r['url']}\n")
                        valid_count += 1
                else:
                    # Resolve on the fly (legacy path)
                    for i, item in enumerate(playlist_items):
                        url = self.extract_video_url_from_item(item)
                        if not url or not url.startswith(('http://','https://')):
                            continue
                        try:
                            duration = int(item.get('duration', 30) or 30)
                        except:
                            duration = 30
                        title = item.get('title') or item.get('name') or f'Item {i+1}'
                        f.write(f'#EXTINF:{duration},{title}\n')
                        f.write(f'{url}\n')
                        valid_count += 1

            if valid_count == 0:
                print('❌ No valid media URLs written to playlist file')
                return None

            print(f"📋 Created smooth playlist file with {valid_count} items")
            return playlist_path
        except Exception as e:
            print(f"❌ Failed to create playlist: {e}")
            return None
    
    def launch_smooth_vlc_playlist(self, playlist_path, use_global_crop=True, use_lua_script=False):
        """Launch MPV with smooth continuous playlist - NO FLICKERS.
        
        Args:
            playlist_path: Path to M3U8 playlist file
            use_global_crop: If True, apply global crop filter (for pure slice videos).
            use_lua_script: If True, use MPV lua script for per-video smart cropping (mixed media)
        """
        try:
            # Kill any existing MPV/VLC first to reset crop parameters
            if self.vlc_process:
                try:
                    self.vlc_process.terminate()
                    subprocess.run(['pkill', 'vlc'], check=False)
                    subprocess.run(['pkill', 'mpv'], check=False)
                    time.sleep(0.3)  # Brief cleanup
                except:
                    pass
            
            # Set display
            import os
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ':0'
            
            # Get effect transition settings
            effect_config = self.vlc_effects.get(self.current_effect, {"crossfade": "0.7", "gap": "0.3"})
            crossfade_time = effect_config.get("crossfade", "0.7")
            
            # Add dynamic crop parameters for horizontal and vertical multi-screen layouts
            screen_id = getattr(self, 'screen_id', '1') or '1'
            screen_num = int(screen_id) if screen_id.isdigit() else 1
            
            # This function should only be called for slice-only videos (no mixed media)
            # Mixed media is handled separately by launch_mixed_media_vlc_playlist
            
            # Detect content type to decide on approach
            has_mixed_media = self.playlist_has_mixed_media_types()
            
            # VLC command for SMOOTH PLAYLIST PLAYBACK
            # MPV command for SMOOTH PLAYLIST PLAYBACK (better than VLC for mixed media)
            mpv_cmd = [
                'mpv',
                playlist_path,
                '--fullscreen',
                '--no-osc',                     # No on-screen controller
                '--no-osd-bar',                 # No progress bar
                '--quiet',
                '--loop-playlist=inf',          # Loop playlist forever
                '--no-audio',                   # Disable audio
                '--image-display-duration=10',  # Image duration
                '--keep-open=no',               # Don't pause at end
                '--force-window=yes'            # Always show window
            ]
            
            # Add lua script for smart per-video cropping in mixed media mode
            if use_lua_script:
                # Use lua script for dynamic crop based on video width
                lua_script_path = '/home/everydayadvertise/Desktop/auto_crop.lua'
                screen_id = getattr(self, 'screen_id', '1') or '1'
                screen_num = int(screen_id) if screen_id.isdigit() else 1
                
                mpv_cmd.extend([
                    f'--script={lua_script_path}',
                    f'--script-opts=screen-num={screen_num}'
                ])
                print(f"🔧 Using MPV lua script for smart cropping (screen {screen_num})")
            
            # Apply global crop only for pure slice video playlists
            elif use_global_crop and screen_num >= 1:
                # PURE slice video playlist - apply global crop (all items are 5760x1080)
                slice_width = 1920
                slice_height = 1080
                x_offset = (screen_num - 1) * slice_width
                crop_geometry = f"{slice_width}:{slice_height}:{x_offset}:0"
                mpv_cmd.extend([f'--vf=crop={crop_geometry}'])
                print(f"🔪 MPV global crop for screen {screen_num}: {crop_geometry} (pure slice playlist)")
                # MIXED media - no global crop to avoid cropping images incorrectly
                print(f"🎭 MPV NO CROP for mixed media (images display correctly)")
                print(f"   ⚠️ Slice videos will show FULL SCREEN (not cropped) - need server-side slicing")
            else:
                print(f"🎯 No crop - FULL SCREEN for screen {screen_id}")
            
            print(f"🎬 Launching MPV playlist...")
            print(f"   � Server slice URLs should return pre-cropped content for this screen")
            
            print(f"🎬 Launching MPV playlist with continuous playback...")
            
            # Start MPV process
            self.vlc_process = subprocess.Popen(mpv_cmd, env=os.environ.copy())
            print(f"✅ MPV playlist started (PID: {self.vlc_process.pid})")
            
        except Exception as e:
            print(f"❌ Failed to start MPV playlist: {e}")
            self.vlc_process = None

    # ---------------- Embedded python-vlc playback (reduced flicker) ---------------- #
    def start_or_update_embedded_playlist(self, resolved_items):
        """Start or update the embedded python-vlc playback loop with resolved items.

        resolved_items: list of {url, duration, title}
        """
        try:
            self.embedded_playlist = resolved_items
            self.current_embedded_index = 0
            if self.embedded_thread and self.embedded_thread.is_alive():
                # Thread will pick up new playlist on next cycle
                print("🔄 Embedded playlist updated in-place (no restart)")
            else:
                print("🚀 Starting embedded playback thread")
                self.embedded_stop_event.clear()
                self.embedded_thread = threading.Thread(target=self._embedded_playback_loop, daemon=True)
                self.embedded_thread.start()
        except Exception as e:
            print(f"❌ Embedded playback init failed, falling back to external VLC: {e}")
            traceback.print_exc()
            self.use_embedded_vlc = False

    def _embedded_playback_loop(self):
        """Loop through playlist using a single python-vlc player to reduce flicker."""
        try:
            # Initialize VLC instance with crop support
            vlc_args = [
                '--no-video-title-show', 
                '--quiet', 
                '--fullscreen', 
                '--avcodec-hw=any',
                '--intf=dummy'
            ]
            instance = vlc.Instance(*vlc_args)
            player = instance.media_player_new()
            
            # Try to set fullscreen
            try:
                player.toggle_fullscreen()
            except:
                pass
                
        except Exception as e:
            print(f"❌ Could not initialize embedded VLC instance: {e}")
            self.use_embedded_vlc = False
            return

        while not self.embedded_stop_event.is_set() and self.playback_active:
            if not getattr(self, 'embedded_playlist', None):
                time.sleep(1)
                continue
            item = self.embedded_playlist[self.current_embedded_index % len(self.embedded_playlist)]
            url = item['url']
            duration = item['duration']
            title = item['title']
            
            # Check if this needs VLC crop (regardless of URL parameters)
            crop_filter = self._get_crop_filter_for_url(url)

            print(f"🎥 Playing (embedded) {self.current_embedded_index+1}/{len(self.embedded_playlist)}: {title}")
            if crop_filter:
                if "slice_count" in crop_filter:
                    print(f"🔄 Dynamic slice: {crop_filter['slice_count']} screens, order {crop_filter['slice_order']}")
                else:
                    print(f"🔄 Static slice: {crop_filter}")
            else:
                print(f"🎬 Full screen mode (no cropping)")
            print(f"📺 URL: {url}")

            try:
                media = instance.media_new(url)
                
                # Pre-apply crop options to media if needed (before playback starts)
                if crop_filter and "slice_count" in crop_filter and "slice_order" in crop_filter:
                    slice_count = crop_filter["slice_count"]
                    slice_order = crop_filter["slice_order"]
                    screen_id = crop_filter["screen_id"]
                    orientation = crop_filter.get("orientation", "horizontal")
                    
                    # Dynamic pre-applied crop based on orientation and screen count
                    if orientation == "horizontal":
                        # HORIZONTAL layouts: calculate slice width
                        if slice_count == 2:  # 3840x1080 -> 1920x1080 each
                            slice_width, slice_height = 1920, 1080
                            x = slice_order * slice_width
                            media.add_option(f"--crop={slice_width}x{slice_height}+{x}+0")
                        elif slice_count == 3:  # 5760x1080 -> 1920x1080 each
                            slice_width, slice_height = 1920, 1080
                            x = slice_order * slice_width
                            media.add_option(f"--crop={slice_width}x{slice_height}+{x}+0")
                        elif slice_count == 4:  # 7680x1080 -> 1920x1080 each
                            slice_width, slice_height = 1920, 1080
                            x = slice_order * slice_width
                            media.add_option(f"--crop={slice_width}x{slice_height}+{x}+0")
                        elif slice_count == 5:  # 9600x1080 -> 1920x1080 each
                            slice_width, slice_height = 1920, 1080
                            x = slice_order * slice_width
                            media.add_option(f"--crop={slice_width}x{slice_height}+{x}+0")
                        print(f"🔧 PRE-APPLIED horizontal crop for screen {screen_id}: slice {slice_order + 1} of {slice_count}")
                        
                    elif orientation == "vertical":
                        # VERTICAL layouts: calculate slice height
                        if slice_count == 2:  # 1080x3840 -> 1080x1920 each
                            slice_width, slice_height = 1080, 1920
                            y = slice_order * slice_height
                            media.add_option(f"--crop={slice_width}x{slice_height}+0+{y}")
                        elif slice_count == 3:  # 1080x5760 -> 1080x1920 each
                            slice_width, slice_height = 1080, 1920
                            y = slice_order * slice_height
                            media.add_option(f"--crop={slice_width}x{slice_height}+0+{y}")
                        elif slice_count == 4:  # 1080x7680 -> 1080x1920 each
                            slice_width, slice_height = 1080, 1920
                            y = slice_order * slice_height
                            media.add_option(f"--crop={slice_width}x{slice_height}+0+{y}")
                        elif slice_count == 5:  # 1080x9600 -> 1080x1920 each
                            slice_width, slice_height = 1080, 1920
                            y = slice_order * slice_height
                            media.add_option(f"--crop={slice_width}x{slice_height}+0+{y}")
                        print(f"🔧 PRE-APPLIED vertical crop for screen {screen_id}: slice {slice_order + 1} of {slice_count}")
                    
                    # Force fullscreen scaling
                    media.add_option("--video-filter=scale")
                    media.add_option("--fullscreen")
                
                player.set_media(media)

                # Start playback and wait for it to actually start
                player.play()

                # Wait for player to start (or timeout)
                start_wait = 0
                while player.get_state() not in [vlc.State.Playing, vlc.State.Ended] and start_wait < 10:
                    time.sleep(0.2)
                    start_wait += 0.2

                # After playback starts, apply VLC crop if needed
                if crop_filter and player.get_state() == vlc.State.Playing:
                    try:
                        if "slice_count" in crop_filter and "slice_order" in crop_filter:
                            slice_count = crop_filter["slice_count"]
                            slice_order = crop_filter["slice_order"]
                            screen_id = crop_filter["screen_id"]

                            # Wait briefly until video reports a valid size
                            vid_wait = 0
                            vw, vh = 0, 0
                            while vid_wait < 3:
                                try:
                                    vw, vh = player.video_get_size(0)
                                except Exception:
                                    pass
                                if vw > 0 and vh > 0:
                                    break
                                time.sleep(0.2)
                                vid_wait += 0.2

                            if vw == 0 or vh == 0:
                                print("⚠️ Could not determine video size for cropping – skipping slice crop this item")
                            else:
                                # Dynamic crop calculation based on orientation
                                orientation = crop_filter.get("orientation", "horizontal")
                                
                                if orientation == "horizontal":
                                    # HORIZONTAL: divide video width by screen count
                                    slice_width = vw // slice_count
                                    slice_height = vh
                                    left = slice_order * slice_width
                                    top = 0
                                    
                                    # VLC crop geometry format for libvlc: WxH+X+Y
                                    geometry = f"{slice_width}x{slice_height}+{left}+{top}"
                                    print(f"✂️ HORIZONTAL crop for screen {screen_id}: {geometry}")
                                    print(f"   📊 {slice_count} screens total, showing slice {slice_order + 1}")
                                    print(f"   📐 Video: {vw}x{vh}, slice: {slice_width}x{slice_height} at x={left}")
                                    
                                elif orientation == "vertical":
                                    # VERTICAL: divide video height by screen count
                                    slice_width = vw
                                    slice_height = vh // slice_count
                                    left = 0
                                    top = slice_order * slice_height
                                    
                                    # VLC crop geometry format for libvlc: WxH+X+Y
                                    geometry = f"{slice_width}x{slice_height}+{left}+{top}"
                                    print(f"✂️ VERTICAL crop for screen {screen_id}: {geometry}")
                                    print(f"   📊 {slice_count} screens total, showing slice {slice_order + 1}")
                                    print(f"   📐 Video: {vw}x{vh}, slice: {slice_width}x{slice_height} at y={top}")
                                
                                # Apply crop using VLC's crop geometry
                                success = player.video_set_crop_geometry(geometry)
                                print(f"✅ Embedded VLC crop applied: success={success}")
                                
                                # If crop_geometry failed, try alternative crop method
                                if success is None or success == False:
                                    print("⚠️ crop_geometry failed, trying alternative crop method...")
                                    try:
                                        if orientation == "horizontal":
                                            # HORIZONTAL alternative methods
                                            crop_ratio = f"{slice_width}:{slice_height}"
                                            player.video_set_crop_ratio(crop_ratio)
                                            print(f"🔧 Applied horizontal crop ratio: {crop_ratio}")
                                            
                                            # Set crop border to position the slice
                                            player.video_set_crop_border(left, 0, vw - left - slice_width, 0)
                                            print(f"🔧 Applied horizontal crop border: left={left}, right={vw - left - slice_width}")
                                            
                                        elif orientation == "vertical":
                                            # VERTICAL alternative methods
                                            crop_ratio = f"{slice_width}:{slice_height}"
                                            player.video_set_crop_ratio(crop_ratio)
                                            print(f"🔧 Applied vertical crop ratio: {crop_ratio}")
                                            
                                            # Set crop border to position the slice (top, right, bottom, left)
                                            player.video_set_crop_border(0, 0, vh - top - slice_height, top)
                                            print(f"🔧 Applied vertical crop border: top={top}, bottom={vh - top - slice_height}")
                                        
                                    except Exception as alt_e:
                                        print(f"⚠️ Alternative crop method also failed: {alt_e}")
                                        # Last resort: try croppadd filter
                                        try:
                                            media = player.get_media()
                                            if media:
                                                media.add_option(f'--video-filter=croppadd')
                                                if orientation == "horizontal":
                                                    media.add_option(f'--croppadd-cropleft={left}')
                                                    media.add_option(f'--croppadd-cropright={vw - left - slice_width}')
                                                    media.add_option(f'--croppadd-croptop=0')
                                                    media.add_option(f'--croppadd-cropbottom=0')
                                                    print(f"🔧 Applied horizontal croppadd: left={left}, right={vw - left - slice_width}")
                                                elif orientation == "vertical":
                                                    media.add_option(f'--croppadd-cropleft=0')
                                                    media.add_option(f'--croppadd-cropright=0')
                                                    media.add_option(f'--croppadd-croptop={top}')
                                                    media.add_option(f'--croppadd-cropbottom={vh - top - slice_height}')
                                                    print(f"🔧 Applied vertical croppadd: top={top}, bottom={vh - top - slice_height}")
                                        except Exception as filter_e:
                                            print(f"⚠️ Croppadd filter failed: {filter_e}")

                                # Force fullscreen scaling after crop is applied
                                try:
                                    time.sleep(0.5)  # Wait for crop to take effect
                                    
                                    # Set aspect ratio to fill screen (stretch cropped slice)
                                    player.video_set_aspect_ratio("")  # Auto aspect ratio
                                    
                                    # Force video to fill entire screen
                                    player.video_set_scale(0)  # Auto-scale to fit screen
                                    
                                    # Toggle fullscreen to force refresh
                                    player.set_fullscreen(False)
                                    time.sleep(0.1)
                                    player.set_fullscreen(True)
                                    
                                    print(f"🔧 Applied fullscreen scaling to stretch cropped slice")
                                    
                                except Exception as scale_e:
                                    print(f"⚠️ Fullscreen scaling failed: {scale_e}")

                                # Let VLC auto-scale the cropped region to fullscreen
                                try:
                                    # Toggle fullscreen to force VLC to rescale the cropped area
                                    player.set_fullscreen(False)
                                    time.sleep(0.1)
                                    player.set_fullscreen(True)
                                    
                                    # 0 = fit to window/fullscreen - should fill entire screen now
                                    r = player.video_set_scale(0)
                                    time.sleep(0.3)
                                    try:
                                        aw, ah = player.video_get_size(0)
                                    except Exception:
                                        aw, ah = -1, -1
                                    print(f"🔧 Post-crop autoscale result scale_ret={r} size={aw}x{ah}")
                                    if aw > 0 and aw < (vw // 2):
                                        print("⚠️ Cropped slice still rendering small; scheduling fallback rebuild next loop")
                                except Exception as se:
                                    print(f"⚠️ Autoscale check failed: {se}")
                    except Exception as crop_e:
                        print(f"⚠️ Dynamic slice crop failed: {crop_e}")
                
                if player.get_state() == vlc.State.Error:
                    print(f"⚠️ VLC player error state")
                    time.sleep(2)
                    self.current_embedded_index = (self.current_embedded_index + 1) % len(self.embedded_playlist)
                    continue
                    
            except Exception as e:
                print(f"⚠️ Failed to start media: {e}")
                time.sleep(2)
                self.current_embedded_index = (self.current_embedded_index + 1) % len(self.embedded_playlist)
                continue

            # Active wait with early break if playlist updates
            start_time = time.time()
            target = duration
            while time.time() - start_time < target and not self.embedded_stop_event.is_set() and self.playback_active:
                time.sleep(0.5)
                # If playlist changed length, break early to adapt
                if len(self.embedded_playlist) != len(getattr(self, 'resolved_playlist_cache', self.embedded_playlist)):
                    break

            # Advance to next item
            self.current_embedded_index = (self.current_embedded_index + 1) % len(self.embedded_playlist)

        try:
            player.stop()
        except Exception:
            pass
        print("🛑 Embedded playback loop exited")
    
    def _launch_external_vlc_slice(self, url, order, count, duration):
        """Launch external VLC process with proper crop and scale for slice."""
        try:
            import subprocess
            import shlex
            
            # Calculate crop parameters
            # We don't know exact video dimensions, so use standard 1920x1080 assumption
            # or let VLC auto-detect and crop proportionally
            slice_width_ratio = f"1/{count}"  # e.g., "1/3" for 3-way split
            left_offset_ratio = f"{order}/{count}"  # e.g., "1/3" for middle slice
            
            cmd = [
                'vlc',
                '--no-video-title-show',
                '--quiet', 
                '--fullscreen',
                '--avcodec-hw=any',
                '--intf=dummy',
                '--video-filter=crop',
                f'--crop={slice_width_ratio}',
                f'--crop-left={left_offset_ratio}',
                '--play-and-exit',
                url
            ]
            
            print(f"🚀 Launching external VLC: {' '.join(cmd[:8])}... {url}")
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for duration or until process ends
            try:
                process.wait(timeout=duration)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            print(f"✅ External VLC slice playback completed")
            
        except Exception as e:
            print(f"❌ External VLC slice failed: {e}")

    def _get_webplayer_transform_for_url(self, url):
        """Get webplayer-style transform parameters for slice URL or screen ID."""
        try:
            screen_id = getattr(self, 'screen_id', '1') or '1'
            screen_num = int(screen_id) if screen_id.isdigit() else 1
            
            # Parse slice parameters from URL if present
            slice_count = 3  # Default to 3-way split
            slice_order = screen_num - 1  # Convert screen 1,2,3 to order 0,1,2
            
            if 'slice_mode=split-h' in url:
                # Extract actual parameters from URL if available
                import re
                count_match = re.search(r'slice_count=(\d+)', url)
                order_match = re.search(r'slice_order=(\d+)', url)
                
                if count_match:
                    slice_count = int(count_match.group(1))
                if order_match:
                    slice_order = int(order_match.group(1))
            
            # For screens 2 and 3, apply webplayer-style horizontal slicing
            if screen_num in [2, 3] or ('slice_mode=split-h' in url and slice_count > 1):
                # Webplayer formula: scaleX(count) + translateX(-(order * 100/count)%)
                scale_x = slice_count
                translate_x_percent = -(slice_order * 100.0 / slice_count)
                
                return {
                    'scale_x': scale_x,
                    'translate_x_percent': translate_x_percent,
                    'slice_order': slice_order,
                    'slice_count': slice_count
                }
                
        except Exception as e:
            print(f"⚠️ Error parsing webplayer transform: {e}")
        
        return None
    
    def run(self):
        """Run the application."""
        if self.root:
            try:
                self.root.mainloop()
            except KeyboardInterrupt:
                self.on_closing()
        else:
            # Headless run loop keep-alive
            try:
                while self.playback_active:
                    time.sleep(2)
            except KeyboardInterrupt:
                self.on_closing()

    def _get_crop_filter_for_url(self, url):
        """Extract crop parameters from slice URL or screen ID for dynamic horizontal/vertical split."""
        print(f"🔍 Checking crop filter for URL: {url}")
        try:
            screen_id = getattr(self, 'screen_id', '1') or '1'
            print(f"🖥️ Screen ID: {screen_id}")
            
            # Parse slice parameters from URL if present (dynamic screen count and orientation)
            if ('slice_mode=split-h' in url or 'slice_mode=split-v' in url) and 'slice_count=' in url:
                import re
                
                # Extract slice_count and slice_order from URL
                slice_count_match = re.search(r'slice_count=(\d+)', url)
                slice_order_match = re.search(r'slice_order=(\d+)', url)
                
                # Detect orientation from slice_mode
                is_vertical = 'slice_mode=split-v' in url
                orientation = "vertical" if is_vertical else "horizontal"
                
                if slice_count_match and slice_order_match:
                    slice_count = int(slice_count_match.group(1))
                    slice_order = int(slice_order_match.group(1))
                    
                    print(f"🎯 Found {orientation} sync video: {slice_count} screens, showing slice {slice_order}")
                    
                    # Return dynamic crop parameters with orientation
                    return {
                        "slice_count": slice_count,
                        "slice_order": slice_order,
                        "screen_id": screen_id,
                        "orientation": orientation
                    }
            
            # Check if this might be a sync video based on screen_id (fallback for URLs without slice params)
            screen_num = int(screen_id)
            if screen_num > 1:  # Screens 2+ likely need cropping in multi-screen setup
                print(f"📍 Screen {screen_id}: Applying default crop (assuming horizontal multi-screen setup)")
                # For fallback, assume common configurations
                if screen_num <= 6:  # Support up to 6 screens
                    return {
                        "slice_count": 3,  # Default assumption - will be overridden by URL params if available
                        "slice_order": screen_num - 1,  # Convert screen_id to 0-based slice_order
                        "screen_id": screen_id,
                        "orientation": "horizontal"  # Default to horizontal
                    }
            
        except Exception as e:
            print(f"⚠️ Error parsing crop filter: {e}")
        
        print("❌ No crop filter needed - playing full video")
        return None

if __name__ == "__main__":
    try:
        app = WebplayerStyleEATVClient()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
