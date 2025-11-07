#!/usr/bin/env python3
"""Test Pi registration endpoint"""
import requests
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# Test registration
pi_id = 'raspberrypi-ce39'
pi_ip = get_local_ip()

print(f"Testing Pi registration...")
print(f"Pi ID: {pi_id}")
print(f"Pi IP: {pi_ip}")

try:
    response = requests.post(
        'https://everydayadvertise.com/api/register_pi',
        json={'pi_id': pi_id, 'pi_ip': pi_ip},
        timeout=10
    )
    print(f"\nResponse: {response.status_code}")
    print(f"Body: {response.json()}")
    
    if response.status_code == 200:
        print("\n✅ Registration successful!")
    else:
        print(f"\n❌ Registration failed: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
