#!/usr/bin/env python3
"""
Get Pi Identifier remotely via SSH
Retrieves the persistent Pi ID without needing to see the screen
"""

import sys
import subprocess

def get_pi_id_ssh(pi_ip="192.168.1.131", username="everydayadvertise"):
    """Get Pi ID via SSH"""
    try:
        # Try to read from saved file
        cmd = f'ssh {username}@{pi_ip} "cat ~/.pizza_hut_tv_id 2>/dev/null || echo \'NOT_FOUND\'"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        pi_id = result.stdout.strip()
        
        if pi_id and pi_id != 'NOT_FOUND':
            print(f"✅ Pi ID: {pi_id}")
            return pi_id
        else:
            # If file doesn't exist, generate ID manually
            print("⚠️  Pi ID file not found, generating from hostname...")
            
            # Get hostname
            cmd_hostname = f'ssh {username}@{pi_ip} "hostname"'
            result_hostname = subprocess.run(cmd_hostname, shell=True, capture_output=True, text=True, timeout=10)
            hostname = result_hostname.stdout.strip()
            
            # Get MAC address
            cmd_mac = f'ssh {username}@{pi_ip} "cat /sys/class/net/eth0/address 2>/dev/null || cat /sys/class/net/wlan0/address"'
            result_mac = subprocess.run(cmd_mac, shell=True, capture_output=True, text=True, timeout=10)
            mac = result_mac.stdout.strip().replace(':', '')[-4:]
            
            pi_id = f"{hostname}-{mac}"
            print(f"✅ Generated Pi ID: {pi_id}")
            
            # Save it for future use
            cmd_save = f'ssh {username}@{pi_ip} "echo \'{pi_id}\' > ~/.pizza_hut_tv_id"'
            subprocess.run(cmd_save, shell=True, timeout=10)
            print(f"💾 Saved Pi ID to ~/.pizza_hut_tv_id")
            
            return pi_id
            
    except subprocess.TimeoutExpired:
        print("❌ SSH connection timeout")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    # Get Pi IP from command line or use default
    pi_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.131"
    username = sys.argv[2] if len(sys.argv) > 2 else "everydayadvertise"
    
    print(f"🔍 Connecting to {username}@{pi_ip}...")
    print()
    
    pi_id = get_pi_id_ssh(pi_ip, username)
    
    if pi_id:
        print()
        print("="*60)
        print(f"   Use this ID in Remote Pi Manager: {pi_id}")
        print("="*60)
    else:
        print()
        print("❌ Failed to retrieve Pi ID")
        print()
        print("Manual alternatives:")
        print(f"1. SSH: ssh {username}@{pi_ip} 'cat ~/.pizza_hut_tv_id'")
        print(f"2. Look at Pi screen (ID shown in corner)")
        print(f"3. Run: ssh {username}@{pi_ip} 'hostname'-XXXX")
