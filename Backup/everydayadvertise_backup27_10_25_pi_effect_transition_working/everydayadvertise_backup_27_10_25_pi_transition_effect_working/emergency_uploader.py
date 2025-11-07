#!/usr/bin/env python3
"""
Emergency File Uploader
Uploads files to server via HTTP API when SSH is blocked
"""

import requests
import base64
import json
import sys
import os

# Server configuration
SERVER_URL = "https://everydayadvertise.com"
UPLOAD_SECRET = "pizza_hut_emergency_upload_2025"

# Files to upload
FILES = [
    {
        'local': r'c:\Users\toeng\Pizza Hut TV\templates\dashboard.html',
        'destination': 'templates/dashboard.html',
        'filename': 'dashboard.html'
    },
    {
        'local': r'c:\Users\toeng\Pizza Hut TV\app.py',
        'destination': 'app.py',
        'filename': 'app.py'
    }
]

def get_ssl_verify() -> bool:
    """Return whether to verify SSL certificates based on env.
    Defaults to True. Set PHTV_SSL_VERIFY to 0/false/no/off to disable (dev only).
    """
    val = os.getenv('PHTV_SSL_VERIFY', '1')
    return not (str(val).strip().lower() in ('0', 'false', 'no', 'off'))

def upload_file(local_path, destination, filename):
    """Upload a single file to server"""
    print(f"\n📤 Uploading {filename}...")
    
    try:
        # Read file content
        with open(local_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"   File size: {len(content)} bytes")
        
        # Encode to base64
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Prepare request
        headers = {
            'X-Upload-Secret': UPLOAD_SECRET,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'filename': filename,
            'content': content_b64,
            'destination': destination
        }
        
        # Send to server
        print(f"   Sending to {SERVER_URL}/api/emergency-upload...")
        response = requests.post(
            f'{SERVER_URL}/api/emergency-upload',
            headers=headers,
            json=payload,
            verify=get_ssl_verify(),
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success: {result.get('message')}")
            return True
        else:
            print(f"   ❌ Error: {response.status_code} - {response.text}")
            return False
            
    except FileNotFoundError:
        print(f"   ❌ Error: File not found: {local_path}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def restart_server():
    """Restart the server service"""
    print("\n🔄 Restarting server...")
    
    try:
        headers = {
            'X-Upload-Secret': UPLOAD_SECRET,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            f'{SERVER_URL}/api/emergency-restart',
            headers=headers,
            verify=get_ssl_verify(),
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ Server restart initiated")
            return True
        else:
            print(f"   ❌ Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("="*70)
    print("   🚀 EMERGENCY FILE UPLOADER - Via HTTP API")
    print("="*70)
    print(f"\nTarget server: {SERVER_URL}")
    print(f"Files to upload: {len(FILES)}")
    print("\nThis will upload files via HTTPS (not SSH)")
    print("Note: The server needs the new app.py with the upload endpoint!")
    print("\n" + "="*70)
    
    # Check if files exist
    for file_info in FILES:
        if not os.path.exists(file_info['local']):
            print(f"\n❌ Error: File not found: {file_info['local']}")
            sys.exit(1)
    
    # Upload each file
    success_count = 0
    for file_info in FILES:
        if upload_file(file_info['local'], file_info['destination'], file_info['filename']):
            success_count += 1
    
    print("\n" + "="*70)
    print(f"\n📊 Results: {success_count}/{len(FILES)} files uploaded successfully")
    
    if success_count == len(FILES):
        print("\n✅ All files uploaded!")
        
        # Ask about restarting
        response = input("\nRestart server now? (y/n): ")
        if response.lower() == 'y':
            restart_server()
            print("\n⏳ Wait 10 seconds for server to restart...")
            print("\nThen test:")
            print("1. Open: https://everydayadvertise.com/dashboard")
            print("2. Press Ctrl+Shift+R (hard refresh)")
            print("3. Open Remote Pi Manager")
            print("4. Connect to Pi")
            print("5. See 📺 Screen Preview!")
            print("6. Click ▶ Start")
            print("7. Screenshots appear! 🎉")
        else:
            print("\nManually restart later with:")
            print("ssh ubuntu@everydayadvertise.com 'sudo systemctl restart pizza-hut-tv'")
    else:
        print("\n❌ Some files failed to upload")
        print("Check the errors above and try again")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    # Suppress SSL warnings only if verification is disabled explicitly
    if not get_ssl_verify():
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Upload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
