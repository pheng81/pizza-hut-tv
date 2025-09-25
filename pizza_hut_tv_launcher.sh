#!/bin/bash
# Pizza Hut TV - Raspberry Pi Client Launcher
# Auto-start script for desktop icon

echo "🍕 Starting Pizza Hut TV Client..."
echo "=================================="

# Set display environment
export DISPLAY=:0.0

# Navigate to home directory
cd /home/everydayadvertise

# Kill any existing VLC processes
pkill vlc 2>/dev/null

# Start Pizza Hut TV with proper display
echo "📺 Launching Pizza Hut TV GUI..."
python3 pi_player.py

echo "✅ Pizza Hut TV client started!"