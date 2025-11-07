#!/bin/bash
# Install Tailscale on Raspberry Pi
# This script sets up Tailscale VPN for Remote Pi Manager production connectivity

echo "🍕 Pizza Hut TV - Tailscale Installation for Raspberry Pi"
echo "=========================================================="
echo ""

# Check if running on Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null && ! grep -q "BCM" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Tailscale is already installed
if command -v tailscale &> /dev/null; then
    echo "✅ Tailscale is already installed"
    echo ""
    tailscale version
    echo ""
    read -p "Reinstall? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Current Tailscale status:"
        sudo tailscale status
        echo ""
        echo "Current Tailscale IP:"
        tailscale ip -4
        exit 0
    fi
fi

# Install Tailscale
echo "📥 Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh

if [ $? -ne 0 ]; then
    echo "❌ Tailscale installation failed!"
    exit 1
fi

echo "✅ Tailscale installed successfully"
echo ""

# Start Tailscale
echo "🚀 Starting Tailscale..."
sudo tailscale up

if [ $? -ne 0 ]; then
    echo "❌ Failed to start Tailscale"
    echo "Please run 'sudo tailscale up' manually"
    exit 1
fi

echo "✅ Tailscale started"
echo ""

# Get Tailscale IP
echo "📍 Your Tailscale IP address:"
TAILSCALE_IP=$(tailscale ip -4)
echo "   $TAILSCALE_IP"
echo ""

# Get Pi ID
PI_ID_FILE="$HOME/.pizza_hut_tv_id"
if [ -f "$PI_ID_FILE" ]; then
    PI_ID=$(cat "$PI_ID_FILE")
    echo "📟 Your Pi ID: $PI_ID"
    echo ""
fi

# Show connection status
echo "🔍 Tailscale connection status:"
sudo tailscale status
echo ""

# Instructions
echo "=========================================================="
echo "🎉 Tailscale Setup Complete!"
echo ""
echo "📝 Next Steps:"
echo "   1. Update pi_id_ip_map.json on AWS server:"
echo "      {"
if [ ! -z "$PI_ID" ]; then
    echo "        \"$PI_ID\": \"$TAILSCALE_IP\""
else
    echo "        \"raspberrypi-XXXX\": \"$TAILSCALE_IP\""
fi
echo "      }"
echo ""
echo "   2. Test connectivity from AWS server:"
echo "      curl http://$TAILSCALE_IP:8080/status"
echo ""
echo "   3. Access Remote Pi Manager:"
echo "      https://everydayadvertise.com/remote-pi-manager"
echo ""
echo "📖 Full guide: REMOTE_PI_MANAGER_PRODUCTION.md"
echo "=========================================================="
