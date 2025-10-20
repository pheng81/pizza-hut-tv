"""
Test Pi Connectivity - Quick Diagnostic Tool

This script helps diagnose connectivity issues with your Raspberry Pi.
"""

import requests
import json

def test_pi_connection():
    """Test connection to Raspberry Pi"""
    pi_id = "raspberrypi-ce39"
    pi_ip = "192.168.1.131"
    pi_port = 8080
    
    print("=" * 60)
    print("🧪 Pi Connectivity Test")
    print("=" * 60)
    print(f"Pi ID: {pi_id}")
    print(f"Pi IP: {pi_ip}")
    print(f"Port: {pi_port}")
    print()
    
    # Test 1: Check if Pi HTTP server is reachable
    print("Test 1: Connecting to Pi HTTP server...")
    pi_url = f"http://{pi_ip}:{pi_port}/status"
    
    try:
        response = requests.get(pi_url, timeout=5)
        
        if response.status_code == 200:
            print("✅ SUCCESS - Pi is reachable!")
            print()
            print("Pi Status Response:")
            print(json.dumps(response.json(), indent=2))
            print()
            print("🎉 Your Pi is online and responding correctly!")
            print()
            print("📍 Network Location:")
            print("   - Pi and this computer are on the SAME network")
            print("   - Local connectivity: ✅ WORKING")
            print()
            return True
        else:
            print(f"⚠️ UNEXPECTED RESPONSE - Status code: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT - Pi did not respond within 5 seconds")
        print()
        print("Possible causes:")
        print("   - Pi is offline or powered off")
        print("   - Pi HTTP server not running (port 8080)")
        print("   - Firewall blocking connection")
        print("   - Wrong IP address")
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION REFUSED - Cannot reach Pi")
        print()
        print("Possible causes:")
        print("   - Pi is on a different network")
        print("   - Pi HTTP server not started")
        print("   - IP address changed")
        return False
        
    except Exception as e:
        print(f"❌ ERROR - {type(e).__name__}: {e}")
        return False

def test_server_to_pi():
    """Test if server can reach Pi through API"""
    print()
    print("=" * 60)
    print("Test 2: Server → Pi Connection (Dashboard API)")
    print("=" * 60)
    
    server_url = "https://everydayadvertise.com"
    pi_id = "raspberrypi-ce39"
    
    print(f"Server: {server_url}")
    print(f"Pi ID: {pi_id}")
    print()
    print("Checking server's ability to reach Pi...")
    
    try:
        response = requests.get(f"{server_url}/api/pi-status/{pi_id}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            
            if status == 'online':
                print("✅ SUCCESS - Server can reach Pi!")
                print()
                print("Response:")
                print(json.dumps(data, indent=2))
                print()
                print("🎉 Dashboard Remote Pi Manager will work!")
                return True
            else:
                print("❌ Pi shows as OFFLINE to server")
                print()
                print("Response:")
                print(json.dumps(data, indent=2))
                print()
                print("📍 Diagnosis:")
                print("   - Pi is registered with server ✅")
                print("   - BUT server cannot reach Pi ❌")
                print()
                print("Reason:")
                print("   - Pi on local network (192.168.1.x)")
                print("   - Server on AWS cloud (different network)")
                print("   - No network path between them")
                print()
                print("Solutions:")
                print("   1. Run dashboard locally (see LOCAL_DASHBOARD_TEST.md)")
                print("   2. Setup port forwarding (see PORT_FORWARDING_GUIDE.md)")
                print("   3. Use Tailscale VPN (see VPN_REVERSE_TUNNEL_GUIDE.md)")
                return False
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR - {type(e).__name__}: {e}")
        return False

def main():
    """Run all connectivity tests"""
    print()
    print("🔍 Pizza Hut TV - Pi Connectivity Diagnostic")
    print()
    
    # Test local connectivity
    local_ok = test_pi_connection()
    
    # Test server connectivity
    server_ok = test_server_to_pi()
    
    # Summary
    print()
    print("=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"Local connectivity (your PC → Pi):  {'✅ PASS' if local_ok else '❌ FAIL'}")
    print(f"Server connectivity (AWS → Pi):     {'✅ PASS' if server_ok else '❌ FAIL'}")
    print()
    
    if local_ok and not server_ok:
        print("🎯 DIAGNOSIS: Network Isolation Issue")
        print()
        print("Your Pi is working correctly, but the AWS server cannot reach it")
        print("because they are on different networks (local vs cloud).")
        print()
        print("RECOMMENDED SOLUTION:")
        print("   1. For testing: Run dashboard locally")
        print("      → See: LOCAL_DASHBOARD_TEST.md")
        print()
        print("   2. For production: Setup Tailscale VPN")
        print("      → See: VPN_REVERSE_TUNNEL_GUIDE.md")
        print()
        print("QUICK FIX (Test Now):")
        print("   cd 'C:\\Users\\toeng\\Pizza Hut TV'")
        print("   python app.py")
        print("   Open: http://localhost:5000")
        print()
    elif local_ok and server_ok:
        print("🎉 EVERYTHING WORKING!")
        print()
        print("Both local and server connectivity are working.")
        print("Dashboard Remote Pi Manager should work correctly!")
        print()
    elif not local_ok:
        print("⚠️ Pi is not reachable from this computer")
        print()
        print("Troubleshooting steps:")
        print("   1. Check if Pi is powered on and connected to network")
        print("   2. Verify Pi IP address: ssh everydayadvertise@raspberrypi.local 'hostname -I'")
        print("   3. Check if Pi service is running:")
        print("      ssh everydayadvertise@raspberrypi.local 'sudo systemctl status pizza-hut-tv'")
        print("   4. Verify Pi HTTP server on port 8080:")
        print("      ssh everydayadvertise@raspberrypi.local 'curl localhost:8080/status'")
        print()

if __name__ == "__main__":
    main()
