#!/bin/bash
# 🍕 Update custom_player.py on Raspberry Pi
# This script updates the custom player to support 4+ screen slices

echo "🍕 Pizza Hut TV - Update Custom Player on Pi"
echo "=============================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration - you can override these with environment variables
PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-raspberrypi.local}"

echo -e "${BLUE}📋 Update Plan:${NC}"
echo "   • Copy updated custom_player.py to Pi: $PI_USER@$PI_HOST"
echo "   • Restart any running custom player processes"
echo ""

# Check if custom_player.py exists locally
if [ ! -f "custom_player.py" ]; then
    echo -e "${RED}❌ custom_player.py not found in current directory${NC}"
    echo "Please run this script from the Pizza Hut TV directory"
    exit 1
fi

# Test connection
echo -e "${YELLOW}🌐 Testing Pi connection...${NC}"
if timeout 5 ssh -o ConnectTimeout=3 "$PI_USER@$PI_HOST" 'echo "Connected"' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Pi is reachable at $PI_USER@$PI_HOST${NC}"
else
    echo -e "${RED}❌ Cannot reach Pi at $PI_USER@$PI_HOST${NC}"
    echo ""
    echo "💡 Try one of these:"
    echo "   1. Use IP address:"
    echo "      export PI_HOST=192.168.1.115"
    echo "      bash $0"
    echo ""
    echo "   2. Use different username:"
    echo "      export PI_USER=everydayadvertise"
    echo "      bash $0"
    exit 1
fi

# Copy custom_player.py to Pi
echo -e "${YELLOW}📤 Uploading custom_player.py to Pi...${NC}"
if scp custom_player.py "$PI_USER@$PI_HOST:/home/$PI_USER/"; then
    echo -e "${GREEN}✅ custom_player.py uploaded successfully${NC}"
else
    echo -e "${RED}❌ Failed to copy custom_player.py${NC}"
    exit 1
fi

# Check if custom player is running and offer to restart
echo -e "${YELLOW}🔍 Checking for running custom player processes...${NC}"
RUNNING_PROCS=$(ssh "$PI_USER@$PI_HOST" "pgrep -f custom_player.py" 2>/dev/null)

if [ ! -z "$RUNNING_PROCS" ]; then
    echo -e "${BLUE}ℹ️  Found running custom player processes: $RUNNING_PROCS${NC}"
    echo ""
    echo "Do you want to restart them? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🔄 Restarting custom player...${NC}"
        ssh "$PI_USER@$PI_HOST" "pkill -f custom_player.py" 2>/dev/null
        sleep 2
        echo -e "${GREEN}✅ Custom player processes stopped${NC}"
        echo -e "${BLUE}ℹ️  You can now launch the custom player from the Pi desktop${NC}"
    else
        echo -e "${YELLOW}⚠️  Skipping restart - changes will take effect on next launch${NC}"
    fi
else
    echo -e "${BLUE}ℹ️  No running custom player processes found${NC}"
fi

echo ""
echo -e "${GREEN}✅ Update complete!${NC}"
echo ""
echo -e "${BLUE}📝 What was fixed:${NC}"
echo "   • Screen slice parsing now correctly handles screen4, screen5, etc."
echo "   • Previously only worked for screen1, screen2, screen3"
echo "   • Now supports unlimited screens"
echo ""
echo -e "${BLUE}🚀 Next steps:${NC}"
echo "   1. If you restarted the player, launch it again from the Pi desktop"
echo "   2. If you didn't restart, close and reopen the custom player"
echo "   3. Verify screen4 and screen5 now show different slices"
echo ""
