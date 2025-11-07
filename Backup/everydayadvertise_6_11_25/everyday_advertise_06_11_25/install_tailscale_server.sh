#!/bin/bash
# Install Tailscale on AWS Server
# This script sets up Tailscale VPN for Remote Pi Manager production connectivity

echo "🍕 Pizza Hut TV - Tailscale Installation for AWS Server"
echo "=========================================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script should be run with sudo"
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

# Show connection status
echo "🔍 Tailscale connection status:"
sudo tailscale status
echo ""

# Check if pi_id_ip_map.json exists
if [ -f "/home/ubuntu/pizza-hut-tv/pi_id_ip_map.json" ]; then
    echo "📋 Current Pi ID mappings:"
    cat /home/ubuntu/pizza-hut-tv/pi_id_ip_map.json
    echo ""
    echo "⚠️  Update these with Tailscale IPs from your Raspberry Pis"
elif [ -f "pi_id_ip_map.json" ]; then
    echo "📋 Current Pi ID mappings:"
    cat pi_id_ip_map.json
    echo ""
    echo "⚠️  Update these with Tailscale IPs from your Raspberry Pis"
else
    echo "⚠️  pi_id_ip_map.json not found"
    echo "   It will be created when Pis register"
fi

echo ""
echo "=========================================================="
echo "🎉 Tailscale Setup Complete!"
echo ""
echo "📝 Next Steps:"
echo "   1. Install Tailscale on Raspberry Pi:"
echo "      scp install_tailscale_pi.sh everydayadvertise@raspberrypi.local:"
echo "      ssh everydayadvertise@raspberrypi.local"
echo "      bash install_tailscale_pi.sh"
echo ""
echo "   2. Update pi_id_ip_map.json with Pi's Tailscale IP"
echo ""
echo "   3. Deploy Remote Pi Manager:"
echo "      Run deploy_remote_pi_manager.ps1"
echo ""
echo "   4. Test connectivity:"
echo "      curl http://[PI_TAILSCALE_IP]:8080/status"
echo ""
echo "📖 Full guide: REMOTE_PI_MANAGER_PRODUCTION.md"
echo "=========================================================="
