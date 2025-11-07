#!/usr/bin/env python3
"""
Debug script to check screen 2 playlist structure
"""
import requests
import json
import pprint

try:
    # Fetch screen 2 playlist
    url = "https://everydayadvertise.com/playlist/1000/1000_screen2"
    headers = {'X-User-Code': '4682'}
    
    print(f"🔍 Fetching: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        playlist = data.get('playlist', [])
        print(f"📋 Found {len(playlist)} items for screen 2")
        
        if playlist:
            print("\n=== FIRST ITEM STRUCTURE ===")
            pprint.pprint(playlist[0])
            
            # Check for slice-related fields
            item = playlist[0]
            slice_fields = {}
            for key in ['slice_aware', 'is_slice', 'slice_url', 'preferred_url', 'url', 'file', 'slices', 'slice_urls', 'sliceVariants', 'variants']:
                if key in item:
                    slice_fields[key] = item[key]
            
            print(f"\n=== SLICE-RELATED FIELDS ===")
            pprint.pprint(slice_fields)
            
        else:
            print("❌ No playlist items found")
    else:
        print(f"❌ Request failed: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {e}")