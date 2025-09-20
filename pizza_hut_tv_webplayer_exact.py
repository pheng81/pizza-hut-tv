#!/usr/bin/env python3
"""
Pizza Hut TV - Pi Client (EXACT WEBPLAYER REPLICA)
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

class PizzaHutTVWebplayerClone:
    def __init__(self, root):
        self.root = root
        self.root.title("Pizza Hut TV - Screen Control")
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
        
        self.current_step = 1
        
        # Start emergency exit daemon
        self.start_emergency_daemon()
        
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
            
            print(f"DEBUG: Got {len(playlist)} playlist items")
            
            if not playlist:
                messagebox.showerror("Error", "No videos in playlist")
                return
            
            # Get first video file and sync reference
            video_item = playlist[0]
            video_file = video_item.get('file')
            sync_ref = video_item.get('sync_ref', {})
            
            if not video_file:
                messagebox.showerror("Error", "No video file found")
                return
            
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
            
            # Extract screen order for slicing (SAME AS WEBPLAYER LOGIC)
            api_order = int(sync_ref.get('order', 0))  # API-provided order
            
            # BACKUP: Extract screen number from screen_id if API order seems wrong
            screen_number = 1  # default
            if '_screen' in self.screen_id:
                try:
                    screen_number = int(self.screen_id.split('_screen')[1])
                except:
                    screen_number = 1
            
            # Use API order if available, otherwise calculate from screen number
            if api_order >= 0 and 'order' in sync_ref:
                order = api_order
                print(f"DEBUG: Using API order: {order}")
            else:
                order = screen_number - 1  # Convert screen 1,2,3 to order 0,1,2
                print(f"DEBUG: Calculated order from screen {screen_number}: {order}")
            
            total_screens = 3  # Pizza Hut TV uses 3 screens
            
            print(f"DEBUG: Screen order: {order}, Total screens: {total_screens}")
            print(f"DEBUG: Video file: {video_file}")
            print(f"DEBUG: Playing video: {video_url}")
            
            # IMPLEMENT PROPER VIDEO SLICING for multi-screen resolutions
            # Detect video resolution and calculate proper slicing
            
            # Get video dimensions from playlist metadata or use defaults
            horizontal = video_item.get('horizontal', True)
            
            if horizontal:
                # Horizontal videos: 1920x1080, 3840x1080, 5760x1080, 7680x1080, 9600x1080
                screen_width = 1920
                screen_height = 1080
                
                # Determine total screens based on video width or sync_ref
                total_width_options = {
                    1920: 1,   # 1 screen
                    3840: 2,   # 2 screens
                    5760: 3,   # 3 screens 
                    7680: 4,   # 4 screens
                    9600: 5    # 5 screens
                }
                
                # Default to 3 screens if not specified
                total_screens = 3
                
            else:
                # Vertical videos: 1080x1920, 1080x3840, 1080x5760, 1080x7680, 1080x9600
                screen_width = 1080
                screen_height = 1920
                
                # For vertical, screens are stacked vertically
                total_height_options = {
                    1920: 1,   # 1 screen
                    3840: 2,   # 2 screens
                    5760: 3,   # 3 screens
                    7680: 4,   # 4 screens 
                    9600: 5    # 5 screens
                }
                
                total_screens = 3
            
            print(f"DEBUG: Video orientation: {'Horizontal' if horizontal else 'Vertical'}")
            print(f"DEBUG: Screen order: {order}, Total screens: {total_screens}")
            print(f"DEBUG: Video file: {video_file}")
            print(f"DEBUG: Using server slice URL: {video_url}")
            
            self.status_label.config(text=f"Playing Screen {order+1} - Server handles slicing")
            
            # Simple VLC launch - server slice URL handles everything
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
            
            print(f"DEBUG: VLC command - using server slice URL:")
            print(f"DEBUG: {' '.join(vlc_args)}")
            print(f"DEBUG: EMERGENCY EXIT METHODS:")
            print(f"DEBUG: - Press X key in GUI window")
            print(f"DEBUG: - Run: touch /tmp/pizza_hut_emergency_exit") 
            print(f"DEBUG: - SSH: pkill vlc")
            
            self.vlc_process = subprocess.Popen(vlc_args)
            
            # Start monitoring and emergency daemon
            self.root.after(2000, self.monitor_vlc)
            
            print(f"DEBUG: VLC started - server slice URL should show correct portion!")
            
        except Exception as e:
            print(f"DEBUG: Error: {e}")
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
    
    def monitor_vlc(self):
        """Monitor VLC process and provide escape options"""
        if self.vlc_process:
            # Check if VLC is still running
            if self.vlc_process.poll() is not None:
                # VLC has exited, clean up
                print("DEBUG: VLC process has exited")
                self.vlc_process = None
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="✅ Video finished - Ready for next action", fg='#90EE90')
                return
            
            # VLC is still running, schedule next check
            self.root.after(2000, self.monitor_vlc)
            
            # Make sure our GUI stays accessible
            try:
                self.root.lift()  # Bring GUI to front briefly
                self.root.after(100, lambda: self.root.lower())  # Then send it back
            except:
                pass
    
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
    app = PizzaHutTVWebplayerClone(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()