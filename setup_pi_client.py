#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Simple Pi Setup Script

This script automatically detects the Pi's identity and helps configure it.
No need to manually enter Pi ID - it uses the Pi's hostname or MAC address.

Usage:
    python3 setup_pi_client.py --pair-code 3835 --store-id 1234 --screen-id 1

Or interactive mode:
    python3 setup_pi_client.py

The script will:
1. Auto-detect Pi identity (hostname, MAC, serial)
2. Prompt for pairing code, store ID, screen ID
3. Fetch any remote configuration from server
4. Set up and start the service
"""

import argparse
import subprocess
import sys
import os
import socket
import uuid


def get_pi_identity():
    """Automatically detect Pi's identity."""
    identity = {}
    
    # Get hostname
    try:
        identity['hostname'] = socket.gethostname()
    except:
        identity['hostname'] = 'unknown'
    
    # Get MAC address
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0,2*6,2)][::-1])
        identity['mac'] = mac
    except:
        identity['mac'] = 'unknown'
    
    # Get Raspberry Pi serial number
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    identity['serial'] = line.split(':')[1].strip()
                    break
    except:
        identity['serial'] = 'unknown'
    
    # Get primary IP address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        identity['ip'] = s.getsockname()[0]
        s.close()
    except:
        identity['ip'] = 'unknown'
    
    return identity


def prompt_configuration():
    """Interactive prompt for configuration."""
    print("\n" + "="*60)
    print("📋 Configuration Setup")
    print("="*60)
    
    # Show detected identity
    identity = get_pi_identity()
    
    # Generate Pi ID (same logic as complete_pi_client.py)
    hostname = identity['hostname']
    mac_suffix = identity['mac'].replace(':', '')[-4:]
    generated_pi_id = f"{hostname}-{mac_suffix}"
    
    print(f"\n🔍 Detected Pi Information:")
    print(f"   Hostname:      {identity['hostname']}")
    print(f"   MAC Address:   {identity['mac']}")
    print(f"   IP Address:    {identity['ip']}")
    print(f"   Serial:        {identity['serial']}")
    print(f"\n   📟 Generated Pi ID: {generated_pi_id}")
    print(f"   (This ID will be displayed on screen)")
    print()
    
    # Use generated Pi ID as default
    pi_id = input(f"Pi Identifier [{generated_pi_id}]: ").strip() or generated_pi_id
    
    # Prompt for other settings
    server = input("Server URL [https://everydayadvertise.com]: ").strip() or "https://everydayadvertise.com"
    pair_code = input("Your Pairing Code (4 digits): ").strip()
    
    while not pair_code or len(pair_code) != 4 or not pair_code.isdigit():
        print("❌ Pairing code must be 4 digits!")
        pair_code = input("Your Pairing Code (4 digits): ").strip()
    
    store_id = input("Store ID: ").strip()
    while not store_id:
        print("❌ Store ID is required!")
        store_id = input("Store ID: ").strip()
    
    screen_id = input("Screen ID [1]: ").strip() or "1"
    
    return {
        'pi_id': pi_id,
        'server': server,
        'pair_code': pair_code,
        'store_id': store_id,
        'screen_id': screen_id,
        'identity': identity
    }


def check_remote_config(server, pi_id, pair_code):
    """Check if there's a remote configuration for this Pi."""
    try:
        import requests
        url = f"{server}/api/get_pi_config/{pi_id}"
        headers = {'X-User-Code': pair_code}
        
        print(f"\n🔍 Checking for remote configuration...")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Found remote configuration!")
                return data.get('config')
        
        print("ℹ️  No remote configuration found (will use local settings)")
        return None
        
    except Exception as e:
        print(f"⚠️  Could not check remote config: {e}")
        return None


def setup_systemd_service(config):
    """Set up the systemd service."""
    try:
        service_name = "everydayadvertise_tv"
        install_dir = os.path.expanduser("~/everydayadvertise_tv_client")
        venv_python = f"{install_dir}/venv/bin/python"
        main_script = f"{install_dir}/complete_pi_client.py"
        
        # Check if files exist
        if not os.path.exists(main_script):
            print(f"❌ {main_script} not found!")
            print("Please ensure complete_pi_client.py is in ~/everydayadvertise_tv_client/")
            return False
        
        # Build command
        exec_start = f"{venv_python} {main_script} --server {config['server']} --store-id {config['store_id']} --screen-id {config['screen_id']} --pair-code {config['pair_code']}"
        
        # Create service file
        service_content = f"""[Unit]
    Description=EverydayAdvertise TV Digital Signage Client
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User={os.environ.get('USER', 'pi')}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/{os.environ.get('USER', 'pi')}/.Xauthority
Environment=PYTHONUNBUFFERED=1
SupplementaryGroups=video render
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
        
        temp_path = "/tmp/everydayadvertise_tv.service"
        with open(temp_path, 'w') as f:
            f.write(service_content)
        
        print(f"\n📝 Creating systemd service...")
        subprocess.run(['sudo', 'cp', temp_path, f'/etc/systemd/system/{service_name}.service'], check=True)
        
        print("🔄 Reloading systemd...")
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        
        print("✅ Enabling service...")
        subprocess.run(['sudo', 'systemctl', 'enable', service_name], check=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup service: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Setup EverydayAdvertise TV Pi client')
    parser.add_argument('--pair-code', help='4-digit pairing code')
    parser.add_argument('--store-id', help='Store ID')
    parser.add_argument('--screen-id', default='1', help='Screen ID (default: 1)')
    parser.add_argument('--server', default='https://everydayadvertise.com', help='Server URL')
    parser.add_argument('--start', action='store_true', help='Start service immediately')
    parser.add_argument('--pi-id', help='Custom Pi identifier (defaults to hostname)')
    
    args = parser.parse_args()
    
    print("╔═══════════════════════════════════════════════════════╗")
    print("║                                                       ║")
    print("║   EverydayAdvertise TV - Pi Client Setup            ║")
    print("║                                                       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    # Get Pi identity
    identity = get_pi_identity()
    
    # Interactive mode if required args not provided
    if not args.pair_code or not args.store_id:
        config = prompt_configuration()
    else:
        config = {
            'pi_id': args.pi_id or identity['hostname'],
            'server': args.server,
            'pair_code': args.pair_code,
            'store_id': args.store_id,
            'screen_id': args.screen_id,
            'identity': identity
        }
    
    # Check for remote configuration
    remote_config = check_remote_config(config['server'], config['pi_id'], config['pair_code'])
    
    # Use remote config if available
    if remote_config:
        print("\n✨ Using remote configuration:")
        print(f"   Store ID:  {remote_config['store_id']}")
        print(f"   Screen ID: {remote_config['screen_id']}")
        config['store_id'] = remote_config['store_id']
        config['screen_id'] = remote_config['screen_id']
    
    # Show final configuration
    print("\n" + "="*60)
    print("📋 Final Configuration:")
    print("="*60)
    print(f"   Pi ID:        {config['pi_id']}")
    print(f"   Server:       {config['server']}")
    print(f"   Store ID:     {config['store_id']}")
    print(f"   Screen ID:    {config['screen_id']}")
    print(f"   Pair Code:    {config['pair_code']}")
    print("="*60)
    
    # Confirm
    confirm = input("\n✅ Proceed with this configuration? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Setup cancelled")
        return
    
    # Setup service
    if setup_systemd_service(config):
        print("\n✅ Service configured successfully!")
        
        if args.start or input("\n🚀 Start service now? (Y/n): ").lower() != 'n':
            print("\n🚀 Starting service...")
            subprocess.run(['sudo', 'systemctl', 'restart', 'everydayadvertise_tv'])
            print("✅ Service started!")
            
            print("\n📋 Useful commands:")
            print("   Status:  sudo systemctl status everydayadvertise_tv")
            print("   Logs:    journalctl -u everydayadvertise_tv -f")
            print("   Stop:    sudo systemctl stop everydayadvertise_tv")
            print("   Restart: sudo systemctl restart everydayadvertise_tv")
        else:
            print("\n💡 To start later, run:")
            print("   sudo systemctl start everydayadvertise_tv")
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
