#!/usr/bin/env python3
"""Minimal test that mimics Pi client initialization"""
import sys
sys.path.insert(0, '/home/everydayadvertise')

print("=" * 60)
print("TESTING MOBILE SYNC ADDON INTEGRATION")
print("=" * 60)

# Test the import exactly as complete_pi_client.py does
try:
    from pi_mobile_sync_addon import MobileSyncAddon
    MOBILE_SYNC_AVAILABLE = True
    print("✅ MOBILE SYNC ADDON IMPORTED SUCCESSFULLY")
except ImportError as e:
    MOBILE_SYNC_AVAILABLE = False
    print(f"❌ MOBILE SYNC ADDON IMPORT FAILED: {e}")
except Exception as e:
    MOBILE_SYNC_AVAILABLE = False
    print(f"❌ MOBILE SYNC ADDON UNEXPECTED ERROR: {e}")

print(f"\nMOBILE_SYNC_AVAILABLE = {MOBILE_SYNC_AVAILABLE}")

if MOBILE_SYNC_AVAILABLE:
    print("\nTesting initialization...")
    
    # Create a mock pi_client object
    class MockPiClient:
        def __init__(self):
            self.server_url = "https://everydayadvertise.com/api"
            self.sio = None
            
    pi_client = MockPiClient()
    
    try:
        mobile_sync = MobileSyncAddon(pi_client)
        print(f"✅ MobileSyncAddon instantiated: {mobile_sync}")
        print(f"   Session ID: {mobile_sync.session_id}")
    except Exception as e:
        print(f"❌ Failed to instantiate: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n❌ Cannot test - import failed")

print("\n" + "=" * 60)
