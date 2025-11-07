#!/bin/bash
# Pizza Hut TV Launcher Script
# Usage: ./launch_pizza_hut_tv.sh [screen_number]

STORE_CODE="1000"
PAIRING_CODE="4682"
SCREEN=${1:-2}  # Default to screen 2 if no argument provided

echo "🍕 Launching Pizza Hut TV for Screen $SCREEN"
echo "📺 Store: $STORE_CODE | Code: $PAIRING_CODE"
echo "🎬 Starting in 3 seconds..."

sleep 3

# Kill any existing instances
pkill -f "python3.*slice_kiosk" 2>/dev/null || true
pkill -f chromium 2>/dev/null || true

# Launch the player
cd /home/everydayadvertise/pizza-hut-tv
DISPLAY=:0 python3 slice_kiosk.py --store "$STORE_CODE" --screen "$SCREEN" --code "$PAIRING_CODE"