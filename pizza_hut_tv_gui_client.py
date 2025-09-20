#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - GUI Client for Raspberry Pi
TV Remote-Friendly Interface with Large Buttons and Keyboard Navigation
Perfect for use on TV screens with remote control
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import sys
import json
import time
import requests
import subprocess
import threading
from datetime import datetime

class PizzaHutTVGUI:
    def __init__(self):
        # Configuration
        self.server_url = "https://everydayadvertise.com"
        self.store_id = None
        self.screen_id = "tv1"
        self.link_code = None  # 4-digit pairing code
        self.store_code = None  # Store number  
        self.username = None
        self.current_stores = []
        self.current_screens = {}
        self.config_file = "client_config.txt"
        self.vlc_process = None
        self.playback_thread = None
        self.playback_running = False
        
        # Authentication state tracking
        self.auth_step = "link_code"  # link_code -> store_code -> screen_select -> playing
        
        # Load saved configuration
        self.load_config()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("🍕 Pizza Hut TV - Pi Client")
        self.root.geometry("1024x768")  # Large size for TV screens
        self.root.configure(bg='#2c3e50')
        
        # Make window fullscreen-capable (F11 to toggle)
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)
        
        # TV Remote keyboard bindings
        self.setup_keyboard_bindings()
        
        # Make window focusable for keyboard input
        self.root.focus_set()
        
        # Button tracking for remote navigation
        self.buttons = []
        self.current_button_index = 0
        
        self.create_widgets()
        
    def setup_keyboard_bindings(self):
        """Setup TV remote-friendly keyboard navigation"""
        # Arrow keys for navigation
        self.root.bind('<Up>', lambda e: self.navigate_buttons('up'))
        self.root.bind('<Down>', lambda e: self.navigate_buttons('down'))
        self.root.bind('<Left>', lambda e: self.navigate_buttons('left'))
        self.root.bind('<Right>', lambda e: self.navigate_buttons('right'))
        
        # Enter/Return to activate selected button
        self.root.bind('<Return>', lambda e: self.activate_current_button())
        self.root.bind('<KP_Enter>', lambda e: self.activate_current_button())
        
        # Number keys for quick menu access
        self.root.bind('<Key-1>', lambda e: self.quick_action(0))
        self.root.bind('<Key-2>', lambda e: self.quick_action(1))
        self.root.bind('<Key-3>', lambda e: self.quick_action(2))
        self.root.bind('<Key-4>', lambda e: self.quick_action(3))
        self.root.bind('<Key-5>', lambda e: self.quick_action(4))
        self.root.bind('<Key-6>', lambda e: self.quick_action(5))
        
        # Common remote control keys
        self.root.bind('<space>', lambda e: self.toggle_playback())
        self.root.bind('<BackSpace>', lambda e: self.stop_playback())
        
    def navigate_buttons(self, direction):
        """Navigate between buttons using TV remote arrows"""
        if not self.buttons:
            return
            
        # Remove highlight from current button
        if self.current_button_index < len(self.buttons):
            current_btn = self.buttons[self.current_button_index]
            current_btn.configure(relief='raised', bg='#3498db')
        
        # Calculate new position
        if direction == 'down':
            self.current_button_index = (self.current_button_index + 1) % len(self.buttons)
        elif direction == 'up':
            self.current_button_index = (self.current_button_index - 1) % len(self.buttons)
        elif direction == 'right':
            # Move to next column (if we have a grid layout)
            self.current_button_index = min(self.current_button_index + 3, len(self.buttons) - 1)
        elif direction == 'left':
            # Move to previous column
            self.current_button_index = max(self.current_button_index - 3, 0)
            
        # Highlight new button
        if self.current_button_index < len(self.buttons):
            new_btn = self.buttons[self.current_button_index]
            new_btn.configure(relief='sunken', bg='#e74c3c')
            new_btn.focus_set()
            
    def activate_current_button(self):
        """Activate currently selected button with Enter/Return"""
        if self.current_button_index < len(self.buttons):
            self.buttons[self.current_button_index].invoke()
            
    def quick_action(self, index):
        """Quick access to main actions via number keys"""
        actions = [
            self.test_connection,
            self.discover_stores,
            self.configure_settings,
            self.configure_authentication,
            self.select_stores,
            self.start_playback
        ]
        if index < len(actions):
            actions[index]()
            
    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11"""
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))
        
    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode with Escape"""
        self.root.attributes('-fullscreen', False)
        
    def create_widgets(self):
        """Create the main GUI interface with proper authentication flow"""
        # Title
        title_frame = tk.Frame(self.root, bg='#2c3e50')
        title_frame.pack(pady=20, fill='x')
        
        title_label = tk.Label(title_frame, 
                              text="🍕 Pizza Hut TV - Pi Client", 
                              font=('Arial', 28, 'bold'),
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack()
        
        subtitle_label = tk.Label(title_frame,
                                 text="TV Remote Navigation: ↑↓←→ Enter | F11=Fullscreen",
                                 font=('Arial', 14),
                                 fg='#bdc3c7', bg='#2c3e50')
        subtitle_label.pack(pady=10)
        
        # Main content area - will show different steps based on auth_step
        self.main_frame = tk.Frame(self.root, bg='#2c3e50')
        self.main_frame.pack(pady=20, padx=40, fill='both', expand=True)
        
        # Show the appropriate step
        self.show_current_step()
            
    def show_current_step(self):
        """Display the current authentication/usage step"""
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.buttons = []
        self.current_button_index = 0
        
        if self.auth_step == "link_code":
            self.show_link_code_step()
        elif self.auth_step == "store_code":
            self.show_store_code_step()
        elif self.auth_step == "screen_select":
            self.show_screen_select_step()
        elif self.auth_step == "playing":
            self.show_playing_step()
        else:
            self.show_link_code_step()  # Default
            
        # Highlight first button
        if self.buttons:
            self.buttons[0].configure(relief='sunken', bg='#e74c3c')
    
    def show_link_code_step(self):
        """Step 1: Enter 4-digit link code"""
        step_frame = tk.LabelFrame(self.main_frame,
                                 text="Step 1: Enter Your 4-Digit TV Code",
                                 font=('Arial', 18, 'bold'),
                                 fg='#ecf0f1', bg='#34495e',
                                 padx=30, pady=20)
        step_frame.pack(fill='both', expand=True)
        
        instruction_label = tk.Label(step_frame,
                                   text="Type the 4-digit code from your TV app or profile page",
                                   font=('Arial', 16),
                                   fg='#bdc3c7', bg='#34495e')
        instruction_label.pack(pady=20)
        
        # Code entry
        entry_frame = tk.Frame(step_frame, bg='#34495e')
        entry_frame.pack(pady=20)
        
        tk.Label(entry_frame, text="4-digit code:",
                font=('Arial', 14), fg='#ecf0f1', bg='#34495e').pack()
        
        self.link_code_entry = tk.Entry(entry_frame,
                                      font=('Arial', 24, 'bold'),
                                      width=6, justify='center',
                                      bg='#2c3e50', fg='#ecf0f1')
        self.link_code_entry.pack(pady=10)
        self.link_code_entry.focus_set()
        
        # Bind Entry key events
        self.link_code_entry.bind('<Return>', lambda e: self.validate_link_code())
        self.link_code_entry.bind('<KeyPress>', self.filter_numeric_input)
        
        # Buttons
        button_frame = tk.Frame(step_frame, bg='#34495e')
        button_frame.pack(pady=30)
        
        self.add_tv_button(button_frame, "Connect Code", self.validate_link_code, 0, 0)
        self.add_tv_button(button_frame, "Skip for Now", self.show_manual_auth, 0, 1)
        
    def show_store_code_step(self):
        """Step 2: Enter store code/number"""
        step_frame = tk.LabelFrame(self.main_frame,
                                 text=f"Step 2: Enter Store Code (TV Code: {self.link_code})",
                                 font=('Arial', 18, 'bold'),
                                 fg='#ecf0f1', bg='#34495e',
                                 padx=30, pady=20)
        step_frame.pack(fill='both', expand=True)
        
        instruction_label = tk.Label(step_frame,
                                   text="Enter your store number/code",
                                   font=('Arial', 16),
                                   fg='#bdc3c7', bg='#34495e')
        instruction_label.pack(pady=20)
        
        # Store entry
        entry_frame = tk.Frame(step_frame, bg='#34495e')
        entry_frame.pack(pady=20)
        
        tk.Label(entry_frame, text="Store code:",
                font=('Arial', 14), fg='#ecf0f1', bg='#34495e').pack()
        
        self.store_code_entry = tk.Entry(entry_frame,
                                       font=('Arial', 20, 'bold'),
                                       width=10, justify='center',
                                       bg='#2c3e50', fg='#ecf0f1')
        self.store_code_entry.pack(pady=10)
        self.store_code_entry.focus_set()
        
        # Bind Entry key events  
        self.store_code_entry.bind('<Return>', lambda e: self.validate_store_code())
        self.store_code_entry.bind('<KeyPress>', self.filter_numeric_input)
        
        # Buttons
        button_frame = tk.Frame(step_frame, bg='#34495e')
        button_frame.pack(pady=30)
        
        self.add_tv_button(button_frame, "Continue", self.validate_store_code, 0, 0)
        self.add_tv_button(button_frame, "Back", self.back_to_link_code, 0, 1)
        
    def show_screen_select_step(self):
        """Step 3: Select screen"""  
        step_frame = tk.LabelFrame(self.main_frame,
                                 text=f"Step 3: Choose Screen (Store: {self.store_code})",
                                 font=('Arial', 18, 'bold'),
                                 fg='#ecf0f1', bg='#34495e',
                                 padx=30, pady=20)
        step_frame.pack(fill='both', expand=True)
        
        # Available screens
        if self.current_screens:
            screens_frame = tk.Frame(step_frame, bg='#34495e')
            screens_frame.pack(pady=20, fill='both', expand=True)
            
            row = 0
            for screen_id, screen_info in self.current_screens.items():
                screen_name = screen_info.get('name', screen_id)
                self.add_tv_button(screens_frame, f"📺 {screen_name}", 
                                 lambda sid=screen_id: self.select_screen(sid), row, 0)
                row += 1
        else:
            # Default screens
            screens_frame = tk.Frame(step_frame, bg='#34495e')
            screens_frame.pack(pady=20, fill='both', expand=True)
            
            default_screens = [
                ("tv1", "TV Screen 1"),
                ("tv2", "TV Screen 2"), 
                ("tv3", "TV Screen 3"),
                ("tv4", "TV Screen 4")
            ]
            
            for i, (screen_id, screen_name) in enumerate(default_screens):
                self.add_tv_button(screens_frame, f"📺 {screen_name}",
                                 lambda sid=screen_id: self.select_screen(sid), i, 0)
        
        # Back button
        button_frame = tk.Frame(step_frame, bg='#34495e')
        button_frame.pack(pady=20)
        self.add_tv_button(button_frame, "← Back to Store", self.back_to_store_code, 0, 0)
        
    def show_playing_step(self):
        """Step 4: Playing content with controls"""
        step_frame = tk.LabelFrame(self.main_frame,
                                 text=f"🎬 Playing: Store {self.store_code} | Screen {self.screen_id}",
                                 font=('Arial', 18, 'bold'),
                                 fg='#ecf0f1', bg='#34495e',
                                 padx=30, pady=20)
        step_frame.pack(fill='both', expand=True)
        
        # Status info
        status_text = f"Server: {self.server_url}\n"
        status_text += f"Link Code: {self.link_code}\n" 
        status_text += f"Store: {self.store_code} | Screen: {self.screen_id}"
        
        status_label = tk.Label(step_frame, text=status_text,
                               font=('Arial', 14), fg='#bdc3c7', bg='#34495e')
        status_label.pack(pady=20)
        
        # Control buttons
        control_frame = tk.Frame(step_frame, bg='#34495e')
        control_frame.pack(pady=30)
        
        self.add_tv_button(control_frame, "▶️ Start Playback", self.start_playback, 0, 0)
        self.add_tv_button(control_frame, "⏹️ Stop Playback", self.stop_playback, 0, 1)
        self.add_tv_button(control_frame, "🔄 Refresh", self.refresh_content, 1, 0)
        self.add_tv_button(control_frame, "⚙️ Settings", self.show_settings, 1, 1)
        
        # Back to selection
        back_frame = tk.Frame(step_frame, bg='#34495e')
        back_frame.pack(pady=20)
        self.add_tv_button(back_frame, "← Change Screen", self.back_to_screen_select, 0, 0)
        
        # Log area
        self.create_log_frame(step_frame)
        
    def add_tv_button(self, parent, text, command, row, column):
        """Add a TV remote-friendly button"""
        button_config = {
            'font': ('Arial', 16, 'bold'),
            'width': 20,
            'height': 2,
            'bg': '#3498db',
            'fg': '#ecf0f1',
            'relief': 'raised',
            'bd': 3,
            'cursor': 'hand2'
        }
        
        btn = tk.Button(parent, text=text, command=command, **button_config)
        btn.grid(row=row, column=column, padx=10, pady=10, sticky='nsew')
        self.buttons.append(btn)
        
        # Configure grid weights for proper scaling
        for i in range(max(3, column + 1)):
            parent.columnconfigure(i, weight=1)
        parent.rowconfigure(row, weight=1)
        
    def create_button_frame(self):
        """Create main action buttons in TV-friendly grid"""
        button_frame = tk.Frame(self.root, bg='#2c3e50')
        button_frame.pack(pady=20, padx=20, fill='both', expand=True)
        
        # Button configuration for TV remote use
        button_config = {
            'font': ('Arial', 16, 'bold'),
            'width': 25,
            'height': 2,
            'bg': '#3498db',
            'fg': 'white',
            'relief': 'raised',
            'bd': 3,
            'activebackground': '#2980b9',
            'activeforeground': 'white'
        }
        
        # Create buttons in 3x2 grid
        buttons_data = [
            ("1️⃣ Test Connection", self.test_connection),
            ("2️⃣ Discover Stores", self.discover_stores),
            ("3️⃣ Settings", self.configure_settings),
            ("4️⃣ Authentication", self.configure_authentication),
            ("5️⃣ Select Store", self.select_stores),
            ("6️⃣ Start Playback", self.start_playback),
        ]
        
        self.buttons = []
        for i, (text, command) in enumerate(buttons_data):
            row = i // 3
            col = i % 3
            
            btn = tk.Button(button_frame, text=text, command=command, **button_config)
            btn.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            self.buttons.append(btn)
            
        # Configure grid weights for proper scaling
        for i in range(3):
            button_frame.columnconfigure(i, weight=1)
        for i in range(2):
            button_frame.rowconfigure(i, weight=1)
            
        # Additional control buttons
        control_frame = tk.Frame(self.root, bg='#2c3e50')
        control_frame.pack(pady=10)
        
        control_config = {
            'font': ('Arial', 14, 'bold'),
            'height': 1,
            'bg': '#e74c3c',
            'fg': 'white',
            'relief': 'raised',
            'bd': 2
        }
        
        stop_btn = tk.Button(control_frame, text="⏹️ Stop Playback", 
                           command=self.stop_playback, **control_config)
        stop_btn.pack(side='left', padx=5)
        
        fullscreen_btn = tk.Button(control_frame, text="🖥️ Fullscreen (F11)", 
                                 command=self.toggle_fullscreen, **control_config)
        fullscreen_btn.pack(side='left', padx=5)
        
        exit_btn = tk.Button(control_frame, text="❌ Exit", 
                           command=self.root.quit, **control_config)
        exit_btn.pack(side='right', padx=5)
        
        # Add control buttons to navigation list
        self.buttons.extend([stop_btn, fullscreen_btn, exit_btn])
        
    def create_log_frame(self):
        """Create log display area"""
        log_frame = tk.LabelFrame(self.root, 
                                text="📝 Activity Log", 
                                font=('Arial', 14, 'bold'),
                                fg='#ecf0f1', bg='#34495e')
        log_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame,
                                                height=8,
                                                font=('Courier', 12),
                                                bg='#2c3e50',
                                                fg='#ecf0f1',
                                                insertbackground='white')
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Welcome message
        self.log_message("🍕 Pizza Hut TV Client Ready!")
        self.log_message("Use TV remote arrows (↑↓←→) and Enter to navigate")
        self.log_message("Number keys 1-6 for quick access | F11 for fullscreen")
        
    def log_message(self, message):
        """Add message to activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def update_status_display(self):
        """Update the status information display"""
        self.server_label.config(text=f"Server: {self.server_url}")
        
        store_text = f"Store: {self.store_id or 'Not selected'}"
        if self.store_id:
            store_text += f" | Screen: {self.screen_id}"
        self.store_label.config(text=store_text)
        
        auth_text = "Authentication: "
        if self.user_code:
            auth_text += f"4-digit code: {self.user_code}"
        elif self.username:
            auth_text += f"Username: {self.username}"
        else:
            auth_text += "None"
        self.auth_label.config(text=auth_text)
        
    # Authentication flow methods
    def filter_numeric_input(self, event):
        """Filter input to numeric only"""
        if not event.char.isdigit() and event.keysym not in ('BackSpace', 'Delete', 'Tab', 'Return'):
            return 'break'
    
    def validate_link_code(self):
        """Validate the 4-digit link code"""
        code = self.link_code_entry.get().strip()
        if len(code) != 4 or not code.isdigit():
            messagebox.showerror("Invalid Code", "Please enter a valid 4-digit code")
            return
            
        self.link_code = code
        self.log_message(f"🔍 Validating link code: {code}")
        
        # Call the API to validate code
        try:
            url = f"{self.server_url}/api/stores_by_code/{code}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.username = data.get('user', {}).get('username', '')
                    self.current_stores = data.get('stores', [])
                    self.current_screens = data.get('screens', {})
                    
                    self.log_message(f"✅ Link code valid for user: {self.username}")
                    self.auth_step = "store_code"
                    self.show_current_step()
                else:
                    messagebox.showerror("Invalid Code", data.get('error', 'Code not found'))
            else:
                messagebox.showerror("Error", f"Server error: {response.status_code}")
                
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not verify code: {str(e)}")
    
    def validate_store_code(self):
        """Validate and proceed with store code"""
        store_code = self.store_code_entry.get().strip()
        if not store_code:
            messagebox.showerror("Invalid Store", "Please enter a store code")
            return
            
        self.store_code = store_code
        self.log_message(f"🏪 Selected store: {store_code}")
        
        # Move to screen selection
        self.auth_step = "screen_select"
        self.show_current_step()
    
    def select_screen(self, screen_id):
        """Select a screen and move to playing step"""
        self.screen_id = screen_id
        self.log_message(f"📺 Selected screen: {screen_id}")
        
        # Move to playing step
        self.auth_step = "playing"
        self.show_current_step()
    
    def back_to_link_code(self):
        """Go back to link code entry"""
        self.auth_step = "link_code"
        self.show_current_step()
    
    def back_to_store_code(self):
        """Go back to store code entry"""
        self.auth_step = "store_code"
        self.show_current_step()
        
    def back_to_screen_select(self):
        """Go back to screen selection"""
        self.auth_step = "screen_select"
        self.show_current_step()
        
    def show_manual_auth(self):
        """Show manual authentication option"""
        # For now, just skip to store selection
        messagebox.showinfo("Manual Auth", "Manual authentication not implemented yet.\nSkipping to store selection.")
        self.auth_step = "store_code"
        self.show_current_step()
        
    def show_settings(self):
        """Show settings dialog"""
        messagebox.showinfo("Settings", "Settings panel not implemented yet.")
        
    def refresh_content(self):
        """Refresh current content"""
        self.log_message("🔄 Refreshing content...")
        if self.playback_running:
            self.stop_playback()
            time.sleep(1)
            self.start_playback()
            
    # Core functionality methods (same as CLI version but with GUI updates)
    def test_connection(self):
        """Test connection to server and show results in GUI"""
        self.log_message("🔍 Testing connection...")
        
        try:
            response = requests.get(f"{self.server_url.rstrip('/')}/health", timeout=10)
            if response.status_code == 200:
                self.log_message(f"✅ Server reachable: {self.server_url}")
            else:
                self.log_message(f"⚠️ Server responds but with status: {response.status_code}")
        except Exception as e:
            self.log_message(f"❌ Server unreachable: {e}")
            messagebox.showerror("Connection Error", 
                               f"Cannot reach server: {self.server_url}\n\nTry configuring server URL first.")
            return False
            
        if not self.store_id:
            self.log_message("⚠️ No store selected. Select store first.")
            messagebox.showwarning("No Store", "Please select a store first using 'Select Store' button.")
            return False
            
        try:
            headers = {'User-Agent': 'phtv-pi/1.0 (Raspberry Pi GUI Client)'}
            if self.user_code:
                headers['X-User-Code'] = self.user_code
                
            url = f"{self.server_url.rstrip('/')}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('playlist'):
                    playlist = data['playlist']
                    self.log_message(f"✅ Content found: {len(playlist)} items in playlist")
                    
                    # Show content summary
                    for i, item in enumerate(playlist[:3]):
                        name = item.get('file', 'Unknown')
                        media_type = item.get('media_type', 'unknown')
                        self.log_message(f"   {i+1}. {name} ({media_type})")
                    
                    if len(playlist) > 3:
                        self.log_message(f"   ... and {len(playlist) - 3} more items")
                        
                    messagebox.showinfo("Connection Success", 
                                      f"Found {len(playlist)} items in playlist!\nReady for playback.")
                    return True
                else:
                    self.log_message(f"⚠️ Server found but no content for store: {self.store_id}")
                    messagebox.showwarning("No Content", 
                                         f"No content found for store: {self.store_id}\n\nTry selecting a different store.")
                    return False
            else:
                self.log_message(f"❌ API error: {response.status_code}")
                messagebox.showerror("API Error", f"Server returned error: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_message(f"❌ Connection test failed: {e}")
            messagebox.showerror("Test Failed", f"Connection test failed: {str(e)}")
            return False
            
    def discover_stores(self):
        """Discover available stores and show in GUI"""
        self.log_message("🔍 Discovering available stores...")
        
        try:
            stores_found, screens_found = self.perform_store_discovery()
            self.current_stores = stores_found
            self.current_screens = screens_found
            
            if stores_found:
                self.log_message(f"📊 Discovery complete: {len(stores_found)} stores found")
                
                # Show discovery results
                result_text = "Found stores:\n\n"
                for store in stores_found[:5]:  # Show first 5
                    store_id = store.get('id', 'Unknown')
                    screens = self.current_screens.get(store_id, {})
                    content_count = sum(len(screen.get('playlist', [])) for screen in screens.values())
                    result_text += f"• {store_id} ({content_count} items)\n"
                
                if len(stores_found) > 5:
                    result_text += f"\n... and {len(stores_found) - 5} more stores"
                    
                messagebox.showinfo("Discovery Results", result_text)
            else:
                self.log_message("❌ No stores found!")
                messagebox.showwarning("No Stores Found", 
                                     "No stores discovered.\n\nTry:\n• Set authentication first\n• Check server URL\n• Verify network connection")
                
        except Exception as e:
            self.log_message(f"❌ Discovery failed: {e}")
            messagebox.showerror("Discovery Error", f"Store discovery failed: {str(e)}")
            
    def perform_store_discovery(self):
        """Perform actual store discovery (same logic as CLI version)"""
        stores_found = []
        screens_found = {}
        
        # Method 1: User code lookup
        if self.user_code:
            try:
                url = f"{self.server_url.rstrip('/')}/api/stores_by_code/{self.user_code}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stores_found = data.get('stores', [])
                        screens_found = data.get('screens', {})
                        self.log_message(f"✅ Found {len(stores_found)} stores via user code")
                        return stores_found, screens_found
                        
            except Exception as e:
                self.log_message(f"⚠️ User code lookup failed: {e}")
        
        # Method 2: Common patterns
        self.log_message("🔍 Scanning for common stores...")
        common_patterns = [
            'test5_at_hotmail.com',
            'heang2_at_gmail.com',
            'heang3_at_hotmail.com',
            'kayson2_at_gmail.com',
            'kalix2_at_gmail.com',
            '1000',
            '1881',
        ]
        
        headers = {'User-Agent': 'phtv-pi/1.0 (Raspberry Pi GUI Client)'}
        if self.user_code:
            headers['X-User-Code'] = self.user_code
            
        for pattern in common_patterns:
            try:
                url = f"{self.server_url.rstrip('/')}/playlist/{pattern}/tv1"
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stores_found.append({'id': pattern, 'name': pattern})
                        screens_found[pattern] = {'tv1': {'playlist': data.get('playlist', [])}}
                        self.log_message(f"   ✅ Found store: {pattern}")
                        
            except Exception:
                continue
                
        return stores_found, screens_found
        
    def select_stores(self):
        """Show store selection dialog"""
        if not self.current_stores:
            # Auto-discover first
            self.discover_stores()
            
        if not self.current_stores:
            return
            
        # Create store selection window
        self.create_store_selection_window()
        
    def create_store_selection_window(self):
        """Create TV-friendly store selection window"""
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Store & Screen")
        selection_window.geometry("800x600")
        selection_window.configure(bg='#2c3e50')
        selection_window.grab_set()  # Modal dialog
        
        # Title
        title_label = tk.Label(selection_window,
                              text="🏪 Select Your Store",
                              font=('Arial', 24, 'bold'),
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=20)
        
        # Store list frame
        list_frame = tk.Frame(selection_window, bg='#34495e', relief='sunken', bd=2)
        list_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        # Scrollable listbox with large font
        listbox = tk.Listbox(list_frame,
                           font=('Arial', 16),
                           height=15,
                           bg='#2c3e50',
                           fg='#ecf0f1',
                           selectbackground='#3498db',
                           selectforeground='white',
                           relief='flat')
        
        scrollbar = tk.Scrollbar(list_frame, orient='vertical', command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Populate listbox
        for store in self.current_stores:
            store_id = store.get('id', 'Unknown')
            screens = self.current_screens.get(store_id, {})
            content_count = sum(len(screen.get('playlist', [])) for screen in screens.values())
            listbox.insert(tk.END, f"{store_id} ({content_count} items)")
            
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Button frame
        btn_frame = tk.Frame(selection_window, bg='#2c3e50')
        btn_frame.pack(pady=20)
        
        def select_store():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                selected_store = self.current_stores[idx]
                self.store_id = selected_store.get('id')
                self.screen_id = "tv1"  # Default screen
                
                self.log_message(f"✅ Selected: {self.store_id}/{self.screen_id}")
                self.save_config()
                self.update_status_display()
                selection_window.destroy()
                
                messagebox.showinfo("Store Selected", f"Selected store: {self.store_id}\nScreen: {self.screen_id}")
            else:
                messagebox.showwarning("No Selection", "Please select a store from the list.")
        
        # Large buttons for TV remote
        btn_config = {
            'font': ('Arial', 16, 'bold'),
            'height': 2,
            'width': 15,
            'bg': '#3498db',
            'fg': 'white',
            'relief': 'raised',
            'bd': 3
        }
        
        select_btn = tk.Button(btn_frame, text="✅ Select Store", 
                             command=select_store, **btn_config)
        select_btn.pack(side='left', padx=10)
        
        cancel_btn = tk.Button(btn_frame, text="❌ Cancel", 
                             command=selection_window.destroy, 
                             bg='#e74c3c', fg='white',
                             font=('Arial', 16, 'bold'),
                             height=2, width=15,
                             relief='raised', bd=3)
        cancel_btn.pack(side='left', padx=10)
        
        # Keyboard navigation for the dialog
        def on_key(event):
            if event.keysym == 'Return':
                select_store()
            elif event.keysym == 'Escape':
                selection_window.destroy()
                
        selection_window.bind('<Key>', on_key)
        selection_window.focus_set()
        listbox.focus_set()
        
        # Auto-select first item
        if self.current_stores:
            listbox.selection_set(0)
            
    def configure_settings(self):
        """Show settings configuration dialog"""
        self.create_settings_window()
        
    def create_settings_window(self):
        """Create TV-friendly settings window"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Configuration Settings")
        settings_window.geometry("700x500")
        settings_window.configure(bg='#2c3e50')
        settings_window.grab_set()
        
        # Title
        title_label = tk.Label(settings_window,
                              text="⚙️ Settings Configuration",
                              font=('Arial', 20, 'bold'),
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=20)
        
        # Settings frame
        settings_frame = tk.Frame(settings_window, bg='#34495e', relief='raised', bd=2)
        settings_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        # Server URL
        tk.Label(settings_frame, text="Server URL:", 
                font=('Arial', 16, 'bold'), 
                fg='#ecf0f1', bg='#34495e').pack(pady=10, anchor='w', padx=20)
        
        server_entry = tk.Entry(settings_frame, 
                              font=('Arial', 16), 
                              width=40,
                              bg='#2c3e50', fg='#ecf0f1')
        server_entry.pack(pady=5, padx=20, fill='x')
        server_entry.insert(0, self.server_url)
        
        # Store ID  
        tk.Label(settings_frame, text="Store ID (optional):", 
                font=('Arial', 16, 'bold'), 
                fg='#ecf0f1', bg='#34495e').pack(pady=(20,5), anchor='w', padx=20)
        
        store_entry = tk.Entry(settings_frame, 
                             font=('Arial', 16), 
                             width=40,
                             bg='#2c3e50', fg='#ecf0f1')
        store_entry.pack(pady=5, padx=20, fill='x')
        if self.store_id:
            store_entry.insert(0, self.store_id)
            
        # Screen ID
        tk.Label(settings_frame, text="Screen ID:", 
                font=('Arial', 16, 'bold'), 
                fg='#ecf0f1', bg='#34495e').pack(pady=(20,5), anchor='w', padx=20)
        
        screen_entry = tk.Entry(settings_frame, 
                              font=('Arial', 16), 
                              width=40,
                              bg='#2c3e50', fg='#ecf0f1')
        screen_entry.pack(pady=5, padx=20, fill='x')
        screen_entry.insert(0, self.screen_id)
        
        # Buttons
        btn_frame = tk.Frame(settings_window, bg='#2c3e50')
        btn_frame.pack(pady=20)
        
        def save_settings():
            new_server = server_entry.get().strip()
            if new_server:
                if not new_server.startswith(('http://', 'https://')):
                    new_server = 'https://' + new_server
                self.server_url = new_server
                
            new_store = store_entry.get().strip()
            if new_store:
                self.store_id = new_store
                
            new_screen = screen_entry.get().strip()
            if new_screen:
                self.screen_id = new_screen
                
            self.save_config()
            self.update_status_display()
            self.log_message("✅ Settings saved")
            settings_window.destroy()
            
            messagebox.showinfo("Settings Saved", "Configuration has been saved successfully!")
        
        btn_config = {
            'font': ('Arial', 16, 'bold'),
            'height': 2,
            'width': 15,
            'relief': 'raised',
            'bd': 3
        }
        
        save_btn = tk.Button(btn_frame, text="💾 Save", 
                           command=save_settings, 
                           bg='#2ecc71', fg='white', **btn_config)
        save_btn.pack(side='left', padx=10)
        
        cancel_btn = tk.Button(btn_frame, text="❌ Cancel", 
                             command=settings_window.destroy, 
                             bg='#e74c3c', fg='white', **btn_config)
        cancel_btn.pack(side='left', padx=10)
        
    def configure_authentication(self):
        """Show authentication configuration dialog"""
        self.create_auth_window()
        
    def create_auth_window(self):
        """Create TV-friendly authentication window"""
        auth_window = tk.Toplevel(self.root)
        auth_window.title("Authentication Setup")
        auth_window.geometry("600x400")
        auth_window.configure(bg='#2c3e50')
        auth_window.grab_set()
        
        # Title
        title_label = tk.Label(auth_window,
                              text="🔐 Authentication Setup",
                              font=('Arial', 20, 'bold'),
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=20)
        
        # Method selection
        method_frame = tk.LabelFrame(auth_window, 
                                   text="Choose Authentication Method",
                                   font=('Arial', 14, 'bold'),
                                   fg='#ecf0f1', bg='#34495e')
        method_frame.pack(pady=20, padx=20, fill='x')
        
        method_var = tk.StringVar(value="code")
        
        tk.Radiobutton(method_frame, text="4-digit User Code (like Android TV)", 
                      variable=method_var, value="code",
                      font=('Arial', 14), 
                      fg='#ecf0f1', bg='#34495e',
                      selectcolor='#3498db').pack(pady=5, anchor='w')
        
        tk.Radiobutton(method_frame, text="Username/Password", 
                      variable=method_var, value="user",
                      font=('Arial', 14), 
                      fg='#ecf0f1', bg='#34495e',
                      selectcolor='#3498db').pack(pady=5, anchor='w')
        
        tk.Radiobutton(method_frame, text="Clear Authentication", 
                      variable=method_var, value="clear",
                      font=('Arial', 14), 
                      fg='#ecf0f1', bg='#34495e',
                      selectcolor='#3498db').pack(pady=5, anchor='w')
        
        # Input frame
        input_frame = tk.Frame(auth_window, bg='#2c3e50')
        input_frame.pack(pady=20, padx=20, fill='x')
        
        # Code input
        tk.Label(input_frame, text="4-digit Code:", 
                font=('Arial', 14, 'bold'), 
                fg='#ecf0f1', bg='#2c3e50').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        
        code_entry = tk.Entry(input_frame, font=('Arial', 16), width=10,
                            bg='#34495e', fg='#ecf0f1')
        code_entry.grid(row=0, column=1, padx=10, pady=5)
        if self.user_code:
            code_entry.insert(0, self.user_code)
        
        # Username input
        tk.Label(input_frame, text="Username:", 
                font=('Arial', 14, 'bold'), 
                fg='#ecf0f1', bg='#2c3e50').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        
        user_entry = tk.Entry(input_frame, font=('Arial', 16), width=20,
                            bg='#34495e', fg='#ecf0f1')
        user_entry.grid(row=1, column=1, padx=10, pady=5)
        if self.username:
            user_entry.insert(0, self.username)
        
        # Password input
        tk.Label(input_frame, text="Password:", 
                font=('Arial', 14, 'bold'), 
                fg='#ecf0f1', bg='#2c3e50').grid(row=2, column=0, sticky='w', padx=10, pady=5)
        
        pass_entry = tk.Entry(input_frame, font=('Arial', 16), width=20, show='*',
                            bg='#34495e', fg='#ecf0f1')
        pass_entry.grid(row=2, column=1, padx=10, pady=5)
        if self.password:
            pass_entry.insert(0, self.password)
        
        # Buttons
        btn_frame = tk.Frame(auth_window, bg='#2c3e50')
        btn_frame.pack(pady=20)
        
        def save_auth():
            method = method_var.get()
            
            if method == "code":
                code = code_entry.get().strip()
                if len(code) == 4 and code.isdigit():
                    self.user_code = code
                    self.username = None
                    self.password = None
                    self.log_message("✅ 4-digit code authentication set")
                else:
                    messagebox.showerror("Invalid Code", "Code must be exactly 4 digits.")
                    return
                    
            elif method == "user":
                username = user_entry.get().strip()
                password = pass_entry.get().strip()
                
                if username and password:
                    self.username = username
                    self.password = password
                    self.user_code = None
                    self.log_message("✅ Username/password authentication set")
                else:
                    messagebox.showerror("Invalid Credentials", "Both username and password are required.")
                    return
                    
            elif method == "clear":
                self.user_code = None
                self.username = None
                self.password = None
                self.log_message("✅ Authentication cleared")
                
            self.save_config()
            self.update_status_display()
            auth_window.destroy()
            
            messagebox.showinfo("Authentication Saved", "Authentication settings have been saved!")
        
        btn_config = {
            'font': ('Arial', 16, 'bold'),
            'height': 2,
            'width': 15,
            'relief': 'raised',
            'bd': 3
        }
        
        save_btn = tk.Button(btn_frame, text="💾 Save", 
                           command=save_auth, 
                           bg='#2ecc71', fg='white', **btn_config)
        save_btn.pack(side='left', padx=10)
        
        cancel_btn = tk.Button(btn_frame, text="❌ Cancel", 
                             command=auth_window.destroy, 
                             bg='#e74c3c', fg='white', **btn_config)
        cancel_btn.pack(side='left', padx=10)
        
    def start_playback(self):
        """Start playlist playback"""
        if not self.store_id:
            messagebox.showwarning("No Store Selected", 
                                 "Please select a store first using 'Select Store' button.")
            return
            
        if self.playback_running:
            messagebox.showinfo("Already Playing", "Playback is already running!")
            return
            
        self.log_message("🎬 Starting playlist playback...")
        self.playback_running = True
        
        # Start playback in separate thread
        self.playback_thread = threading.Thread(target=self.playback_loop, daemon=True)
        self.playback_thread.start()
        
        messagebox.showinfo("Playback Started", 
                          "Playback has started!\nPress 'Stop Playback' or Backspace to stop.")
        
    def playback_loop(self):
        """Main playback loop (runs in separate thread)"""
        try:
            while self.playback_running:
                playlist = self.get_playlist()
                if not playlist:
                    self.log_message("⚠️ No content found. Retrying in 30 seconds...")
                    time.sleep(30)
                    continue
                    
                for item in playlist:
                    if not self.playback_running:
                        break
                        
                    if self.vlc_process:
                        self.vlc_process.terminate()
                        self.vlc_process = None
                        
                    url = item.get('url') or item.get('slice_url')
                    media_type = item.get('media_type', 'video')
                    duration = max(int(item.get('duration', 10)), 5)
                    
                    if url:
                        self.vlc_process = self.play_media(url, media_type)
                        if self.vlc_process:
                            try:
                                self.vlc_process.wait(timeout=duration)
                            except subprocess.TimeoutExpired:
                                if self.vlc_process:
                                    self.vlc_process.terminate()
                                    
                    time.sleep(1)
                    
        except Exception as e:
            self.log_message(f"❌ Playback error: {e}")
        finally:
            self.playback_running = False
            if self.vlc_process:
                self.vlc_process.terminate()
                self.vlc_process = None
                
    def stop_playback(self):
        """Stop playlist playback"""
        if not self.playback_running:
            messagebox.showinfo("Not Playing", "No playback is currently running.")
            return
            
        self.log_message("⏹️ Stopping playback...")
        self.playback_running = False
        
        if self.vlc_process:
            self.vlc_process.terminate()
            self.vlc_process = None
            
        messagebox.showinfo("Playback Stopped", "Playback has been stopped.")
        
    def toggle_playback(self):
        """Toggle playback state (space bar shortcut)"""
        if self.playback_running:
            self.stop_playback()
        else:
            self.start_playback()
            
    # Configuration and utility methods (same as CLI version)
    def get_playlist(self):
        """Get current playlist from server"""
        if not self.store_id:
            return []
            
        try:
            headers = {'User-Agent': 'phtv-pi/1.0 (Raspberry Pi GUI Client)'}
            if self.user_code:
                headers['X-User-Code'] = self.user_code
                
            url = f"{self.server_url.rstrip('/')}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('playlist', [])
                    
        except Exception as e:
            self.log_message(f"❌ Error getting playlist: {e}")
            
        return []
        
    def play_media(self, url, media_type='video'):
        """Play media using VLC with Pi optimizations"""
        try:
            vlc_args = [
                'vlc',
                '--intf', 'dummy',
                '--fullscreen',
                '--loop',
                '--no-video-title-show',
                '--quiet'
            ]
            
            if media_type == 'video':
                vlc_args.extend([
                    '--avcodec-hw=mmal',
                    '--file-caching=2000'
                ])
                
            vlc_args.append(url)
            
            self.log_message(f"▶️ Playing: {url}")
            return subprocess.Popen(vlc_args)
            
        except Exception as e:
            self.log_message(f"❌ Error starting playback: {e}")
            return None
            
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                f.write(f"SERVER_URL={self.server_url}\n")
                if self.store_id:
                    f.write(f"STORE_ID={self.store_id}\n")
                f.write(f"SCREEN_ID={self.screen_id}\n")
                if self.user_code:
                    f.write(f"USER_CODE={self.user_code}\n")
                if self.username:
                    f.write(f"USERNAME={self.username}\n")
                if self.password:
                    f.write(f"PASSWORD={self.password}\n")
        except Exception as e:
            self.log_message(f"⚠️ Could not save config: {e}")
            
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            if key == 'SERVER_URL':
                                self.server_url = value
                            elif key == 'STORE_ID':
                                self.store_id = value
                            elif key == 'SCREEN_ID':
                                self.screen_id = value
                            elif key == 'USER_CODE':
                                self.user_code = value
                            elif key == 'USERNAME':
                                self.username = value
                            elif key == 'PASSWORD':
                                self.password = value
            except Exception as e:
                print(f"⚠️ Could not load config: {e}")
                
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

if __name__ == "__main__":
    print("🍕 Pizza Hut TV GUI Client Starting...")
    
    # Check VLC installation
    try:
        subprocess.run(['vlc', '--version'], capture_output=True, check=True)
    except:
        print("⚠️ VLC not found. Some features may not work.")
        
    # Create and run GUI
    app = PizzaHutTVGUI()
    app.run()