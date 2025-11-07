#!/usr/bin/env python3
"""
Test script to manually trigger auto_create_sync_screens from the last completed job.
This simulates what the "Auto-Sync Screens" button does.
"""

import requests
import json

# Server details
SERVER = "https://pizzahut.everydayadvertise.com"
STORE_ID = 1000

# You'll need to get a valid session cookie from your browser
# Open browser DevTools -> Application -> Cookies -> copy the 'session' cookie value
SESSION_COOKIE = input("Paste your session cookie value: ").strip()

def test_auto_create():
    # Create session with cookie
    session = requests.Session()
    session.cookies.set('session', SESSION_COOKIE, domain='pizzahut.everydayadvertise.com')
    
    print("\n🔍 Step 1: Fetching list of completed slice jobs...")
    
    # Get list of completed jobs
    response = session.get(f"{SERVER}/api/list_slice_jobs")
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Failed to get jobs: {response.text}")
        return
    
    data = response.json()
    
    if not data.get('success'):
        print(f"❌ API error: {data}")
        return
    
    jobs = data.get('jobs', [])
    
    if not jobs:
        print("❌ No completed jobs found!")
        return
    
    print(f"✅ Found {len(jobs)} completed job(s)")
    
    # Get the most recent job
    last_job = jobs[0]
    print(f"\n📋 Last completed job:")
    print(f"   Job ID: {last_job['job_id']}")
    print(f"   Screens: {last_job['screen_count']}")
    print(f"   Layout: {last_job['layout']}")
    print(f"   Progress: {last_job['progress']}%")
    print(f"   Files: {len(last_job['result'])}")
    
    # Show the sliced files
    print(f"\n📹 Sliced files:")
    for i, file_info in enumerate(last_job['result'], 1):
        print(f"   {i}. Screen {file_info['screen_number']}: {file_info['filename']}")
        print(f"      Size: {file_info['size'] / 1024 / 1024:.2f} MB")
        print(f"      URL: {file_info['url']}")
    
    # Ask for confirmation
    confirm = input(f"\n❓ Create {last_job['screen_count']} synchronized screens? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("❌ Cancelled by user")
        return
    
    print(f"\n🚀 Step 2: Calling /auto_create_sync_screens...")
    
    # Call auto_create_sync_screens
    payload = {
        'sliced_files': last_job['result'],
        'layout': last_job['layout'],
        'store_id': STORE_ID
    }
    
    response = session.post(
        f"{SERVER}/auto_create_sync_screens",
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Failed to create screens: {response.text}")
        return
    
    result = response.json()
    
    print(f"\n📊 Response:")
    print(json.dumps(result, indent=2))
    
    if result.get('success'):
        print(f"\n✅ SUCCESS!")
        print(f"   Created {result['count']} screens:")
        for screen_id in result['screens']:
            print(f"      - {screen_id}")
        print(f"\n🎉 All done! Refresh your dashboard to see the new screens.")
    else:
        print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 Auto-Create Sync Screens Test Script")
    print("=" * 60)
    
    try:
        test_auto_create()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
