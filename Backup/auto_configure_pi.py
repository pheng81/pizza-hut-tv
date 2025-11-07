#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Pi Auto-Configuration Script

This script allows a Raspberry Pi to automatically fetch its configuration
from the server and set itself up.

Usage:
    python3 auto_configure_pi.py --pi-id pi-001 --pair-code 3835 --server https://everydayadvertise.com

The script will:
1. Fetch configuration from the server
2. Update the Pi's systemd service with correct parameters
3. Restart the service to apply changes
"""

import argparse
import requests
import json
import subprocess
import sys
import os


def fetch_pi_config(server_url, pi_id, pair_code):
    """Fetch configuration from the server."""
    try:
        url = f"{server_url}/api/get_pi_config/{pi_id}"
        headers = {'X-User-Code': pair_code}
        
        print(f"🔍 Fetching configuration from {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('config')
            else:
                print(f"❌ Server error: {data.get('error', 'Unknown error')}")
                return None
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to fetch configuration: {e}")
        return None


def update_systemd_service(config, server_url):
    """Update the systemd service with new configuration."""
    try:
        service_name = "pizza-hut-tv"
        install_dir = os.path.expanduser("~/pizza-hut-tv")
        venv_python = f"{install_dir}/venv/bin/python"
        main_script = f"{install_dir}/complete_pi_client.py"
        
        # Build command line arguments
        args = [
            f"--server {server_url}",
            f"--store-id {config['store_id']}",
            f"--screen-id {config['screen_id']}",
            f"--pair-code {config['pair_code']}"
        ]
        
        exec_start = f"{venv_python} {main_script} {' '.join(args)}"
        
        # Create systemd service content
        service_content = f"""[Unit]
Description=Pizza Hut TV Digital Signage Client
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User={os.environ.get('USER', 'pi')}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/{os.environ.get('USER', 'pi')}/.Xauthority
Environment=PYTHONUNBUFFERED=1
WorkingDirectory={install_dir}
ExecStartPre=/bin/sleep 10
ExecStart={exec_start}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
"""
        
        # Write service file
        service_path = f"/etc/systemd/system/{service_name}.service"
        temp_path = "/tmp/pizza-hut-tv.service"
        
        with open(temp_path, 'w') as f:
            f.write(service_content)
        
        print(f"📝 Writing service file to {service_path}...")
        subprocess.run(['sudo', 'cp', temp_path, service_path], check=True)
        
        print("🔄 Reloading systemd...")
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        
        print("✅ Enabling service...")
        subprocess.run(['sudo', 'systemctl', 'enable', service_name], check=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to update systemd service: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Auto-configure Pizza Hut TV Pi client from server'
    )
    parser.add_argument('--pi-id', required=True, help='Unique Pi identifier (e.g., pi-001)')
    parser.add_argument('--pair-code', required=True, help='4-digit pairing code')
    parser.add_argument('--server', required=True, help='Server URL (e.g., https://everydayadvertise.com)')
    parser.add_argument('--start', action='store_true', help='Start the service after configuration')
    
    args = parser.parse_args()
    
    print("╔═══════════════════════════════════════════════════════╗")
    print("║                                                       ║")
    print("║   🍕 Pizza Hut TV - Pi Auto-Configuration 🍕         ║")
    print("║                                                       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    # Fetch configuration from server
    config = fetch_pi_config(args.server, args.pi_id, args.pair_code)
    
    if not config:
        print("\n❌ Failed to fetch configuration from server")
        sys.exit(1)
    
    print("\n✅ Configuration received:")
    print(f"   Pi ID:     {config['pi_id']}")
    print(f"   Store ID:  {config['store_id']}")
    print(f"   Screen ID: {config['screen_id']}")
    print(f"   Pair Code: {config['pair_code']}")
    print()
    
    # Update systemd service
    if update_systemd_service(config, args.server):
        print("\n✅ Service configured successfully!")
        
        if args.start:
            print("\n🚀 Starting service...")
            subprocess.run(['sudo', 'systemctl', 'restart', 'pizza-hut-tv'])
            print("✅ Service started!")
        else:
            print("\n💡 To start the service, run:")
            print("   sudo systemctl restart pizza-hut-tv")
        
        print("\n📋 Service commands:")
        print("   Status:  sudo systemctl status pizza-hut-tv")
        print("   Logs:    journalctl -u pizza-hut-tv -f")
        print("   Stop:    sudo systemctl stop pizza-hut-tv")
        print()
        
    else:
        print("\n❌ Failed to configure service")
        sys.exit(1)


if __name__ == '__main__':
    main()
