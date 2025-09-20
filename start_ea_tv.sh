#!/bin/bash
# EA TV - Simple Terminal Launcher
# For terminal/SSH access

echo "📺 Starting EA TV..."
echo "==================="

cd /home/everydayadvertise
pkill vlc 2>/dev/null

echo "🚀 Launching EA TV..."
python3 pizza_hut_tv_webplayer_exact.py