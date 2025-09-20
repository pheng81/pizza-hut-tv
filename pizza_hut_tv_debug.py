#!/usr/bin/env python3
"""
Pizza Hut TV - Pi GUI Client (FIXED Screen Data Structure)
Correctly parses the nested screen data structure from API
"""

import tkinter as tk
from tkinter import messagebox, ttk
import requests
import json
import subprocess

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
        title_label.pack(pady=(0, 20))
        
        # Server info
        server_info = tk.Label(self.main_frame,
                              text=f"Server: {self.server_url} ✅",
                              font=('Arial', 10),
                              fg='#00ff00',
                              bg='#0b0b0b')
        server_info.pack(pady=(0, 10))
        
        # Content area
        self.content_frame = tk.Frame(self.main_frame, bg='#0b0b0b')
        self.content_frame.pack(fill='both', expand=True)
        
        self.create_link_code_step()
        self.create_store_code_step()
        self.create_screen_selection_step()
        self.create_playing_step()
        
    def create_link_code_step(self):
        self.link_frame = tk.Frame(self.content_frame, bg='#0d0d0d', relief='solid', bd=1)
        
        # Title
        tk.Label(self.link_frame, 
                text="Step 1: Enter Link Code", 
                font=('Arial', 18, 'bold'), 
                fg='white', 
                bg='#0d0d0d').pack(pady=20)
        
        # Instructions
        tk.Label(self.link_frame, 
                text="Please enter the 4-digit link code (try 1769):", 
                font=('Arial', 12), 
                fg='#cccccc', 
                bg='#0d0d0d').pack(pady=(0, 15))
        
        # Entry frame
        entry_frame = tk.Frame(self.link_frame, bg='#0d0d0d')
        entry_frame.pack(pady=10)
        
        self.code_entry = tk.Entry(entry_frame, 
                                  font=('Arial', 16, 'bold'), 
                                  width=10,
                                  justify='center',
                                  bg='#1a1a1a',
                                  fg='white',
                                  relief='flat',
                                  bd=5)
        self.code_entry.pack(pady=10)
        self.code_entry.bind('<Return>', lambda e: self.validate_link_code())
        self.code_entry.insert(0, "1769")
        
        # Button
        tk.Button(entry_frame, text='Validate Code', 
                          command=self.validate_link_code,
                          bg='#c8102e', 
                          fg='white', 
                          font=('Arial', 14, 'bold'),
                          relief='flat',
                          pady=8).pack(pady=(10,0))
        
    def create_store_code_step(self):
        self.store_frame = tk.Frame(self.content_frame, bg='#0d0d0d', relief='solid', bd=1)
        
        # Title
        tk.Label(self.store_frame, 
                text="Step 2: Enter Store Code", 
                font=('Arial', 18, 'bold'), 
                fg='white', 
                bg='#0d0d0d').pack(pady=20)
        
        # User info
        self.user_label = tk.Label(self.store_frame, 
                                  text="", 
                                  font=('Arial', 12), 
                                  fg='#cccccc', 
                                  bg='#0d0d0d')
        self.user_label.pack(pady=(0, 15))
        
        # Instructions
        tk.Label(self.store_frame, 
                text="Please enter the store code (try 1000):", 
                font=('Arial', 12), 
                fg='#cccccc', 
                bg='#0d0d0d').pack(pady=(0, 15))
        
        # Entry frame
        entry_frame = tk.Frame(self.store_frame, bg='#0d0d0d')
        entry_frame.pack(pady=10)
        
        self.store_entry = tk.Entry(entry_frame, 
                                   font=('Arial', 16, 'bold'), 
                                   width=10,
                                   justify='center',
                                   bg='#1a1a1a',
                                   fg='white',
                                   relief='flat',
                                   bd=5)
        self.store_entry.pack(pady=10)
        self.store_entry.bind('<Return>', lambda e: self.validate_store_code())
        
        # Button
        tk.Button(entry_frame, text='Validate Store', 
                          command=self.validate_store_code,
                          bg='#c8102e', 
                          fg='white', 
                          font=('Arial', 14, 'bold'),
                          relief='flat',
                          pady=8).pack(pady=(10,0))
        
    def create_screen_selection_step(self):
        self.screen_frame = tk.Frame(self.content_frame, bg='#0d0d0d', relief='solid', bd=1)
        
        # Title
        tk.Label(self.screen_frame, 
                text="Step 3: Select Screen", 
                font=('Arial', 18, 'bold'), 
                fg='white', 
                bg='#0d0d0d').pack(pady=20)
        
        # Instructions
        tk.Label(self.screen_frame, 
                text="Choose your screen:", 
                font=('Arial', 12), 
                fg='#cccccc', 
                bg='#0d0d0d').pack(pady=(0, 20))
        
        # Debug info
        self.debug_label = tk.Label(self.screen_frame, 
                                   text="", 
                                   font=('Arial', 8), 
                                   fg='#888888', 
                                   bg='#0d0d0d',
                                   wraplength=600)
        self.debug_label.pack(pady=(0, 10))
        
        # Screen buttons container
        screen_container = tk.Frame(self.screen_frame, bg='#0d0d0d')
        screen_container.pack(pady=10)
        
        # Screen selection buttons (2x2 grid)
        screens = [
            ("Screen 1", 1), ("Screen 2", 2),
            ("Screen 3", 3), ("Screen 4", 4)
        ]
        
        for i, (text, screen_id) in enumerate(screens):
            row = i // 2
            col = i % 2
            
            frame = tk.Frame(screen_container, bg='#0d0d0d')
            frame.grid(row=row, column=col, padx=20, pady=10)
            
            btn = tk.Button(frame, text=text,
                           command=lambda s=screen_id: self.select_screen(s),
                           bg='#c8102e',
                           fg='white',
                           font=('Arial', 14, 'bold'),
                           width=12,
                           height=2,
                           relief='flat')
            btn.pack()
        
    def create_playing_step(self):
        self.playing_frame = tk.Frame(self.content_frame, bg='#0d0d0d', relief='solid', bd=1)
        
        # Title
        tk.Label(self.playing_frame, 
                text="Screen Control", 
                font=('Arial', 18, 'bold'), 
                fg='white', 
                bg='#0d0d0d').pack(pady=20)
        
        # Info
        self.playing_info = tk.Label(self.playing_frame, 
                                    text="", 
                                    font=('Arial', 12), 
                                    fg='#cccccc', 
                                    bg='#0d0d0d')
        self.playing_info.pack(pady=(0, 20))
        
        # Video info
        self.video_info = tk.Label(self.playing_frame, 
                                  text="", 
                                  font=('Arial', 10), 
                                  fg='#888888', 
                                  bg='#0d0d0d',
                                  wraplength=600)
        self.video_info.pack(pady=(0, 20))
        
        # Control buttons
        button_frame = tk.Frame(self.playing_frame, bg='#0d0d0d')
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text='Start Playback',
                         command=self.start_playback,
                         bg='#c8102e',
                         fg='white',
                         font=('Arial', 14, 'bold'),
                         relief='flat',
                         padx=20,
                         pady=10).pack(side='left', padx=10)
        
        tk.Button(button_frame, text='Stop Playback',
                        command=self.stop_playback,
                        bg='#666666',
                        fg='white',
                        font=('Arial', 14, 'bold'),
                        relief='flat',
                        padx=20,
                        pady=10).pack(side='left', padx=10)
        
        tk.Button(button_frame, text='Back to Screen Select',
                        command=self.back_to_screen_select,
                        bg='#333333',
                        fg='white',
                        font=('Arial', 14, 'bold'),
                        relief='flat',
                        padx=20,
                        pady=10).pack(side='left', padx=10)
        
    def show_current_step(self):
        # Hide all frames
        for frame in [self.link_frame, self.store_frame, self.screen_frame, self.playing_frame]:
            frame.pack_forget()
            
        # Show current step
        if self.current_step == 'link_code':
            self.link_frame.pack(fill='both', expand=True, padx=50, pady=50)
            self.code_entry.focus()
        elif self.current_step == 'store_code':
            self.user_label.configure(text=f"Logged in as: {self.username}")
            self.store_frame.pack(fill='both', expand=True, padx=50, pady=50)
            self.store_entry.focus()
            self.store_entry.delete(0, 'end')
            self.store_entry.insert(0, "1000")
        elif self.current_step == 'screen_select':
            # Show debug info about available screens
            available_screens = []
            for store_id, screens in self.screen_data.items():
                if str(store_id) == str(self.store_code):
                    for screen_key in screens.keys():
                        available_screens.append(screen_key)
            
            debug_text = f"Store {self.store_code} screens: {available_screens}"
            self.debug_label.configure(text=debug_text)
            
            self.screen_frame.pack(fill='both', expand=True, padx=50, pady=50)
        elif self.current_step == 'playing':
            info_text = f"Store: {self.store_code} | Screen: {self.screen_id}"
            self.playing_info.configure(text=info_text)
            
            # Show video info
            video_file, screen_info = self.get_screen_info()
            if video_file and screen_info:
                playlist_items = len(screen_info.get('playlist', []))
                video_text = f"Video: {video_file}\nPlaylist items: {playlist_items}"
                self.video_info.configure(text=video_text)
            else:
                self.video_info.configure(text="No video data found")
            
            self.playing_frame.pack(fill='both', expand=True, padx=50, pady=50)
    
    def get_screen_info(self):
        """Get screen info by checking the nested structure"""
        # Try different possible screen key formats
        possible_keys = [
            f"{self.store_code}_screen{self.screen_id}",
            f"screen{self.screen_id}",
            str(self.screen_id)
        ]
        
        # Look in the store's screens
        if str(self.store_code) in self.screen_data:
            store_screens = self.screen_data[str(self.store_code)]
            for key in possible_keys:
                if key in store_screens:
                    screen_info = store_screens[key]
                    video_file = screen_info.get('file', '')
                    return video_file, screen_info
        
        # Look in all screens directly
        for key in possible_keys:
            if key in self.screen_data:
                screen_info = self.screen_data[key]
                video_file = screen_info.get('file', '')
                return video_file, screen_info
        
        return None, None
            
    def validate_link_code(self):
        code = self.code_entry.get().strip()
        if len(code) != 4 or not code.isdigit():
            messagebox.showerror('Invalid Code', 'Please enter a valid 4-digit code')
            return
            
        # Show loading state
        self.code_entry.configure(state='disabled')
        self.root.update()
        
        try:
            url = f'{self.server_url}/api/stores_by_code/{code}'
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Debug: Print the structure
                print("API Response structure:")
                print(json.dumps(data, indent=2))
                
                # Check if we have screens data
                if 'screens' in data and data.get('success'):
                    self.link_code = code
                    self.username = data.get('user', {}).get('username', 'Pizza Hut User')
                    self.screen_data = data['screens']  # Store screen data
                    self.current_step = 'store_code'
                    self.show_current_step()
                    messagebox.showinfo('Success', f'Link code validated!\nUser: {self.username}\n\nFound screens for stores: {list(self.screen_data.keys())}')
                else:
                    messagebox.showerror('Invalid Code', 'Code not found or invalid')
                    self.code_entry.configure(state='normal')
            else:
                messagebox.showerror('Error', f'Server error: {response.status_code}')
                self.code_entry.configure(state='normal')
        except Exception as e:
            messagebox.showerror('Connection Error', f'Could not verify code: {str(e)}')
            self.code_entry.configure(state='normal')
        finally:
            if self.current_step == 'link_code':
                self.code_entry.configure(state='normal')
                
    def validate_store_code(self):
        store = self.store_entry.get().strip()
        if not store:
            messagebox.showerror('Invalid Store', 'Please enter a store code')
            return
        
        # Check if this store exists in our screen data
        if str(store) not in self.screen_data:
            available_stores = list(self.screen_data.keys())
            messagebox.showerror('Invalid Store', f'Store {store} not found.\n\nAvailable stores: {available_stores}')
            return
            
        self.store_code = store
        self.current_step = 'screen_select'
        self.show_current_step()
        
    def select_screen(self, screen_id):
        self.screen_id = screen_id
        self.current_step = 'playing'
        self.show_current_step()
        
    def back_to_screen_select(self):
        self.current_step = 'screen_select'
        self.show_current_step()
        
    def start_playback(self):
        video_file, screen_info = self.get_screen_info()
        
        if video_file and screen_info:
            # Use /media/ endpoint like webplayer - FIXED
            video_url = f'{self.server_url}/media/{video_file}'
            messagebox.showinfo('Starting Playback', f'Playing video:\n{video_file}\n\nURL: {video_url}')
            
            # Start VLC with corrected video URL
            try:
                subprocess.Popen(['vlc', '--intf', 'dummy', '--fullscreen', '--loop', video_url])
            except FileNotFoundError:
                messagebox.showerror('VLC Not Found', 'VLC media player is not installed.\n\nInstall with:\nsudo apt install vlc')
        else:
            # Debug: Show what screen data we have
            debug_info = f"Store: {self.store_code}, Screen: {self.screen_id}\n"
            debug_info += f"Available data: {list(self.screen_data.keys())}\n"
            if str(self.store_code) in self.screen_data:
                store_screens = self.screen_data[str(self.store_code)]
                debug_info += f"Store screens: {list(store_screens.keys())}"
            
            messagebox.showerror('No Video Found', f'No video file found.\n\n{debug_info}')
        
    def stop_playback(self):
        try:
            subprocess.run(['pkill', 'vlc'], check=False)
            messagebox.showinfo('Stopped', 'Playback stopped - VLC closed')
        except:
            messagebox.showinfo('Stopped', 'Attempted to stop playback')
        
    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)
        
    def exit_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.root.attributes('-fullscreen', False)

if __name__ == "__main__":
    root = tk.Tk()
    app = PizzaHutTVApp(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        root.quit()