#!/bin/bash

# Deploy updated Pi client to Raspberry Pi
echo "Deploying enhanced Pi client to Raspberry Pi..."

# Check if password is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <raspberry_pi_password>"
    echo "Example: $0 your_password_here"
    exit 1
fi

PI_PASSWORD="$1"
PI_USER="everydayadvertise"
PI_HOST="raspberrypi"

# Create temporary directory for transfer
TEMP_DIR="/tmp/pi_client_update"
mkdir -p "$TEMP_DIR"

# Copy the enhanced Pi client file
cp "phtv_pi_client.py" "$TEMP_DIR/"

# Use sshpass to transfer file (install sshpass if not available)
echo "Transferring enhanced Pi client..."
sshpass -p "$PI_PASSWORD" scp "$TEMP_DIR/phtv_pi_client.py" "$PI_USER@$PI_HOST:/home/everydayadvertise/"

if [ $? -eq 0 ]; then
    echo "✅ Pi client updated successfully!"
    echo "The EA TV icon on desktop will now use enhanced synchronization"
    
    # Restart any running EA TV process
    echo "Restarting EA TV process if running..."
    sshpass -p "$PI_PASSWORD" ssh "$PI_USER@$PI_HOST" "pkill -f phtv_pi_client.py || true"
    
    echo "✅ Deployment complete! You can now click the EA TV icon to test synchronized playback."
else
    echo "❌ Failed to transfer files to Raspberry Pi"
    exit 1
fi

# Cleanup
rm -rf "$TEMP_DIR"