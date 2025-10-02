#!/bin/bash
# 🍕 Create Pi Desktop Shortcuts
# Run this directly on the Raspberry Pi to create desktop shortcuts

echo "🍕 Creating Pizza Hut TV Desktop Shortcuts"
echo "=========================================="

# Create Desktop directory if it doesn't exist
mkdir -p ~/Desktop

# Create main GUI shortcut
echo "📱 Creating GUI shortcut..."
cat > ~/Desktop/PizzaHutTV.desktop << 'EOF'
[Desktop Entry]
Name=🍕 Pizza Hut TV
Comment=Pizza Hut TV Client for Raspberry Pi - GUI Mode
Exec=python3 /home/everydayadvertise/pi_client.py
Icon=multimedia-video-player
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;
StartupNotify=true
Path=/home/everydayadvertise
StartupWMClass=pi_client
EOF

# Create EATV desktop launcher for the full webplayer-style client
echo "🖥️ Creating EATV shortcut..."
cat > ~/Desktop/EATV.desktop << 'EOF'
[Desktop Entry]
Name=EATV
Comment=Launch the Everyday Advertise TV webplayer experience
Exec=python3 /home/everydayadvertise/pizza-hut-tv/webplayer_style_pi_client.py
Icon=applications-multimedia
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;
StartupNotify=true
Path=/home/everydayadvertise/pizza-hut-tv
StartupWMClass=webplayer_style_pi_client
EOF

# Create headless shortcut for production
echo "🎬 Creating headless shortcut..."
cat > ~/Desktop/PizzaHutTV-Headless.desktop << 'EOF'
[Desktop Entry]
Name=🍕 Pizza Hut TV (Headless)
Comment=Pizza Hut TV Client - Production Mode
Exec=python3 /home/everydayadvertise/pi_client.py --headless --store PHTV001 --screen tv1
Icon=video-display
Terminal=true
Type=Application
Categories=AudioVideo;Video;Player;
StartupNotify=true
Path=/home/everydayadvertise
EOF

# Create autostart shortcut
echo "🚀 Creating autostart shortcut..."
cat > ~/Desktop/PizzaHutTV-Autostart.desktop << 'EOF'
[Desktop Entry]
Name=🍕 Pizza Hut TV (Auto)
Comment=Auto-start Pizza Hut TV on boot
Exec=python3 /home/everydayadvertise/pi_client.py --headless --store PHTV001 --screen tv1
Icon=system-run
Terminal=false
Type=Application
Categories=System;
StartupNotify=false
Path=/home/everydayadvertise
Hidden=false
EOF
# Make all desktop files executable and trusted
chmod +x ~/Desktop/PizzaHutTV*.desktop ~/Desktop/EATV.desktop

# Try to set as trusted (works on newer Pi OS)
for file in ~/Desktop/PizzaHutTV*.desktop ~/Desktop/EATV.desktop; do
    gio set "$file" metadata::trusted true 2>/dev/null || true
done

echo ""
echo "✅ Desktop shortcuts created!"
echo ""
echo "📋 Available shortcuts:"
echo "   🍕 Pizza Hut TV - GUI mode for setup and monitoring"
echo "   🖥️ EATV - Webplayer-style client"
echo "   🍕 Pizza Hut TV (Headless) - Production playback mode"
echo "   🍕 Pizza Hut TV (Auto) - For autostart setup"
echo ""
echo "💡 To use:"
echo "   1. Double-click 'Pizza Hut TV' for GUI setup"
echo "   2. Configure server, store ID, screen ID"
echo "   3. Click Start to begin playback"
echo ""
echo "🎯 For production:"
echo "   • Use 'Pizza Hut TV (Headless)' for fullscreen playback"
echo "   • Runs without GUI, logs to pi_client.log"
echo ""
echo "🚀 For autostart on boot:"
echo "   • Copy 'Pizza Hut TV (Auto)' to ~/.config/autostart/"
echo "   • mkdir -p ~/.config/autostart"
echo "   • cp ~/Desktop/PizzaHutTV-Autostart.desktop ~/.config/autostart/"
echo ""
echo "Ready to launch! 🍕✨"