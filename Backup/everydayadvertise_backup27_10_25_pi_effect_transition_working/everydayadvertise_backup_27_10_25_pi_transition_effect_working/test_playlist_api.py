import requests
import json

# Test what the webplayer actually receives
url = 'https://api.everydayadvertise.com/playlist/1000/1000_screen1'
response = requests.get(url)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"\n✅ WEBPLAYER RECEIVES {len(data)} ITEMS:\n")
    print("=" * 70)
    
    for i, item in enumerate(data, 1):
        print(f"\nItem {i}:")
        print(f"  File: {item.get('file', 'N/A')[:60]}...")
        print(f"  Duration: {item.get('duration', 'N/A')}")
        print(f"  Has sync_ref: {'sync_ref' in item}")
        if 'sync_ref' in item:
            print(f"  Sync group: {item['sync_ref'].get('group', 'N/A')}")
else:
    print(f"❌ Error: {response.text}")
