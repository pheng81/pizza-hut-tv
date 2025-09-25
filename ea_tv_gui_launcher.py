#!/usr/bin/env python3
"""
Simple EA TV Pi Client - GUI selector for easy startup
Works without server authentication for testing
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os

class EATVLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EA TV - Screen Selector")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.geometry("+{}+{}".format(
            (self.root.winfo_screenwidth() // 2) - 200,
            (self.root.winfo_screenheight() // 2) - 150
        ))
        
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the GUI elements."""
        
        # Title
        title_label = tk.Label(
            self.root, 
            text="🍕 EA TV - Pizza Hut TV", 
            font=("Arial", 16, "bold"),
            fg="#C41E3A"  # Pizza Hut red
        )
        title_label.pack(pady=20)
        
        # Server selection
        server_frame = tk.Frame(self.root)
        server_frame.pack(pady=10)
        
        tk.Label(server_frame, text="Server:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.server_var = tk.StringVar(value="https://everydayadvertise.com")
        server_combo = ttk.Combobox(
            server_frame, 
            textvariable=self.server_var,
            values=[
                "https://everydayadvertise.com",
                "http://54.252.90.27:8082",
                "http://localhost:5002"
            ],
            width=40
        )
        server_combo.pack(pady=5)
        
        # Screen selection
        screen_frame = tk.Frame(self.root)
        screen_frame.pack(pady=10)
        
        tk.Label(screen_frame, text="Select Screen:", font=("Arial", 10, "bold")).pack(anchor='w')
        
        self.screen_var = tk.StringVar(value="1")
        screen_options = [
            ("Screen 1 (Left)", "1"),
            ("Screen 2 (Center)", "2"), 
            ("Screen 3 (Right)", "3")
        ]
        
        for text, value in screen_options:
            rb = tk.Radiobutton(
                screen_frame,
                text=text,
                variable=self.screen_var,
                value=value,
                font=("Arial", 10)
            )
            rb.pack(anchor='w', pady=2)
        
        # Store ID
        store_frame = tk.Frame(self.root)
        store_frame.pack(pady=10)
        
        tk.Label(store_frame, text="Store ID:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.store_var = tk.StringVar(value="1000")
        store_entry = tk.Entry(store_frame, textvariable=self.store_var, width=20)
        store_entry.pack(pady=5)
        
        # Launch button
        launch_btn = tk.Button(
            self.root,
            text="🚀 Launch EA TV",
            font=("Arial", 12, "bold"),
            bg="#C41E3A",
            fg="white",
            command=self.launch_ea_tv,
            width=20,
            height=2
        )
        launch_btn.pack(pady=20)
        
        # Test connectivity button
        test_btn = tk.Button(
            self.root,
            text="🔗 Test Server Connection",
            font=("Arial", 10),
            command=self.test_connection,
            width=25
        )
        test_btn.pack(pady=5)
        
    def test_connection(self):
        """Test connection to the selected server."""
        server = self.server_var.get()
        try:
            import requests
            response = requests.get(f"{server}/api/sync-time", timeout=5)
            if response.status_code == 200:
                messagebox.showinfo("Success", f"✅ Connected to server successfully!\n\nServer: {server}\nSync API: Working")
            else:
                messagebox.showwarning("Warning", f"⚠️ Server responded with status {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"❌ Failed to connect to server:\n\n{str(e)}")
    
    def launch_ea_tv(self):
        """Launch the EA TV Pi client with selected options."""
        server = self.server_var.get().strip()
        store = self.store_var.get().strip()
        screen = self.screen_var.get()
        
        if not server or not store:
            messagebox.showerror("Error", "Please fill in all required fields!")
            return
            
        # Construct command
        cmd = [
            "python3", 
            "/home/everydayadvertise/phtv_pi_client.py",
            "--server", server,
            "--store", store,
            "--screen", screen,
            "--windowed"  # Start in windowed mode for easier testing
        ]
        
        try:
            # Show launching message
            messagebox.showinfo("Launching", f"🚀 Starting EA TV...\n\nServer: {server}\nStore: {store}\nScreen: {screen}")
            
            # Close this window
            self.root.destroy()
            
            # Launch EA TV
            subprocess.run(cmd, cwd="/home/everydayadvertise")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch EA TV:\n\n{str(e)}")
    
    def run(self):
        """Run the launcher."""
        self.root.mainloop()

if __name__ == "__main__":
    launcher = EATVLauncher()
    launcher.run()