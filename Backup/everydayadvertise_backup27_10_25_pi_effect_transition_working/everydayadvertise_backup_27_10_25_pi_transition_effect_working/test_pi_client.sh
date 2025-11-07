#!/bin/bash
# Test script to run Pi client with full error output

echo "🍕 Starting Pizza Hut TV Pi Client with debug output..."
echo "📝 Logs will be saved to pi_client_debug.log"
echo ""

cd /home/everydayadvertise/pizza-hut-tv/

python3 complete_pi_client.py --debug 2>&1 | tee pi_client_debug.log

echo ""
echo "✅ Client stopped. Check pi_client_debug.log for errors."
