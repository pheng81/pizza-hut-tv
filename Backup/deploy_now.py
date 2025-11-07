"""
ONE-COMMAND DEPLOYMENT
Run this from your PC - no RealVNC needed!
"""

import subprocess
import sys

print("="*70)
print("   🚀 ONE-COMMAND DEPLOYMENT")
print("="*70)
print("\nRunning uploader script on Pi via SSH...")
print("This will upload files from Pi to server via HTTPS\n")

# Run the Python script on the Pi via SSH
result = subprocess.run(
    ['ssh', 'everydayadvertise@raspberrypi', 'python3 /tmp/pi_uploader.py'],
    capture_output=False
)

if result.returncode == 0:
    print("\n" + "="*70)
    print("   ✅ DEPLOYMENT COMPLETE!")
    print("="*70)
    print("\nWait 10 seconds, then test:")
    print("1. Open: https://everydayadvertise.com/dashboard")
    print("2. Press: Ctrl+Shift+R")
    print("3. Open: Remote Pi Manager")
    print("4. Connect to Pi")
    print("5. See: 📺 Screen Preview!")
    print("6. Click: ▶ Start")
    print("7. Screenshots appear! 🎉")
else:
    print("\n❌ Deployment failed - check errors above")
    sys.exit(1)
