import requests
import json

# Check Pi1 and Pi2 device registrations
server = "https://everydayadvertise.com"

# Common device IDs to check
devices = [
    "raspberrypi",
    "raspberrypi-new-3ef9",
]

print("=== Checking Pi Registrations ===\n")

# Try to fetch from auto-registration endpoint
for device_id in devices:
    try:
        # This would require checking the server's registration system
        print(f"Device: {device_id}")
        print(f"  Need to check dashboard for registration details")
    except Exception as e:
        print(f"Error checking {device_id}: {e}")

print("\n=== Checking Store Playlists ===\n")

# Check common test stores
stores_to_check = [
    ("1000", "1000_screen1"),
    ("1000", "1000_screen2"),
    ("test9", "test9_screen1"),
    ("test9", "test9_screen2"),
]

for store_id, screen_id in stores_to_check:
    try:
        url = f"{server}/api/playlist/{store_id}/{screen_id}"
        print(f"\nChecking {store_id}/{screen_id}:")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            playlist = response.json()
            items = playlist.get('items', [])
            print(f"  ✅ {len(items)} items in playlist")
            
            for i, item in enumerate(items, 1):
                item_type = item.get('type', 'unknown')
                duration = item.get('duration', 'N/A')
                url_preview = item.get('url', '')[:60] + '...' if item.get('url') else 'N/A'
                
                print(f"  {i}. Type: {item_type}, Duration: {duration}s")
                
                # Check schedule
                schedule = item.get('schedule', {})
                if schedule and any(schedule.values()):
                    print(f"     Schedule: {schedule.get('start_time', 'N/A')} - {schedule.get('end_time', 'N/A')}")
                else:
                    print(f"     Schedule: None (plays 24/7)")
        else:
            print(f"  ❌ Status: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n=== Summary ===")
print("To determine which Pi plays which playlist:")
print("1. Check your dashboard for device registrations")
print("2. Look for 'raspberrypi' (Pi1) and 'raspberrypi-new-3ef9' (Pi2)")
print("3. See which store/screen each is assigned to")
