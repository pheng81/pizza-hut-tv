#!/usr/bin/env python3
"""
Simple EA TV Pi Client Test Script
Tests basic functionality without complex imports
"""

import sys
import os

print("🔍 EA TV Pi Client Diagnostics")
print("=" * 40)

# Test 1: Python version
print(f"✅ Python version: {sys.version}")

# Test 2: Working directory
print(f"✅ Current directory: {os.getcwd()}")

# Test 3: Required files
required_files = ['phtv_pi_client.py']
for file in required_files:
    if os.path.exists(file):
        print(f"✅ Found: {file}")
    else:
        print(f"❌ Missing: {file}")

# Test 4: Basic imports
try:
    import requests
    print("✅ requests module available")
except ImportError:
    print("❌ requests module missing - install with: pip3 install requests")

try:
    import tkinter
    print("✅ tkinter module available")
except ImportError:
    print("❌ tkinter module missing - install with: sudo apt-get install python3-tk")

try:
    import vlc
    print("✅ vlc module available")
except ImportError:
    print("❌ vlc module missing - install with: pip3 install python-vlc")

# Test 5: Network connectivity
try:
    import urllib.request
    response = urllib.request.urlopen('http://54.252.90.27:8082/api/sync-time', timeout=5)
    print("✅ Server connectivity OK")
except Exception as e:
    print(f"❌ Server connectivity failed: {e}")

print("\n🎯 Quick Fix Commands:")
print("sudo apt-get update")
print("sudo apt-get install python3-tk python3-pip vlc")
print("pip3 install requests python-vlc")

print("\n📺 To start EA TV after fixing:")
print("python3 phtv_pi_client.py")