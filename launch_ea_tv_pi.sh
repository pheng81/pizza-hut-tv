#!/bin/bash
"""
EA TV Pi Client Launcher - Sets up proper display environment
"""

# Set display for local Pi screen
export DISPLAY=:0

# Kill any existing instances
pkill -f webplayer_style_pi_client.py
pkill vlc

# Wait a moment
sleep 2

# Start the EA TV client
cd /home/everydayadvertise
python3 webplayer_style_pi_client.py

echo "EA TV client finished"