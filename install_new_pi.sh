#!/bin/bash
###############################################################################
# 🍕 Pizza Hut TV - Complete Pi Installation Script
# 
# This script installs EVERYTHING needed on a fresh Raspberry Pi:
# - System packages (MPV, Python, libraries)
# - Python dependencies
# - Application files
# - Systemd service for auto-start
# 
# Usage:
#   1. Copy this script to the Pi
#   2. Run: bash install_new_pi.sh
#   3. Follow the prompts
#
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="pizza-hut-tv"
INSTALL_DIR="$HOME/pizza-hut-tv"
VENV_DIR="$INSTALL_DIR/venv"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                       ║${NC}"
echo -e "${BLUE}║   🍕 Pizza Hut TV - Complete Pi Installation 🍕      ║${NC}"
echo -e "${BLUE}║                                                       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Warning: This doesn't appear to be a Raspberry Pi${NC}"
    read -p "Continue anyway? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

echo -e "${GREEN}✓ Detected Raspberry Pi${NC}"
echo ""

# Check for internet connection
echo -e "${BLUE}[1/8]${NC} Checking internet connection..."
if ping -c 1 google.com &> /dev/null; then
    echo -e "${GREEN}✓ Internet connection OK${NC}"
else
    echo -e "${RED}✗ No internet connection detected${NC}"
    echo -e "${YELLOW}Please connect to internet and try again${NC}"
    exit 1
fi
echo ""

# Update system packages
echo -e "${BLUE}[2/8]${NC} Updating system packages..."
sudo apt update
echo -e "${GREEN}✓ System updated${NC}"
echo ""

# Install system dependencies
echo -e "${BLUE}[3/8]${NC} Installing system packages (MPV, Python, libraries)..."
echo -e "${YELLOW}This may take a few minutes...${NC}"

sudo apt install -y \
    mpv \
    libmpv2 \
    libmpv-dev \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-pygame \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libfreetype6-dev \
    libjpeg-dev \
    libportmidi-dev \
    git \
    curl \
    unclutter \
    xdotool

echo -e "${GREEN}✓ System packages installed${NC}"
echo ""

# Create installation directory
echo -e "${BLUE}[4/8]${NC} Creating installation directory..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✓ Directory created: $INSTALL_DIR${NC}"
echo ""

# Create Python virtual environment
echo -e "${BLUE}[5/8]${NC} Creating Python virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment already exists, removing...${NC}"
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✓ Virtual environment created${NC}"
echo ""

# Install Python packages
echo -e "${BLUE}[6/8]${NC} Installing Python packages..."
echo -e "${YELLOW}Installing core dependencies...${NC}"

pip install requests>=2.31.0
pip install pygame>=2.5.0
pip install python-mpv>=1.0.8
pip install pillow>=10.0.0
pip install psutil>=5.9.0
pip install coloredlogs>=15.0.0

echo -e "${GREEN}✓ Python packages installed${NC}"
echo ""

# Download application files from repository
echo -e "${BLUE}[7/8]${NC} Downloading application files..."

# Check if files already exist in current directory
if [ -f "complete_pi_client.py" ] && [ -f "seamless_video_player.py" ] && [ -f "transition_engine.py" ]; then
    echo -e "${GREEN}✓ Application files already present${NC}"
else
    echo -e "${YELLOW}Please ensure these files are in $INSTALL_DIR:${NC}"
    echo "  - complete_pi_client.py"
    echo "  - seamless_video_player.py"
    echo "  - transition_engine.py"
    echo ""
    echo -e "${YELLOW}You can copy them using:${NC}"
    echo "  scp complete_pi_client.py seamless_video_player.py transition_engine.py pi@raspberrypi:$INSTALL_DIR/"
    echo ""
    read -p "Press Enter when files are ready, or Ctrl+C to exit..."
    
    # Check again
    if [ ! -f "complete_pi_client.py" ] || [ ! -f "seamless_video_player.py" ] || [ ! -f "transition_engine.py" ]; then
        echo -e "${RED}✗ Required files not found!${NC}"
        exit 1
    fi
fi

chmod +x complete_pi_client.py
echo ""

# Get configuration from user
echo -e "${BLUE}[8/8]${NC} Configuration setup..."
echo ""
echo -e "${YELLOW}Please provide the following information:${NC}"
echo ""

read -p "Server URL (default: https://everydayadvertise.com): " SERVER_URL
SERVER_URL=${SERVER_URL:-https://everydayadvertise.com}

read -p "Store ID: " STORE_ID
while [ -z "$STORE_ID" ]; do
    echo -e "${RED}Store ID is required!${NC}"
    read -p "Store ID: " STORE_ID
done

read -p "Screen ID (default: 1): " SCREEN_ID
SCREEN_ID=${SCREEN_ID:-1}

read -p "Pair Code (optional, press Enter to skip): " PAIR_CODE

echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Server:    $SERVER_URL"
echo "  Store ID:  $STORE_ID"
echo "  Screen ID: $SCREEN_ID"
if [ -n "$PAIR_CODE" ]; then
    echo "  Pair Code: $PAIR_CODE"
fi
echo ""

# Create systemd service
echo -e "${BLUE}Creating systemd service...${NC}"

EXEC_START="$VENV_DIR/bin/python $INSTALL_DIR/complete_pi_client.py --server $SERVER_URL --store-id $STORE_ID --screen-id $SCREEN_ID"
if [ -n "$PAIR_CODE" ]; then
    EXEC_START="$EXEC_START --pair-code $PAIR_CODE"
fi

sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Pizza Hut TV Digital Signage Client
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$USER/.Xauthority
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=$INSTALL_DIR
ExecStartPre=/bin/sleep 10
ExecStart=$EXEC_START
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

# Configure auto-hide cursor
echo -e "${BLUE}Configuring display settings...${NC}"

# Add unclutter to autostart if not already there
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

if [ ! -f "$AUTOSTART_DIR/unclutter.desktop" ]; then
    cat > "$AUTOSTART_DIR/unclutter.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Unclutter
Exec=unclutter -idle 0.1 -root
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
fi

# Reload systemd and enable service
echo -e "${BLUE}Enabling service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                       ║${NC}"
echo -e "${GREEN}║   ✓ Installation Complete! ✓                         ║${NC}"
echo -e "${GREEN}║                                                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📋 Summary:${NC}"
echo "  ✓ System packages installed"
echo "  ✓ Python environment configured"
echo "  ✓ Application files ready"
echo "  ✓ Service configured to auto-start"
echo ""
echo -e "${YELLOW}🎮 Service Commands:${NC}"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Restart: sudo systemctl restart $SERVICE_NAME"
echo "  Status:  sudo systemctl status $SERVICE_NAME"
echo "  Logs:    journalctl -u $SERVICE_NAME -f"
echo ""
echo -e "${YELLOW}🚀 Next Steps:${NC}"
echo "  1. Start the service: sudo systemctl start $SERVICE_NAME"
echo "  2. Check status: sudo systemctl status $SERVICE_NAME"
echo "  3. View logs: journalctl -u $SERVICE_NAME -f"
echo ""
echo -e "${YELLOW}💡 The system will auto-start on boot!${NC}"
echo ""

read -p "Would you like to start the service now? (y/N): " START_NOW
if [[ $START_NOW =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}Starting service...${NC}"
    sudo systemctl start $SERVICE_NAME
    sleep 2
    
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✓ Service started successfully!${NC}"
        echo ""
        echo -e "${YELLOW}Checking logs...${NC}"
        journalctl -u $SERVICE_NAME -n 20 --no-pager
    else
        echo -e "${RED}✗ Service failed to start${NC}"
        echo -e "${YELLOW}Check logs with: journalctl -u $SERVICE_NAME -n 50${NC}"
    fi
else
    echo -e "${YELLOW}You can start the service later with:${NC}"
    echo "  sudo systemctl start $SERVICE_NAME"
fi

echo ""
echo -e "${GREEN}🍕 Pizza Hut TV installation complete! 🍕${NC}"
echo ""
