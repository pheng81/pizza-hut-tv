#!/usr/bin/env python3
"""Test mixed media detection logic"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ea_tv_pi import WebplayerStyleEATVClient

def test_mixed_media_detection():
    """Test the mixed media detection with sample playlist items"""
    
    # Create a test instance
    player = WebplayerStyleEATVClient()
    
    # Test Case 1: Mixed media playlist (slice video + image)
    mixed_playlist = [
        {
            'url': 'http://54.252.90.27:5000/slice-video/123?slice_mode=2&slice_count=3&cb=1234567890',
            'duration': 30,
            'title': 'Slice Video Test'
        },
        {
            'url': 'http://54.252.90.27:5000/media/image123.jpg?cb=1234567890', 
            'duration': 10,
            'title': 'Image Test'
        }
    ]
    
    # Test Case 2: All slice videos
    slice_playlist = [
        {
            'url': 'http://54.252.90.27:5000/slice-video/123?slice_mode=2&slice_count=3&cb=1234567890',
            'duration': 30,
            'title': 'Slice Video 1'
        },
        {
            'url': 'http://54.252.90.27:5000/slice-video/456?slice_mode=2&slice_count=3&cb=1234567890',
            'duration': 25,
            'title': 'Slice Video 2'
        }
    ]
    
    # Test Case 3: All images
    image_playlist = [
        {
            'url': 'http://54.252.90.27:5000/media/image123.jpg?cb=1234567890',
            'duration': 10,
            'title': 'Image 1'
        },
        {
            'url': 'http://54.252.90.27:5000/media/image456.jpg?cb=1234567890',
            'duration': 8,
            'title': 'Image 2'
        }
    ]
    
    print("=== Mixed Media Detection Test ===")
    
    # Test mixed media playlist
    player.resolved_playlist_cache = mixed_playlist
    has_mixed = player.playlist_has_mixed_media_types()
    has_slices = player.playlist_has_slice_videos()
    print(f"Mixed playlist - Has mixed media: {has_mixed}, Has slice videos: {has_slices}")
    print(f"Should use specialized handling: {has_mixed and has_slices}")
    
    # Test slice-only playlist  
    player.resolved_playlist_cache = slice_playlist
    has_mixed = player.playlist_has_mixed_media_types()
    has_slices = player.playlist_has_slice_videos()
    print(f"Slice-only playlist - Has mixed media: {has_mixed}, Has slice videos: {has_slices}")
    print(f"Should use specialized handling: {has_mixed and has_slices}")
    
    # Test image-only playlist
    player.resolved_playlist_cache = image_playlist
    has_mixed = player.playlist_has_mixed_media_types()
    has_slices = player.playlist_has_slice_videos()
    print(f"Image-only playlist - Has mixed media: {has_mixed}, Has slice videos: {has_slices}")
    print(f"Should use specialized handling: {has_mixed and has_slices}")
    
    print("\n=== Mixed Media Playlist Creation Test ===")
    
    # Test playlist creation
    player.resolved_playlist_cache = mixed_playlist
    playlist_path = player.create_mixed_media_vlc_playlist(mixed_playlist, pre_resolved=True)
    if playlist_path:
        print(f"✅ Successfully created mixed media playlist: {playlist_path}")
        
        # Read and display the playlist content
        try:
            with open(playlist_path, 'r') as f:
                content = f.read()
            print("Playlist content:")
            print(content)
        except Exception as e:
            print(f"❌ Could not read playlist file: {e}")
            
        # Clean up
        try:
            os.remove(playlist_path)
            print("🧹 Cleaned up test playlist file")
        except:
            pass
    else:
        print("❌ Failed to create mixed media playlist")

if __name__ == '__main__':
    test_mixed_media_detection()