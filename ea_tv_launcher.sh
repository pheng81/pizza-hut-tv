#!/bin/bash
# EA TV - Raspberry Pi Client Launcher
# Auto-start script for desktop icon

echo "📺 Starting EA TV Client..."
echo "============================"

# Set display environment
export DISPLAY=:0.0

# Navigate to home directory
cd /home/everydayadvertise

# Kill any existing VLC processes
pkill vlc 2>/dev/null

# Start EA TV with proper display
echo "📺 Launching EA TV GUI..."
python3 pizza_hut_tv_webplayer_exact.py

echo "✅ EA TV session ended."