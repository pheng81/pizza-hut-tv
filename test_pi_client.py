#!/usr/bin/env python3
"""
Quick test launcher for the Pi client with schedule transition testing
"""
import sys
import os

def test_pi_client():
    """Launch Pi client with debugging for schedule transitions"""
    print("🚀 Testing Pizza Hut TV Pi Client with Schedule Transitions")
    print("=" * 60)
    
    # Set TV code for testing (use kayson2@gmail.com which has active content)
    test_tv_code = "5132"
    
    print(f"📺 Testing with TV Code: {test_tv_code}")
    print(f"👤 User: kayson2@gmail.com")
    print(f"🎬 Expected: Should play repeating video with 10s duration")
    print(f"🔄 Schedule Monitor: Will check every 30s for transitions")
    print()
    
    print("🔍 Debug Features Enabled:")
    print("  - Schedule transition monitoring every 30 seconds")
    print("  - Automatic video transition on schedule changes") 
    print("  - Proper handling of repeating vs non-repeating videos")
    print("  - Emergency exit available (Ctrl+C or emergency scripts)")
    print()
    
    # Pre-set environment for testing
    os.environ['PIZZA_HUT_TV_CODE'] = test_tv_code
    os.environ['PIZZA_HUT_DEBUG'] = '1'
    
    print("⚡ Starting Pi Client...")
    print("   (Watch for DEBUG messages showing schedule transitions)")
    print("   (Press Ctrl+C to exit when done)")
    print()
    
    try:
        # Import and run the Pi client
        import pi_player
        pi_player.main()
    except KeyboardInterrupt:
        print("\n🛑 Testing stopped by user")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pi_client()