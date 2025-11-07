#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Enhanced Pi Test Suite
========================================
Comprehensive test suite for Pi client functionality
"""

import sys
import os
import time
import subprocess
import socket
import json
import requests
import traceback
from pathlib import Path

def test_basic_connectivity():
    """Test basic server connectivity."""
    print("🌐 Testing Server Connection")
    print("-" * 25)
    
    try:
        response = requests.get("https://everydayadvertise.com/api/health", timeout=10)
        if response.status_code == 200:
            print("✅ Server reachable")
            return True
        else:
            print(f"❌ Server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_playlist_api():
    """Test playlist API."""
    print("\n📋 Testing Playlist API")
    print("-" * 20)
    
    store_id = "PHTV001"
    screen_id = "tv1"
    
    try:
        url = f"https://everydayadvertise.com/api/playlist/{store_id}/{screen_id}"
        headers = {'User-Agent': 'phtv-pi-test/1.0'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                playlist_count = len(data.get('playlist', []))
                print(f"✅ Playlist API working ({playlist_count} items)")
                return True
            else:
                print(f"❌ API error: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Playlist test failed: {e}")
        return False

def test_python_modules():
    """Test required Python modules."""
    print("\n🐍 Testing Python Modules")
    print("-" * 22)
    
    modules = [
        ('requests', 'HTTP client'),
        ('json', 'JSON parsing'),
        ('threading', 'Multi-threading'),
        ('subprocess', 'Process control'),
        ('socket', 'Network operations'),
        ('time', 'Time functions'),
        ('os', 'Operating system'),
        ('sys', 'System functions')
    ]
    
    all_good = True
    
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name:<12} - {description}")
        except ImportError:
            print(f"❌ {module_name:<12} - Missing!")
            all_good = False
    
    return all_good

def test_optional_modules():
    """Test optional modules for enhanced functionality."""
    print("\n🎮 Testing Optional Modules (for video playback)")
    print("-" * 45)
    
    optional_modules = [
        ('pygame', 'Graphics and basic video'),
        ('vlc', 'VLC media player'),
        ('psutil', 'System monitoring')
    ]
    
    available_count = 0
    
    for module_name, description in optional_modules:
        try:
            if module_name == 'vlc':
                import vlc
                # Test VLC instance creation
                instance = vlc.Instance(['--quiet'])
                player = instance.media_player_new()
                print(f"✅ {module_name:<12} - {description}")
            else:
                __import__(module_name)
                print(f"✅ {module_name:<12} - {description}")
            available_count += 1
        except ImportError:
            print(f"⚠️ {module_name:<12} - Not installed (optional)")
        except Exception as e:
            print(f"⚠️ {module_name:<12} - Error: {str(e)[:30]}")
    
    if available_count > 0:
        print(f"\n💡 {available_count} optional modules available for enhanced features")
    else:
        print(f"\n⚠️ No optional modules - basic functionality only")
    
    return True

def test_system_tools():
    """Test system tools availability."""
    print("\n🔧 Testing System Tools")
    print("-" * 18)
    
    tools = [
        ('omxplayer', 'Hardware video player'),
        ('vlc', 'VLC media player'),
        ('python3', 'Python interpreter'),
        ('systemctl', 'Service manager')
    ]
    
    tools_available = 0
    
    for tool, description in tools:
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ {tool:<12} - {description}")
                tools_available += 1
            else:
                print(f"❌ {tool:<12} - Not working")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print(f"⚠️ {tool:<12} - Not installed")
    
    return tools_available > 0

def test_network_advanced():
    """Advanced network tests."""
    print("\n🌐 Advanced Network Tests")
    print("-" * 23)
    
    tests_passed = 0
    
    # DNS resolution
    try:
        socket.gethostbyname('google.com')
        print("✅ DNS resolution working")
        tests_passed += 1
    except socket.gaierror:
        print("❌ DNS resolution failed")
    
    # Internet connectivity
    try:
        sock = socket.create_connection(("8.8.8.8", 53), timeout=5)
        sock.close()
        print("✅ Internet connectivity working")
        tests_passed += 1
    except (socket.timeout, socket.error):
        print("❌ Internet connectivity failed")
    
    # HTTPS support
    try:
        response = requests.get("https://httpbin.org/get", timeout=5)
        if response.status_code == 200:
            print("✅ HTTPS support working")
            tests_passed += 1
        else:
            print("❌ HTTPS support issues")
    except Exception:
        print("❌ HTTPS support failed")
    
    return tests_passed >= 2

def test_pi_specific():
    """Test Raspberry Pi specific features."""
    print("\n🍓 Raspberry Pi Specific Tests")
    print("-" * 28)
    
    # Check if running on Pi
    is_pi = False
    try:
        with open('/proc/cpuinfo', 'r') as f:
            if 'Raspberry Pi' in f.read():
                print("✅ Running on Raspberry Pi")
                is_pi = True
            else:
                print("⚠️ Not running on Raspberry Pi")
    except FileNotFoundError:
        print("⚠️ Not running on Linux (probably Windows/Mac)")
    
    if is_pi:
        # GPU memory check
        try:
            result = subprocess.run(['vcgencmd', 'get_mem', 'gpu'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                gpu_mem = result.stdout.strip().split('=')[1]
                gpu_mb = int(gpu_mem.replace('M', ''))
                if gpu_mb >= 128:
                    print(f"✅ GPU memory: {gpu_mem} (good)")
                else:
                    print(f"⚠️ GPU memory: {gpu_mem} (recommend 128M+)")
        except:
            print("⚠️ Cannot check GPU memory")
        
        # Temperature check
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                temp = result.stdout.strip().split('=')[1]
                print(f"✅ Temperature: {temp}")
        except:
            print("⚠️ Cannot check temperature")
    
    return True

def run_comprehensive_test():
    """Run all tests and provide summary."""
    print("🍕 Pizza Hut TV - Pi Client Test Suite")
    print("=" * 38)
    
    test_results = []
    
    # Run tests
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("Playlist API", test_playlist_api),
        ("Python Modules", test_python_modules),
        ("Optional Modules", test_optional_modules),
        ("System Tools", test_system_tools),
        ("Network Advanced", test_network_advanced),
        ("Pi Specific", test_pi_specific)
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            test_results.append(result)
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {e}")
            test_results.append(False)
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n📊 Test Summary")
    print("=" * 14)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total-passed}/{total}")
    print(f"📈 Success Rate: {(passed/total*100):.1f}%")
    
    # Recommendations
    print(f"\n💡 Recommendations")
    print("=" * 17)
    
    if passed == total:
        print("🎉 All tests passed! Your system is ready for Pizza Hut TV.")
        print("\nNext steps:")
        print("1. Deploy the enhanced Pi client")
        print("2. Configure store/screen IDs")
        print("3. Start the service")
    elif passed >= total * 0.7:  # 70% pass rate
        print("✅ System is mostly ready with minor issues.")
        print("\nThe Pi client should work, but some features may be limited.")
        print("Consider installing optional modules for better performance.")
    else:
        print("⚠️ System has significant issues that should be resolved.")
        print("\nCritical issues found. Please address before deployment:")
        print("1. Check network connectivity")
        print("2. Install missing Python modules")
        print("3. Verify server accessibility")
    
    return passed >= total * 0.7

def main():
    """Main entry point."""
    try:
        success = run_comprehensive_test()
        
        print(f"\n" + "=" * 50)
        if success:
            print("🚀 System is ready for Pizza Hut TV!")
            return 0
        else:
            print("❌ System needs attention before deployment.")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n🛑 Test interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())