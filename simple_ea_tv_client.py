#!/usr/bin/env python3
"""
🍕 Simple EA TV Pi Client - No Hang, Easy to Close
Works exactly like webplayer with store code input
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import webbrowser
import subprocess
import sys
import threading
import time

class SimpleEATVClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🍕 EA TV - Pizza Hut TV")
        self.root.geometry("500x400")
        self.root.configure(bg='#C41E3A')  # Pizza Hut red
        
        # Make window closeable easily
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind ESC key to close
        self.root.bind('<Escape>', lambda e: self.on_closing())
        self.root.bind('<q>', lambda e: self.on_closing())
        self.root.bind('<Q>', lambda e: self.on_closing())
        
        self.setup_gui()
        self.running = True
        
    def setup_gui(self):
        """Setup the main GUI."""
        
        # Title
        title_frame = tk.Frame(self.root, bg='#C41E3A')
        title_frame.pack(pady=20)
        
        tk.Label(
            title_frame,
            text="🍕 EA TV",
            font=("Arial", 24, "bold"),
            fg="white",
            bg="#C41E3A"
        ).pack()
        
        tk.Label(
            title_frame,
            text="Pizza Hut TV Client",
            font=("Arial", 12),
            fg="white",
            bg="#C41E3A"
        ).pack()
        
        # Main content frame
        content_frame = tk.Frame(self.root, bg="white", padx=20, pady=20)
        content_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Store code input
        tk.Label(
            content_frame,
            text="Enter Store Code or Link:",
            font=("Arial", 12, "bold")
        ).pack(pady=10)
        
        self.store_entry = tk.Entry(
            content_frame,
            font=("Arial", 12),
            width=30
        )
        self.store_entry.pack(pady=5)
        self.store_entry.insert(0, "1000")  # Default store
        
        # Screen selection
        tk.Label(
            content_frame,
            text="Select Screen:",
            font=("Arial", 12, "bold")
        ).pack(pady=(20, 5))
        
        self.screen_var = tk.StringVar(value="1")
        screen_frame = tk.Frame(content_frame, bg="white")
        screen_frame.pack(pady=5)
        
        for i, screen_name in enumerate(["Screen 1 (Left)", "Screen 2 (Center)", "Screen 3 (Right)"], 1):
            tk.Radiobutton(
                screen_frame,
                text=screen_name,
                variable=self.screen_var,
                value=str(i),
                font=("Arial", 10),
                bg="white"
            ).pack(anchor='w')
        
        # Buttons
        button_frame = tk.Frame(content_frame, bg="white")
        button_frame.pack(pady=20)
        
        # Start button
        tk.Button(
            button_frame,
            text="🚀 Start EA TV",
            font=("Arial", 12, "bold"),
            bg="#C41E3A",
            fg="white",
            command=self.start_tv,
            width=15,
            height=2
        ).pack(side='left', padx=5)
        
        # Open webplayer button
        tk.Button(
            button_frame,
            text="🌐 Open Webplayer",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            command=self.open_webplayer,
            width=15,
            height=2
        ).pack(side='left', padx=5)
        
        # Close button
        tk.Button(
            button_frame,
            text="❌ Close",
            font=("Arial", 12, "bold"),
            bg="#666666",
            fg="white",
            command=self.on_closing,
            width=15,
            height=2
        ).pack(side='left', padx=5)
        
        # Status
        self.status_label = tk.Label(
            content_frame,
            text="Ready to start...",
            font=("Arial", 10),
            fg="gray"
        )
        self.status_label.pack(pady=10)
        
        # Instructions
        instructions = """
        Instructions:
        • Enter your store code (default: 1000)
        • Select your screen (1, 2, or 3)
        • Click Start EA TV or Open Webplayer
        • Press ESC or Q to close anytime
        """
        
        tk.Label(
            content_frame,
            text=instructions,
            font=("Arial", 9),
            justify='left',
            fg="gray"
        ).pack(pady=10)
        
    def start_tv(self):
        """Start the EA TV client."""
        store_code = self.store_entry.get().strip()
        screen = self.screen_var.get()
        
        if not store_code:
            messagebox.showerror("Error", "Please enter a store code!")
            return
        
        self.status_label.config(text=f"Starting EA TV for store {store_code}, screen {screen}...")
        
        # For now, show a demo screen since the full client has issues
        self.show_demo_screen(store_code, screen)
        
    def show_demo_screen(self, store_code, screen):
        """Show a demo TV screen while we fix the full client."""
        demo_window = tk.Toplevel(self.root)
        demo_window.title(f"EA TV - Store {store_code} - Screen {screen}")
        demo_window.configure(bg='red')
        demo_window.attributes('-fullscreen', True)
        
        # Bind ESC to close demo
        demo_window.bind('<Escape>', lambda e: demo_window.destroy())
        
        label = tk.Label(
            demo_window,
            text=f"🍕 EA TV - Store {store_code}\nScreen {screen}\n\nDemo Mode\n\n{time.strftime('%H:%M:%S')}\n\nPress ESC to close",
            font=("Arial", 48),
            fg="white",
            bg="red"
        )
        label.pack(expand=True)
        
        def update_time():
            if demo_window.winfo_exists():
                try:
                    current_time = time.strftime('%H:%M:%S')
                    label.config(text=f"🍕 EA TV - Store {store_code}\nScreen {screen}\n\nDemo Mode - Synchronized\n\n{current_time}\n\nPress ESC to close")
                    demo_window.after(1000, update_time)
                except:
                    pass
        
        update_time()
        self.status_label.config(text=f"EA TV running in demo mode - Press ESC to close")
        
    def open_webplayer(self):
        """Open the webplayer in browser."""
        try:
            # Try to open in chromium browser
            subprocess.Popen(['chromium-browser', '--start-fullscreen', 'https://everydayadvertise.com/webplayer'])
            self.status_label.config(text="Webplayer opened in browser")
        except:
            try:
                # Fallback to default browser
                webbrowser.open('https://everydayadvertise.com/webplayer')
                self.status_label.config(text="Webplayer opened in default browser")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open webplayer: {e}")
    
    def on_closing(self):
        """Handle window closing."""
        self.running = False
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
        app = SimpleEATVClient()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)