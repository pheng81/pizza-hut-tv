#!/usr/bin/env python3
"""
Test script to debug Pi client slice handling
"""

# Simulate the Pi client slice detection logic
def _resolve_screen_number(screen_id):
    """Return the numeric screen index (1-based), tolerant of full IDs like 1000_screen2."""
    import re
    raw = str(screen_id or '').strip()
    if not raw:
        return 1
    match = re.search(r'(?:_screen)?(\d+)$', raw)
    if match:
        return int(match.group(1))
    if raw.isdigit():
        return int(raw)
    return 1

def _get_crop_filter_for_url(screen_id, url):
    """Extract crop parameters from slice URL or screen ID for horizontal split."""
    try:
        screen_id_str = str(screen_id or '1')
        
        # Parse slice parameters from URL if present
        if 'slice_mode=split-h' in url and 'slice_count=3' in url:
            # Horizontal 3-way split for screens 1, 2, 3
            if 'slice_order=0' in url or screen_id_str == '1':
                # Screen 1 (left third): crop right 2/3
                return {"top": 0, "bottom": 0, "left": 0, "right": 2}
            elif 'slice_order=1' in url or screen_id_str == '2':
                # Screen 2 (middle third): crop left 1/3 and right 1/3
                return {"top": 0, "bottom": 0, "left": 1, "right": 1}
            elif 'slice_order=2' in url or screen_id_str == '3':
                # Screen 3 (right third): crop left 2/3
                return {"top": 0, "bottom": 0, "left": 2, "right": 0}
        
        # For screens 2 and 3 without explicit slice URL, apply default 3-way horizontal crop
        elif screen_id_str == '2':
            return {"top": 0, "bottom": 0, "left": 1, "right": 1}
        elif screen_id_str == '3':
            return {"top": 0, "bottom": 0, "left": 2, "right": 0}
        
    except Exception as e:
        print(f"⚠️ Error parsing crop filter: {e}")
    
    return None

# Test cases
test_cases = [
    # Test screen IDs
    ("1000_screen1", "https://example.com/video.mp4"),
    ("1000_screen2", "https://example.com/video.mp4"),  
    ("1000_screen3", "https://example.com/video.mp4"),
    
    # Test with slice URLs
    ("1000_screen1", "https://example.com/slice-video?slice_mode=split-h&slice_count=3&slice_order=0"),
    ("1000_screen2", "https://example.com/slice-video?slice_mode=split-h&slice_count=3&slice_order=1"),
    ("1000_screen3", "https://example.com/slice-video?slice_mode=split-h&slice_count=3&slice_order=2"),
]

print("Pi Client Slice Logic Test")
print("=" * 50)

for screen_id, url in test_cases:
    screen_num = _resolve_screen_number(screen_id)
    crop_filter = _get_crop_filter_for_url(screen_num, url)
    
    print(f"Screen ID: {screen_id}")
    print(f"  Resolved screen number: {screen_num}")
    print(f"  URL: {url}")
    print(f"  Crop filter: {crop_filter}")
    print()