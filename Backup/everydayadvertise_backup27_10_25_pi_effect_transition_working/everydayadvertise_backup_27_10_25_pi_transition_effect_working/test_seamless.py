#!/usr/bin/env python3
"""Test seamless video player initialization"""

import pygame
import sys

print("🔧 Testing seamless video player...")

try:
    # Initialize pygame first (like complete_pi_client does)
    pygame.init()
    screen = pygame.display.set_mode((2560, 1440), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
    print(f"✅ Pygame initialized: {screen.get_size()}")
    
    # Import and initialize SeamlessMediaPlayer
    from seamless_video_player import SeamlessMediaPlayer
    
    print("🎬 Creating SeamlessMediaPlayer...")
    player = SeamlessMediaPlayer(screen)
    print("✅ SeamlessMediaPlayer created successfully!")
    
    print(f"   Window size: {player.window_size}")
    print(f"   Screen: {player.screen}")
    print(f"   Video player: {player.video_player}")
    
    # Clean up
    player.cleanup()
    pygame.quit()
    
    print("\n✅ ALL TESTS PASSED!")
    sys.exit(0)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
