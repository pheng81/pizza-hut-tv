#!/usr/bin/env python3
"""
Create a test video for EA TV playback
"""

import subprocess
import os

def create_test_video():
    """Create a simple test video using ffmpeg if available"""
    try:
        # Check if ffmpeg is available
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ ffmpeg not found, trying to install...")
            subprocess.run(['sudo', 'apt-get', 'update'], check=False)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], check=False)
        
        # Create a simple test video with colored screens
        test_videos = [
            {
                'name': 'test_screen_1.mp4',
                'color': 'red',
                'text': 'SCREEN 1 - LEFT'
            },
            {
                'name': 'test_screen_2.mp4', 
                'color': 'green',
                'text': 'SCREEN 2 - CENTER'
            },
            {
                'name': 'test_screen_3.mp4',
                'color': 'blue', 
                'text': 'SCREEN 3 - RIGHT'
            }
        ]
        
        for video in test_videos:
            output_file = f"/home/everydayadvertise/{video['name']}"
            
            # Create a 30-second video with colored background and text
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f"color=c={video['color']}:s=1920x1080:d=30",
                '-vf', f"drawtext=text='{video['text']}':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2",
                '-c:v', 'libx264',
                '-t', '30',
                output_file
            ]
            
            print(f"Creating {video['name']}...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Created {output_file}")
            else:
                print(f"❌ Failed to create {video['name']}: {result.stderr}")
        
        print("\n✅ Test videos created successfully!")
        print("You can now test EA TV with local videos.")
        
    except Exception as e:
        print(f"❌ Error creating test videos: {e}")

if __name__ == "__main__":
    create_test_video()