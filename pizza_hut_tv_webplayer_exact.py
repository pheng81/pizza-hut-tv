#!/usr/bin/env python3
"""
EA TV - Pi Client (EXACT WEBPLAYER REPLICA)
Uses same flow: Link Code → Store Code → Screen Selection → Play
With FOOLPROOF EMERGENCY EXIT SYSTEM
"""

import tkinter as tk
from tkinter import messagebox
import requests
import json
import subprocess
import os
import signal
import sys
import threading
import time
from datetime import datetime

class EATVWebplayerClone:
    def __init__(self, root):
        self.root = root
        self.root.title("EA TV - Screen Control")
        self.root.geometry("600x400")
        self.root.configure(bg='#0b0b0b')
        
        # Make window interactive and ensure focus
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        
        # Emergency Exit System - Multiple Methods
        self.root.bind('<KeyPress>', self.handle_keypress)
        self.root.focus_set()
        self.root.focus_force()
        
        # Server configuration - FIXED: Use HTTPS as server redirects to it
        self.server_url = "https://everydayadvertise.com"
        
        # State variables - SAME AS WEBPLAYER
        self.code = ""      # 4-digit TV code
        self.store_id = ""  # Store code
        self.screen_id = "" # Screen number
        self.vlc_process = None
        self.emergency_timer = None
        self.current_item_index = 0  # Track which item we're currently playing for rotation
        self.playlist_start_time = None  # Track when we started the current playlist cycle
        
        self.current_step = 1
        
        # Start emergency exit daemon
        self.start_emergency_daemon()
        
        # Test schedule logic on startup
        self.root.after(2000, self.test_schedule_logic)
        
        # Start schedule monitoring timer - check every 30 seconds for schedule changes
        self.root.after(5000, self.schedule_monitor)
        
        self.create_widgets()
        self.show_step()
        
        print("===== EMERGENCY EXIT METHODS =====")
        print("1. Press 'X' key in this window")
        print("2. Create file: touch /tmp/pizza_hut_emergency_exit")
        print("3. Send command: echo 'EXIT' > /tmp/pizza_hut_emergency_pipe")
        print("4. Close this window")
        print("5. SSH and run: pkill vlc")
        print("=====================================")
        
    def create_widgets(self):
        # Main container
        self.main_frame = tk.Frame(self.root, bg='#0b0b0b')
        self.main_frame.pack(fill='both', expand=True, padx=40, pady=40)
        
        # STEP 1: Enter 4-digit TV code (SAME AS WEBPLAYER)
        self.step1_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=28, pady=28)
        
        tk.Label(self.step1_frame, text="Enter your Android TV pairing code", 
                font=('Arial', 18, 'bold'), fg='white', bg='#0d0d0d').pack(pady=(0, 8))
        
        tk.Label(self.step1_frame, text="Type the 4-digit code from your TV app or profile page.", 
                font=('Arial', 11), fg='#bbbbbb', bg='#0d0d0d').pack(pady=(0, 16))
        
        tk.Label(self.step1_frame, text="4-digit code", 
                font=('Arial', 10), fg='#cccccc', bg='#0d0d0d').pack(anchor='w', pady=(12, 8))
        
        self.code_entry = tk.Entry(self.step1_frame, font=('Arial', 14, 'bold'), 
                                  width=12, justify='center', bg='#000000', fg='white',
                                  insertbackground='white', relief='flat', bd=5)
        self.code_entry.pack(pady=(0, 18), ipady=8)
        self.code_entry.bind('<Return>', lambda e: self.submit_code())
        
        tk.Button(self.step1_frame, text="Link Code", font=('Arial', 12, 'bold'),
                 bg='#c8102e', fg='white', padx=20, pady=10, relief='flat',
                 command=self.submit_code).pack(pady=(0, 14))
        
        tk.Label(self.step1_frame, text="Next you'll enter the store code and pick a screen.", 
                font=('Arial', 9), fg='#9a9a9a', bg='#0d0d0d').pack()
        
        # STEP 2: Enter store code (SAME AS WEBPLAYER)
        self.step2_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=28, pady=28)
        
        tk.Label(self.step2_frame, text="Enter store code", 
                font=('Arial', 18, 'bold'), fg='white', bg='#0d0d0d').pack(pady=(0, 8))
        
        self.tv_code_label = tk.Label(self.step2_frame, text="TV code: ", 
                                     font=('Arial', 11), fg='#bbbbbb', bg='#0d0d0d')
        self.tv_code_label.pack(pady=(0, 16))
        
        tk.Label(self.step2_frame, text="Store code", 
                font=('Arial', 10), fg='#cccccc', bg='#0d0d0d').pack(anchor='w', pady=(12, 8))
        
        self.store_entry = tk.Entry(self.step2_frame, font=('Arial', 14, 'bold'), 
                                   width=12, justify='center', bg='#000000', fg='white',
                                   insertbackground='white', relief='flat', bd=5)
        self.store_entry.pack(pady=(0, 18), ipady=8)
        self.store_entry.bind('<Return>', lambda e: self.submit_store())
        
        tk.Button(self.step2_frame, text="Continue", font=('Arial', 12, 'bold'),
                 bg='#c8102e', fg='white', padx=20, pady=10, relief='flat',
                 command=self.submit_store).pack(pady=(0, 14))
        
        tk.Label(self.step2_frame, text="You'll choose a screen next.", 
                font=('Arial', 9), fg='#9a9a9a', bg='#0d0d0d').pack()
        
        # STEP 3: Choose screen (SAME AS WEBPLAYER)
        self.step3_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=20, pady=20)
        
        # Header
        self.header_label = tk.Label(self.step3_frame, text="", 
                                    font=('Arial', 12), fg='#cccccc', bg='#0d0d0d')
        self.header_label.pack(pady=(0, 20))
        
        tk.Label(self.step3_frame, text="Screens", 
                font=('Arial', 14, 'bold'), fg='white', bg='#0d0d0d').pack(anchor='w', pady=(0, 10))
        
        self.screens_frame = tk.Frame(self.step3_frame, bg='#0d0d0d')
        self.screens_frame.pack(fill='x')
        
        # STEP 4: Video control
        self.step4_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=28, pady=28)
        
        self.status_label = tk.Label(self.step4_frame, text="", 
                                    font=('Arial', 12), fg='#cccccc', bg='#0d0d0d')
        self.status_label.pack(pady=(0, 10))
        
        # Emergency exit instructions
        emergency_label = tk.Label(self.step4_frame, 
                                  text="🔴 EMERGENCY EXIT: Press 'X', 'Esc', or 'Q' to stop video", 
                                  font=('Arial', 10, 'bold'), fg='#ff6b6b', bg='#0d0d0d')
        emergency_label.pack(pady=(0, 20))
        
        control_frame = tk.Frame(self.step4_frame, bg='#0d0d0d')
        control_frame.pack()
        
        tk.Button(control_frame, text="▶ Play Video", font=('Arial', 12, 'bold'),
                 bg='#c8102e', fg='white', padx=20, pady=10, relief='flat', cursor='hand2',
                 command=self.play_video).pack(side='left', padx=(0, 10))
        
        tk.Button(control_frame, text="⏹ Stop Video", font=('Arial', 12, 'bold'),
                 bg='#ff6b6b', fg='white', padx=20, pady=10, relief='flat', cursor='hand2',
                 command=self.emergency_stop).pack(side='left', padx=(0, 10))
        
        tk.Button(control_frame, text="← Back to Screens", font=('Arial', 11),
                 bg='#4a4a4a', fg='white', padx=15, pady=8, relief='flat', cursor='hand2',
                 command=self.back_to_screens).pack(side='left')
        
    def show_step(self):
        # Hide all steps
        self.step1_frame.pack_forget()
        self.step2_frame.pack_forget()
        self.step3_frame.pack_forget()
        self.step4_frame.pack_forget()
        
        # Show current step
        if self.current_step == 1:
            self.step1_frame.pack(fill='both', expand=True)
            self.code_entry.focus()
        elif self.current_step == 2:
            self.step2_frame.pack(fill='both', expand=True)
            self.store_entry.focus()
        elif self.current_step == 3:
            self.step3_frame.pack(fill='both', expand=True)
        elif self.current_step == 4:
            self.step4_frame.pack(fill='both', expand=True)
    
    def submit_code(self):
        """EXACT SAME AS WEBPLAYER: Validate 4-digit code"""
        code = self.code_entry.get().strip().replace(' ', '')
        
        if not (len(code) == 4 and code.isdigit()):
            messagebox.showerror("Error", "Please enter your 4-digit TV code.")
            return
        
        try:
            # SAME API CALL AS WEBPLAYER
            url = f"{self.server_url}/api/stores_by_code/{code}"
            print(f"DEBUG: Testing code {code} at {url}")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"DEBUG: Response: {json.dumps(data, indent=2)}")
                
                if data.get('success'):
                    self.code = code
                    self.tv_code_label.config(text=f"TV code: {code}")
                    self.current_step = 2
                    self.show_step()
                else:
                    messagebox.showerror("Error", data.get('error', 'TV code not valid'))
            else:
                messagebox.showerror("Error", "TV code not valid")
                
        except Exception as e:
            messagebox.showerror("Error", "Could not verify code. Check your connection.")
            print(f"DEBUG: Error: {e}")
    
    def submit_store(self):
        """EXACT SAME AS WEBPLAYER: Enter store code"""
        store = self.store_entry.get().strip().replace(' ', '')
        
        if not store:
            messagebox.showerror("Error", "Please enter your store code.")
            return
        
        self.store_id = store
        self.header_label.config(text=f"TV code: {self.code} • Store: {self.store_id}")
        
        # Show screen selection (screens 1, 2, 3 like typical Pizza Hut setup)
        self.create_screen_buttons()
        self.current_step = 3
        self.show_step()
    
    def create_screen_buttons(self):
        """Create screen buttons (1, 2, 3)"""
        for widget in self.screens_frame.winfo_children():
            widget.destroy()
        
        print("DEBUG: Creating screen buttons...")
        for screen_num in [1, 2, 3]:
            btn = tk.Button(self.screens_frame,
                           text=f"Screen {screen_num}",
                           font=('Arial', 14), bg='#0d0d0d', fg='#e2e2e2',
                           relief='flat', pady=12, anchor='w', cursor='hand2',
                           activebackground='#161616', activeforeground='#ffffff',
                           command=lambda s=screen_num: self.select_screen(s))
            btn.pack(fill='x', pady=1, padx=5)
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#161616'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#0d0d0d'))
            btn.bind('<Button-1>', lambda e, s=screen_num: self.select_screen(s))
            print(f"DEBUG: Created Screen {screen_num} button with command")
        
        # Ensure the window has focus after creating buttons
        self.root.focus_force()
        print("DEBUG: Screen buttons created and window focused")
    
    def select_screen(self, screen_num):
        """Select screen - SAME AS WEBPLAYER"""
        print(f"DEBUG: *** SCREEN {screen_num} BUTTON CLICKED! ***")
        print(f"DEBUG: Button click detected for screen {screen_num}")
        
        # Format screen ID as store_screenX to match API response
        self.screen_id = f"{self.store_id}_screen{screen_num}"
        self.status_label.config(text=f"Selected: Store {self.store_id}, Screen {screen_num}")
        self.current_step = 4
        self.show_step()
        
        print(f"DEBUG: Selected Store {self.store_id}, Screen {self.screen_id}")
        print(f"DEBUG: Moving to step 4 (video playback)")
    
    def play_video(self):
        """Play video - SAME METHOD AS WEBPLAYER WITH SLICING"""
        try:
            # SAME AS WEBPLAYER: Use playlist endpoint with X-User-Code header
            headers = {'X-User-Code': self.code}
            playlist_url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            
            print(f"DEBUG: Getting playlist: {playlist_url}")
            print(f"DEBUG: Headers: {headers}")
            
            response = requests.get(playlist_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"DEBUG: Playlist error {response.status_code}: {response.text}")
                messagebox.showerror("Error", f"Cannot access playlist: {response.status_code}")
                return
            
            data = response.json()
            playlist = data.get('playlist', [])
            
            print(f"DEBUG: ===== INITIAL PLAYLIST LOAD =====")
            print(f"DEBUG: Got {len(playlist)} playlist items for {self.store_id}/{self.screen_id}")
            
            for i, item in enumerate(playlist):
                print(f"DEBUG: Item {i+1}: {item.get('file')} - Enabled: {item.get('enabled', True)}")
                print(f"DEBUG:   Duration: {item.get('duration', 10)}s, Start: {item.get('start')}, End: {item.get('end')}")
                print(f"DEBUG:   Days: {item.get('days', [])}")
                if item.get('sync_ref'):
                    print(f"DEBUG:   Sync: {item.get('sync_ref')}")
                if item.get('schedule'):
                    print(f"DEBUG:   Extra windows: {len(item.get('schedule', []))}")
            print(f"DEBUG: ===== END INITIAL LOAD =====")
            
            if not playlist:
                messagebox.showerror("Error", "No videos in playlist")
                return
            
            # Find currently scheduled video item instead of just taking first
            video_item = self.find_current_scheduled_item(playlist)
            
            if not video_item:
                print("DEBUG: No video scheduled now, will check again in 30 seconds")
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="⏳ Waiting for next scheduled video...", fg='#FFA500')
                # Auto-retry in 30 seconds
                self.root.after(30000, self.auto_play_next_scheduled)
                return
            
            video_file = video_item.get('file')
            
            if not video_file:
                messagebox.showerror("Error", "No video file found in scheduled item")
                return
            
            # Use the dedicated play_video_item method which handles everything
            print(f"DEBUG: Playing scheduled item: {video_file}")
            print(f"DEBUG: About to call play_video_item with duration: {video_item.get('duration', 10)}")
            self.play_video_item(video_item)
            
        except Exception as e:
            print(f"DEBUG: Error in play_video: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Error playing video: {str(e)}")
    
    def start_emergency_daemon(self):
        """Start emergency exit monitoring daemon"""
        def emergency_monitor():
            exit_file = "/tmp/pizza_hut_emergency_exit"
            pipe_file = "/tmp/pizza_hut_emergency_pipe"
            
            # Create named pipe for emergency commands
            try:
                os.mkfifo(pipe_file)
            except FileExistsError:
                pass
            
            print(f"DEBUG: Emergency daemon monitoring {exit_file} and {pipe_file}")
            
            while True:
                try:
                    # Method 1: Check for emergency exit file
                    if os.path.exists(exit_file):
                        print("DEBUG: Emergency exit file detected!")
                        self.root.after(0, self.emergency_stop)  # Thread-safe GUI update
                        os.remove(exit_file)
                    
                    # Method 2: Check named pipe for commands
                    try:
                        if os.path.exists(pipe_file):
                            with open(pipe_file, 'r', encoding='utf-8') as pipe:
                                # Use non-blocking read
                                import select
                                if select.select([pipe], [], [], 0.1)[0]:
                                    command = pipe.read().strip()
                                    if command == "EXIT":
                                        print("DEBUG: Emergency exit command received!")
                                        self.root.after(0, self.emergency_stop)
                                    elif command == "FULLSCREEN_OFF":
                                        print("DEBUG: Exit fullscreen command received!")
                                        self.root.after(0, self.exit_fullscreen_only)
                    except:
                        pass
                    
                    time.sleep(0.1)  # Check every 100ms
                    
                except Exception as e:
                    print(f"DEBUG: Emergency daemon error: {e}")
                    time.sleep(1)
        
        # Start daemon in background thread
        daemon_thread = threading.Thread(target=emergency_monitor, daemon=True)
        daemon_thread.start()
        
        # Also create emergency exit methods in shell
        self.create_emergency_scripts()
    
    def create_emergency_scripts(self):
        """Create emergency exit scripts users can run"""
        try:
            # Script 1: Simple emergency exit
            script1 = '''#!/bin/bash
echo "EMERGENCY EXIT TRIGGERED"
touch /tmp/pizza_hut_emergency_exit
echo "EXIT" > /tmp/pizza_hut_emergency_pipe
pkill -9 vlc
'''
            with open("/tmp/emergency_exit.sh", "w") as f:
                f.write(script1)
            os.chmod("/tmp/emergency_exit.sh", 0o755)
            
            # Script 2: Exit fullscreen only
            script2 = '''#!/bin/bash
echo "EXIT FULLSCREEN ONLY"
echo "FULLSCREEN_OFF" > /tmp/pizza_hut_emergency_pipe
'''
            with open("/tmp/exit_fullscreen.sh", "w") as f:
                f.write(script2)
            os.chmod("/tmp/exit_fullscreen.sh", 0o755)
            
            print("DEBUG: Emergency scripts created:")
            print("  /tmp/emergency_exit.sh - Full emergency exit")
            print("  /tmp/exit_fullscreen.sh - Exit fullscreen only")
            
        except Exception as e:
            print(f"DEBUG: Could not create emergency scripts: {e}")
    
    def exit_fullscreen_only(self):
        """Try to exit fullscreen without killing VLC"""
        print("DEBUG: Attempting to exit VLC fullscreen...")
        
        if self.vlc_process:
            try:
                # Try multiple methods to exit fullscreen
                subprocess.run(["xdotool", "search", "--name", "VLC", "key", "Escape"], check=False, timeout=2)
                subprocess.run(["xdotool", "search", "--name", "VLC", "key", "F11"], check=False, timeout=2)
                print("DEBUG: Sent fullscreen exit keys to VLC")
            except:
                print("DEBUG: Could not send keys to VLC")
    
    def handle_keypress(self, event):
        """Handle special key combinations for emergency exit"""
        key = event.keysym.lower()
        print(f"DEBUG: Key pressed: {key}")
        
        # Emergency exit keys - X, Escape, or Q to stop video
        if key in ['x', 'escape', 'q']:
            print(f"DEBUG: Emergency exit triggered by '{key}' key")
            self.emergency_stop()
            
    def emergency_stop(self):
        """Emergency stop VLC using multiple foolproof methods"""
        print("DEBUG: ===== EMERGENCY STOP ACTIVATED =====")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"DEBUG: Emergency stop at {timestamp}")
        
        # Method 1: Terminate our VLC process reference
        if self.vlc_process:
            try:
                print("DEBUG: Method 1 - Terminating tracked VLC process...")
                self.vlc_process.terminate()
                time.sleep(1)
                
                if self.vlc_process.poll() is None:
                    print("DEBUG: Force killing tracked VLC...")
                    self.vlc_process.kill()
                    time.sleep(0.5)
                    
                print("DEBUG: Tracked VLC process stopped")
            except Exception as e:
                print(f"DEBUG: Method 1 failed: {e}")
            finally:
                self.vlc_process = None
        
        # Method 2: System-wide VLC termination (most reliable)
        try:
            print("DEBUG: Method 2 - System-wide VLC termination...")
            subprocess.run(['pkill', '-9', 'vlc'], timeout=3, capture_output=True)
            print("DEBUG: All VLC processes terminated system-wide")
        except Exception as e:
            print(f"DEBUG: Method 2 failed: {e}")
        
        # Method 3: Kill VLC by name using killall
        try:
            print("DEBUG: Method 3 - killall VLC...")
            subprocess.run(['killall', '-9', 'vlc'], timeout=3, capture_output=True)
            print("DEBUG: killall VLC completed")
        except Exception as e:
            print(f"DEBUG: Method 3 failed: {e}")
        
        # Method 4: X11/GUI window termination
        try:
            print("DEBUG: Method 4 - Closing VLC windows...")
            subprocess.run(["xdotool", "search", "--name", "VLC", "windowkill"], timeout=3, capture_output=True)
            print("DEBUG: VLC windows closed")
        except Exception as e:
            print(f"DEBUG: Method 4 failed: {e}")
        
        # Method 5: Reset display state
        try:
            print("DEBUG: Method 5 - Resetting display...")
            subprocess.run(["xset", "dpms", "force", "on"], timeout=2, capture_output=True)
            print("DEBUG: Display reset")
        except Exception as e:
            print(f"DEBUG: Method 5 failed: {e}")
        
        print("DEBUG: ===== EMERGENCY STOP COMPLETE =====")
        print("DEBUG: Returning to GUI menu...")
        
        # Return focus to GUI and show status
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)  # Bring to front
        self.root.attributes('-topmost', False) # Remove always-on-top
        
        if hasattr(self, 'status_label'):
            self.status_label.config(text="✅ Video stopped - Ready for next action", fg='#90EE90')
        
        print("DEBUG: Emergency stop complete - GUI ready")
    
    def back_to_screens(self):
        """Stop video and go back to screen selection"""
        print("DEBUG: Going back to screen selection")
        
        # Stop any running video first
        self.emergency_stop()
        
        # Go back to step 3 (screen selection)
        self.current_step = 3
        self.show_step()
        
        print("DEBUG: Returned to screen selection")
    
    def schedule_monitor(self):
        """Continuously monitor for schedule changes and trigger smooth transitions when needed"""
        try:
            if not hasattr(self, 'current_scheduled_item'):
                self.current_scheduled_item = None
                
            # Get current playlist and determine what should be playing now
            headers = {
                'X-User-Code': self.code,
                'User-Agent': 'EA-TV-Pi-Client/1.0'
            }
            
            playlist_url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(playlist_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                playlist = data.get('playlist', [])
                
                # Find what should be playing now
                scheduled_item = self.find_current_scheduled_item(playlist)
                
                if scheduled_item:
                    scheduled_file = scheduled_item.get('file')
                    
                    # Check if we need to transition to a different item
                    current_file = getattr(self.current_scheduled_item, 'get', lambda x: None)('file') if self.current_scheduled_item else None
                    
                    if scheduled_file != current_file:
                        print(f"DEBUG: Schedule transition detected!")
                        print(f"DEBUG: Current: {current_file}")
                        print(f"DEBUG: Should be: {scheduled_file}")
                        
                        # Only transition if it's actually a different video
                        self.current_scheduled_item = scheduled_item
                        
                        # Use smooth crossfade transition instead of abrupt stop-start
                        print("DEBUG: Using crossfade transition for schedule change")
                        self.start_crossfade_transition(scheduled_item)
                        
                        # Update status
                        if hasattr(self, 'status_label'):
                            self.status_label.config(text=f"🔄 Crossfade to: {scheduled_file}", fg='#00BFFF')
                    else:
                        # Same item should be playing - check if we need to restart it
                        if not self.vlc_process or self.vlc_process.poll() is not None:
                            print(f"DEBUG: VLC not running, starting scheduled item with crossfade: {scheduled_file}")
                            self.current_scheduled_item = scheduled_item
                            # Use crossfade even for restarts to ensure smooth startup
                            self.start_crossfade_transition(scheduled_item)
                        else:
                            # VLC is running the correct video - leave it alone
                            print(f"DEBUG: Correct video playing: {scheduled_file}")
                            self.current_scheduled_item = scheduled_item
                            self.play_video_item(scheduled_item)
                else:
                    # No item scheduled - only stop if something is playing
                    if self.vlc_process and self.vlc_process.poll() is None:
                        print("DEBUG: No item scheduled - stopping current playback")
                        self.smooth_stop_playback()
                        
                    self.current_scheduled_item = None
                    if hasattr(self, 'status_label'):
                        self.status_label.config(text="⏳ Waiting for next scheduled video...", fg='#FFA500')
            
        except Exception as e:
            print(f"DEBUG: Schedule monitor error: {e}")
        
        # Schedule next check in 30 seconds
        self.root.after(30000, self.schedule_monitor)

    def smooth_transition_to_item(self, video_item):
        """Smoothly transition to a new video item using crossfade"""
        video_file = video_item.get('file')
        new_content_type = self.detect_content_type(video_item)
        
        # Determine current content type if we have something playing
        current_content_type = 'unknown'
        if hasattr(self, 'current_scheduled_item') and self.current_scheduled_item:
            current_content_type = self.detect_content_type(self.current_scheduled_item)
        
        print(f"DEBUG: ===== SMOOTH TRANSITION =====")
        print(f"DEBUG: From: {current_content_type} -> To: {new_content_type}")
        print(f"DEBUG: New file: {video_file}")
        print(f"DEBUG: ===========================")
        
        # If no VLC is running, just start normally
        if not self.vlc_process or self.vlc_process.poll() is not None:
            print("DEBUG: No VLC running, starting new content")
            self.play_video_item(video_item)
            return
        
        # Use crossfade transition for smooth change
        self.start_crossfade_transition(video_item)
    
    def start_optimized_content(self, video_item):
        """Start content with optimized VLC settings for minimal startup time"""
        try:
            video_file = video_item.get('file')
            
            # Get video URL
            slice_url = video_item.get('slice_url')
            if slice_url:
                if 'localhost' not in slice_url and '127.0.0.1' not in slice_url:
                    video_url = slice_url.replace('http:', 'https:')
                else:
                    video_url = slice_url
            else:
                video_url = video_item.get('url') or f"{self.server_url}/media/{video_file}"
            
            # Get content type and optimized VLC settings
            content_type = self.detect_content_type(video_item)
            item_duration = video_item.get('duration', 10)
            repeat = video_item.get('repeat', False)
            
            # Use comprehensive fullscreen VLC settings for all content types  
            if content_type == 'image':
                base_args = [
                    'vlc',
                    '--intf', 'dummy',
                    '--image-duration', str(item_duration),
                    '--loop' if repeat else '--play-and-exit'
                ]
            else:  # video
                if repeat:
                    # Repeating videos - loop forever
                    base_args = [
                        'vlc',
                        '--intf', 'dummy',
                        '--loop'
                    ]
                else:
                    # Non-repeating videos - play once and exit after duration
                    base_args = [
                        'vlc',
                        '--intf', 'dummy',
                        '--run-time', str(item_duration),
                        '--play-and-exit'
                    ]
            
            # Apply comprehensive fullscreen settings
            vlc_args = self.get_comprehensive_fullscreen_args(base_args, video_url)
            
            # Start VLC immediately with minimal delay
            self.vlc_process = subprocess.Popen(
                vlc_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            print(f"DEBUG: Optimized VLC started with PID: {self.vlc_process.pid} ({content_type})")
            
            # Update status immediately
            if hasattr(self, 'status_label'):
                content_icon = "🖼️" if content_type == 'image' else "🎬"
                loop_text = f" ({content_type} looping)" if repeat else f" ({content_type} {item_duration}s)"
                self.status_label.config(text=f"▶️ {content_icon} Playing: {video_file}{loop_text}", fg='#90EE90')
            
            # Schedule preemptive transition for non-repeating content to prevent gaps
            if not repeat:
                # Start transition 2 seconds before content ends to overlap with next content
                transition_delay = max(1000, int(item_duration * 1000 - 2000))  # At least 1s, but 2s before end
                print(f"DEBUG: Scheduling preemptive transition in {transition_delay}ms")
                self.root.after(transition_delay, self.force_next_item)
            
            # Start monitoring immediately
            self.root.after(1000, self.monitor_vlc)
            
        except Exception as e:
            print(f"DEBUG: Failed to start optimized content: {e}")
            # Final fallback
            self.play_video_item(video_item)
    
    def play_video_item_with_fade(self, video_item):
        """Play video/image with optimized startup for smooth transitions"""
        # Use the same optimized approach as smooth transitions
        self.start_optimized_content(video_item)
    
    def monitor_vlc(self):
        """Monitor VLC process and handle natural transitions"""
        if self.vlc_process:
            # Check if VLC is still running
            if self.vlc_process.poll() is not None:
                # VLC has exited naturally, handle transition
                print("DEBUG: VLC process has exited naturally")
                self.vlc_process = None
                
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="📺 Content ended, transitioning...", fg='#FFA500')
                
                # Check what should play next based on current schedule
                if hasattr(self, 'current_scheduled_item') and self.current_scheduled_item:
                    item = self.current_scheduled_item
                    
                    # Check if this same item should still be playing
                    if self.is_item_scheduled_now(item):
                        if item.get('repeat', False):
                            print("DEBUG: Restarting repeating content (natural end)")
                        else:
                            print("DEBUG: Non-repeating content ended, checking for next scheduled item")
                        
                        # Start the same item again (for repeating) or let schedule monitor handle it
                        self.play_video_item(item)
                        return
                
                # No specific item to restart - let schedule monitor handle what's next
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="⏰ Content ended, checking schedule...", fg='#FFA500')
                return
            
            # VLC is still running, schedule next check
            # Skip monitoring if we're in the middle of a crossfade
            if not hasattr(self, 'previous_vlc_process') or not self.previous_vlc_process:
                self.root.after(2000, self.monitor_vlc)
            else:
                # During crossfade, check more frequently
                self.root.after(500, self.monitor_vlc)
            
            # Make sure our GUI stays accessible
            try:
                self.root.lift()  # Bring GUI to front briefly
                self.root.after(100, lambda: self.root.lower())  # Then send it back
            except:
                pass
    
    def auto_play_next_scheduled(self):
        """Automatically play the next scheduled item"""
        try:
            print("DEBUG: Auto-playing next scheduled item...")
            
            # Refresh playlist to get current scheduled items
            headers = {
                'X-User-Code': self.code,
                'User-Agent': 'EA-TV-Pi-Client/1.0'
            }
            
            playlist_url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(playlist_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                playlist = data.get('playlist', [])
                
                print(f"DEBUG: ===== FULL PLAYLIST ANALYSIS =====")
                print(f"DEBUG: Total playlist items: {len(playlist)}")
                
                for i, item in enumerate(playlist):
                    print(f"DEBUG: --- Item {i+1} ---")
                    print(f"DEBUG: File: {item.get('file', 'NO FILE')}")
                    print(f"DEBUG: Enabled: {item.get('enabled', True)}")
                    print(f"DEBUG: Duration: {item.get('duration', 'NO DURATION')}")
                    print(f"DEBUG: Start time: {item.get('start', 'NO START')}")
                    print(f"DEBUG: End time: {item.get('end', 'NO END')}")
                    print(f"DEBUG: Days: {item.get('days', 'NO DAYS')}")
                    print(f"DEBUG: URL: {item.get('url', 'NO URL')}")
                    print(f"DEBUG: Slice URL: {item.get('slice_url', 'NO SLICE_URL')}")
                    print(f"DEBUG: Sync ref: {item.get('sync_ref', 'NO SYNC_REF')}")
                    
                    # Check additional schedule windows
                    schedule_windows = item.get('schedule', [])
                    if schedule_windows:
                        print(f"DEBUG: Additional schedule windows: {len(schedule_windows)}")
                        for j, window in enumerate(schedule_windows):
                            print(f"DEBUG:   Window {j+1}: {window}")
                    else:
                        print(f"DEBUG: No additional schedule windows")
                    print(f"DEBUG: ---")
                
                print(f"DEBUG: ===== END PLAYLIST ANALYSIS =====")
                
                if playlist:
                    # Find the currently scheduled item
                    current_item = self.find_current_scheduled_item(playlist)
                    
                    if current_item and current_item.get('file'):
                        print(f"DEBUG: Playing next scheduled item: {current_item.get('file')}")
                        self.play_video_item(current_item)
                        return
                
            # No scheduled item found - try again in 30 seconds
            print("DEBUG: No scheduled item found - will retry in 30 seconds")
            if hasattr(self, 'status_label'):
                self.status_label.config(text="⏳ Waiting for next scheduled video...", fg='#FFA500')
            self.root.after(30000, self.auto_play_next_scheduled)
            
        except Exception as e:
            print(f"DEBUG: Error in auto_play_next_scheduled: {e}")
            # Retry in 30 seconds on error
            self.root.after(30000, self.auto_play_next_scheduled)
    
    def find_current_scheduled_item(self, playlist):
        """Find the item that should be playing now based on schedule rules"""
        from datetime import datetime
        
        # Rule 1: Enabled switch is required - disabled items are ignored everywhere
        enabled_items = [item for item in playlist if item.get('enabled', True)]
        
        if not enabled_items:
            print("DEBUG: No enabled items in playlist")
            return None
        
        # Rule 2: Check for items currently in scheduled windows
        scheduled_items = []
        for item in enabled_items:
            if self.is_item_scheduled_now(item):
                scheduled_items.append(item)
        
        # Rule 3: Rotation selection
        if scheduled_items:
            # At least one item is in a scheduled window - only rotate among scheduled items
            print(f"DEBUG: {len(scheduled_items)} items currently in scheduled windows")
            return self.rotate_through_items(scheduled_items)
        else:
            # No items scheduled right now - fall back to enabled items with repeat=true
            repeat_items = [item for item in enabled_items if item.get('repeat', False)]
            if repeat_items:
                print(f"DEBUG: No scheduled items - falling back to {len(repeat_items)} repeat items")
                return self.rotate_through_items(repeat_items)
            else:
                print("DEBUG: No scheduled items and no repeat items available")
                return None
    
    def rotate_through_items(self, items):
        """Rotate through items based on their durations"""
        from datetime import datetime
        
        if not items:
            return None
            
        if len(items) == 1:
            print(f"DEBUG: Only one item to rotate: {items[0].get('file')}")
            return items[0]
            
        # Multiple items - rotate based on durations
        now = datetime.now()
        
        # Reset cycle tracking if needed
        if self.playlist_start_time is None:
            self.playlist_start_time = now
            self.current_item_index = 0
            
        # Calculate total cycle time (sum of all durations)
        total_cycle_seconds = sum(item.get('duration', 10) for item in items)
        
        # Calculate current position within the cycle
        elapsed_seconds = (now - self.playlist_start_time).total_seconds()
        cycle_position = elapsed_seconds % total_cycle_seconds
        
        # Find which item should be playing at this cycle position
        cumulative_time = 0
        for i, item in enumerate(items):
            item_duration = item.get('duration', 10)
            if cycle_position < cumulative_time + item_duration:
                print(f"DEBUG: Cycle position {cycle_position:.1f}s -> Item {i}: {item.get('file')} (duration: {item_duration}s)")
                return item
            cumulative_time += item_duration
            
        # Fallback - should not happen, but return first item
        print(f"DEBUG: Fallback to first item: {items[0].get('file')}")
        return items[0]
    
    def is_item_scheduled_now(self, item):
        """Check if an item should be playing right now"""
        from datetime import datetime
        
        now = datetime.now()
        current_time = now.time()
        current_weekday = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][now.weekday()]
        
        print(f"DEBUG: Checking schedule for {item.get('file')} - Current time: {current_time}, Weekday: {current_weekday}")
        
        # Check primary schedule
        if self.check_time_window(item, current_time, current_weekday):
            print(f"DEBUG: Item {item.get('file')} matches primary schedule window")
            return True
            
        # Check additional schedule windows
        schedule_windows = item.get('schedule', [])
        for window in schedule_windows:
            if window.get('sync_master'):  # Skip sync indicators
                continue
            if self.check_schedule_window(window, current_time, current_weekday):
                print(f"DEBUG: Item {item.get('file')} matches additional schedule window")
                return True
        
        print(f"DEBUG: Item {item.get('file')} is NOT currently scheduled")
        return False
    
    def check_time_window(self, item, current_time, current_weekday):
        """Check if current time falls within item's primary time window according to scheduling rules"""
        from datetime import datetime, date
        
        start_time = item.get('start')
        end_time = item.get('end')
        days = item.get('days', [])
        
        print(f"DEBUG: Time window check - start: {start_time}, end: {end_time}, days: {days}")
        
        # If no time restrictions, item is always active
        if not start_time and not end_time and not days:
            print("DEBUG: No time restrictions - item is always active")
            return True
        
        # Check if this is a dated interval (contains YYYY-MM-DD)
        has_date_in_start = start_time and len(start_time) > 8 and '-' in start_time
        has_date_in_end = end_time and len(end_time) > 8 and '-' in end_time
        
        if has_date_in_start or has_date_in_end:
            print("DEBUG: Detected dated interval - treating as one-off absolute interval")
            return self.check_dated_interval(start_time, end_time, datetime.now())
        
        # Time-only scheduling with weekdays (repeating weekly)
        print("DEBUG: Time-only scheduling with potential weekday repeats")
        
        # Check weekday restrictions first
        if days and current_weekday not in days:
            print(f"DEBUG: Current weekday {current_weekday} not in allowed days {days}")
            return False
            
        # If only days are specified but no times, check day only
        if days and not start_time and not end_time:
            print(f"DEBUG: Only day restriction - current weekday {current_weekday} {'in' if current_weekday in days else 'not in'} {days}")
            return current_weekday in days
        
        # Parse time-only strings (HH:MM:SS format)
        return self.check_time_only_range(start_time, end_time, current_time)
    
    def check_dated_interval(self, start_time, end_time, current_datetime):
        """Handle one-off dated intervals (YYYY-MM-DD with or without time)"""
        from datetime import datetime, time
        
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        
        # Parse start datetime
        start_dt = None
        if start_time:
            if 'T' in start_time or ' ' in start_time:
                # Full datetime
                try:
                    start_dt = datetime.fromisoformat(start_time.replace('T', ' '))
                except:
                    try:
                        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                    except:
                        start_dt = None
            else:
                # Date only - normalize to 00:00:00
                try:
                    start_date = datetime.strptime(start_time, '%Y-%m-%d').date()
                    start_dt = datetime.combine(start_date, time(0, 0, 0))
                except:
                    start_dt = None
        
        # Parse end datetime
        end_dt = None
        if end_time:
            if 'T' in end_time or ' ' in end_time:
                # Full datetime
                try:
                    end_dt = datetime.fromisoformat(end_time.replace('T', ' '))
                except:
                    try:
                        end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                    except:
                        end_dt = None
            else:
                # Date only - normalize to 23:59:59
                try:
                    end_date = datetime.strptime(end_time, '%Y-%m-%d').date()
                    end_dt = datetime.combine(end_date, time(23, 59, 59))
                except:
                    end_dt = None
        
        # Date-only normalization rules
        if start_dt and not end_dt and len(start_time) == 10:  # Date only start
            # Start=YYYY-MM-DD with no end → active from 00:00 to 23:59:59 on that date
            end_dt = datetime.combine(start_dt.date(), time(23, 59, 59))
            
        if end_dt and not start_dt and len(end_time) == 10:  # Date only end
            # End=YYYY-MM-DD with no start → active from 00:00 to 23:59:59 on that date  
            start_dt = datetime.combine(end_dt.date(), time(0, 0, 0))
        
        # Handle same date with end < start (spans to next day)
        if start_dt and end_dt and start_dt.date() == end_dt.date() and end_dt.time() < start_dt.time():
            print("DEBUG: Same date with end < start - treating as continuous one-off window spanning to next day")
            # Current implementation: check if we're after start OR before end (next day)
            return current_datetime >= start_dt or (current_date == start_dt.date() and current_time <= end_dt.time())
        
        # Normal datetime range check
        if start_dt and end_dt:
            return start_dt <= current_datetime <= end_dt
        elif start_dt:
            return current_datetime >= start_dt
        elif end_dt:
            return current_datetime <= end_dt
            
        return True
    
    def check_time_only_range(self, start_time, end_time, current_time):
        """Check time-only range (HH:MM:SS format) for weekly repeating"""
        # Parse time strings (HH:MM:SS format)
        start_time_obj = None
        if start_time:
            try:
                start_parts = start_time.split(':')
                start_hour, start_min = int(start_parts[0]), int(start_parts[1])
                start_sec = int(start_parts[2]) if len(start_parts) > 2 else 0
                start_time_obj = current_time.replace(hour=start_hour, minute=start_min, second=start_sec, microsecond=0)
            except:
                start_time_obj = None
        
        end_time_obj = None        
        if end_time:
            try:
                end_parts = end_time.split(':')
                end_hour, end_min = int(end_parts[0]), int(end_parts[1])
                end_sec = int(end_parts[2]) if len(end_parts) > 2 else 0
                end_time_obj = current_time.replace(hour=end_hour, minute=end_min, second=end_sec, microsecond=0)
            except:
                end_time_obj = None
        
        # Check if current time is in window
        if start_time_obj and end_time_obj:
            if start_time_obj <= end_time_obj:
                # Normal time range (e.g., 9:00 to 17:00)
                return start_time_obj <= current_time <= end_time_obj
            else:
                # Overnight time range (e.g., 22:00 to 6:00)
                return current_time >= start_time_obj or current_time <= end_time_obj
        elif start_time_obj:
            # Only start time specified
            return current_time >= start_time_obj
        elif end_time_obj:
            # Only end time specified  
            return current_time <= end_time_obj
        
        return True
    
    def check_schedule_window(self, window, current_time, current_weekday):
        """Check if current time falls within a schedule window using the same rules as primary windows"""
        from datetime import datetime
        
        start_time = window.get('start')
        end_time = window.get('end')
        days = window.get('days', [])
        enabled = window.get('enabled', True)
        
        print(f"DEBUG: Checking schedule window - enabled: {enabled}, start: {start_time}, end: {end_time}, days: {days}")
        
        if not enabled:
            print("DEBUG: Schedule window is disabled")
            return False
        
        # Use the same logic as primary time window
        # Create a temporary item-like object to reuse the logic
        temp_item = {
            'start': start_time,
            'end': end_time, 
            'days': days
        }
        
        return self.check_time_window(temp_item, current_time, current_weekday)
    
    
    def detect_content_type(self, video_item):
        """Detect if the item is a video or image based on file extension"""
        video_file = video_item.get('file', '')
        
        # Common image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        # Common video extensions  
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        
        file_lower = video_file.lower()
        
        for ext in image_extensions:
            if file_lower.endswith(ext):
                return 'image'
                
        for ext in video_extensions:
            if file_lower.endswith(ext):
                return 'video'
        
        # Default to video for unknown extensions
        return 'video'
    
    def get_comprehensive_fullscreen_args(self, base_args, video_url):
        """Get comprehensive fullscreen VLC arguments that work for all content types"""
        return base_args + [
            '--fullscreen',
            '--no-video-title-show',
            '--no-osd',
            '--no-video-deco', 
            '--no-embedded-video',
            '--video-on-top',
            '--no-video-title',
            '--disable-screensaver',
            '--no-snapshot-preview',
            '--no-audio',  # Disable audio for TV displays
            video_url
        ]
    
    def get_vlc_args_for_content(self, video_item, video_url):
        """Get appropriate VLC arguments based on content type with comprehensive fullscreen"""
        content_type = self.detect_content_type(video_item)
        item_duration = video_item.get('duration', 10)
        repeat = video_item.get('repeat', False)
        
        print(f"DEBUG: Content type detected: {content_type}")
        print(f"DEBUG: Duration: {item_duration}s, Repeat: {repeat}")
        
        if content_type == 'image':
            # Images need special handling with duration
            if repeat:
                print("DEBUG: Image will loop indefinitely until schedule changes")
                base_args = [
                    'vlc',
                    '--intf', 'dummy',
                    '--image-duration', str(item_duration),
                    '--loop'
                ]
            else:
                print(f"DEBUG: Image will display for {item_duration}s then exit")
                base_args = [
                    'vlc', 
                    '--intf', 'dummy',
                    '--image-duration', str(item_duration),
                    '--play-and-exit'
                ]
        else:
            # Videos - respect duration and repeat settings
            if repeat:
                print("DEBUG: Video will loop indefinitely until schedule changes")
                base_args = [
                    'vlc',
                    '--intf', 'dummy',
                    '--loop'
                ]
            else:
                print(f"DEBUG: Video will play for {item_duration}s then stop")
                base_args = [
                    'vlc',
                    '--intf', 'dummy',
                    '--run-time', str(item_duration),
                    '--play-and-exit'
                ]
        
        # Apply comprehensive fullscreen settings to all content
        return self.get_comprehensive_fullscreen_args(base_args, video_url), content_type

    def play_video_item(self, video_item):
        """Play a specific video item with proper slice URL handling and schedule-aware duration"""
        video_file = video_item.get('file')
        item_duration = video_item.get('duration', 10)  # Get item duration
        repeat = video_item.get('repeat', False)  # Check if item should repeat
        
        print(f"DEBUG: ===== PLAYING VIDEO ITEM =====")
        print(f"DEBUG: File: {video_file}")
        print(f"DEBUG: Item Duration: {item_duration} seconds")
        print(f"DEBUG: Repeat: {repeat}")
        print(f"DEBUG: Item data: {video_item}")
        print(f"DEBUG: ===== END VIDEO ITEM INFO =====")

        if not video_file:
            print("DEBUG: No video file found in item")
            return
            
        sync_ref = video_item.get('sync_ref', {})
        
        # EXACT WEBPLAYER LOGIC: Check for slice_url first
        slice_url = video_item.get('slice_url')
        if slice_url:
            # Use server-provided slice URL (already contains correct slice)
            if 'localhost' not in slice_url and '127.0.0.1' not in slice_url:
                video_url = slice_url.replace('http:', 'https:')
            else:
                video_url = slice_url
            print(f"DEBUG: Using server slice_url: {video_url}")
        else:
            # Fallback: Use url or file field with /media/ endpoint
            video_url = video_item.get('url') or f"{self.server_url}/media/{video_file}"
            print(f"DEBUG: Using fallback URL: {video_url}")
        
        # Get appropriate VLC configuration for the content type
        vlc_args, content_type = self.get_vlc_args_for_content(video_item, video_url)
        
        # Determine force stop timing based on content type
        if content_type == 'image' and not repeat:
            # Images should transition after their duration
            force_stop_delay = int(item_duration * 1000 + 1000)  # +1s buffer for images
            print(f"DEBUG: Image will display for {item_duration}s + 1s buffer")
        elif content_type == 'video' and not repeat:
            # Videos get longer cycles to reduce restarts 
            force_stop_delay = int(item_duration * 1000 * 3)  # Check every 3 cycles
            print(f"DEBUG: Video will repeat in cycles to reduce restarts")
        else:
            # Repeating content - no forced stop
            force_stop_delay = None
            print(f"DEBUG: {content_type.title()} will loop indefinitely until schedule changes")
        
        try:
            self.vlc_process = subprocess.Popen(
                vlc_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            print(f"DEBUG: VLC started with PID: {self.vlc_process.pid}")
            print(f"DEBUG: Content type: {content_type}")
            
            # Update status with content type info
            if hasattr(self, 'status_label'):
                if content_type == 'image':
                    if repeat:
                        loop_text = f" (image looping every {item_duration}s)"
                    else:
                        loop_text = f" (image {item_duration}s)"
                else:  # video
                    if repeat:
                        loop_text = " (video looping)"
                    else:
                        loop_text = f" (video cycles)"
                
                content_icon = "🖼️" if content_type == 'image' else "🎬"
                self.status_label.config(text=f"▶️ {content_icon} Playing: {video_file}{loop_text}", fg='#90EE90')
            
            # Schedule checks less frequently to reduce restarts
            if force_stop_delay:
                self.root.after(force_stop_delay, self.force_next_item)
            
            # Start monitoring
            self.root.after(2000, self.monitor_vlc)
            
        except Exception as e:
            print(f"DEBUG: Failed to start VLC: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"❌ Video failed: {e}", fg='#FF6B6B')
    
    def force_next_item(self):
        """Force transition to next item after duration expires with crossfade transition"""
        print("DEBUG: Content duration expired, starting crossfade to next item")
        
        # Get the next scheduled item immediately instead of waiting
        try:
            headers = {
                'X-User-Code': self.code,
                'User-Agent': 'EA-TV-Pi-Client/1.0'
            }
            
            playlist_url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(playlist_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                playlist = data.get('playlist', [])
                
                # Find what should be playing now
                next_item = self.find_current_scheduled_item(playlist)
                
                if next_item:
                    # Start crossfade transition to next item
                    print(f"DEBUG: Starting crossfade to: {next_item.get('file')}")
                    self.start_crossfade_transition(next_item)
                    return
                    
        except Exception as e:
            print(f"DEBUG: Error getting next item for crossfade: {e}")
        
        # Fallback - just stop current and let schedule monitor handle it
        if self.vlc_process and self.vlc_process.poll() is None:
            print("DEBUG: Fallback - stopping current VLC")
            try:
                self.vlc_process.terminate()
                self.vlc_process.wait(timeout=2)
            except:
                try:
                    self.vlc_process.kill()
                except:
                    pass
            self.vlc_process = None
            
        if hasattr(self, 'status_label'):
            self.status_label.config(text="⏰ Duration complete, checking schedule...", fg='#FFA500')
    
    def start_crossfade_transition(self, next_item):
        """Start crossfade transition by starting next content while current fades out"""
        try:
            video_file = next_item.get('file')
            print(f"DEBUG: ===== CROSSFADE TRANSITION =====")
            print(f"DEBUG: Starting next content: {video_file}")
            
            # If no VLC is currently running, just start the new content normally
            if not self.vlc_process or self.vlc_process.poll() is not None:
                print("DEBUG: No VLC running - starting new content directly")
                self.play_video_item(next_item)
                return
                
            print(f"DEBUG: Current VLC running - starting crossfade")
            
            # Get URL for next content
            slice_url = next_item.get('slice_url')
            if slice_url:
                if 'localhost' not in slice_url and '127.0.0.1' not in slice_url:
                    video_url = slice_url.replace('http:', 'https:')
                else:
                    video_url = slice_url
            else:
                video_url = next_item.get('url') or f"{self.server_url}/media/{video_file}"
            
            # Get content type and settings
            content_type = self.detect_content_type(next_item)
            item_duration = next_item.get('duration', 10)
            repeat = next_item.get('repeat', False)
            
            # Prepare VLC args for next content with fade-in using comprehensive fullscreen settings
            base_args = self.get_comprehensive_fullscreen_args()
            
            if content_type == 'image':
                vlc_args = [
                    'vlc',
                    '--intf', 'dummy'
                ] + base_args + [
                    '--image-duration', str(item_duration),
                    '--video-filter', 'fade',
                    '--fade-in', '1',  # 1 second fade in
                    '--loop' if repeat else '--play-and-exit',
                    video_url
                ]
            else:  # video
                if repeat:
                    # Repeating videos with crossfade
                    vlc_args = [
                        'vlc',
                        '--intf', 'dummy'
                    ] + base_args + [
                        '--video-filter', 'fade',
                        '--fade-in', '1',  # 1 second fade in
                        '--loop',
                        video_url
                    ]
                else:
                    # Non-repeating videos with crossfade - respect duration
                    vlc_args = [
                        'vlc',
                        '--intf', 'dummy'
                    ] + base_args + [
                        '--video-filter', 'fade',
                        '--fade-in', '1',  # 1 second fade in
                        '--run-time', str(item_duration),
                        '--play-and-exit',
                        video_url
                    ]
            
            # Start new VLC process
            new_vlc_process = subprocess.Popen(
                vlc_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            print(f"DEBUG: New VLC started with PID: {new_vlc_process.pid} ({content_type})")
            
            # Update current item
            self.current_scheduled_item = next_item
            
            # Schedule fade-out of old VLC after brief overlap
            if self.vlc_process and self.vlc_process.poll() is None:
                print("DEBUG: Scheduling fade-out of current content")
                self.root.after(1000, lambda: self.fade_out_previous_content(self.vlc_process))
            
            # Switch to new VLC process
            self.vlc_process = new_vlc_process
            
            # Update status
            if hasattr(self, 'status_label'):
                content_icon = "🖼️" if content_type == 'image' else "🎬"
                duration_text = f" ({item_duration}s)" if not repeat else " (looping)"
                self.status_label.config(text=f"🔄 {content_icon} Crossfade: {video_file}{duration_text}", fg='#00BFFF')
            
            # Schedule force transition for non-repeating content
            if not repeat:
                force_delay = int(item_duration * 1000 - 2000)  # Start transition 2s before end
                if force_delay > 0:
                    self.root.after(force_delay, self.force_next_item)
            
            # Start monitoring new VLC
            self.root.after(1000, self.monitor_vlc)
            
        except Exception as e:
            print(f"DEBUG: Crossfade transition failed: {e}")
            # Fallback to simple transition
            self.smooth_transition_to_item(next_item)
    
    def fade_out_previous_content(self, old_vlc_process):
        """Gently terminate the previous VLC process after crossfade"""
        if old_vlc_process and old_vlc_process.poll() is None:
            try:
                print("DEBUG: Fading out previous content")
                old_vlc_process.terminate()
                # Give it a moment to terminate gracefully
                import threading
                threading.Timer(1.0, lambda: old_vlc_process.kill() if old_vlc_process.poll() is None else None).start()
            except Exception as e:
                print(f"DEBUG: Error fading out previous content: {e}")
                try:
                    old_vlc_process.kill()
                except:
                    pass
    
    def test_schedule_logic(self):
        """Test function to verify schedule logic is working"""
        from datetime import datetime
        
        print("DEBUG: ===== TESTING SCHEDULE LOGIC =====")
        now = datetime.now()
        current_time = now.time()
        current_weekday = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][now.weekday()]
        
        print(f"DEBUG: Current time: {current_time}")
        print(f"DEBUG: Current weekday: {current_weekday}")
        
        # Test different schedule scenarios
        test_items = [
            {
                'file': 'always_active.mp4',
                'enabled': True,
                'duration': 10,
                # No schedule restrictions - should always be active
            },
            {
                'file': 'today_only.mp4', 
                'enabled': True,
                'duration': 15,
                'days': [current_weekday]  # Only today
            },
            {
                'file': 'wrong_day.mp4',
                'enabled': True, 
                'duration': 20,
                'days': ['xyz']  # Invalid day - should never be active
            },
            {
                'file': 'disabled.mp4',
                'enabled': False,  # Disabled - should never be active
                'duration': 25
            }
        ]
        
        print("DEBUG: Testing schedule items:")
        for i, item in enumerate(test_items):
            is_scheduled = self.is_item_scheduled_now(item)
            print(f"DEBUG: Item {i+1} '{item['file']}' -> Scheduled: {is_scheduled}")
            
        print("DEBUG: ===== END SCHEDULE TEST =====")
    
    def stop_video(self):
        """Stop video playback"""
        if self.vlc_process:
            try:
                self.vlc_process.terminate()
            except:
                pass
        
        try:
            subprocess.run(['pkill', 'vlc'], capture_output=True)
        except:
            pass
        
        self.vlc_process = None
        self.status_label.config(text="Video stopped")

def main():
    def signal_handler(signum, frame):
        print("\nShutting down...")
        try:
            subprocess.run(['pkill', 'vlc'], capture_output=True)
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Pizza Hut TV - Pi Client (Webplayer Clone)")
    print("==========================================")
    print("Exact same flow as webplayer:")
    print("1. Enter 4-digit TV code")
    print("2. Enter store code")
    print("3. Choose screen")
    print("4. Play video")
    print()
    
    root = tk.Tk()
    app = EATVWebplayerClone(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()