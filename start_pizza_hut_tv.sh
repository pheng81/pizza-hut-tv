#!/bin/bash
# Pizza Hut TV - Desktop Launcher
# Run this script directly on the Pi desktop

echo "=== Pizza Hut TV Desktop Launcher ==="
echo

# Check if we're in a desktop environment
if [ -z "$DISPLAY" ]; then
    echo "❌ No desktop environment detected!"
    echo "This script must be run from the Pi desktop, not SSH."
    echo
    echo "To run Pizza Hut TV GUI:"
    echo "1. Open terminal on Pi desktop (not SSH)"
    echo "2. Run: python3 webplayer_style_gui_pi.py"
    echo
    echo "Or double-click this script from the desktop file manager."
    exit 1
fi

echo "✅ Desktop environment detected"
echo "Starting Pizza Hut TV GUI..."
echo

# Change to home directory
cd ~

# Check if the GUI file exists
if [ ! -f "webplayer_style_gui_pi.py" ]; then
    echo "❌ webplayer_style_gui_pi.py not found!"
    echo "Make sure the file is in your home directory: /home/everydayadvertise/"
    exit 1
fi

echo "✅ GUI file found"
echo "Launching Pizza Hut TV..."
echo

# Start the GUI
python3 webplayer_style_gui_pi.py

echo
echo "Pizza Hut TV GUI closed."