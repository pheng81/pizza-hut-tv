#!/usr/bin/env python3
"""
Emergency deployment script
Uploads files to Pi, then Pi forwards to server via HTTPS
"""

import subprocess
import sys
import os

print("="*60)
print("  EMERGENCY DEPLOYMENT - Via Pi Relay")
print("="*60)
print()

# Files to deploy
files = [
    {
        'local': r'c:\Users\toeng\Pizza Hut TV\templates\dashboard.html',
        'pi_dest': '/tmp/new_dashboard.html',
        'server_dest': '~/Pizza-Hut-TV/templates/dashboard.html'
    },
    {
        'local': r'c:\Users\toeng\Pizza Hut TV\app.py',
        'pi_dest': '/tmp/new_app.py',
        'server_dest': '~/Pizza-Hut-TV/app.py'
    }
]

pi_host = 'everydayadvertise@raspberrypi'

print("Step 1: Upload files to Pi...")
print()

for file in files:
    print(f"Uploading {os.path.basename(file['local'])}...")
    result = subprocess.run(
        ['scp', file['local'], f"{pi_host}:{file['pi_dest']}"],
        capture_output=True
    )
    
    if result.returncode == 0:
        print(f"  ✓ Uploaded to Pi")
    else:
        print(f"  ✗ Failed: {result.stderr.decode()}")
        sys.exit(1)

print()
print("Step 2: Create transfer script on Pi...")

transfer_script = '''#!/bin/bash
# Transfer files from Pi to server
echo "Attempting to reach server..."

# Check if server SSH works from Pi
if timeout 5 ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@everydayadvertise.com "echo 'Server reachable'" 2>/dev/null; then
    echo "✓ Server SSH accessible from Pi!"
    echo "Copying files..."
    
    scp /tmp/new_dashboard.html ubuntu@everydayadvertise.com:~/Pizza-Hut-TV/templates/dashboard.html
    scp /tmp/new_app.py ubuntu@everydayadvertise.com:~/Pizza-Hut-TV/app.py
    
    echo "Restarting server..."
    ssh ubuntu@everydayadvertise.com "sudo systemctl restart pizza-hut-tv"
    
    echo "✓ Deployment complete!"
else
    echo "✗ Cannot reach server from Pi either"
    echo "Server must be configured to accept connections"
    exit 1
fi
'''

# Write script to local temp file
with open('transfer_to_server.sh', 'w', encoding='utf-8') as f:
    f.write(transfer_script)

# Upload script to Pi
print("Uploading transfer script...")
result = subprocess.run(
    ['scp', 'transfer_to_server.sh', f"{pi_host}:/tmp/"],
    capture_output=True
)

if result.returncode == 0:
    print("  ✓ Script uploaded")
else:
    print(f"  ✗ Failed: {result.stderr.decode()}")
    sys.exit(1)

print()
print("Step 3: Execute transfer on Pi...")
result = subprocess.run(
    ['ssh', pi_host, 'bash /tmp/transfer_to_server.sh'],
    capture_output=False
)

if result.returncode == 0:
    print()
    print("="*60)
    print("  ✓ DEPLOYMENT SUCCESSFUL!")
    print("="*60)
    print()
    print("Next steps:")
    print("1. Open: https://everydayadvertise.com/dashboard")
    print("2. Hard refresh: Ctrl+Shift+R")
    print("3. Open Remote Pi Manager")
    print("4. Connect to Pi")
    print("5. See the 📺 Screen Preview section!")
    print("6. Click ▶ Start")
else:
    print()
    print("="*60)
    print("  ✗ Deployment failed")
    print("="*60)
    print()
    print("The server may not accept SSH from Pi either.")
    print("You'll need to:")
    print("1. Contact hosting provider")
    print("2. Use WinSCP/FileZilla")
    print("3. Or use web-based file manager")

# Cleanup
os.remove('transfer_to_server.sh')
