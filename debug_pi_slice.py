#!/usr/bin/env python3
"""
Debug script for Pi client slice issue
Run this on the Pi to check what's happening
"""
import sys
import os

# Add the Desktop path to find ea_tv.py
sys.path.append('/home/everydayadvertise/Desktop')

try:
    from ea_tv import EATVApp
    
    print("🔍 DEBUGGING PI CLIENT SLICE ISSUE")
    print("=" * 50)
    
    # Test screen 2 setup
    app = EATVApp()
    app.screen_id = '2'  # This should be how screen 2 is set
    app.store_code = '1000'
    
    print(f"Screen ID set to: {app.screen_id}")
    print(f"Store code: {app.store_code}")
    
    # Test screen number resolution
    screen_num = app._resolve_screen_number()
    print(f"Resolved screen number: {screen_num}")
    
    # Test full screen ID resolution
    full_screen_id = app._resolve_full_screen_id()
    print(f"Full screen ID: {full_screen_id}")
    
    # Test URLs with slice parameters
    test_urls = [
        "https://everydayadvertise.com/slice-video?slice_mode=split-h&slice_count=3&slice_order=1",
        "https://everydayadvertise.com/media/video.mp4",
    ]
    
    for url in test_urls:
        print(f"\n🎬 Testing URL: {url}")
        
        # Test crop filter
        crop_filter = app._get_crop_filter_for_url(url)
        print(f"  Crop filter: {crop_filter}")
        
        # Test webplayer transform  
        transform = app._get_webplayer_transform_for_url(url)
        print(f"  Webplayer transform: {transform}")
        
    print("\n" + "=" * 50)
    print("If crop_filter and transform are None for screen 2,")
    print("that explains why screen 2 shows full video!")
    
except ImportError as e:
    print(f"❌ Could not import ea_tv: {e}")
    print("Make sure this script is run on the Pi with ea_tv.py available")
except Exception as e:
    print(f"❌ Error: {e}")