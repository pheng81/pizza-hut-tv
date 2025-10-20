#!/usr/bin/env python3
"""
Properly integrate VNC handlers into complete_pi_client.py
"""
import re

print("=" * 50)
print("  VNC Handler Integration (Python)")
print("=" * 50)
print()

# Read the file
print("[1/5] Reading complete_pi_client.py...")
with open('complete_pi_client.py', 'r') as f:
    content = f.read()

# Create backup
print("[2/5] Creating backup...")
with open('complete_pi_client.py.backup_vnc2', 'w') as f:
    f.write(content)
print("✅ Backup: complete_pi_client.py.backup_vnc2")
print()

# Add import after line with "from seamless_video_player import"
print("[3/5] Adding VNC import...")
vnc_import = "from pi_vnc_tunnel import init_vnc_tunnel, get_vnc_tunnel"

if vnc_import in content:
    print("⚠️  VNC import already exists, skipping...")
else:
    # Find the seamless_video_player import line
    pattern = r'(from seamless_video_player import .*\n)'
    replacement = r'\1' + vnc_import + '\n'
    content = re.sub(pattern, replacement, content)
    print("✅ VNC import added")
print()

# Add VNC handlers after the 'disconnect' handler (before start_websocket_connection method)
print("[4/5] Adding VNC handlers...")

vnc_handlers = '''
        @self.sio.on('vnc_connect')
        def on_vnc_connect(data):
            """Handle VNC connection request from dashboard"""
            logger.info(f'🖥️  VNC connect request from dashboard: {data}')
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
            logger.info('🖥️  VNC disconnect request from dashboard')
            try:
                tunnel = get_vnc_tunnel()
                if tunnel:
                    tunnel.disconnect()
                    logger.info('✅ VNC tunnel disconnected')
            except Exception as e:
                logger.error(f'❌ VNC disconnect error: {e}')
'''

if 'on_vnc_connect' in content:
    print("⚠️  VNC handlers already exist, skipping...")
else:
    # Find the start_websocket_connection method
    pattern = r'(\n    def start_websocket_connection\(self\):)'
    replacement = vnc_handlers + r'\1'
    content = re.sub(pattern, replacement, content)
    print("✅ VNC handlers added")
print()

# Add VNC initialization after sio.connect() call
print("[5/5] Adding VNC tunnel initialization...")

vnc_init = '''
                        # Initialize VNC tunnel
                        try:
                            vnc_tunnel = init_vnc_tunnel(self.sio, self.pi_id)
                            logger.info('✅ VNC tunnel initialized')
                        except Exception as e:
                            logger.error(f'⚠️  VNC tunnel init failed: {e}')
'''

if 'init_vnc_tunnel' in content and 'VNC tunnel initialized' in content:
    print("⚠️  VNC initialization already exists, skipping...")
else:
    # Find the heartbeat thread start line (after sio.connect)
    pattern = r"(# Start heartbeat thread\n\s+threading\.Thread\(target=self\.websocket_heartbeat, daemon=True\)\.start\(\)\n)"
    replacement = vnc_init + r'\1'
    content = re.sub(pattern, replacement, content)
    print("✅ VNC initialization added")
print()

# Write the modified content
with open('complete_pi_client.py', 'w') as f:
    f.write(content)

print("=" * 50)
print("✅ Integration Complete!")
print("=" * 50)
print()
print("Next steps:")
print("1. Restart: pkill -f complete_pi_client && python3 complete_pi_client.py --server https://everydayadvertise.com &")
print("2. Check logs: tail -f pi_client.log")
print("3. Test VNC from dashboard!")
print()
