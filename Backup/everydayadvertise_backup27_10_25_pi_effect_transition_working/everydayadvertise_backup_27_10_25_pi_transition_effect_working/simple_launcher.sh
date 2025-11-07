#!/bin/bash
# Simple Pizza Hut TV launcher for testing

cd ~/pizza-hut-tv
source bin/activate

# Clear screen and show status
clear
echo "🍕 Pizza Hut TV - Setup Flow Launcher"
echo "====================================="
echo "Starting Pizza Hut TV with setup flow..."
echo "Use keyboard to enter numbers"
echo "Press ESC to go back or quit"
echo "====================================="

# Run with proper environment
DISPLAY=:0 python3 pi_client_ui.py --server "http://192.168.1.100:5000" --debug