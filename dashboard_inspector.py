#!/usr/bin/env python3
"""
Dashboard Content Inspector
Check what content exists and why it's not being scheduled
"""
import requests
import json
from datetime import datetime, timedelta

def inspect_dashboard():
    print("📊 Dashboard Content Inspector")
    print("=" * 50)
    
    base_url = "https://everydayadvertise.com"
    headers = {'X-User-Code': '1234'}
    store_id = "toengpheng_at_gmail.com"
    
    # Try different API endpoints to find content
    endpoints = [
        f"/api/content/{store_id}",
        f"/api/files/{store_id}",
        f"/content/{store_id}",
        f"/files/{store_id}",
        f"/api/playlist/{store_id}",
        f"/dashboard/api/content/{store_id}",
        f"/admin/content/{store_id}"
    ]
    
    print(f"🔍 Checking content for: {store_id}")
    
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\n🌐 Testing: {endpoint}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        if 'items' in data:
                            items = data['items']
                            print(f"   ✅ Found {len(items)} items")
                            for item in items[:3]:  # Show first 3
                                print(f"      📁 {item.get('file', 'unknown')}")
                                if 'sync_ref' in item:
                                    print(f"         🔄 SYNC VIDEO!")
                        elif len(data) > 0:
                            print(f"   ✅ Data keys: {list(data.keys())}")
                    elif isinstance(data, list):
                        print(f"   ✅ Found {len(data)} items")
                        for item in data[:3]:
                            if isinstance(item, dict):
                                print(f"      📁 {item.get('file', item.get('name', 'unknown'))}")
                            else:
                                print(f"      📄 {item}")
                    else:
                        print(f"   📄 Response: {str(data)[:100]}")
                except json.JSONDecodeError:
                    text = response.text[:200]
                    print(f"   📄 Text response: {text}")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    # Check schedule/timing endpoints
    print(f"\n⏰ Checking Schedule Information:")
    print("-" * 40)
    
    schedule_endpoints = [
        f"/api/schedule/{store_id}",
        f"/schedule/{store_id}",
        f"/api/active/{store_id}",
        f"/active/{store_id}"
    ]
    
    for endpoint in schedule_endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\n📅 Testing: {endpoint}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   ✅ Schedule data found")
                    if isinstance(data, dict) and 'active' in data:
                        print(f"      Active items: {len(data.get('active', []))}")
                    elif isinstance(data, list):
                        print(f"      Schedule items: {len(data)}")
                except:
                    print(f"   📄 Text: {response.text[:100]}")
            else:
                print(f"   ❌ {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    inspect_dashboard()