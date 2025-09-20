#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import subprocess
import sys
import time
import threading
import signal
import os

class PizzaHutTVPlayer:
    def __init__(self):
        self.server_url = "http://everydayadvertise.com"
        self.vlc_process = None
        self.current_store = None
        self.current_screen = None
        self.setup_ui()
        
    def setup_ui(self):
        self.root = tk.Tk()
        self.root.title("Pizza Hut TV Player")
        self.root.configure(bg='#0b0b0b')
        self.root.geometry("800x600")
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', background='#0b0b0b', foreground='#c8102e', 
                       font=('Arial', 16, 'bold'))
        style.configure('Custom.TLabel', background='#0b0b0b', foreground='white', 
                       font=('Arial', 10))
        style.configure('Custom.TButton', background='#c8102e', foreground='white',
                       font=('Arial', 10, 'bold'))
        style.configure('Custom.TEntry', fieldbackground='#333333', foreground='white',
                       bordercolor='#c8102e')
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#0b0b0b', padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Pizza Hut TV Player", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Step 1: Store Link Code
        step1_frame = tk.Frame(main_frame, bg='#0d0d0d', relief='raised', bd=2, padx=15, pady=15)
        step1_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(step1_frame, text="Step 1: Enter 4-digit store link code", style='Custom.TLabel').pack(anchor='w')
        
        self.link_code_entry = ttk.Entry(step1_frame, style='Custom.TEntry', font=('Arial', 12))
        self.link_code_entry.pack(fill='x', pady=(5, 10))
        self.link_code_entry.bind('<Return>', lambda e: self.get_stores())
        
        ttk.Button(step1_frame, text="Get Stores", command=self.get_stores, style='Custom.TButton').pack()
        
        # Step 2: Store Code
        step2_frame = tk.Frame(main_frame, bg='#0d0d0d', relief='raised', bd=2, padx=15, pady=15)
        step2_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(step2_frame, text="Step 2: Enter store code", style='Custom.TLabel').pack(anchor='w')
        
        self.store_code_entry = ttk.Entry(step2_frame, style='Custom.TEntry', font=('Arial', 12))
        self.store_code_entry.pack(fill='x', pady=(5, 10))
        self.store_code_entry.bind('<Return>', lambda e: self.get_screens())
        
        ttk.Button(step2_frame, text="Get Screens", command=self.get_screens, style='Custom.TButton').pack()
        
        # Step 3: Screen Selection
        step3_frame = tk.Frame(main_frame, bg='#0d0d0d', relief='raised', bd=2, padx=15, pady=15)
        step3_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(step3_frame, text="Step 3: Select screen", style='Custom.TLabel').pack(anchor='w')
        
        # Screen selection area
        self.screen_frame = tk.Frame(step3_frame, bg='#0d0d0d')
        self.screen_frame.pack(fill='x', pady=(5, 10))
        
        # Step 4: Video Control
        step4_frame = tk.Frame(main_frame, bg='#0d0d0d', relief='raised', bd=2, padx=15, pady=15)
        step4_frame.pack(fill='x')
        
        ttk.Label(step4_frame, text="Step 4: Video Control", style='Custom.TLabel').pack(anchor='w')
        
        control_frame = tk.Frame(step4_frame, bg='#0d0d0d')
        control_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(control_frame, text="Play Video", command=self.play_video, style='Custom.TButton').pack(side='left', padx=(0, 10))
        ttk.Button(control_frame, text="Stop Video", command=self.stop_video, style='Custom.TButton').pack(side='left')
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Ready - Enter 4-digit link code to start", style='Custom.TLabel')
        self.status_label.pack(pady=(20, 0))
        
        # Bind keyboard events for TV remote
        self.root.bind('<Key>', self.handle_key_press)
        self.root.focus_set()
        
    def handle_key_press(self, event):
        """Handle TV remote key presses"""
        if event.keysym in ['Return', 'KP_Enter']:
            # Enter key - trigger appropriate action based on current step
            pass
        elif event.keysym == 'Escape':
            self.stop_video()
            
    def get_stores(self):
        """Get stores using the 4-digit link code"""
        link_code = self.link_code_entry.get().strip()
        if not link_code:
            messagebox.showerror("Error", "Please enter a 4-digit link code")
            return
            
        try:
            self.status_label.config(text="Getting stores...")
            response = requests.get(f"{self.server_url}/api/stores_by_code/{link_code}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('stores'):
                    self.status_label.config(text=f"Found {len(data['stores'])} stores. Enter store code.")
                    print(f"Available stores: {data['stores']}")
                else:
                    self.status_label.config(text="No stores found for this link code")
            else:
                self.status_label.config(text=f"Error: Server returned {response.status_code}")
                
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            print(f"Error getting stores: {e}")
    
    def get_screens(self):
        """Get screens for the entered store code"""
        store_code = self.store_code_entry.get().strip()
        if not store_code:
            messagebox.showerror("Error", "Please enter a store code")
            return
            
        try:
            self.status_label.config(text="Getting screens...")
            response = requests.get(f"{self.server_url}/api/screens/{store_code}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"Screens API response: {data}")
                
                if data.get('success') and data.get('screens'):
                    self.current_store = store_code
                    self.display_screens(data['screens'])
                else:
                    self.status_label.config(text="No screens found for this store")
            else:
                self.status_label.config(text=f"Error: Server returned {response.status_code}")
                
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            print(f"Error getting screens: {e}")
            
    def display_screens(self, screens_data):
        """Display available screens as buttons"""
        # Clear existing screen buttons
        for widget in self.screen_frame.winfo_children():
            widget.destroy()
            
        # Parse screens data structure
        screen_count = 0
        
        # Handle nested structure: {store_id: {screen_key: screen_data}}
        for store_id, store_screens in screens_data.items():
            if isinstance(store_screens, dict):
                for screen_key, screen_info in store_screens.items():
                    screen_count += 1
                    
                    # Extract screen number from key (e.g., "1000_screen1" -> "1")
                    screen_display = screen_key.split('_screen')[-1] if '_screen' in screen_key else screen_key
                    
                    button = ttk.Button(
                        self.screen_frame,
                        text=f"Screen {screen_display}",
                        command=lambda sk=screen_key, si=screen_info: self.select_screen(sk, si),
                        style='Custom.TButton'
                    )
                    button.pack(side='left', padx=(0, 10), pady=5)
        
        if screen_count > 0:
            self.status_label.config(text=f"Found {screen_count} screens. Select a screen to play video.")
        else:
            self.status_label.config(text="No screens available")
    
    def select_screen(self, screen_key, screen_info):
        """Select a screen and prepare for video playback"""
        self.current_screen = screen_key
        self.current_screen_info = screen_info
        
        # Extract screen number for display
        screen_display = screen_key.split('_screen')[-1] if '_screen' in screen_key else screen_key
        self.status_label.config(text=f"Selected Screen {screen_display}. Click 'Play Video' to start.")
        
        print(f"Selected screen: {screen_key}")
        print(f"Screen info: {screen_info}")
    
    def play_video(self):
        """Play video for the selected screen using VLC with /media/ endpoint"""
        if not self.current_store or not self.current_screen or not hasattr(self, 'current_screen_info'):
            messagebox.showerror("Error", "Please select a screen first")
            return
            
        try:
            # Stop any existing video
            self.stop_video()
            
            # Get video file from playlist
            playlist = self.current_screen_info.get('playlist', [])
            if not playlist:
                messagebox.showerror("Error", "No playlist found for this screen")
                return
                
            # Get the first video file
            video_item = playlist[0]
            video_file = video_item.get('file', '')
            
            if not video_file:
                messagebox.showerror("Error", "No video file found in playlist")
                return
            
            # Construct the correct video URL using /media/ endpoint like webplayer
            video_url = f"{self.server_url}/media/{video_file}"
            
            print(f"Playing video: {video_url}")
            self.status_label.config(text=f"Playing: {video_file.split('/')[-1]}")
            
            # Launch VLC with the video URL
            vlc_args = [
                'vlc', 
                '--fullscreen',
                '--loop',
                '--no-osd',
                '--qt-start-minimized',
                video_url
            ]
            
            self.vlc_process = subprocess.Popen(vlc_args)
            
        except Exception as e:
            self.status_label.config(text=f"Error playing video: {str(e)}")
            print(f"Error: {e}")
    
    def stop_video(self):
        """Stop the current video"""
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
                
        self.status_label.config(text="Video stopped")
    
    def run(self):
        """Start the application"""
        # Handle Ctrl+C gracefully
        def signal_handler(signum, frame):
            self.stop_video()
            self.root.quit()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop_video()
            sys.exit(0)

def main():
    print("Pizza Hut TV Player - Pi Edition")
    print("=================================")
    print("Using /media/ endpoint for video streaming")
    print("Press Ctrl+C to exit")
    print()
    
    app = PizzaHutTVPlayer()
    app.run()

if __name__ == "__main__":
    main()