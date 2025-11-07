#!/bin/bash
# Quick test script for custom player

echo "======================================"
echo "Testing Custom Media Player"
echo "======================================"
echo ""

# Check Python
echo "1. Checking Python..."
python3 --version

# Check dependencies
echo ""
echo "2. Checking dependencies..."
python3 -c "import cv2; print('  ✅ OpenCV installed')" 2>/dev/null || echo "  ❌ OpenCV missing - run: sudo apt-get install python3-opencv"
python3 -c "import PIL; print('  ✅ PIL installed')" 2>/dev/null || echo "  ❌ PIL missing - run: sudo apt-get install python3-pil"
python3 -c "import numpy; print('  ✅ NumPy installed')" 2>/dev/null || echo "  ❌ NumPy missing - run: sudo apt-get install python3-numpy"
python3 -c "import requests; print('  ✅ Requests installed')" 2>/dev/null || echo "  ❌ Requests missing - run: sudo apt-get install python3-requests"

# Check display
echo ""
echo "3. Checking display..."
if [ -z "$DISPLAY" ]; then
    echo "  ⚠️  DISPLAY not set - setting to :0"
    export DISPLAY=:0
else
    echo "  ✅ DISPLAY=$DISPLAY"
fi

# Check playlist
echo ""
echo "4. Testing playlist fetch..."
curl -s "https://everydayadvertise.com/playlist/1000/1000_screen2" | head -n 5
echo "  (showing first 5 lines)"

# Check file permissions
echo ""
echo "5. Checking file..."
if [ -f "/home/everydayadvertise/Desktop/custom_player.py" ]; then
    echo "  ✅ custom_player.py exists"
    ls -lh /home/everydayadvertise/Desktop/custom_player.py
else
    echo "  ❌ custom_player.py not found"
fi

echo ""
echo "======================================"
echo "Ready to test!"
echo "======================================"
echo ""
echo "Run player for screen 2 (middle slice):"
echo "  python3 /home/everydayadvertise/Desktop/custom_player.py 1000 2"
echo ""
echo "Press Ctrl+C or ESC to stop"
echo ""
