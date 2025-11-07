#!/bin/bash
# 🍕 Enhanced Pi Client Installer v3.0
# Professional deployment script for Pizza Hut TV Pi Client

set -e  # Exit on any error

echo "🍕 Pizza Hut TV - Enhanced Pi Client Installer v3.0"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
INSTALL_DIR="/home/pi/pizza-hut-tv"
SERVICE_NAME="phtv-client"
LOG_DIR="/var/log/phtv"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${PURPLE}🔧 $1${NC}"
}

# Check if running on Pi
check_pi_environment() {
    log_step "Checking Pi environment..."
    
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        log_warning "This doesn't appear to be a Raspberry Pi"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check Pi model
    PI_MODEL=$(grep "Model" /proc/cpuinfo | cut -d':' -f2 | xargs)
    log_info "Detected: $PI_MODEL"
    
    # Check GPU memory
    GPU_MEM=$(vcgencmd get_mem gpu | cut -d'=' -f2 | sed 's/M//')
    log_info "GPU Memory: ${GPU_MEM}MB"
    
    if [ "$GPU_MEM" -lt 128 ]; then
        log_warning "GPU memory is low ($GPU_MEM MB). Recommending 128MB+ for video playback"
        log_info "💡 You can increase this with: sudo raspi-config → Advanced Options → Memory Split → 128"
    fi
    
    log_success "Pi environment check complete"
}

# Update system
update_system() {
    log_step "Updating system packages..."
    
    sudo apt update
    sudo apt upgrade -y
    
    log_success "System updated"
}

# Install system dependencies
install_system_deps() {
    log_step "Installing system dependencies..."
    
    # Essential packages
    sudo apt install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        curl \
        wget \
        unzip \
        htop \
        screen \
        supervisor
    
    # Video playback dependencies
    sudo apt install -y \
        omxplayer \
        vlc \
        ffmpeg \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer-plugins-bad1.0-dev \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-libav \
        gstreamer1.0-tools \
        gstreamer1.0-x \
        gstreamer1.0-alsa \
        gstreamer1.0-gl \
        gstreamer1.0-gtk3 \
        gstreamer1.0-qt5 \
        gstreamer1.0-pulseaudio
    
    # SDL2 for pygame
    sudo apt install -y \
        libsdl2-dev \
        libsdl2-image-dev \
        libsdl2-mixer-dev \
        libsdl2-ttf-dev \
        libfreetype6-dev \
        libportmidi-dev \
        libjpeg-dev \
        python3-numpy
    
    # Pi-specific libraries
    sudo apt install -y \
        libraspberrypi-dev \
        libraspberrypi-doc \
        libraspberrypi-bin
    
    log_success "System dependencies installed"
}

# Create installation directory
create_install_dir() {
    log_step "Creating installation directory..."
    
    sudo mkdir -p "$INSTALL_DIR"
    sudo mkdir -p "$LOG_DIR"
    sudo chown pi:pi "$INSTALL_DIR"
    sudo chown pi:pi "$LOG_DIR"
    
    log_success "Installation directory created: $INSTALL_DIR"
}

# Install Python dependencies
install_python_deps() {
    log_step "Installing Python dependencies..."
    
    cd "$INSTALL_DIR"
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    # Install dependencies from requirements file
    if [ -f "pi_requirements.txt" ]; then
        pip install -r pi_requirements.txt
    else
        # Fallback to essential packages
        pip install \
            requests \
            pygame \
            psutil \
            python-vlc \
            coloredlogs \
            watchdog \
            netifaces \
            py-cpuinfo
    fi
    
    log_success "Python dependencies installed"
}

# Download client files
download_client() {
    log_step "Downloading client files..."
    
    cd "$INSTALL_DIR"
    
    # You would typically download from your server or repository
    # For now, we'll create placeholders
    
    if [ ! -f "enhanced_pi_client.py" ]; then
        log_info "Client file should be copied manually to $INSTALL_DIR/enhanced_pi_client.py"
    fi
    
    # Make executable
    chmod +x enhanced_pi_client.py 2>/dev/null || true
    
    log_success "Client files ready"
}

# Create systemd service
create_service() {
    log_step "Creating systemd service..."
    
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Pizza Hut TV Enhanced Pi Client
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=pi
WorkingDirectory=$INSTALL_DIR
Environment=DISPLAY=:0
Environment=PULSE_RUNTIME_PATH=/run/user/1000/pulse
ExecStartPre=/bin/sleep 30
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/enhanced_pi_client.py --server https://everydayadvertise.com --store PHTV001 --screen tv1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=phtv-client

[Install]
WantedBy=multi-user.target
EOF
    
    # Enable and start service
    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME}
    
    log_success "Systemd service created and enabled"
}

# Configure autostart
configure_autostart() {
    log_step "Configuring autostart..."
    
    # Create desktop entry for manual launch
    mkdir -p /home/pi/Desktop
    
    cat > /home/pi/Desktop/PizzaHutTV.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Pizza Hut TV
Comment=Start Pizza Hut TV Client
Exec=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/enhanced_pi_client.py
Icon=applications-multimedia
Terminal=true
Categories=AudioVideo;Player;
EOF
    
    chmod +x /home/pi/Desktop/PizzaHutTV.desktop
    
    # Configure auto-login (optional)
    log_info "To enable auto-login: sudo raspi-config → Boot Options → Desktop Autologin"
    
    log_success "Autostart configured"
}

# Optimize Pi settings
optimize_pi() {
    log_step "Optimizing Pi settings..."
    
    # GPU memory split (if not already set)
    if [ "$GPU_MEM" -lt 128 ]; then
        log_info "Setting GPU memory to 128MB..."
        echo "gpu_mem=128" | sudo tee -a /boot/config.txt
        log_warning "Reboot required for GPU memory change to take effect"
    fi
    
    # Disable screen blanking
    sudo sed -i 's/#xserver-command=X/xserver-command=X -s 0 -dpms/' /etc/lightdm/lightdm.conf
    
    # Set up log rotation
    sudo tee /etc/logrotate.d/phtv > /dev/null << EOF
$LOG_DIR/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 pi pi
}
EOF
    
    log_success "Pi optimization complete"
}

# Create management scripts
create_management_scripts() {
    log_step "Creating management scripts..."
    
    # Start script
    cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python enhanced_pi_client.py "$@"
EOF
    
    # Stop script
    cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
sudo systemctl stop phtv-client
pkill -f enhanced_pi_client.py
EOF
    
    # Status script
    cat > "$INSTALL_DIR/status.sh" << 'EOF'
#!/bin/bash
echo "=== Pizza Hut TV Client Status ==="
sudo systemctl status phtv-client --no-pager
echo ""
echo "=== Recent Logs ==="
journalctl -u phtv-client -n 20 --no-pager
echo ""
echo "=== System Resources ==="
echo "CPU: $(vcgencmd measure_temp) | $(vcgencmd get_throttled)"
echo "Memory: $(free -h | grep Mem | awk '{print $3"/"$2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3"/"$2" ("$5" used)"}')"
EOF
    
    # Update script
    cat > "$INSTALL_DIR/update.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "🔄 Updating Pizza Hut TV Client..."
sudo systemctl stop phtv-client
source venv/bin/activate
pip install --upgrade -r pi_requirements.txt
sudo systemctl start phtv-client
echo "✅ Update complete"
EOF
    
    # Make scripts executable
    chmod +x "$INSTALL_DIR"/*.sh
    
    log_success "Management scripts created"
}

# Display configuration info
show_configuration() {
    log_step "Configuration Summary"
    
    echo -e "${CYAN}📋 Installation Details:${NC}"
    echo "   • Install Directory: $INSTALL_DIR"
    echo "   • Service Name: $SERVICE_NAME"
    echo "   • Log Directory: $LOG_DIR"
    echo "   • Pi Model: $PI_MODEL"
    echo "   • GPU Memory: ${GPU_MEM}MB"
    echo ""
    echo -e "${CYAN}🎮 Management Commands:${NC}"
    echo "   • Start:   sudo systemctl start $SERVICE_NAME"
    echo "   • Stop:    sudo systemctl stop $SERVICE_NAME"
    echo "   • Status:  sudo systemctl status $SERVICE_NAME"
    echo "   • Logs:    journalctl -u $SERVICE_NAME -f"
    echo "   • Manual:  $INSTALL_DIR/start.sh"
    echo ""
    echo -e "${CYAN}📁 Quick Scripts:${NC}"
    echo "   • Status:  $INSTALL_DIR/status.sh"
    echo "   • Update:  $INSTALL_DIR/update.sh"
    echo "   • Stop:    $INSTALL_DIR/stop.sh"
    echo ""
}

# Main installation flow
main() {
    log_info "Starting Enhanced Pi Client installation..."
    
    check_pi_environment
    update_system
    install_system_deps
    create_install_dir
    install_python_deps
    download_client
    create_service
    configure_autostart
    optimize_pi
    create_management_scripts
    
    show_configuration
    
    log_success "🎉 Installation complete!"
    echo ""
    log_info "Next steps:"
    echo "1. Copy enhanced_pi_client.py to $INSTALL_DIR/"
    echo "2. Edit server settings in the service file if needed"
    echo "3. Start the service: sudo systemctl start $SERVICE_NAME"
    echo "4. Reboot if GPU memory was changed"
    echo ""
    log_warning "Don't forget to configure your server URL, store ID, and screen ID!"
}

# Run installation
main "$@"