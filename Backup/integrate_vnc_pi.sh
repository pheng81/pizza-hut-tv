#!/bin/bash
# Automatic VNC Integration Script for Pi
# This script adds VNC handlers to complete_pi_client.py

echo "========================================="
echo "  VNC Handler Integration"
echo "========================================="
echo ""

# Backup the original file
echo "[1/4] Creating backup..."
cp complete_pi_client.py complete_pi_client.py.backup_vnc
echo "✅ Backup created: complete_pi_client.py.backup_vnc"
echo ""

# Add import at the top (after line 29 - after seamless_video_player import)
echo "[2/4] Adding VNC import..."
sed -i '29 a from pi_vnc_tunnel import init_vnc_tunnel, get_vnc_tunnel' complete_pi_client.py
echo "✅ Import added"
echo ""

# Find the line number where we register other handlers (after @self.sio.on('request_screenshot'))
echo "[3/4] Adding VNC handlers..."

# Create the VNC handlers code
cat > /tmp/vnc_handlers.txt << 'HANDLERS'

        @self.sio.on('vnc_connect')
        def on_vnc_connect(data):
            """Handle VNC connection request from dashboard"""
            logger.info(f'🖥️ VNC connect request from dashboard: {data}')
            try:
                tunnel = get_vnc_tunnel()
                if tunnel:
                    tunnel.connect(data.get('dashboard_sid'))
                    logger.info('✅ VNC tunnel connected')
                else:
                    logger.error('❌ VNC tunnel not initialized')
            except Exception as e:
                logger.error(f'❌ VNC connect error: {e}')

        @self.sio.on('vnc_data')
        def on_vnc_data(data):
            """Handle VNC data from dashboard (mouse/keyboard)"""
            try:
                tunnel = get_vnc_tunnel()
                if tunnel:
                    tunnel.send_to_vnc(data)
            except Exception as e:
                logger.error(f'❌ VNC data error: {e}')

        @self.sio.on('vnc_disconnect')
        def on_vnc_disconnect(data):
            """Handle VNC disconnection from dashboard"""
            logger.info('🖥️ VNC disconnect request from dashboard')
            try:
                tunnel = get_vnc_tunnel()
                if tunnel:
                    tunnel.disconnect()
                    logger.info('✅ VNC tunnel disconnected')
            except Exception as e:
                logger.error(f'❌ VNC disconnect error: {e}')
HANDLERS

# Find the line after request_screenshot handler and insert VNC handlers
LINE_NUM=$(grep -n "@self.sio.on('request_screenshot')" complete_pi_client.py | cut -d: -f1)
if [ -z "$LINE_NUM" ]; then
    echo "❌ Could not find request_screenshot handler"
    exit 1
fi

# Add handlers after the request_screenshot handler block (approximately 15 lines after)
INSERT_LINE=$((LINE_NUM + 15))
sed -i "${INSERT_LINE}r /tmp/vnc_handlers.txt" complete_pi_client.py
echo "✅ VNC handlers added at line $INSERT_LINE"
echo ""

# Add VNC tunnel initialization after sio.connect()
echo "[4/4] Adding VNC tunnel initialization..."

# Find the line with self.sio.connect and add initialization after it
CONNECT_LINE=$(grep -n "self.sio.connect" complete_pi_client.py | head -1 | cut -d: -f1)
if [ -z "$CONNECT_LINE" ]; then
    echo "❌ Could not find sio.connect line"
    exit 1
fi

# Add initialization after the connect block (approximately 5 lines after)
INIT_LINE=$((CONNECT_LINE + 5))

cat > /tmp/vnc_init.txt << 'INIT'
                        
                        # Initialize VNC tunnel
                        try:
                            vnc_tunnel = init_vnc_tunnel(self.sio, self.pi_id)
                            logger.info('✅ VNC tunnel initialized')
                        except Exception as e:
                            logger.error(f'⚠️ VNC tunnel init failed: {e}')
INIT

sed -i "${INIT_LINE}r /tmp/vnc_init.txt" complete_pi_client.py
echo "✅ VNC initialization added at line $INIT_LINE"
echo ""

# Clean up temp files
rm /tmp/vnc_handlers.txt /tmp/vnc_init.txt

echo "========================================="
echo "✅ Integration Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Restart the Pi service:"
echo "   sudo systemctl restart pizzahut-tv-pi.service"
echo ""
echo "2. Check logs:"
echo "   sudo journalctl -u pizzahut-tv-pi -f"
echo ""
echo "3. Test VNC from dashboard!"
echo ""
echo "If anything goes wrong, restore backup:"
echo "   cp complete_pi_client.py.backup_vnc complete_pi_client.py"
echo ""
