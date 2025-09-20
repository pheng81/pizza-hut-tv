#!/bin/bash
# 🍕 Pizza Hut TV - Python Environment Fix for Pi OS Bookworm
# Run this if you get "externally-managed-environment" errors

echo "🔧 Pizza Hut TV - Python Environment Fix"
echo "========================================"
echo ""
echo "Fixing Python package installation for newer Pi OS versions..."
echo ""

# Update package list
echo "📦 Updating package list..."
sudo apt update -qq

# Install required Python packages via apt (system method)
echo "📦 Installing Python packages via system package manager..."
sudo apt install -y \
    python3-requests \
    python3-tk \
    python3-pil \
    python3-pil.imagetk \
    python3-setuptools

# Verify installations
echo ""
echo "🔍 Verifying installations..."

if python3 -c "import requests" 2>/dev/null; then
    echo "✅ requests module available"
else
    echo "❌ requests module missing"
fi

if python3 -c "import tkinter" 2>/dev/null; then
    echo "✅ tkinter module available (GUI support)"
else
    echo "❌ tkinter module missing (GUI won't work)"
fi

echo ""
echo "✅ Python environment fix complete!"
echo ""
echo "You can now run the Pizza Hut TV installer:"
echo "   ./pizza-hut-tv-enhanced-installer.sh"
echo ""
echo "Or if already installed, run the client:"
echo "   cd ~/pizza-hut-tv-pi"
echo "   python3 pizza_hut_tv_client.py"
echo "   python3 pizza_hut_tv_gui_client.py"