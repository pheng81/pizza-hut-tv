#!/usr/bin/env python3
"""
Run this ON THE PI to upload files to server via HTTP
This bypasses SSH completely!
"""

import requests
import base64
import json
import time
import os

SERVER_URL = "https://everydayadvertise.com"
UPLOAD_SECRET = "pizza_hut_emergency_upload_2025"

FILES = [
    {
        'local': '/tmp/new_app.py',
        'destination': 'app.py',
        'filename': 'app.py'
    },
    {
        'local': '/tmp/new_dashboard.html',
        'destination': 'templates/dashboard.html',
        'filename': 'dashboard.html'
    }
]

def get_ssl_verify() -> bool:
    """Return whether to verify SSL certificates based on env.
    Defaults to True. Set PHTV_SSL_VERIFY to 0/false/no/off to disable (dev only).
    """
    val = os.getenv('PHTV_SSL_VERIFY', '1')
    return not (str(val).strip().lower() in ('0', 'false', 'no', 'off'))

def upload_file(local_path, destination, filename):
    """Upload file to server"""
    print(f"\n📤 Uploading {filename}...")
    
    try:
        # Read file
        with open(local_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"   Size: {len(content)} bytes")
        
        # Encode to base64
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Send to server
        response = requests.post(
            f'{SERVER_URL}/api/emergency-upload',
            headers={
                'X-Upload-Secret': UPLOAD_SECRET,
                'Content-Type': 'application/json'
            },
            json={
                'filename': filename,
                'content': content_b64,
                'destination': destination
            },
            verify=get_ssl_verify(),
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"   ✅ Success!")
            return True
        else:
            print(f"   ❌ Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def restart_server():
    """Restart server"""
    print("\n🔄 Restarting server...")
    try:
        requests.post(
            f'{SERVER_URL}/api/emergency-restart',
            headers={'X-Upload-Secret': UPLOAD_SECRET},
            verify=get_ssl_verify(),
            timeout=10
        )
        print("   ✅ Restart initiated")
        return True
    except:
        return False

print("="*60)
print("  PI → SERVER FILE UPLOADER")
print("="*60)

success = 0
for f in FILES:
    if upload_file(f['local'], f['destination'], f['filename']):
        success += 1

print(f"\n📊 {success}/{len(FILES)} uploaded")

if success == len(FILES):
    restart_server()
    print("\n✅ DONE! Wait 10 seconds then test dashboard.")
else:
    print("\n❌ Some files failed. Check errors above.")
