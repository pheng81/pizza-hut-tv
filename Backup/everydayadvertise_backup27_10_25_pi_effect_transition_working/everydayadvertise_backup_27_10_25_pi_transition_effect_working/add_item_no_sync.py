"""
Helper script to add Item 2 (image) to auto-created sync screens WITHOUT sync_ref.

This implements Option B: Keep sync_ref on Item 1 (video), remove from Item 2 (image)
"""

import json
import sys

def add_item_without_sync(screen_id, media_file, duration=10):
    """Add a new playlist item without sync_ref to a screen"""
    
    with open('store_config.json', 'r') as f:
        cfg = json.load(f)
    
    # Navigate to the screen
    if '1000' not in cfg['screens']:
        print("❌ Store 1000 not found")
        return False
    
    if screen_id not in cfg['screens']['1000']:
        print(f"❌ Screen {screen_id} not found")
        return False
    
    # Get current playlist
    playlist = cfg['screens']['1000'][screen_id]['playlist']
    
    # Create new item WITHOUT sync_ref (Option B)
    new_item = {
        'file': media_file,
        'duration': duration,
        'id': f'item_{len(playlist) + 1}',  # Simple incrementing ID
        'type': 'image' if media_file.endswith(('.jpg', '.jpeg', '.png', '.gif')) else 'video'
    }
    
    # NO sync_ref here - this is the key for Option B!
    
    # Add to playlist
    playlist.append(new_item)
    
    # Save
    with open('store_config.json', 'w') as f:
        json.dump(cfg, f, indent=2)
    
    print(f"✅ Added Item {len(playlist)} to {screen_id}")
    print(f"   File: {media_file}")
    print(f"   Duration: {duration}s")
    print(f"   Has sync_ref: NO (Option B)")
    print(f"\n   Item 1: Video WITH sync_ref → All screens sync perfectly")
    print(f"   Item 2: Image WITHOUT sync_ref → Displays instantly, no sync delay")
    
    return True

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python add_item_no_sync.py <screen_id> <media_file> <duration>")
        print("Example: python add_item_no_sync.py 1000_screen1 'users/toengpheng_at_gmail.com/2025-10/my-image.jpg' 10")
        sys.exit(1)
    
    screen_id = sys.argv[1]
    media_file = sys.argv[2]
    duration = int(sys.argv[3])
    
    add_item_without_sync(screen_id, media_file, duration)
