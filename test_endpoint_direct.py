#!/usr/bin/env python3
"""
Test the register_pi endpoint directly on the server
"""
import requests

print("=" * 60)
print("Testing /api/register_pi endpoint")
print("=" * 60)

# Test 1: External HTTPS (through nginx)
print("\n1. Testing via HTTPS (everydayadvertise.com)...")
try:
    r = requests.post(
        'https://everydayadvertise.com/api/register_pi',
        json={'pi_id': 'test-external', 'pi_ip': '1.2.3.4'},
        timeout=10
    )
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text[:200]}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Direct to Gunicorn on localhost:5002
print("\n2. Testing direct to Gunicorn (localhost:5002)...")
try:
    r = requests.post(
        'http://localhost:5002/api/register_pi',
        json={'pi_id': 'test-direct', 'pi_ip': '5.6.7.8'},
        timeout=10
    )
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text[:200]}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Check if endpoint exists in routes
print("\n3. Listing all /api routes...")
try:
    # This won't work remotely, but shows the intent
    print("   (Cannot list routes remotely)")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("If Status 404: Flask not loading route")
print("If Connection refused: Gunicorn not running")
print("If HTTPS works but not direct: nginx config issue")
print("=" * 60)
