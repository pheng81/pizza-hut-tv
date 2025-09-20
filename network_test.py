#!/usr/bin/env python3
"""
Pizza Hut TV - Network Connectivity Test for Pi
Tests network connectivity and server status step by step
"""

import requests
import socket
import time

def test_basic_connectivity():
    print("=== Pizza Hut TV Network Test ===")
    
    # Test 1: Basic internet connectivity
    print("\n1. Testing basic internet connectivity...")
    try:
        response = requests.get("http://google.com", timeout=5)
        print("✓ Internet connection working")
    except Exception as e:
        print(f"✗ Internet connection failed: {e}")
        return False
    
    # Test 2: DNS resolution
    print("\n2. Testing DNS resolution for everydayadvertise.com...")
    try:
        ip = socket.gethostbyname("everydayadvertise.com")
        print(f"✓ DNS resolved: everydayadvertise.com -> {ip}")
    except Exception as e:
        print(f"✗ DNS resolution failed: {e}")
        return False
    
    # Test 3: Port connectivity
    print("\n3. Testing port 5002 connectivity...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("everydayadvertise.com", 5002))
        sock.close()
        
        if result == 0:
            print("✓ Port 5002 is accessible")
        else:
            print(f"✗ Port 5002 connection failed (result: {result})")
            return False
    except Exception as e:
        print(f"✗ Port test failed: {e}")
        return False
    
    # Test 4: HTTP server response
    print("\n4. Testing HTTP server response...")
    server_url = "http://everydayadvertise.com:5002"
    try:
        response = requests.get(f"{server_url}/", timeout=10)
        print(f"✓ Server responding: HTTP {response.status_code}")
    except requests.exceptions.ConnectTimeout:
        print("✗ Server connection timeout - server may be down")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Server connection error: {e}")
        return False
    except Exception as e:
        print(f"✗ Server test failed: {e}")
        return False
    
    # Test 5: API endpoint
    print("\n5. Testing API endpoint with short timeout...")
    try:
        url = f'{server_url}/api/stores_by_code/1769'
        print(f"Testing URL: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API response: {data}")
            
            if data.get('success'):
                username = data.get('user', {}).get('username', '')
                print(f"✓ Authentication successful for user: {username}")
                return True
            else:
                print(f"✗ Authentication failed: {data.get('error', 'Unknown error')}")
                return False
        else:
            print(f"✗ API returned HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ API request timed out after 10 seconds")
        return False
    except Exception as e:
        print(f"✗ API test failed: {e}")
        return False

def main():
    print("Starting comprehensive network test...")
    print("This will test each step with proper timeouts.")
    print("-" * 50)
    
    success = test_basic_connectivity()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ ALL TESTS PASSED - Pizza Hut TV should work!")
    else:
        print("✗ Some tests failed - check network or server status")
        print("\nTroubleshooting:")
        print("1. Check if Pi has internet access: ping google.com")
        print("2. Check if server is running: ping everydayadvertise.com")
        print("3. Verify server is on port 5002")
        print("4. Try accessing http://everydayadvertise.com:5002 in browser")
    
    print("=" * 50)

if __name__ == "__main__":
    main()