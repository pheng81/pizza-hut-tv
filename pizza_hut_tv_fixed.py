#!/usr/bin/env python3
"""
Pizza Hut TV - Pi GUI Client (FIXED - Correct Server URL)
Uses the correct server URL without port 5002
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
        
        # Server configuration - FIXED: Use correct URL without port 5002
        self.server_url = "http://everydayadvertise.com"
        
        # Authentication state
        self.link_code = ""
        self.username = ""
        self.store_code = ""
        self.screen_id = ""
        self.current_step = "link_code"  # link_code, store_code, screen_select, playing
        
        # Fullscreen state
        self.is_fullscreen = False
        
        self.create_widgets()
        self.show_current_step()
        
        # Keyboard bindings
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)
        self.root.focus_set()  # Enable keyboard events
        
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
        self.code_entry.insert(0, "1769")  # Pre-fill with working code
        
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
            self.store_entry.insert(0, "1000")  # Pre-fill with working store
        elif self.current_step == 'screen_select':
            self.screen_frame.pack(fill='both', expand=True, padx=50, pady=50)
        elif self.current_step == 'playing':
            self.playing_info.configure(text=f"Store: {self.store_code} | Screen: {self.screen_id}")
            self.playing_frame.pack(fill='both', expand=True, padx=50, pady=50)
            
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
            print(f"Testing URL: {url}")  # Debug
            response = requests.get(url, timeout=15)
            
            print(f"Response status: {response.status_code}")  # Debug
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response data: {data}")  # Debug
                
                # Check if we have screens data (which means authentication worked)
                if 'screens' in data:
                    self.link_code = code
                    self.username = "Pizza Hut User"  # Default username since API doesn't return user info
                    self.current_step = 'store_code'
                    self.show_current_step()
                    messagebox.showinfo('Success', 'Link code validated successfully!')
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
            # Re-enable the entry if we're still on this step
            if self.current_step == 'link_code':
                self.code_entry.configure(state='normal')
                
    def validate_store_code(self):
        store = self.store_entry.get().strip()
        if not store:
            messagebox.showerror('Invalid Store', 'Please enter a store code')
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
        playlist_url = f'{self.server_url}/playlist/{self.store_code}/{self.screen_id}'
        messagebox.showinfo('Starting Playback', f'Playing from:\n{playlist_url}\n\nVLC will start in fullscreen mode.')
        
        # Start VLC in fullscreen
        try:
            subprocess.Popen(['vlc', '--intf', 'dummy', '--fullscreen', playlist_url])
        except FileNotFoundError:
            messagebox.showerror('VLC Not Found', 'VLC media player is not installed.\n\nInstall with:\nsudo apt install vlc')
        
    def stop_playback(self):
        # Kill all VLC processes
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