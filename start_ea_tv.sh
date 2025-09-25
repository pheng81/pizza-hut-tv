#!/bin/bash
# EA TV - Simple Terminal Launcher
# For terminal/SSH access

echo "📺 Starting EA TV..."
echo "==================="

cd /home/everydayadvertise
pkill vlc 2>/dev/null

echo "🚀 Launching EA TV..."
python3 pi_player.py