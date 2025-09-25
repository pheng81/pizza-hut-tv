#!/usr/bin/env python3
"""
Test smooth transition VLC playlist creation
"""

import tempfile
import os
import requests

def test_vlc_playlist_creation():
    """Test creating VLC playlist for smooth transitions"""
    
    # Sample playlist data (like what we get from server)
    sample_playlist = [
        {
            "duration": 18,
            "preferred_url": "https://example.com/video1.mp4",
            "media_type": "video"
        },
        {
            "duration": 10,
            "url": "https://example.com/video2.mp4", 
            "media_type": "video"
        },
        {
            "duration": 15,
            "slice_url": "https://example.com/video3.mp4",
            "media_type": "video"
        }
    ]
    
    print("🔍 Testing VLC playlist creation for smooth transitions...")
    
    try:
        # Create temporary playlist file
        fd, playlist_file = tempfile.mkstemp(suffix='.m3u', text=True)
        
        with os.fdopen(fd, 'w') as f:
            f.write("#EXTM3U\n")
            
            for i, item in enumerate(sample_playlist):
                duration = int(item.get('duration', 10))
                
                # Get video URL with priority order
                video_url = None
                if 'preferred_url' in item:
                    video_url = item['preferred_url']
                elif 'slice_url' in item:
                    video_url = item['slice_url']
                elif 'url' in item:
                    video_url = item['url']
                
                if video_url:
                    f.write(f"#EXTINF:{duration},\n")
                    f.write(f"{video_url}\n")
                    print(f"   Item {i+1}: {duration}s - {video_url}")
        
        print(f"✅ Created VLC playlist: {playlist_file}")
        
        # Show the contents
        print("\n📋 VLC Playlist Contents:")
        with open(playlist_file, 'r') as f:
            content = f.read()
            print(content)
        
        # Test VLC command that would be used
        vlc_cmd = [
            'vlc',
            playlist_file,
            '--fullscreen',
            '--no-video-title-show', 
            '--no-osd',
            '--quiet',
            '--intf', 'dummy',
            '--loop',
            '--no-random',
            '--playlist-autostart'
        ]
        
        print("🎬 VLC Command for smooth playback:")
        print(" ".join(vlc_cmd))
        
        # Clean up
        os.unlink(playlist_file)
        print("\n✅ Playlist test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error testing playlist creation: {e}")

def test_real_playlist_from_server():
    """Test with real playlist from server"""
    print("\n🌐 Testing with real server playlist...")
    
    try:
        url = "https://everydayadvertise.com/playlist/1000/1000_screen1"
        headers = {'X-User-Code': '4682'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            playlist_data = response.json()
            playlist_items = playlist_data.get('playlist', [])
            
            print(f"📋 Retrieved {len(playlist_items)} real items")
            
            if playlist_items:
                # Create real VLC playlist
                fd, playlist_file = tempfile.mkstemp(suffix='.m3u', text=True)
                
                total_duration = 0
                with os.fdopen(fd, 'w') as f:
                    f.write("#EXTM3U\n")
                    
                    for i, item in enumerate(playlist_items):
                        duration = int(item.get('duration', 10))
                        total_duration += duration
                        
                        # Get video URL with priority order
                        video_url = None
                        if 'preferred_url' in item:
                            video_url = item['preferred_url']
                        elif 'slice_url' in item:
                            video_url = item['slice_url']
                        elif 'url' in item:
                            video_url = item['url']
                        
                        if video_url:
                            f.write(f"#EXTINF:{duration},\n")
                            f.write(f"{video_url}\n")
                            print(f"   Real Item {i+1}: {duration}s - {item.get('media_type', 'unknown')}")
                
                print(f"✅ Total playlist duration: {total_duration}s")
                print(f"✅ Created real playlist: {playlist_file}")
                
                # Clean up
                os.unlink(playlist_file)
                
        else:
            print(f"❌ Server returned: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing real playlist: {e}")

if __name__ == "__main__":
    test_vlc_playlist_creation()
    test_real_playlist_from_server()