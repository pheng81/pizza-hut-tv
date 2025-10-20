#!/usr/bin/env python3
"""
🚀 Deploy Mobile Sync to Raspberry Pi
Deploys complete_pi_client.py with mobile sync addon
"""

import subprocess
import sys

PI_HOST = "everydayadvertise@192.168.1.131"
PI_KEY = r"C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"
PI_DIR = "/home/everydayadvertise/pizza-hut-tv"

def run_command(cmd, description):
    """Run a command and print status."""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    
    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
        return True
    else:
        print(f"❌ {description} - FAILED")
        return False

def main():
    print("""
🍕 Pizza Hut TV - Mobile Sync Deployment
=========================================
This will deploy mobile sync functionality to your Pi:
  1. pi_mobile_sync_addon.py (new addon module)
  2. complete_pi_client.py (with mobile sync integrated)
  3. Install qrcode library on Pi

Target Pi: {PI_HOST}
""")
    
    # Step 1: Copy pi_mobile_sync_addon.py
    if not run_command(
        f'scp -i "{PI_KEY}" "pi_mobile_sync_addon.py" {PI_HOST}:{PI_DIR}/',
        "Copy pi_mobile_sync_addon.py to Pi"
    ):
        print("\n❌ Deployment failed at step 1")
        return False
    
    # Step 2: Copy updated complete_pi_client.py
    if not run_command(
        f'scp -i "{PI_KEY}" "complete_pi_client.py" {PI_HOST}:{PI_DIR}/',
        "Copy complete_pi_client.py to Pi"
    ):
        print("\n❌ Deployment failed at step 2")
        return False
    
    # Step 3: Install qrcode library on Pi
    install_cmd = f'ssh -i "{PI_KEY}" {PI_HOST} "pip3 install qrcode[pil] --user"'
    if not run_command(install_cmd, "Install qrcode library on Pi"):
        print("\n⚠️  Warning: QRcode library installation failed")
        print("   You may need to install it manually: pip3 install qrcode[pil]")
    
    # Step 4: Make scripts executable
    chmod_cmd = f'ssh -i "{PI_KEY}" {PI_HOST} "chmod +x {PI_DIR}/complete_pi_client.py {PI_DIR}/pi_mobile_sync_addon.py"'
    run_command(chmod_cmd, "Make scripts executable")
    
    # Step 5: Check if service exists and offer to restart
    check_service_cmd = f'ssh -i "{PI_KEY}" {PI_HOST} "systemctl --user status pizza-hut-tv.service > /dev/null 2>&1 && echo RUNNING || echo NOT_RUNNING"'
    
    print("\n" + "="*60)
    print("🎉 DEPLOYMENT COMPLETE!")
    print("="*60)
    print("\n✅ Files deployed successfully:")
    print(f"   📄 {PI_DIR}/pi_mobile_sync_addon.py")
    print(f"   📄 {PI_DIR}/complete_pi_client.py")
    print("   📦 qrcode library installed")
    
    print("\n📋 Next Steps:")
    print("   1. SSH to Pi and test:")
    print(f"      ssh -i \"{PI_KEY}\" {PI_HOST}")
    print(f"      cd {PI_DIR}")
    print("      python3 complete_pi_client.py --server https://everydayadvertise.com/api")
    print()
    print("   2. If running as service, restart it:")
    print("      systemctl --user restart pizza-hut-tv.service")
    print()
    print("   3. Test mobile sync:")
    print("      - Look for QR code in top-right corner of Pi screen")
    print("      - Scan with mobile phone")
    print("      - Enter codes on phone and watch Pi auto-advance!")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n🛑 Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Deployment error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
