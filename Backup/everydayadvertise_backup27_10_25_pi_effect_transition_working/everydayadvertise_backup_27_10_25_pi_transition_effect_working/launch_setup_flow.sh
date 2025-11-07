#!/bin/bash
# 🍕 Pizza Hut TV - Setup Flow Launcher
# Launches Pi client with webplayer-style setup flow

cd ~/pizza-hut-tv
source bin/activate  # Virtual environment is in current directory

echo "🍕 Pizza Hut TV - Setup Flow"
echo "================================"

# Check if running in desktop environment
if [ -n "$DISPLAY" ]; then
    echo "Running in desktop mode"
    python3 pi_client_ui.py --server "http://192.168.1.100:5000" 
else
    echo "Running in console mode (will switch to framebuffer)"
    sudo -E env PATH="$PATH" python3 pi_client_ui.py --server "http://192.168.1.100:5000"
fi