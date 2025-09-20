#!/usr/bin/env python3
"""
Pizza Hut TV - Basic GUI Test for Pi
Tests if tkinter works properly on Pi OS
"""

import tkinter as tk
from tkinter import messagebox

def test_button():
    messagebox.showinfo("Test", "Button clicked successfully!")

def main():
    root = tk.Tk()
    root.title("Pi GUI Test")
    root.geometry("400x300")
    root.configure(bg='#0b0b0b')
    
    # Title
    title = tk.Label(root, text="Pizza Hut TV - Pi Test", 
                     font=('Arial', 16, 'bold'),
                     fg='#c8102e', bg='#0b0b0b')
    title.pack(pady=20)
    
    # Test button
    button = tk.Button(root, text="Test Button",
                      command=test_button,
                      bg='#c8102e', fg='white',
                      font=('Arial', 12, 'bold'),
                      relief='flat', padx=20, pady=10)
    button.pack(pady=20)
    
    # Info
    info = tk.Label(root, text="If this window appears, tkinter works on your Pi!",
                   font=('Arial', 10), fg='white', bg='#0b0b0b')
    info.pack(pady=10)
    
    # Exit button
    exit_btn = tk.Button(root, text="Exit",
                        command=root.quit,
                        bg='#666666', fg='white',
                        font=('Arial', 10), relief='flat')
    exit_btn.pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    main()