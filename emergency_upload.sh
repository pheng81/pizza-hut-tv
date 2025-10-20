#!/bin/bash
# Emergency deployment script - Run on Pi to upload files to server

echo "=================================="
echo "Emergency File Upload via Web API"
echo "=================================="

# This script will be run ON THE PI to upload files to the server
# Since direct SSH is blocked, we'll use the web API

SERVER_URL="https://everydayadvertise.com"
PI_DIR="/home/everydayadvertise"
TEMP_DIR="/tmp/upload_files"

# Create temp directory
mkdir -p $TEMP_DIR

echo "Files received from your PC will be uploaded to server..."
echo ""
echo "This script needs to be run after you SCP files to Pi first."
echo ""
echo "Usage:"
echo "1. From your PC: scp templates/dashboard.html everydayadvertise@raspberrypi:$TEMP_DIR/"
echo "2. From your PC: scp app.py everydayadvertise@raspberrypi:$TEMP_DIR/"
echo "3. On Pi: bash $PI_DIR/emergency_upload.sh"
echo ""
echo "Or we can upload directly if files are already on Pi..."

# Check if we can reach server
echo "Testing server connection..."
if curl -s -o /dev/null -w "%{http_code}" $SERVER_URL | grep -q "200"; then
    echo "✓ Server is reachable"
else
    echo "✗ Cannot reach server"
    exit 1
fi

echo ""
echo "Note: This script is prepared. Run the SCP commands from your PC first."
