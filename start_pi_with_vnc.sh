#!/bin/bash
# Start Pi Client with VNC Support
# Sets DISPLAY variable for screen capture

export DISPLAY=:0
cd /home/everydayadvertise

echo "========================================="
echo "Starting Pi Client with VNC Support"
echo "DISPLAY=$DISPLAY"
echo "========================================="

# Kill any existing instances
pkill -f complete_pi_client.py

# Start the client
python3 complete_pi_client.py --server https://everydayadvertise.com > pi_client_vnc.log 2>&1 &

PID=$!
echo "Pi Client started with PID: $PID"
echo "Waiting for initialization..."
sleep 5

# Check logs
echo ""
echo "Recent logs:"
tail -30 pi_client_vnc.log | grep -E "VNC|tunnel|registered|Connected|ERROR" || tail -30 pi_client_vnc.log

echo ""
echo "========================================="
echo "Pi Client is running!"
echo "Check logs: tail -f ~/pi_client_vnc.log"
echo "========================================="
