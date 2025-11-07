#!/usr/bin/env python3
"""
🍕 Simple Pizza Hut TV Client - Debug Version
Test to see what's going wrong
"""

import tkinter as tk
from tkinter import messagebox
import sys
import os

class SimplePizzaHutClient:
    def __init__(self):
        print("🍕 Starting Simple Pizza Hut TV Client...")
        
        # Set display
        if not os.environ.get('DISPLAY'):
            os.environ['DISPLAY'] = ':0'
        
        # Create window
        self.root = tk.Tk()
        self.root.title("🍕 Pizza Hut TV - Debug")
        self.root.geometry("800x600")
        self.root.configure(bg='#0d0d0d')
        
        # Make it fullscreen and on top
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        
        print("✅ Window created successfully")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup simple UI"""
        # Title
        title = tk.Label(
            self.root,
            text="🍕 PIZZA HUT TV",
            font=("Arial", 48, "bold"),
            fg="white",
            bg="#0d0d0d"
        )
        title.pack(pady=50)
        
        # Instruction
        instruction = tk.Label(
            self.root,
            text="Enter 4-digit TV code:",
            font=("Arial", 24),
            fg="white",
            bg="#0d0d0d"
        )
        instruction.pack(pady=20)
        
        # Input field
        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(
            self.root,
            textvariable=self.input_var,
            font=("Arial", 36, "bold"),
            justify='center',
            width=10,
            bg="white",
            fg="black"
        )
        self.input_field.pack(pady=30)
        self.input_field.focus_set()
        
        # Bind events
        self.input_field.bind('<Return>', self.on_enter)
        self.root.bind('<Escape>', self.on_escape)
        
        # Connect button
        self.connect_btn = tk.Button(
            self.root,
            text="CONNECT",
            font=("Arial", 24, "bold"),
            bg="#c8102e",
            fg="white",
            command=self.connect,
            width=15,
            height=2
        )
        self.connect_btn.pack(pady=30)
        
        # Status
        self.status = tk.Label(
            self.root,
            text="Ready to connect...",
            font=("Arial", 18),
            fg="#cccccc",
            bg="#0d0d0d"
        )
        self.status.pack(pady=20)
        
        print("✅ UI setup complete")
    
    def on_enter(self, event):
        self.connect()
    
    def on_escape(self, event):
        self.root.quit()
    
    def connect(self):
        code = self.input_var.get().strip()
        if len(code) != 4 or not code.isdigit():
            self.status.config(text="❌ Please enter exactly 4 digits", fg="red")
            return
        
        self.status.config(text=f"✅ Code entered: {code}", fg="green")
        print(f"🔗 User entered code: {code}")
        
        # For now, just show success
        messagebox.showinfo("Success", f"TV Code {code} entered successfully!\n\nIn real version, this would:\n1. Connect to server\n2. Load store selection\n3. Start video playback")
    
    def run(self):
        print("🚀 Starting main loop...")
        self.root.mainloop()
        print("🛑 Application closed")

if __name__ == "__main__":
    try:
        print("🍕 Pizza Hut TV Debug Client Starting...")
        app = SimplePizzaHutClient()
        app.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)