#!/bin/bash
# 🍕 Pi Client Installer v2.0
# Install and configure the new simple Pi client

echo "🍕 Pizza Hut TV - Pi Client Installer v2.0"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PI_USER="everydayadvertise"
PI_HOST="raspberrypi"
CLIENT_FILE="pi_client.py"

echo -e "${BLUE}📋 Installation Plan:${NC}"
echo "   • Copy pi_client.py to Pi"
echo "   • Install Python dependencies" 
echo "   • Install VLC media player"
echo "   • Create desktop shortcut"
echo "   • Test functionality"
echo ""

# Step 1: Test connection
echo -e "${YELLOW}🌐 Testing Pi connection...${NC}"
if timeout 5 ssh -o ConnectTimeout=3 "$PI_USER@$PI_HOST" 'echo "Connected"' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Pi is reachable${NC}"
else
    echo -e "${RED}❌ Cannot reach Pi at $PI_HOST${NC}"
    echo "Try using IP address:"
    echo "  export PI_HOST=192.168.1.115"
    echo "  bash $0"
    exit 1
fi

# Step 2: Copy client file
echo -e "${YELLOW}📤 Copying client to Pi...${NC}"
if [ ! -f "$CLIENT_FILE" ]; then
    echo -e "${RED}❌ $CLIENT_FILE not found${NC}"
    echo "Please run this script from the directory containing $CLIENT_FILE"
    exit 1
fi

if scp "$CLIENT_FILE" "$PI_USER@$PI_HOST:/home/$PI_USER/"; then
    echo -e "${GREEN}✅ Client copied successfully${NC}"
else
    echo -e "${RED}❌ Failed to copy client${NC}"
    exit 1
fi

# Step 3: Install dependencies on Pi
echo -e "${YELLOW}🔧 Installing dependencies on Pi...${NC}"
ssh "$PI_USER@$PI_HOST" << 'ENDSSH'
    echo "📦 Updating package list..."
    sudo apt update -qq
    
    echo "🐍 Installing Python packages..."
    sudo apt install -y python3-pip python3-tk python3-vlc vlc
    
    echo "📚 Installing Python modules..."
    pip3 install --user requests python-vlc
    
    echo "🔧 Setting up client..."
    chmod +x pi_client.py
    
    echo "✅ Dependencies installed"
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi

# Step 4: Create desktop shortcut
echo -e "${YELLOW}🖥️ Creating desktop shortcut...${NC}"
ssh "$PI_USER@$PI_HOST" << 'ENDSSH'
    mkdir -p /home/everydayadvertise/Desktop
    
    # Create desktop file with proper icon
    cat > /home/everydayadvertise/Desktop/PizzaHutTV.desktop << 'EOF'
[Desktop Entry]
Name=🍕 Pizza Hut TV
Comment=Pizza Hut TV Client for Raspberry Pi
Exec=python3 /home/everydayadvertise/pi_client.py
Icon=multimedia-video-player
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;
StartupNotify=true
Path=/home/everydayadvertise
StartupWMClass=pi_client
EOF

    # Create EATV launcher for the full webplayer-style client
    cat > /home/everydayadvertise/Desktop/EATV.desktop << 'EOF'
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
    
    # Make desktop file executable and trusted
    chmod +x /home/everydayadvertise/Desktop/PizzaHutTV.desktop /home/everydayadvertise/Desktop/EATV.desktop
    gio set /home/everydayadvertise/Desktop/PizzaHutTV.desktop metadata::trusted true 2>/dev/null || true
    gio set /home/everydayadvertise/Desktop/EATV.desktop metadata::trusted true 2>/dev/null || true
    
    # Also create a headless version for autostart
    cat > /home/everydayadvertise/Desktop/PizzaHutTV-Headless.desktop << 'EOF'
[Desktop Entry]
Name=🍕 Pizza Hut TV (Headless)
Comment=Pizza Hut TV Client - Headless Mode
Exec=python3 /home/everydayadvertise/pi_client.py --headless --store PHTV001 --screen tv1
Icon=video-display
Terminal=true
Type=Application
Categories=AudioVideo;Video;Player;
StartupNotify=true
Path=/home/everydayadvertise
EOF
    
    chmod +x /home/everydayadvertise/Desktop/PizzaHutTV-Headless.desktop
    gio set /home/everydayadvertise/Desktop/PizzaHutTV-Headless.desktop metadata::trusted true 2>/dev/null || true
    
    echo "✅ Desktop shortcuts created:"
    echo "   • 🍕 Pizza Hut TV (GUI mode)"
    echo "   • 🖥️ EATV (Webplayer experience)"
    echo "   • 🍕 Pizza Hut TV (Headless) for production"
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Desktop shortcut created${NC}"
else
    echo -e "${YELLOW}⚠️ Desktop shortcut creation failed${NC}"
fi

# Step 5: Test basic functionality
echo -e "${YELLOW}🧪 Testing client functionality...${NC}"
ssh "$PI_USER@$PI_HOST" << 'ENDSSH'
    echo "🧪 Running basic tests..."
    
    # Test Python imports
    python3 -c "
import sys
print(f'✅ Python {sys.version_info.major}.{sys.version_info.minor}')

try:
    import requests
    print('✅ requests module')
except ImportError as e:
    print(f'❌ requests module: {e}')

try:
    import vlc
    print('✅ vlc module')
except ImportError as e:
    print(f'❌ vlc module: {e}')

try:
    import tkinter
    print('✅ tkinter module')
except ImportError as e:
    print(f'❌ tkinter module: {e}')
"
    
    # Test VLC
    if command -v vlc > /dev/null 2>&1; then
        echo "✅ VLC installed"
    else
        echo "❌ VLC not found"
    fi
    
    # Test server connectivity
    if curl -s --head https://everydayadvertise.com > /dev/null; then
        echo "✅ Server reachable"
    else
        echo "⚠️ Server connectivity issue"
    fi
    
    echo "🏁 Tests complete"
ENDSSH

# Step 6: Final instructions
echo ""
echo -e "${GREEN}🎉 Installation Complete!${NC}"
echo "================================"
echo ""
echo -e "${BLUE}📋 How to Use:${NC}"
echo "1. SSH to Pi: ssh $PI_USER@$PI_HOST"
echo "2. Run with GUI: python3 pi_client.py"
echo "3. Run headless: python3 pi_client.py --headless"
echo "4. Or use desktop shortcut: Pi TV Client"
echo ""
echo -e "${BLUE}🎮 GUI Features:${NC}"
echo "• Configure server URL, store ID, screen ID"
echo "• Start/stop playback with buttons"
echo "• Monitor status and current video"
echo "• Toggle fullscreen mode"
echo "• Manual playlist refresh"
echo ""
echo -e "${BLUE}📁 Files on Pi:${NC}"
echo "• Client: /home/$PI_USER/pi_client.py"
echo "• Desktop: /home/$PI_USER/Desktop/PiTVClient.desktop"
echo "• Logs: /home/$PI_USER/pi_client.log"
echo ""
echo -e "${BLUE}⚡ Quick Start:${NC}"
echo "ssh $PI_USER@$PI_HOST"
echo "python3 pi_client.py"
echo ""
echo -e "${GREEN}🚀 Ready to rock! 🍕${NC}"