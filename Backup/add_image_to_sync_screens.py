"""
Add Item 2 (image) to ALL 4 auto-created sync screens WITHOUT sync_ref.
Implements Option B: Videos stay synced, images display instantly.
"""

import json

# Configuration
IMAGE_FILE = 'users/toengpheng_at_gmail.com/2025-10/your-image.jpg'  # ← CHANGE THIS
IMAGE_DURATION = 10  # seconds

def add_image_to_all_screens():
    with open('store_config.json', 'r') as f:
        cfg = json.load(f)
    
    screens = cfg['screens']['1000']
    screens_updated = 0
    
    for screen_id in ['1000_screen1', '1000_screen2', '1000_screen3', '1000_screen4']:
        if screen_id not in screens:
            print(f"⚠️  {screen_id} not found, skipping")
            continue
        
        playlist = screens[screen_id]['playlist']
        
        # Check if already has 2 items
        if len(playlist) >= 2:
            print(f"ℹ️  {screen_id} already has {len(playlist)} items, skipping")
            continue
        
        # Add image WITHOUT sync_ref (Option B)
        new_item = {
            'file': IMAGE_FILE,
            'duration': IMAGE_DURATION,
            'id': f'item_{len(playlist) + 1}',
            'type': 'image'
            # NO sync_ref = displays instantly after video!
        }
        
        playlist.append(new_item)
        screens_updated += 1
        print(f"✅ {screen_id}: Added image (duration={IMAGE_DURATION}s, NO sync_ref)")
    
    if screens_updated > 0:
        with open('store_config.json', 'w') as f:
            json.dump(cfg, f, indent=2)
        print(f"\n🎉 Successfully updated {screens_updated} screens!")
        print(f"\n📋 Rotation pattern:")
        print(f"   Item 1: Sliced video (30s) WITH sync_ref → Perfect 4-screen sync")
        print(f"   Item 2: Your image ({IMAGE_DURATION}s) WITHOUT sync_ref → Instant display")
        print(f"   🔄 Loops: Video → Image → Video → Image...")
    else:
        print("\n❌ No screens were updated")

if __name__ == '__main__':
    print("=" * 70)
    print("🎬 Option B Implementation: Keep Video Sync, Remove Image Sync")
    print("=" * 70)
    print(f"\nImage file: {IMAGE_FILE}")
    print(f"Duration: {IMAGE_DURATION} seconds")
    print("\n⚠️  Make sure IMAGE_FILE path is correct before running!\n")
    
    add_image_to_all_screens()
