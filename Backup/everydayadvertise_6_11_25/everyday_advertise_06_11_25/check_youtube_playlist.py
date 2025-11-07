import requests

# Fetch the playlist from the server API (same as Pi client does)
url = "https://everydayadvertise.com/playlist/1931/1931_screen3"
params = {'skip_schedule_filter': '1', 'user_code': '8329'}

print(f"Fetching: {url}")
print(f"Params: {params}")

response = requests.get(url, params=params)
print(f"Status: {response.status_code}")

data = response.json()
print(f"\nResponse keys: {data.keys()}")

# Try both 'items' and 'playlist' keys
items = data.get('items') or data.get('playlist', [])
print(f"Number of items: {len(items)}")

print("\n=== PLAYLIST ITEMS ===")
for item in items:
    file_val = item.get('file', '')
    url_val = item.get('url', '')
    print(f"\nID: {item.get('id')}")
    print(f"  File: {file_val}")
    print(f"  URL: {url_val}")
    print(f"  Duration: {item.get('duration')}")
    if 'youtube:' in str(file_val) or 'youtube:' in str(url_val):
        print(f"  ▶️ YOUTUBE VIDEO DETECTED!")

