#!/usr/bin/env python3
"""
Debug version of slice kiosk - opens in window mode to see what's happening
"""
import subprocess
import sys

# Test the webplayer URL in windowed mode
url = "https://everydayadvertise.com/webplayer/play?store=1000&screen=2&code=4682"

print(f"🔍 Testing webplayer URL: {url}")
print("Opening in windowed mode for debugging...")

# Simple windowed browser for testing
cmd = [
    "chromium-browser",
    "--disable-web-security", 
    "--allow-running-insecure-content",
    "--autoplay-policy=no-user-gesture-required",
    "--incognito",
    url
]

try:
    subprocess.run(cmd)
except KeyboardInterrupt:
    print("Interrupted by user")
except Exception as e:
    print(f"Error: {e}")