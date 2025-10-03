#!/usr/bin/env python3
"""
🍕 Custom Media Player with GUI - EXACTLY like ea_tv.py
Full Tkinter GUI with TV linking, store selection, screen selection
Pure Python player - no VLC/MPV
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image
import requests
import threading
import time
import os
import sys
from io import BytesIO
import tempfile
import hashlib
import re
import statistics
from datetime import datetime, timedelta

class ServerTimeSync:
    """Enterprise-grade server time synchronization - like webplayer"""
    def __init__(self, base_url="https://everydayadvertise.com"):
        self.base_url = base_url
        self.server_time_offset = 0  # Offset between server and client
        self.network_latency = 0
        self.last_sync = 0
        self.sync_samples = []
        self.sync_interval_ms = 2000  # 2-second alignment intervals
        
    def get_server_time(self, max_retries=3):
        """Fetch server time with latency compensation - EXACTLY like webplayer"""
        samples = []
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                response = requests.get(
                    f"{self.base_url}/api/server_time",
                    headers={'Cache-Control': 'no-cache'},
                    timeout=5
                )
                request_latency_ms = (time.time() - start_time) * 1000
                
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")
                
                data = response.json()
                client_time_ms = time.time() * 1000
                server_time_ms = data.get('server_time_ms', client_time_ms)
                
                # Compensate for network latency (half of round-trip)
                adjusted_server_time = server_time_ms + (request_latency_ms / 2)
                offset = adjusted_server_time - client_time_ms
                
                samples.append({
                    'offset': offset,
                    'latency': request_latency_ms,
                    'timestamp': client_time_ms
                })
                
                print(f"🌐 SERVER TIME SAMPLE {attempt + 1}: "
                      f"latency={request_latency_ms:.1f}ms, "
                      f"offset={offset:.3f}ms")
                
            except Exception as e:
                print(f"⚠️ Server time sync attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    print("❌ All sync attempts failed, using local time")
                    return time.time() * 1000
                time.sleep(0.1)
        
        if samples:
            # Calculate median offset for accuracy
            offsets = sorted([s['offset'] for s in samples])
            median_offset = statistics.median(offsets)
            
            # Calculate average latency
            avg_latency = sum(s['latency'] for s in samples) / len(samples)
            
            self.server_time_offset = median_offset
            self.network_latency = avg_latency
            self.last_sync = time.time() * 1000
            
            # Store samples for trend analysis
            self.sync_samples.append({
                'offset': median_offset,
                'latency': avg_latency,
                'timestamp': self.last_sync
            })
            
            # Keep only last 10 samples
            if len(self.sync_samples) > 10:
                self.sync_samples = self.sync_samples[-10:]
            
            print(f"✅ FINAL SERVER TIME SYNC: "
                  f"offset={median_offset:.3f}ms, "
                  f"latency={avg_latency:.1f}ms, "
                  f"samples={len(samples)}")
            
            return time.time() * 1000 + median_offset
        
        return time.time() * 1000
    
    def get_current_server_time(self):
        """Get current server time using cached offset"""
        return time.time() * 1000 + self.server_time_offset
    
    def calculate_next_sync_moment(self):
        """Calculate next aligned timestamp - ALL screens sync to same moment"""
        server_time = self.get_current_server_time()
        next_sync = ((server_time // self.sync_interval_ms) + 1) * self.sync_interval_ms
        
        print(f"🎯 GLOBAL SYNC: Next alignment at timestamp {int(next_sync)}")
        return next_sync
    
    def wait_for_sync_moment(self, target_timestamp):
        """Wait until exact sync moment"""
        while True:
            current = self.get_current_server_time()
            remaining = (target_timestamp - current) / 1000.0
            
            if remaining <= 0:
                print(f"🚀 SYNC MOMENT REACHED!")
                break
            
            if remaining > 0.5:
                time.sleep(0.1)
            else:
                time.sleep(0.001)  # Precise timing


# Schedule checking functions - MATCH DASHBOARD LOGIC
def parse_time_string(time_str, now):
    """Parse HH:MM or ISO datetime string"""
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # ISO format: YYYY-MM-DDTHH:MM:SS
    if 'T' in time_str or ('-' in time_str and len(time_str) > 10):
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except:
            return None
    
    # Date only: YYYY-MM-DD
    if len(time_str) == 10 and time_str.count('-') == 2:
        try:
            return datetime.strptime(time_str, '%Y-%m-%d')
        except:
            return None
    
    # Time only: HH:MM or HH:MM:SS
    if ':' in time_str:
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        except:
            return None
    
    return None


def is_in_time_window(now, start_str, end_str, days=None):
    """Check if now is within time window - MATCHES DASHBOARD"""
    # Check weekday first
    if days:
        weekday = ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]
        if weekday not in days:
            return False
    
    if not (start_str or end_str):
        return True
    
    # Parse times
    start_time = parse_time_string(start_str, now) if start_str else None
    end_time = parse_time_string(end_str, now) if end_str else None
    
    # Date-only normalization
    if end_str and len(end_str) == 10 and end_time:
        end_time = end_time.replace(hour=23, minute=59, second=59)
    if start_str and len(start_str) == 10 and not end_str and start_time:
        end_time = start_time.replace(hour=23, minute=59, second=59)
    if end_str and len(end_str) == 10 and not start_str and end_time:
        start_time = end_time.replace(hour=0, minute=0, second=0)
    
    # Handle overnight wrap (e.g., 22:00 - 02:00)
    if start_time and end_time:
        time_only = (':' in (start_str or '') and len(start_str or '') <= 8)
        if end_time < start_time:
            if not time_only and start_time.date() == end_time.date():
                # Same-date absolute: treat as end + 1 day
                end_time_plus = end_time + timedelta(days=1)
                return start_time <= now <= end_time_plus
            # Overnight: active if after start OR before end
            return now >= start_time or now <= end_time
        else:
            # Normal: active if between start and end
            return start_time <= now <= end_time
    
    # Single boundary
    if start_time and now < start_time:
        return False
    if end_time and now > end_time:
        return False
    
    return True


def is_item_active_now(item):
    """Check if item should play based on schedule - MATCHES DASHBOARD LOGIC"""
    now = datetime.now()
    
    # Check if enabled
    if not item.get('enabled', True):
        return False
    
    # Check multiple schedule windows first (priority)
    schedule_windows = item.get('schedule', [])
    if schedule_windows:
        for window in schedule_windows:
            if is_in_time_window(now, window.get('start'), window.get('end'), window.get('days')):
                return True  # Active in at least one window
        return False  # No windows are active
    
    # Check single start/end window
    start = item.get('start')
    end = item.get('end')
    days = item.get('days', [])
    
    if start or end or days:
        return is_in_time_window(now, start, end, days)
    
    # No schedule restrictions = always active
    return True


class CustomPlayerGUI:
    def __init__(self):
        # Set display
        if not os.environ.get('DISPLAY'):
            os.environ['DISPLAY'] = ':0'
        
        self.root = tk.Tk()
        self.root.title("🍕 EA TV - Custom Player")
        self.root.geometry("600x500")
        self.root.configure(bg='#0d0d0d')
        
        # State
        self.android_tv_code = ""
        self.store_code = ""
        self.screen_id = ""
        self.current_step = 1
        self.player = None
        
        # Setup GUI
        self.setup_gui()
        
        # Make closeable
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Escape>', lambda e: self.on_closing())
        
    def setup_gui(self):
        """Setup the GUI"""
        self.panel = tk.Frame(self.root, bg='#0d0d0d', padx=28, pady=28)
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
            text="Type the 4-digit code from dashboard",
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
        
        # Input field
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
        self.input_field.bind('<Return>', lambda e: self.next_step())
        self.input_field.focus()
        
        # Main button
        self.main_button = tk.Button(
            self.panel,
            text="Link Code",
            font=("Arial", 12, "bold"),
            bg="#c8102e",
            fg="#ffffff",
            activebackground="#a00d24",
            activeforeground="#ffffff",
            bd=0,
            padx=32,
            pady=12,
            cursor="hand2",
            command=self.next_step
        )
        self.main_button.pack(pady=(0, 12))
        
        # Status label
        self.status_label = tk.Label(
            self.panel,
            text="",
            font=("Arial", 10),
            fg="#999999",
            bg="#0d0d0d"
        )
        self.status_label.pack(pady=(8, 0))
        
    def next_step(self):
        """Handle next button click"""
        if self.current_step == 1:
            self.verify_android_code()
        elif self.current_step == 3:
            self.select_screen()
            
    def verify_android_code(self):
        """Accept Android TV code (no verification needed)"""
        code = self.input_field.get().strip()
        
        if not code:
            self.status_label.config(text="❌ Please enter a code", fg="#ff4444")
            return
        
        if len(code) != 4 or not code.isdigit():
            self.status_label.config(text="❌ Code must be 4 digits", fg="#ff4444")
            return
        
        # Just accept the code - no API verification
        self.android_tv_code = code
        self.status_label.config(text=f"✅ Code accepted: {code}", fg="#00ff00")
        print(f"✅ Android TV Code: {code}")
        self.root.update()
        time.sleep(0.5)
        self.show_store_selection()
    
    def show_store_selection(self):
        """Show store code entry screen"""
        self.current_step = 2
        
        # Clear current widgets
        for widget in self.panel.winfo_children():
            widget.destroy()
        
        # Title
        tk.Label(
            self.panel,
            text="Enter Store ID",
            font=("Arial", 20, "bold"),
            fg="#f4f4f4",
            bg="#0d0d0d"
        ).pack(pady=(0, 12))
        
        # Subtitle
        tk.Label(
            self.panel,
            text=f"TV Code: {self.android_tv_code}",
            font=("Arial", 12),
            fg="#bbbbbb",
            bg="#0d0d0d"
        ).pack(pady=(0, 16))
        
        # Input label
        tk.Label(
            self.panel,
            text="Store ID (e.g., 1000, 1001, 1002)",
            font=("Arial", 11),
            fg="#cccccc",
            bg="#0d0d0d"
        ).pack(anchor='w', pady=(12, 8))
        
        # Input field
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
        self.input_field.bind('<Return>', lambda e: self.select_store_by_input())
        self.input_field.focus()
        
        # Main button
        tk.Button(
            self.panel,
            text="Continue",
            font=("Arial", 12, "bold"),
            bg="#c8102e",
            fg="#ffffff",
            activebackground="#a00d24",
            activeforeground="#ffffff",
            bd=0,
            padx=32,
            pady=12,
            cursor="hand2",
            command=self.select_store_by_input
        ).pack(pady=(0, 12))
        
        # Back button
        tk.Button(
            self.panel,
            text="← Back",
            font=("Arial", 11),
            bg="#666666",
            fg="#ffffff",
            activebackground="#555555",
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.setup_gui
        ).pack(pady=(0, 12))
        
        # Status label
        self.status_label = tk.Label(
            self.panel,
            text="Each store has different screens",
            font=("Arial", 10),
            fg="#999999",
            bg="#0d0d0d"
        )
        self.status_label.pack(pady=(8, 0))
    
    def select_store_by_input(self):
        """Handle store ID input"""
        store_id = self.input_field.get().strip()
        
        if not store_id:
            self.status_label.config(text="❌ Please enter a store ID", fg="#ff4444")
            return
        
        if not store_id.isdigit():
            self.status_label.config(text="❌ Store ID must be numeric", fg="#ff4444")
            return
        
        self.store_code = store_id
        print(f"✅ Store ID: {store_id}")
        self.show_screen_selection()
    
    def show_screen_selection(self):
        """Show screen selection - fetch from API"""
        self.current_step = 3
        
        # Clear
        for widget in self.panel.winfo_children():
            widget.destroy()
        
        # Title
        tk.Label(
            self.panel,
            text="Select Screen",
            font=("Arial", 20, "bold"),
            fg="#f4f4f4",
            bg="#0d0d0d"
        ).pack(pady=(0, 12))
        
        # Subtitle
        tk.Label(
            self.panel,
            text=f"Store: {self.store_code} | TV Code: {self.android_tv_code}",
            font=("Arial", 12),
            fg="#bbbbbb",
            bg="#0d0d0d"
        ).pack(pady=(0, 16))
        
        # Status label
        status_label = tk.Label(
            self.panel,
            text="🔍 Loading available screens...",
            font=("Arial", 11),
            fg="#ffaa00",
            bg="#0d0d0d"
        )
        status_label.pack(pady=(0, 12))
        
        self.root.update()
        
        # Fetch actual screens from API
        try:
            url = f"https://everydayadvertise.com/api/stores_by_code/{self.android_tv_code}"
            print(f"🔍 Fetching screens from: {url}")
            response = requests.get(url, timeout=10)
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"❌ Failed to load screens (Status: {response.status_code})"
                print(f"{error_msg}")
                try:
                    error_data = response.json()
                    print(f"   Error details: {error_data}")
                    if 'error' in error_data:
                        error_msg = f"❌ {error_data['error']}"
                except:
                    pass
                status_label.config(text=error_msg, fg="#ff4444")
                # Add back button
                tk.Button(
                    self.panel,
                    text="← Back",
                    font=("Arial", 11),
                    bg="#666666",
                    fg="#ffffff",
                    activebackground="#555555",
                    activeforeground="#ffffff",
                    bd=0,
                    padx=20,
                    pady=8,
                    cursor="hand2",
                    command=self.show_store_selection
                ).pack(pady=10)
                return
            
            data = response.json()
            if not data.get('success'):
                status_label.config(text="❌ Invalid response", fg="#ff4444")
                # Add back button
                tk.Button(
                    self.panel,
                    text="← Back",
                    font=("Arial", 11),
                    bg="#666666",
                    fg="#ffffff",
                    activebackground="#555555",
                    activeforeground="#ffffff",
                    bd=0,
                    padx=20,
                    pady=8,
                    cursor="hand2",
                    command=self.show_store_selection
                ).pack(pady=10)
                return
            
            screens_data = data.get('screens', {}).get(self.store_code, {})
            
            if not screens_data:
                # Check if ANY stores exist
                all_stores = data.get('stores', [])
                store_ids = [str(s.get('id')) for s in all_stores if s.get('id')]
                
                if store_ids:
                    status_label.config(
                        text=f"❌ Store '{self.store_code}' not found.\nAvailable stores: {', '.join(store_ids)}",
                        fg="#ff4444"
                    )
                else:
                    status_label.config(
                        text="❌ No stores configured.\nPlease add stores in dashboard first.",
                        fg="#ff4444"
                    )
                
                # Add back button to re-enter store ID
                tk.Button(
                    self.panel,
                    text="← Back to Store Entry",
                    font=("Arial", 12, "bold"),
                    bg="#c8102e",
                    fg="#ffffff",
                    activebackground="#a00d24",
                    activeforeground="#ffffff",
                    bd=0,
                    padx=32,
                    pady=12,
                    cursor="hand2",
                    command=self.show_store_selection
                ).pack(pady=20)
                return
            
            status_label.config(text=f"✅ Found {len(screens_data)} screen(s)", fg="#00ff00")
            
            # Create scrollable frame for screen options
            canvas = tk.Canvas(self.panel, bg='#0d0d0d', highlightthickness=0, height=350)
            scrollbar = tk.Scrollbar(self.panel, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='#0d0d0d')
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True, pady=12)
            scrollbar.pack(side="right", fill="y")
            
            # Display actual screens from dashboard
            for full_screen_id, screen_info in sorted(screens_data.items()):
                # Extract screen type from full ID (e.g., "1000_screen2" -> "screen2")
                screen_id = full_screen_id.replace(f"{self.store_code}_", "")
                
                # Determine screen type and icon
                if screen_id.startswith('promo'):
                    icon = "📱"
                    desc = f"Vertical display - {screen_info.get('vertical', True) and 'Portrait' or 'Landscape'}"
                elif screen_id.startswith('screen'):
                    icon = "🖥️"
                    screen_num = screen_id.replace('screen', '')
                    desc = f"Horizontal display #{screen_num}"
                else:
                    icon = "📺"
                    desc = "Display"
                
                frame = tk.Frame(scrollable_frame, bg='#1a1a1a', bd=1, relief='solid')
                frame.pack(fill='x', pady=4, padx=8)
                
                btn = tk.Button(
                    frame,
                    text=f"{icon} {screen_id.title()}\n{desc}",
                    font=("Arial", 11),
                    bg="#1a1a1a",
                    fg="#ffffff",
                    activebackground="#c8102e",
                    activeforeground="#ffffff",
                    bd=0,
                    padx=15,
                    pady=10,
                    cursor="hand2",
                    justify='left',
                    anchor='w',
                    command=lambda s=screen_id: self.on_screen_selected(s)
                )
                btn.pack(fill='x')
            
            # Add back button below the screen list
            tk.Button(
                self.panel,
                text="← Back to Store Entry",
                font=("Arial", 11),
                bg="#666666",
                fg="#ffffff",
                activebackground="#555555",
                activeforeground="#ffffff",
                bd=0,
                padx=20,
                pady=8,
                cursor="hand2",
                command=self.show_store_selection
            ).pack(pady=12)
                
        except Exception as e:
            status_label.config(text=f"❌ Error: {str(e)[:50]}", fg="#ff4444")
            print(f"❌ Error fetching screens: {e}")
            
            # Add back button on error
            tk.Button(
                self.panel,
                text="← Back to Store Entry",
                font=("Arial", 12, "bold"),
                bg="#c8102e",
                fg="#ffffff",
                activebackground="#a00d24",
                activeforeground="#ffffff",
                bd=0,
                padx=32,
                pady=12,
                cursor="hand2",
                command=self.show_store_selection
            ).pack(pady=20)
    
    def on_screen_selected(self, screen_id):
        """Handle screen selection and start player"""
        self.screen_id = screen_id
        
        # Clear GUI
        for widget in self.panel.winfo_children():
            widget.destroy()
        
        # Show starting message
        tk.Label(
            self.panel,
            text="✅ Setup Complete!",
            font=("Arial", 20, "bold"),
            fg="#00ff00",
            bg="#0d0d0d"
        ).pack(pady=20)
        
        tk.Label(
            self.panel,
            text=f"Store: {self.store_code} | Screen: {self.screen_id}",
            font=("Arial", 12),
            fg="#bbbbbb",
            bg="#0d0d0d"
        ).pack(pady=10)
        
        tk.Label(
            self.panel,
            text="Starting player...",
            font=("Arial", 14),
            fg="#ffaa00",
            bg="#0d0d0d"
        ).pack(pady=20)
        
        self.root.update()
        time.sleep(1)
        
        # Hide GUI window
        self.root.withdraw()
        
        # Start player
        self.start_player()
    
    def start_player(self):
        """Start the custom player"""
        self.player = CustomMediaPlayer(
            self.store_code,
            self.screen_id,
            self.android_tv_code
        )
        
        try:
            self.player.start()
        except Exception as e:
            print(f"❌ Player error: {e}")
            self.root.deiconify()
            messagebox.showerror("Error", f"Player failed: {e}")
    
    def on_closing(self):
        """Handle window close"""
        if self.player:
            self.player.stop()
        self.root.quit()
        sys.exit(0)
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()


class CustomMediaPlayer:
    """The actual media player"""
    def __init__(self, store_code, screen_id, android_tv_code=None):
        self.store_code = store_code
        self.screen_id = screen_id
        self.android_tv_code = android_tv_code
        self.running = False
        self.current_playlist = []
        self.current_index = 0
        self.last_playlist_signature = None
        
        # Default screen dimensions (will be auto-detected at start)
        self.screen_width = 1920
        self.screen_height = 1080
        self.slice_width = 1920
        self.actual_screen_width = None
        self.actual_screen_height = None
        
        # Calculate crop offset for slice videos
        # IMPORTANT: Screen IDs can be ANY user-defined string (not just "screen1", "screen2", etc.)
        # The slice order comes from playlist metadata (sync_ref.order), NOT from parsing screen ID!
        # We'll set crop_x_offset dynamically when playlist is loaded, based on sync_ref.order
        
        # Detect if this is a promo screen (promo screens don't use slicing)
        if str(screen_id).startswith('promo'):
            self.is_promo = True
        else:
            self.is_promo = False
        
        # Initialize crop offset to 0 - will be updated from playlist metadata
        self.crop_x_offset = 0
        self.slice_order = 0  # Will be set from sync_ref.order when playlist loads
        
        self.transition_duration = 0.5
        self.fade_enabled = True
        self.media_cache = {}
        self.cache_dir = tempfile.gettempdir()
        self.window_name = f"EA TV Screen {screen_id}"
        
        # Screen orientation and rotation (from dashboard)
        self.orientation = 'default'  # 'vertical', 'horizontal', 'default'
        self.rotation = 0  # 0, 90, 180, 270 degrees
        
        # Initialize server time sync coordinator
        self.sync = ServerTimeSync()
        
        # Log screen configuration
        screen_type = "Promo" if self.is_promo else f"Screen {screen_id}"
        print(f"\n🎬 Player Ready - {screen_type} | Store {store_code}")
        print(f"🔑 Screen ID: {screen_id} (slice order will be loaded from playlist metadata)")
        print(f"🔑 Press ESC or Q to exit\n")
        
    def start(self):
        self.running = True
        
        # Synchronize with server time FIRST
        print("🌐 Synchronizing with server time...")
        self.sync.get_server_time()
        
        # Get playlist BEFORE creating window to know orientation
        playlist_items = self.get_playlist_from_server()
        
        print(f"📐 Orientation: {self.orientation}, Rotation: {self.rotation}°")
        
        # Create window and detect actual screen size
        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            
            # Get actual screen dimensions by creating a test frame
            import tkinter as tk
            root = tk.Tk()
            self.actual_screen_width = root.winfo_screenwidth()
            self.actual_screen_height = root.winfo_screenheight()
            root.destroy()
            
            print(f"🖥️ Detected screen: {self.actual_screen_width}x{self.actual_screen_height}")
            
            # Use detected dimensions
            self.screen_width = self.actual_screen_width
            self.screen_height = self.actual_screen_height
            
        except Exception as e:
            print(f"❌ Window error: {e}")
            print(f"🖥️ Using default: {self.screen_width}x{self.screen_height}")
        
        if playlist_items:
            self.current_playlist = playlist_items
            self.last_playlist_signature = self.calc_signature(playlist_items)
        
        threading.Thread(target=self.playlist_manager_loop, daemon=True).start()
        self.playback_loop()
        
    def stop(self):
        self.running = False
        cv2.destroyAllWindows()
        
    def calc_signature(self, playlist):
        try:
            parts = []
            for item in playlist:
                url, _ = self.resolve_url(item)
                if url:
                    url_clean = re.sub(r'[&?]cb=\d+', '', url)
                    parts.append((url_clean, item.get('duration', 10)))
            return hash(tuple(parts))
        except:
            return hash(str(playlist))
        
    def get_playlist_from_server(self):
        try:
            # Construct full screen ID for API call
            # self.screen_id is already like "screen0", "screen1", "promo1", etc.
            full_screen_id = f"{self.store_code}_{self.screen_id}"
                
            url = f"https://everydayadvertise.com/playlist/{self.store_code}/{full_screen_id}"
            headers = {}
            if self.android_tv_code:
                headers['X-User-Code'] = self.android_tv_code
            
            print(f"🔍 Fetching playlist:")
            print(f"   Store: {self.store_code}")
            print(f"   Screen: {self.screen_id}")
            print(f"   Full Screen ID: {full_screen_id}")
            print(f"   URL: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Update orientation and rotation from dashboard
                self.orientation = data.get('orientation', 'default')
                self.rotation = int(data.get('rotation', 0))
                
                # Always log rotation setting for debugging
                print(f"📐 Screen config - Orientation: {self.orientation}, Rotation: {self.rotation}°")
                
                playlist = data.get('playlist', [])
                print(f"✅ Loaded {len(playlist)} items from playlist")
                
                # Extract slice order from sync_ref metadata (correct approach - don't parse screen ID!)
                # Check first video item for sync_ref.order to determine this screen's slice position
                print(f"🔍 DEBUG: is_promo={self.is_promo}, playlist items={len(playlist)}")
                if playlist and not self.is_promo:
                    for item in playlist:
                        media_type = item.get('media_type')
                        print(f"🔍 DEBUG: Checking item - media_type={media_type}")
                        if media_type == 'video':
                            sync_ref = item.get('sync_ref', {})
                            print(f"🔍 DEBUG: Found video item, sync_ref={sync_ref}")
                            if isinstance(sync_ref, dict) and sync_ref:
                                # Get slice order from metadata (0 = first slice, 1 = second slice, etc.)
                                self.slice_order = int(sync_ref.get('order', 0))
                                self.crop_x_offset = self.slice_order * self.slice_width
                                slice_count = sync_ref.get('count', 1)
                                slice_mode = sync_ref.get('mode', 'split-h')
                                print(f"🎬 Slice configuration from playlist metadata:")
                                print(f"   Slice order: {self.slice_order} (of {slice_count} screens)")
                                print(f"   Slice mode: {slice_mode}")
                                print(f"   Crop X offset: {self.crop_x_offset}px")
                                break
                    else:
                        # No sync_ref found in any video item
                        print(f"ℹ️ No slice metadata found - displaying full video")
                        self.slice_order = 0
                        self.crop_x_offset = 0
                
                # Debug: Show first item if available
                if playlist:
                    first_item = playlist[0]
                    print(f"   First item: {first_item.get('file', 'unknown')[:50]}...")
                else:
                    print(f"⚠️ Playlist is EMPTY - no items returned!")
                    
                return playlist
            else:
                print(f"❌ Playlist fetch failed: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Response: {response.text[:200]}")
            return []
        except Exception as e:
            print(f"❌ Playlist fetch error: {e}")
            return []
    
    def resolve_url(self, item):
        try:
            slice_aware = item.get('slice_aware') or item.get('is_slice') or False
            
            if slice_aware:
                slice_url = item.get('slice_url')
                if slice_url and 'slice-video' in slice_url:
                    match = re.search(r'/slice-video/(.+?)(?:\?|$)', slice_url)
                    if match:
                        return f"https://cdn.everydayadvertise.com/{match.group(1)}", True
                    return slice_url, True
            
            url = item.get('url')
            if url:
                if 'slice-video' in url:
                    match = re.search(r'/slice-video/(.+?)(?:\?|$)', url)
                    if match:
                        return f"https://cdn.everydayadvertise.com/{match.group(1)}", True
                return url, 'slice-video' in url or slice_aware
            return None, False
        except:
            return None, False
    
    def download_media(self, url):
        try:
            cache_key = hashlib.md5(url.encode()).hexdigest()
            if cache_key in self.media_cache:
                return self.media_cache[cache_key]
            
            response = requests.get(url, timeout=30, stream=True)
            if response.status_code != 200:
                return None
            
            content_type = response.headers.get('content-type', '')
            is_video = 'video' in content_type or url.lower().endswith(('.mp4', '.webm'))
            is_image = 'image' in content_type or url.lower().endswith(('.jpg', '.png'))
            
            if is_video:
                temp_file = os.path.join(self.cache_dir, f"{cache_key}.mp4")
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                self.media_cache[cache_key] = ('video', temp_file)
                return ('video', temp_file)
            elif is_image:
                pil_image = Image.open(BytesIO(response.content))
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                self.media_cache[cache_key] = ('image', cv_image)
                return ('image', cv_image)
            return None
        except:
            return None
    
    def crop_frame(self, frame, is_slice):
        try:
            if not is_slice:
                return self.resize_frame(frame)
            h, w = frame.shape[:2]
            if w >= 5000:
                x_start = self.crop_x_offset
                x_end = x_start + self.slice_width
                if x_end > w:
                    x_end = w
                    x_start = max(0, x_end - self.slice_width)
                cropped = frame[0:h, x_start:x_end]
                # Apply rotation and resize to fill screen
                rotated = self.apply_rotation(cropped)
                # Ensure it fills the screen
                return cv2.resize(rotated, (self.screen_width, self.screen_height), interpolation=cv2.INTER_LINEAR)
            return self.resize_frame(frame)
        except:
            return frame
    
    def apply_rotation(self, frame):
        """Apply rotation transform based on self.rotation and orientation"""
        try:
            # First, apply dashboard rotation setting
            if self.rotation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif self.rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif self.rotation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # Then, if vertical orientation, rotate 90° more to fit horizontal screen
            if self.orientation == 'vertical':
                h, w = frame.shape[:2]
                # If frame is portrait (taller than wide), rotate to landscape
                if h > w:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            
            return frame
        except Exception as e:
            print(f"⚠️ Rotation error: {e}")
            return frame
    
    def resize_frame(self, frame):
        try:
            # Apply rotation first
            frame = self.apply_rotation(frame)
            
            h, w = frame.shape[:2]
            
            # Use actual screen dimensions
            target_w, target_h = self.screen_width, self.screen_height
            
            # Debug: Print dimensions (only occasionally to avoid spam)
            if hasattr(self, '_debug_frame_count'):
                self._debug_frame_count += 1
            else:
                self._debug_frame_count = 0
                print(f"🖼️ Frame after rotation: {w}x{h}")
                print(f"🖥️ Target screen: {target_w}x{target_h}")
                print(f"📐 Orientation: {self.orientation}, Rotation: {self.rotation}°")
            
            # Calculate scale to FILL screen (no black bars, may crop edges slightly)
            scale = max(target_w / w, target_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            
            if self._debug_frame_count == 0:
                print(f"📏 Scale: {scale:.3f}, Scaled size: {new_w}x{new_h}")
                crop_w = new_w - target_w
                crop_h = new_h - target_h
                print(f"✂️ Cropping: {crop_w}px width, {crop_h}px height from center")
            
            # Resize with high-quality interpolation
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Crop from center to exact screen size
            y_start = max(0, (new_h - target_h) // 2)
            x_start = max(0, (new_w - target_w) // 2)
            
            cropped = resized[y_start:y_start+target_h, x_start:x_start+target_w]
            
            # Ensure exact dimensions
            if cropped.shape[0] != target_h or cropped.shape[1] != target_w:
                cropped = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            
            return cropped
        except Exception as e:
            print(f"⚠️ Resize error: {e}")
            return frame
    
    def fade(self, old, new, progress):
        try:
            if old is None: return new
            if new is None: return old
            
            # ALWAYS use full physical screen dimensions
            target_w, target_h = self.screen_width, self.screen_height
            
            if old.shape != new.shape:
                old = cv2.resize(old, (target_w, target_h))
                new = cv2.resize(new, (target_w, target_h))
            return cv2.addWeighted(old, 1 - progress, new, progress, 0)
        except:
            return new
    
    def play_video(self, path, is_slice, duration, last):
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened(): return last
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            start = time.time()
            done = False
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                proc = self.crop_frame(frame, is_slice)
                elapsed = time.time() - start
                if not done and elapsed < self.transition_duration:
                    proc = self.fade(last, proc, elapsed / self.transition_duration)
                else:
                    done = True
                cv2.imshow(self.window_name, proc)
                if elapsed >= duration:
                    cap.release()
                    return proc
                key = cv2.waitKey(int(1000 / fps)) & 0xFF
                if key == 27 or key == ord('q') or key == ord('Q'):  # ESC or Q
                    print("🛑 Exit key pressed")
                    self.running = False
                    break
            cap.release()
            return proc
        except:
            return last
    
    def play_image(self, img, is_slice, duration, last):
        try:
            proc = self.crop_frame(img, is_slice)
            start = time.time()
            done = False
            while self.running:
                elapsed = time.time() - start
                if not done and elapsed < self.transition_duration:
                    disp = self.fade(last, proc, elapsed / self.transition_duration)
                else:
                    disp = proc
                    done = True
                cv2.imshow(self.window_name, disp)
                if elapsed >= duration: return proc
                key = cv2.waitKey(100) & 0xFF
                if key == 27 or key == ord('q') or key == ord('Q'):  # ESC or Q
                    print("🛑 Exit key pressed")
                    self.running = False
                    break
            return proc
        except:
            return last
    
    def playback_loop(self):
        last = None
        played_once = set()  # Track items played once (for repeat=false)
        
        # ALWAYS use full physical screen dimensions
        canvas_w, canvas_h = self.screen_width, self.screen_height
        
        while self.running:
            if not self.current_playlist:
                black = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
                cv2.putText(black, "Waiting for content...", (canvas_w//4, canvas_h//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
                cv2.imshow(self.window_name, black)
                key = cv2.waitKey(1000) & 0xFF
                if key == 27 or key == ord('q') or key == ord('Q'):  # ESC or Q
                    print("🛑 Exit key pressed")
                    break
                continue
            
            # ⏰ FILTER ITEMS BASED ON SCHEDULE (enabled, start, end, days, schedule)
            active_items = [i for i in self.current_playlist if is_item_active_now(i)]
            
            if not active_items:
                # No items active right now - show "waiting" screen
                black = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
                cv2.putText(black, "No scheduled content now", (canvas_w//5, canvas_h//2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (200,200,0), 2)
                cv2.imshow(self.window_name, black)
                key = cv2.waitKey(1000) & 0xFF
                if key == 27 or key == ord('q') or key == ord('Q'):
                    print("🛑 Exit key pressed")
                    break
                print("⏰ No items scheduled right now, waiting...")
                time.sleep(5)
                continue
            
            # 🔁 FILTER OUT NON-REPEATING ITEMS ALREADY PLAYED
            playable_items = []
            for item in active_items:
                item_id = item.get('id') or item.get('file')
                if item.get('repeat', True):
                    playable_items.append(item)
                elif item_id not in played_once:
                    playable_items.append(item)
            
            if not playable_items:
                # All items played once - reset cycle
                print("🔄 All play-once items completed, resetting cycle")
                played_once.clear()
                playable_items = active_items
            
            # Get current item from playable set
            if self.current_index >= len(playable_items):
                self.current_index = 0
            
            item = playable_items[self.current_index]
            url, is_slice = self.resolve_url(item)
            if not url:
                self.current_index = (self.current_index + 1) % len(playable_items)
                continue
            
            duration = int(item.get('duration', 10) or 10)
            title = item.get('title') or item.get('file', 'Item')
            
            # 🎯 WAIT FOR SYNC MOMENT - All screens align here!
            next_sync = self.sync.calculate_next_sync_moment()
            print(f"⏳ Waiting for sync moment... (item: {title})")
            self.sync.wait_for_sync_moment(next_sync)
            print(f"▶️  {title} ({duration}s) - SYNCHRONIZED START!")
            
            # Mark as played if repeat=false
            if not item.get('repeat', True):
                item_id = item.get('id') or item.get('file')
                if item_id:
                    played_once.add(item_id)
            
            media = self.download_media(url)
            if not media:
                self.current_index = (self.current_index + 1) % len(playable_items)
                continue
            
            mtype, content = media
            if mtype == 'video':
                last = self.play_video(content, is_slice, duration, last)
            else:
                last = self.play_image(content, is_slice, duration, last)
            
            self.current_index = (self.current_index + 1) % len(playable_items)
    
    def playlist_manager_loop(self):
        while self.running:
            try:
                # Re-sync server time every 60 seconds
                time_since_sync = (time.time() * 1000 - self.sync.last_sync) / 1000
                if time_since_sync > 60:
                    print("🔄 Re-syncing server time...")
                    self.sync.get_server_time()
                
                items = self.get_playlist_from_server()
                if items:
                    sig = self.calc_signature(items)
                    if sig != self.last_playlist_signature:
                        print(f"🔄 Playlist updated ({len(items)} items)")
                        self.current_playlist = items
                        self.current_index = 0
                        self.last_playlist_signature = sig
                        self.media_cache.clear()
                time.sleep(15)
            except:
                time.sleep(10)


def main():
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
    
    app = CustomPlayerGUI()
    app.run()


if __name__ == '__main__':
    main()
