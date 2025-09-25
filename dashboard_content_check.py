#!/usr/bin/env python3
"""
Direct Dashboard and Content Analysis
Check the actual dashboard page and uploaded files
"""
import requests

def check_dashboard_content():
    print("📊 Direct Dashboard Content Analysis")
    print("=" * 50)
    
    base_url = "https://everydayadvertise.com"
    store_id = "toengpheng_at_gmail.com"
    
    # Test the dashboard page directly
    print(f"🔍 Checking dashboard for: {store_id}")
    
    try:
        # Try to get the main dashboard page
        dashboard_url = f"{base_url}/dashboard"
        response = requests.get(dashboard_url, timeout=10)
        
        print(f"📱 Dashboard Status: {response.status_code}")
        
        if response.status_code == 200:
            # Look for forms or data that might show content
            content = response.text
            
            # Check if there are any upload forms or file references
            if "upload" in content.lower():
                print("✅ Upload functionality detected")
            if "sync" in content.lower():
                print("✅ Sync functionality detected")
            if "video" in content.lower():
                print("✅ Video handling detected")
            if store_id in content:
                print(f"✅ Store ID {store_id} found in dashboard")
            
            # Look for JavaScript that might handle content
            import re
            js_files = re.findall(r'src=["\']([^"\']*\.js[^"\']*)["\']', content)
            print(f"📜 Found {len(js_files)} JavaScript files")
            
            # Look for any content listings
            if "playlist" in content.lower():
                print("✅ Playlist functionality detected")
                
        else:
            print(f"❌ Dashboard not accessible: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Dashboard check error: {e}")
    
    # Check the library endpoint that was mentioned in the code
    print(f"\n📚 Checking Media Library:")
    print("-" * 30)
    
    try:
        library_url = f"{base_url}/library"
        response = requests.get(library_url, timeout=10)
        
        print(f"📚 Library Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                files = data.get('files', [])
                print(f"📁 Found {len(files)} files in library")
                
                for file_info in files[:5]:  # Show first 5 files
                    name = file_info.get('name', 'unknown')
                    media_type = file_info.get('media_type', 'unknown')
                    print(f"   📄 {name} ({media_type})")
                    
            except:
                print("❌ Library response not JSON")
        else:
            print(f"❌ Library error: {response.text[:100]}")
            
    except Exception as e:
        print(f"❌ Library check error: {e}")
    
    # Try to check if there's a configuration file or content store
    print(f"\n⚙️  Configuration Check:")
    print("-" * 30)
    
    endpoints = [
        "/config",
        "/api/config", 
        "/store/config",
        f"/api/store/{store_id}",
        f"/store/{store_id}/config"
    ]
    
    for endpoint in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=5)
            print(f"⚙️  {endpoint}: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and len(data) > 0:
                        print(f"   ✅ Config data found: {list(data.keys())[:5]}")
                except:
                    print(f"   📄 Text response: {response.text[:100]}")
        except:
            pass

if __name__ == "__main__":
    check_dashboard_content()