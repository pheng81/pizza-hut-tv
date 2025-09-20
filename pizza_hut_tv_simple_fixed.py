#!/usr/bin/env python3
"""
Pizza Hut TV - Pi GUI Client (Simple Layout, Working Video)
Uses /media/ endpoint like webplayer
"""

import tkinter as tk
from tkinter import messagebox
import requests
import json
import subprocess
import os
import signal
import sys

class PizzaHutTVApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pizza Hut TV - Screen Control")
        self.root.geometry("800x600")
        self.root.configure(bg='#0b0b0b')  # Dark background like webplayer
        
        # Server configuration
        self.server_url = "http://everydayadvertise.com"
        
        # Authentication state
        self.link_code = ""
        self.username = ""
        self.store_code = ""
        self.screen_id = ""
        self.current_step = "link_code"
        self.screen_data = {}  # Store screen information
        self.vlc_process = None
        
        # Fullscreen state
        self.is_fullscreen = False
        
        self.create_widgets()
        self.show_current_step()
        
        # Keyboard bindings
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)
        self.root.focus_set()
        
    def create_widgets(self):
        # Main container
        self.main_frame = tk.Frame(self.root, bg='#0b0b0b')
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(self.main_frame, 
                              text="Pizza Hut TV Screen Control", 
                              font=('Arial', 24, 'bold'), 
                              fg='#c8102e',  # Pizza Hut red
                              bg='#0b0b0b')
        title_label.pack(pady=(0, 30))
        
        # Step 1: Link Code Input
        self.step1_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=20, pady=20)
        
        link_label = tk.Label(self.step1_frame, 
                             text="Enter 4-digit link code:", 
                             font=('Arial', 14),
                             fg='white', bg='#0d0d0d')
        link_label.pack(pady=(0, 10))
        
        self.link_entry = tk.Entry(self.step1_frame, 
                                  font=('Arial', 16),
                                  width=10,
                                  justify='center',
                                  bg='#333333',
                                  fg='white',
                                  insertbackground='white')
        self.link_entry.pack(pady=(0, 15))
        self.link_entry.bind('<Return>', lambda e: self.submit_link_code())
        
        self.link_button = tk.Button(self.step1_frame,
                                    text="Submit",
                                    font=('Arial', 12, 'bold'),
                                    bg='#c8102e',
                                    fg='white',
                                    padx=30,
                                    pady=10,
                                    command=self.submit_link_code)
        self.link_button.pack()
        
        # Step 2: Store Code Input
        self.step2_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=20, pady=20)
        
        store_label = tk.Label(self.step2_frame, 
                              text="Enter store code:", 
                              font=('Arial', 14),
                              fg='white', bg='#0d0d0d')
        store_label.pack(pady=(0, 10))
        
        self.store_entry = tk.Entry(self.step2_frame, 
                                   font=('Arial', 16),
                                   width=10,
                                   justify='center',
                                   bg='#333333',
                                   fg='white',
                                   insertbackground='white')
        self.store_entry.pack(pady=(0, 15))
        self.store_entry.bind('<Return>', lambda e: self.submit_store_code())
        
        self.store_button = tk.Button(self.step2_frame,
                                     text="Get Screens",
                                     font=('Arial', 12, 'bold'),
                                     bg='#c8102e',
                                     fg='white',
                                     padx=30,
                                     pady=10,
                                     command=self.submit_store_code)
        self.store_button.pack()
        
        # Step 3: Screen Selection
        self.step3_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=20, pady=20)
        
        screen_label = tk.Label(self.step3_frame, 
                               text="Select screen:", 
                               font=('Arial', 14),
                               fg='white', bg='#0d0d0d')
        screen_label.pack(pady=(0, 15))
        
        self.screens_container = tk.Frame(self.step3_frame, bg='#0d0d0d')
        self.screens_container.pack()
        
        # Step 4: Video Control
        self.step4_frame = tk.Frame(self.main_frame, bg='#0d0d0d', padx=20, pady=20)
        
        control_label = tk.Label(self.step4_frame, 
                                text="Video Control:", 
                                font=('Arial', 14),
                                fg='white', bg='#0d0d0d')
        control_label.pack(pady=(0, 15))
        
        button_frame = tk.Frame(self.step4_frame, bg='#0d0d0d')
        button_frame.pack()
        
        self.play_button = tk.Button(button_frame,
                                    text="Play Video",
                                    font=('Arial', 12, 'bold'),
                                    bg='#c8102e',
                                    fg='white',
                                    padx=20,
                                    pady=10,
                                    command=self.play_video)
        self.play_button.pack(side='left', padx=(0, 10))
        
        self.stop_button = tk.Button(button_frame,
                                    text="Stop Video",
                                    font=('Arial', 12, 'bold'),
                                    bg='#666666',
                                    fg='white',
                                    padx=20,
                                    pady=10,
                                    command=self.stop_video)
        self.stop_button.pack(side='left')
        
        # Status label
        self.status_label = tk.Label(self.main_frame,
                                    text="Enter 4-digit link code to start",
                                    font=('Arial', 12),
                                    fg='#888888',
                                    bg='#0b0b0b')
        self.status_label.pack(pady=(20, 0))
        
    def show_current_step(self):
        """Show only the current step"""
        # Hide all frames
        self.step1_frame.pack_forget()
        self.step2_frame.pack_forget()
        self.step3_frame.pack_forget()
        self.step4_frame.pack_forget()
        
        # Show current step
        if self.current_step == "link_code":
            self.step1_frame.pack(fill='x', pady=10)
            self.link_entry.focus_set()
        elif self.current_step == "store_code":
            self.step2_frame.pack(fill='x', pady=10)
            self.store_entry.focus_set()
        elif self.current_step == "screen_select":
            self.step3_frame.pack(fill='x', pady=10)
        elif self.current_step == "video_control":
            self.step4_frame.pack(fill='x', pady=10)
    
    def submit_link_code(self):
        """Submit the 4-digit link code"""
        self.link_code = self.link_entry.get().strip()
        if not self.link_code:
            messagebox.showerror("Error", "Please enter a link code")
            return
        
        try:
            self.status_label.config(text="Checking link code...")
            response = requests.get(f"{self.server_url}/api/stores_by_code/{self.link_code}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('stores'):
                    self.status_label.config(text="Link code valid. Enter store code.")
                    self.current_step = "store_code"
                    self.show_current_step()
                else:
                    self.status_label.config(text="Invalid link code")
                    messagebox.showerror("Error", "Invalid link code")
            else:
                self.status_label.config(text="Server error")
                messagebox.showerror("Error", f"Server error: {response.status_code}")
                
        except Exception as e:
            self.status_label.config(text="Connection error")
            messagebox.showerror("Error", f"Connection error: {str(e)}")
    
    def submit_store_code(self):
        """Submit the store code and get screens"""
        self.store_code = self.store_entry.get().strip()
        if not self.store_code:
            messagebox.showerror("Error", "Please enter a store code")
            return
        
        try:
            self.status_label.config(text="Getting screens...")
            response = requests.get(f"{self.server_url}/api/screens/{self.store_code}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"DEBUG: Screens response: {json.dumps(data, indent=2)}")
                
                if data.get('success') and data.get('screens'):
                    self.screen_data = data['screens']
                    self.create_screen_buttons()
                    self.current_step = "screen_select"
                    self.show_current_step()
                    self.status_label.config(text="Select a screen")
                else:
                    self.status_label.config(text="No screens found")
                    messagebox.showerror("Error", "No screens found for this store")
            else:
                self.status_label.config(text="Server error")
                messagebox.showerror("Error", f"Server error: {response.status_code}")
                
        except Exception as e:
            self.status_label.config(text="Connection error")
            messagebox.showerror("Error", f"Connection error: {str(e)}")
    
    def create_screen_buttons(self):
        """Create buttons for available screens"""
        # Clear existing buttons
        for widget in self.screens_container.winfo_children():
            widget.destroy()
        
        # Handle nested screen structure: {store_id: {screen_key: screen_data}}
        for store_id, store_screens in self.screen_data.items():
            if isinstance(store_screens, dict):
                for screen_key, screen_info in store_screens.items():
                    # Extract screen number from key (e.g., "1000_screen1" -> "1")
                    screen_display = screen_key.split('_screen')[-1] if '_screen' in screen_key else screen_key
                    
                    button = tk.Button(self.screens_container,
                                     text=f"Screen {screen_display}",
                                     font=('Arial', 12, 'bold'),
                                     bg='#c8102e',
                                     fg='white',
                                     padx=20,
                                     pady=10,
                                     command=lambda sk=screen_key, si=screen_info: self.select_screen(sk, si))
                    button.pack(pady=5)
    
    def select_screen(self, screen_key, screen_info):
        """Select a screen"""
        self.screen_id = screen_key
        self.current_screen_info = screen_info
        
        # Extract screen number for display
        screen_display = screen_key.split('_screen')[-1] if '_screen' in screen_key else screen_key
        self.status_label.config(text=f"Selected Screen {screen_display}")
        
        print(f"DEBUG: Selected screen {screen_key}")
        print(f"DEBUG: Screen info: {json.dumps(screen_info, indent=2)}")
        
        self.current_step = "video_control"
        self.show_current_step()
    
    def play_video(self):
        """Play video using /media/ endpoint"""
        if not hasattr(self, 'current_screen_info'):
            messagebox.showerror("Error", "Please select a screen first")
            return
        
        try:
            # Stop any existing video
            self.stop_video()
            
            # Get playlist from screen info
            playlist = self.current_screen_info.get('playlist', [])
            if not playlist:
                messagebox.showerror("Error", "No playlist found")
                return
            
            # Get first video file
            video_item = playlist[0]
            video_file = video_item.get('file', '')
            
            if not video_file:
                messagebox.showerror("Error", "No video file found")
                return
            
            # Use /media/ endpoint like webplayer
            video_url = f"{self.server_url}/media/{video_file}"
            
            print(f"DEBUG: Playing video URL: {video_url}")
            self.status_label.config(text=f"Playing: {os.path.basename(video_file)}")
            
            # Try VLC with different options for Pi compatibility
            vlc_cmd = [
                'vlc',
                '--fullscreen',
                '--loop',
                '--no-osd',
                '--intf', 'dummy',
                '--no-video-title-show',
                '--no-audio',
                '--network-caching=3000',
                video_url
            ]
            
            print(f"DEBUG: VLC command: {' '.join(vlc_cmd)}")
            self.vlc_process = subprocess.Popen(vlc_cmd, 
                                              stdout=subprocess.PIPE, 
                                              stderr=subprocess.PIPE)
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            print(f"ERROR: {e}")
    
    def stop_video(self):
        """Stop video playback"""
        if self.vlc_process:
            try:
                self.vlc_process.terminate()
                self.vlc_process.wait(timeout=5)
            except:
                try:
                    self.vlc_process.kill()
                except:
                    pass
            finally:
                self.vlc_process = None
        
        # Also try to kill any lingering VLC processes
        try:
            subprocess.run(['pkill', 'vlc'], capture_output=True)
        except:
            pass
        
        self.status_label.config(text="Video stopped")
    
    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
    
    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        self.is_fullscreen = False
        self.root.attributes("-fullscreen", False)

def main():
    # Handle Ctrl+C gracefully
    def signal_handler(signum, frame):
        print("\nShutting down gracefully...")
        try:
            subprocess.run(['pkill', 'vlc'], capture_output=True)
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Pizza Hut TV - Pi Client (Simple Layout)")
    print("========================================")
    print("Uses /media/ endpoint for video streaming")
    print("Press F11 for fullscreen, Escape to exit fullscreen")
    print("Press Ctrl+C to exit")
    print()
    
    root = tk.Tk()
    app = PizzaHutTVApp(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()