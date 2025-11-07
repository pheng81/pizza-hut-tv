#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/everydayadvertise')

print("Testing mobile sync addon import...")
try:
    from pi_mobile_sync_addon import MobileSyncAddon
    print("✅ SUCCESS: MobileSyncAddon imported!")
    print(f"   Class: {MobileSyncAddon}")
    print(f"   Methods: {[m for m in dir(MobileSyncAddon) if not m.startswith('_')]}")
except Exception as e:
    print(f"❌ FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
