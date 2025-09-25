#!/usr/bin/env python3
"""
Video Diagnostic Tool for Pizza Hut TV System
Helps identify issues with video files that cause delays or hanging
"""

import requests
import subprocess
import json
import time
from urllib.parse import urlparse

def test_video_url(url):
    """Test if a video URL is accessible and get basic info"""
    print(f"\n🔍 Testing video URL: {url}")
    
    try:
        # Test HTTP response
        start_time = time.time()
        response = requests.head(url, timeout=10)
        response_time = time.time() - start_time
        
        print(f"✅ HTTP Status: {response.status_code}")
        print(f"⏱️  Response Time: {response_time:.2f}s")
        
        # Get content info
        if 'content-length' in response.headers:
            size_mb = int(response.headers['content-length']) / (1024 * 1024)
            print(f"📁 File Size: {size_mb:.2f} MB")
        
        if 'content-type' in response.headers:
            print(f"📄 Content Type: {response.headers['content-type']}")
            
        # Check if it's a video
        if 'video' not in response.headers.get('content-type', ''):
            print("⚠️  WARNING: Not detected as video content!")
            
        return True
        
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: URL took too long to respond")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {e}")
        return False

def analyze_slice_video(url):
    """Analyze slice video parameters"""
    print(f"\n🔪 Analyzing slice video parameters...")
    
    parsed = urlparse(url)
    if 'slice_mode' in url:
        print("✅ Slice video detected")
        
        # Extract slice parameters
        params = dict([param.split('=') for param in parsed.query.split('&')])
        
        slice_mode = params.get('slice_mode', 'unknown')
        slice_count = params.get('slice_count', 'unknown') 
        slice_order = params.get('slice_order', 'unknown')
        
        print(f"📊 Slice Mode: {slice_mode}")
        print(f"🔢 Slice Count: {slice_count}")
        print(f"📍 Slice Order: {slice_order}")
        
        # Check for potential issues
        if slice_mode == 'split-h' and int(slice_count) > 4:
            print("⚠️  WARNING: High horizontal slice count may cause performance issues")
            
        if slice_mode == 'split-v' and int(slice_count) > 2:
            print("⚠️  WARNING: High vertical slice count may cause performance issues")
            
    else:
        print("ℹ️  Regular video (not sliced)")

def test_vlc_compatibility(url):
    """Test if VLC can handle the video"""
    print(f"\n🎬 Testing VLC compatibility...")
    
    # Simple VLC test command
    vlc_cmd = [
        'vlc',
        '--intf', 'dummy',
        '--run-time=5',  # Run for 5 seconds only
        '--no-video',    # Don't show video window
        '--no-audio',    # Don't play audio
        url,
        'vlc://quit'
    ]
    
    try:
        result = subprocess.run(vlc_cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print("✅ VLC can handle this video")
        else:
            print("❌ VLC had issues with this video")
            print(f"Error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("⏱️  VLC test timed out - video may cause hanging")
    except FileNotFoundError:
        print("ℹ️  VLC not found on this system (normal for Windows)")

def main():
    """Run diagnostic on current video"""
    print("🎯 Pizza Hut TV Video Diagnostic Tool")
    print("=" * 50)
    
    # Current video from Pi
    current_url = "https://everydayadvertise.com/slice-video/users/toengpheng_at_gmail.com/2025-09/214f30be-a572-41ae-81fc-30d0c459aae9.mp4?slice_mode=split-h&slice_count=3&slice_order=0"
    
    # Run diagnostics
    url_ok = test_video_url(current_url)
    analyze_slice_video(current_url)
    
    if url_ok:
        test_vlc_compatibility(current_url)
    
    print(f"\n📋 SUMMARY:")
    print(f"URL Accessible: {'✅ Yes' if url_ok else '❌ No'}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if not url_ok:
        print("- Check network connectivity")
        print("- Verify video file exists on server")
    
    print("- Try reducing slice count if using sliced videos")
    print("- Consider using MP4 format with H.264 codec")
    print("- Keep video files under 100MB for better performance")

if __name__ == "__main__":
    main()