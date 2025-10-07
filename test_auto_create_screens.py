#!/usr/bin/env python3
"""Test script to manually trigger auto_create_sync_screens endpoint"""
import requests
import json

# Test data from the completed job
test_data = {
    "sliced_files": [
        {
            "screen_number": 1,
            "filename": "users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen1.mp4",
            "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen1.mp4",
            "size": 27550786
        },
        {
            "screen_number": 2,
            "filename": "users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen2.mp4",
            "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen2.mp4",
            "size": 38328218
        },
        {
            "screen_number": 3,
            "filename": "users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen3.mp4",
            "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen3.mp4",
            "size": 32009329
        },
        {
            "screen_number": 4,
            "filename": "users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen4.mp4",
            "url": "https://cdn.everydayadvertise.com/users/test22_at_gmail.com/2025-10/cb535114-0668-47fa-91b1-0e90892e3a4d-screen4.mp4",
            "size": 29628018
        }
    ],
    "layout": "horizontal",
    "store_id": 1000
}

print("Testing auto_create_sync_screens endpoint...")
print(f"Sending data: {json.dumps(test_data, indent=2)}")

try:
    # Note: This will fail with 401 if not logged in, but we can check server logs
    response = requests.post(
        'https://everydayadvertise.com/auto_create_sync_screens',
        json=test_data,
        timeout=30
    )
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        print(f"Response data: {response.json()}")
        print("\n✅ SUCCESS! Screens created!")
    else:
        print(f"Response text: {response.text}")
        if response.status_code == 401:
            print("\n⚠️  401 Unauthorized (expected - need to be logged in)")
            print("But we can check server logs to see if endpoint was hit!")
        else:
            print(f"\n❌ Failed with status {response.status_code}")
            
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("Check server logs for '[auto_create_sync_screens]' entries")
