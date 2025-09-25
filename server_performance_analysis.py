#!/usr/bin/env python3
"""
Server Performance Analysis for Pizza Hut TV
Compare slice video vs regular video performance
"""

import requests
import time
import statistics

def test_server_response(url, description, num_tests=5):
    """Test server response time multiple times for accuracy"""
    print(f"\n🔍 Testing {description}")
    print(f"URL: {url}")
    
    response_times = []
    
    for i in range(num_tests):
        try:
            start_time = time.time()
            response = requests.head(url, timeout=30)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # Convert to ms
            response_times.append(response_time)
            
            print(f"Test {i+1}: {response_time:.2f}ms - Status: {response.status_code}")
            
        except Exception as e:
            print(f"Test {i+1}: ERROR - {e}")
            
    if response_times:
        avg_time = statistics.mean(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        print(f"📊 Results: Avg: {avg_time:.2f}ms, Min: {min_time:.2f}ms, Max: {max_time:.2f}ms")
        
        # Performance assessment
        if avg_time < 100:
            print("✅ EXCELLENT - Very fast response")
        elif avg_time < 300:
            print("⚠️ SLOW - Noticeable delay")
        else:
            print("❌ VERY SLOW - Major performance issue")
            
        return avg_time
    
    return None

def analyze_slice_performance():
    """Analyze slice video processing performance vs alternatives"""
    print("🎯 Pizza Hut TV Server Performance Analysis")
    print("=" * 60)
    
    # Base video URL (without slicing)
    base_url = "https://everydayadvertise.com/users/toengpheng_at_gmail.com/2025-09/214f30be-a572-41ae-81fc-30d0c459aae9.mp4"
    
    # Slice video URLs
    slice_url_0 = "https://everydayadvertise.com/slice-video/users/toengpheng_at_gmail.com/2025-09/214f30be-a572-41ae-81fc-30d0c459aae9.mp4?slice_mode=split-h&slice_count=3&slice_order=0"
    slice_url_1 = "https://everydayadvertise.com/slice-video/users/toengpheng_at_gmail.com/2025-09/214f30be-a572-41ae-81fc-30d0c459aae9.mp4?slice_mode=split-h&slice_count=3&slice_order=1"
    slice_url_2 = "https://everydayadvertise.com/slice-video/users/toengpheng_at_gmail.com/2025-09/214f30be-a572-41ae-81fc-30d0c459aae9.mp4?slice_mode=split-h&slice_count=3&slice_order=2"
    
    # Test different scenarios
    base_time = test_server_response(base_url, "Original Video (No Slicing)")
    slice0_time = test_server_response(slice_url_0, "Slice 0 (Left Third)")
    slice1_time = test_server_response(slice_url_1, "Slice 1 (Middle Third)")  
    slice2_time = test_server_response(slice_url_2, "Slice 2 (Right Third)")
    
    print(f"\n📋 PERFORMANCE SUMMARY:")
    print(f"=" * 40)
    
    if base_time and slice0_time:
        slowdown = (slice0_time / base_time) * 100 - 100
        print(f"Original video: {base_time:.2f}ms")
        print(f"Slice video: {slice0_time:.2f}ms")
        print(f"Slice processing overhead: {slowdown:.1f}% slower")
        
    print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
    print(f"=" * 40)
    
    if slice0_time and slice0_time > 200:
        print("🔄 SERVER-SIDE SOLUTIONS:")
        print("1. Pre-process and cache slice videos")
        print("2. Use CDN caching for processed slices") 
        print("3. Implement background processing queue")
        print("4. Add Redis/Memcached for slice results")
        
        print("\n🎬 ALTERNATIVE APPROACHES:")
        print("1. Upload separate files for each screen (fastest)")
        print("2. Use client-side cropping (if supported)")
        print("3. Reduce slice count (3 slices → 2 slices)")
        print("4. Pre-generate slices during upload")
        
    print(f"\n⚡ IMMEDIATE IMPROVEMENTS:")
    print("1. Enable server-side caching headers")
    print("2. Use HTTP/2 for faster connections") 
    print("3. Compress slice videos during processing")
    print("4. Implement slice video preloading")

if __name__ == "__main__":
    analyze_slice_performance()