#!/usr/bin/env python3
"""
Fix test store "1111" name on the server.
Updates the store name from "Canley Vale" to "Test Store 1111"
"""
import requests
import json

# Server configuration
SERVER_URL = "http://54.252.90.27:5000"
USERNAME = "test9@gmail.com"
PASSWORD = input("Enter password for test9@gmail.com: ")

# Login
session = requests.Session()
print("Logging in...")
login_response = session.post(f"{SERVER_URL}/login", data={
    "username": USERNAME,
    "password": PASSWORD
}, allow_redirects=True)

if login_response.status_code != 200 or "Invalid" in login_response.text:
    print(f"❌ Login failed: {login_response.status_code}")
    print(login_response.text[:500])
    exit(1)

print("✅ Logged in successfully")

# Get current stores to see what we have
print("\nFetching current stores...")
stores_response = session.get(f"{SERVER_URL}/stores")
if stores_response.status_code == 200:
    stores_data = stores_response.json()
    print(f"\nCurrent stores:")
    for store in stores_data.get('stores', []):
        print(f"  - ID: {store.get('id')}, Name: {store.get('name')}")
else:
    print(f"❌ Failed to fetch stores: {stores_response.status_code}")

# Update store name using the add_store endpoint (which also updates existing stores)
print("\n🔧 Updating store '1111' name to 'Test Store 1111'...")
update_response = session.post(f"{SERVER_URL}/add_store", 
    data={
        "store_id": "1111",
        "store_name": "Test Store 1111"
    },
    allow_redirects=True
)

if update_response.status_code == 200:
    result = update_response.json()
    if result.get('success'):
        print(f"✅ {result.get('message')}")
    else:
        print(f"❌ Update failed: {result.get('message')}")
else:
    print(f"❌ Update request failed: {update_response.status_code}")
    print(update_response.text[:500])

# Verify the change
print("\n📋 Verifying updated stores...")
stores_response = session.get(f"{SERVER_URL}/stores")
if stores_response.status_code == 200:
    stores_data = stores_response.json()
    print(f"\nUpdated stores:")
    for store in stores_data.get('stores', []):
        store_id = store.get('id')
        store_name = store.get('name')
        if store_id == "1111":
            print(f"  ✅ ID: {store_id}, Name: {store_name}")
        else:
            print(f"  - ID: {store_id}, Name: {store_name}")
else:
    print(f"❌ Failed to verify: {stores_response.status_code}")

print("\n✅ Done! The dashboard should now show 'Test Store 1111' for both Pis.")
