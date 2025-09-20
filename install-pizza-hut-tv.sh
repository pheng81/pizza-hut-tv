#!/bin/bash
# Pizza Hut TV Pi - Simple One-Click Installer
# Just run this file and everything gets installed!

echo "🍕 Pizza Hut TV - One-Click Pi Installer"
echo "========================================"
echo ""
echo "This will download and run the complete installer."
echo ""

# Check for internet connection
if ! ping -c 1 8.8.8.8 &> /dev/null; then
    echo "❌ No internet connection. Please connect to network first."
    exit 1
fi

echo "📡 Downloading installer..."

# Try to download from your server first (when available)
if curl -f -s "http://192.168.1.115:5002/static/pizza-hut-tv-pi-installer.sh" -o "/tmp/phtv-installer.sh" 2>/dev/null; then
    echo "✅ Downloaded from Pizza Hut TV server"
elif curl -f -s "https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/pizza-hut-tv-pi-installer.sh" -o "/tmp/phtv-installer.sh" 2>/dev/null; then
    echo "✅ Downloaded from GitHub"
else
    echo "❌ Could not download installer. Please check your internet connection."
    echo ""
    echo "🔧 Manual installation:"
    echo "1. Copy pizza-hut-tv-pi-installer.sh to your Pi"
    echo "2. Run: chmod +x pizza-hut-tv-pi-installer.sh && ./pizza-hut-tv-pi-installer.sh"
    exit 1
fi

echo "🚀 Starting installation..."
chmod +x /tmp/phtv-installer.sh
/tmp/phtv-installer.sh

# Clean up
rm -f /tmp/phtv-installer.sh

echo ""
echo "🎉 Installation completed!"