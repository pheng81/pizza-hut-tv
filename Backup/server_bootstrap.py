#!/usr/bin/env python3
"""
SERVER BOOTSTRAP SCRIPT
This runs ON THE SERVER to download files from Pi
"""
import requests
import base64
import os
import sys

PI_IP = "YOUR_PI_PUBLIC_IP"  # User needs to fill this
PI_PORT = 8765

print("="*70)
print("   🚀 SERVER SELF-BOOTSTRAP")
print("="*70)
print()

files = [
    {
        'url': f'http://{PI_IP}:{PI_PORT}/new_app.py',
        'destination': '/home/everydayadvertise/pizza-hut-tv/app.py',
        'backup': '/home/everydayadvertise/pizza-hut-tv/app.py.backup'
    },
    {
        'url': f'http://{PI_IP}:{PI_PORT}/new_dashboard.html',
        'destination': '/home/everydayadvertise/pizza-hut-tv/templates/dashboard.html',
        'backup': '/home/everydayadvertise/pizza-hut-tv/templates/dashboard.html.backup'
    }
]

success = 0

for file_info in files:
    filename = os.path.basename(file_info['destination'])
    print(f"📥 Downloading {filename}...")
    
    try:
        # Download from Pi
        response = requests.get(file_info['url'], timeout=30)
        
        if response.status_code == 200:
            # Backup existing file
            if os.path.exists(file_info['destination']):
                os.rename(file_info['destination'], file_info['backup'])
                print(f"   💾 Backed up existing file")
            
            # Write new file
            with open(file_info['destination'], 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            print(f"   ✅ Success! ({len(response.content)} bytes)")
            success += 1
        else:
            print(f"   ❌ HTTP {response.status_code}")
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()

print("="*70)
print(f"   📊 {success}/{len(files)} files updated")
print("="*70)
print()

if success == len(files):
    print("✅ Bootstrap complete!")
    print()
    print("🔄 Restarting service...")
    os.system('sudo systemctl restart pizza-hut-tv')
    print("✅ Service restarted!")
else:
    print("❌ Some files failed. Check errors above.")
    sys.exit(1)
