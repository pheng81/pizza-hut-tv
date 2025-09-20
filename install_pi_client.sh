#!/bin/bash
# Pizza Hut TV - Raspberry Pi Client Installation Script
# Installs all dependencies and sets up the client for Pi

set -e

echo "🍕 Pizza Hut TV - Raspberry Pi Client Installer"
echo "=============================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "   The client may still work, but performance might not be optimal."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Updating system packages..."
sudo apt update

echo "🔧 Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-pygame \
    omxplayer \
    vlc \
    git \
    curl \
    unzip

echo "🐍 Installing Python dependencies..."
pip3 install --user \
    pygame \
    requests \
    argparse

echo "📁 Setting up Pizza Hut TV client directory..."
INSTALL_DIR="$HOME/pizza-hut-tv-pi"
mkdir -p "$INSTALL_DIR"

# Copy the client script
if [ -f "phtv_pi_client.py" ]; then
    cp phtv_pi_client.py "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/phtv_pi_client.py"
else
    echo "❌ Error: phtv_pi_client.py not found in current directory"
    echo "   Please ensure you're running this from the Pizza Hut TV directory"
    exit 1
fi

echo "⚙️  Creating configuration file..."
cat > "$INSTALL_DIR/config.sh" << 'EOF'
#!/bin/bash
# Pizza Hut TV Pi Client Configuration
# Edit these values for your setup

# Server settings (REQUIRED)
export PHTV_SERVER="http://192.168.1.115:5002"
export PHTV_STORE="1000"
export PHTV_SCREEN="tv1"

# Display settings
export PHTV_FULLSCREEN="true"    # Set to "false" for windowed mode
export PHTV_DEBUG="false"        # Set to "true" for debug logging

# You can override these by setting environment variables
# or by editing this file directly
EOF

echo "🚀 Creating startup script..."
cat > "$INSTALL_DIR/start_phtv.sh" << 'EOF'
#!/bin/bash
# Pizza Hut TV Pi Client Startup Script

cd "$(dirname "$0")"

# Load configuration
source config.sh

# Check required variables
if [ -z "$PHTV_SERVER" ] || [ -z "$PHTV_STORE" ] || [ -z "$PHTV_SCREEN" ]; then
    echo "❌ Error: Please configure PHTV_SERVER, PHTV_STORE, and PHTV_SCREEN in config.sh"
    exit 1
fi

echo "🍕 Starting Pizza Hut TV Pi Client..."
echo "   Server: $PHTV_SERVER"
echo "   Store:  $PHTV_STORE"  
echo "   Screen: $PHTV_SCREEN"
echo

# Build command arguments
ARGS="--server $PHTV_SERVER --store $PHTV_STORE --screen $PHTV_SCREEN"

if [ "$PHTV_FULLSCREEN" = "false" ]; then
    ARGS="$ARGS --windowed"
fi

if [ "$PHTV_DEBUG" = "true" ]; then
    ARGS="$ARGS --debug"
fi

# Start the client
exec python3 phtv_pi_client.py $ARGS
EOF

chmod +x "$INSTALL_DIR/start_phtv.sh"

echo "📋 Creating systemd service..."
sudo tee /etc/systemd/system/pizza-hut-tv.service > /dev/null << EOF
[Unit]
Description=Pizza Hut TV Pi Client
After=network.target graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment=DISPLAY=:0
ExecStart=$INSTALL_DIR/start_phtv.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
EOF

echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

echo "✅ Installation complete!"
echo
echo "📝 Next steps:"
echo "1. Edit configuration: nano $INSTALL_DIR/config.sh"
echo "2. Test manually:      cd $INSTALL_DIR && ./start_phtv.sh"
echo "3. Enable auto-start:  sudo systemctl enable pizza-hut-tv"
echo "4. Start service:      sudo systemctl start pizza-hut-tv"
echo "5. Check status:       sudo systemctl status pizza-hut-tv"
echo
echo "🎥 Controls when running:"
echo "   ESC or Q  = Quit"
echo "   SPACE     = Skip to next video"  
echo "   N         = Next video"
echo "   R         = Refresh playlist"
echo
echo "📍 Installation directory: $INSTALL_DIR"
echo
echo "⚠️  IMPORTANT: Make sure to configure your server URL, store ID, and screen ID in config.sh"