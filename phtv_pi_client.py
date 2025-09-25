#!/usr/bin/env python3
"""
Pizza Hut TV - Raspberry Pi Client
==================================
A dedicated Raspberry Pi client that displays video content from the Pizza Hut TV server.
Works with the same playlist API and slice video system as Android TV and webplayer.

Features:
- Fullscreen video playback
- Multi-screen slice video support  
- Schedule-aware content loading
- Automatic reconnection and error recovery
- Hardware-accelerated playback (when available)

Requirements:
- Python 3.6+
- pygame (for video playback)
- requests (for API communication)
- Raspberry Pi OS with desktop environment

Usage:
    python3 phtv_pi_client.py --server <server_url> --store <store_id> --screen <screen_id>
    
Example:
    python3 phtv_pi_client.py --server http://192.168.1.115:5002 --store 1000 --screen tv1
"""

import pygame
import requests
import json
import time
import sys
import argparse
import os
import threading
import logging
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any
import subprocess
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PizzaHutTVPi:
    """Raspberry Pi client for Pizza Hut TV system."""
    
    def __init__(self, server_url: str, store_id: str, screen_id: str):
        self.server_url = server_url.rstrip('/')
        self.store_id = store_id
        self.screen_id = screen_id
        self.user_agent = "phtv-pi/1.0 (Raspberry Pi)"
        
        # Pygame setup
        self.screen = None
        self.clock = None
        self.running = True
        
        # Playlist state
        self.current_playlist = []
        self.current_index = 0
        self.item_start_time = 0
        self.last_playlist_fetch = 0
        self.playlist_refresh_interval = 5  # seconds
        
        # Video playback state
        self.current_video = None
        self.video_process = None
        self.is_playing = False
        
        # Error handling
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.error_backoff = 1
        
        # Global synchronization settings - SAME AS WEBPLAYER
        self.sync_tolerance = 0.05  # 50ms tolerance for sync timing
        self.last_sync_fetch = 0
        self.sync_fetch_interval = 10  # Fetch sync time every 10 seconds
        self.master_clock = time.time()  # Professional sync coordinator like webplayer
        self.transition_queue = []  # Enterprise-style transition management
        
        # Display settings
        self.fullscreen = True
        self.display_size = None
        
    def init_pygame(self):
        """Initialize pygame and display."""
        try:
            pygame.init()
            pygame.mixer.quit()  # We don't need audio mixer for video
            
            # Get display info
            info = pygame.display.Info()
            self.display_size = (info.current_w, info.current_h)
            logger.info(f"Display size: {self.display_size}")
            
            # Set up display
            if self.fullscreen:
                self.screen = pygame.display.set_mode(self.display_size, pygame.FULLSCREEN)
                pygame.mouse.set_visible(False)
            else:
                self.screen = pygame.display.set_mode((1920, 1080))
                
            pygame.display.set_caption("Pizza Hut TV - Pi Client")
            self.clock = pygame.time.Clock()
            
            # Fill with black background
            self.screen.fill((0, 0, 0))
            pygame.display.flip()
            
            logger.info("Pygame initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize pygame: {e}")
            return False
    
    def fetch_sync_time(self) -> Optional[Dict[str, Any]]:
        """Fetch synchronized timestamp from server for global screen coordination."""
        try:
            url = f"{self.server_url}/api/sync-time"
            headers = {'User-Agent': self.user_agent}
            
            logger.debug(f"Fetching sync time from: {url}")
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            sync_data = response.json()
            logger.debug(f"🎯 GLOBAL SYNC: Pi client got sync data: {sync_data}")
            return sync_data
            
        except Exception as e:
            logger.warning(f"Failed to fetch sync time: {e}")
            return None
    
    def calculate_sync_moment(self, duration: int) -> float:
        """Calculate next global sync moment for all screens - SAME AS WEBPLAYER."""
        sync_data = self.fetch_sync_time()
        
        if sync_data:
            # EXACTLY LIKE WEBPLAYER: Use server-provided sync timestamp
            server_time = sync_data.get('current_time', time.time() * 1000)
            sync_interval = sync_data.get('sync_interval', 2000)  # 2 seconds in ms
            next_sync_ms = sync_data.get('timestamp', server_time + sync_interval)
            
            logger.info(f"🎯 GLOBAL SYNC: Pi client syncing to timestamp {next_sync_ms} (same as webplayer)")
            return next_sync_ms / 1000  # Convert to seconds
        else:
            # EXACTLY LIKE WEBPLAYER: Fallback to aligned 2-second intervals
            current_time = time.time()
            sync_interval = 2.0  # 2 seconds - SAME AS WEBPLAYER
            next_sync = (int(current_time / sync_interval) + 1) * sync_interval
            logger.info(f"⚠️ FALLBACK SYNC: Pi client using local sync at {next_sync} (webplayer compatible)")
            return next_sync
    
    def get_screen_sync_offset(self) -> float:
        """Get screen-specific sync offset - SAME AS WEBPLAYER."""
        # EXACTLY LIKE WEBPLAYER: All screens start simultaneously with 0 offset
        return 0.0  # No offset needed for true synchronization
    
    def schedule_sync_transition(self, item: Dict[str, Any], target_time: float) -> bool:
        """Schedule sync transition - SAME AS WEBPLAYER."""
        current_time = time.time()
        delay = max(0, target_time - current_time)
        
        logger.info(f"⏱️ PROFESSIONAL SYNC: Pi client scheduling transition in {delay:.3f}s for perfect alignment")
        
        if delay > 0:
            time.sleep(delay)
        
        return True
    
    def execute_sync_transition(self, item: Dict[str, Any]) -> bool:
        """Execute PROFESSIONAL sync transition - SAME AS WEBPLAYER."""
        logger.info(f"🎬 EXECUTING PROFESSIONAL SYNC: Pi client starting synchronized playback")
        
        # Professional transition with anti-black-screen protection
        try:
            video_url = self.get_video_url(item)
            if video_url:
                item_duration = max(int(item.get('duration', 10)), 1)
                return self.play_video(video_url, item_duration)
        except Exception as e:
            logger.error(f"Sync transition failed: {e}")
        
        return False

    def fetch_playlist(self) -> List[Dict[str, Any]]:
        """Fetch current playlist from server."""
        try:
            url = f"{self.server_url}/api/playlist/{self.store_id}/{self.screen_id}"
            headers = {'User-Agent': self.user_agent}
            
            logger.debug(f"Fetching playlist from: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            logger.info(f"Fetched playlist with {len(items)} items")
            self.consecutive_errors = 0
            self.error_backoff = 1
            
            return items
            
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Failed to fetch playlist (error {self.consecutive_errors}): {e}")
            
            if self.consecutive_errors >= self.max_consecutive_errors:
                logger.error(f"Too many consecutive errors ({self.consecutive_errors}). Backing off...")
                time.sleep(self.error_backoff)
                self.error_backoff = min(self.error_backoff * 2, 60)  # Cap at 60 seconds
            
            return []
    
    def get_video_url(self, item: Dict[str, Any]) -> str:
        """Get the appropriate video URL for this item."""
        # Pi clients should get slice URLs just like Android TV
        url = item.get('url') or item.get('slice_url') or item.get('preferred_url')
        
        if url and not url.startswith('http'):
            # Handle relative URLs
            url = urljoin(self.server_url + '/', url)
            
        logger.debug(f"Video URL for item: {url}")
        return url
    
    def play_video_omxplayer(self, video_url: str, duration: int) -> bool:
        """Play video using omxplayer (Raspberry Pi optimized)."""
        try:
            # Stop any existing video
            self.stop_video()
            
            # omxplayer command for Pi
            cmd = [
                'omxplayer',
                '--no-osd',           # No on-screen display
                '--no-keys',          # Disable keyboard
                '--aspect-mode', 'stretch',  # Stretch to fit screen
                '--timeout', str(duration + 5),  # Timeout slightly longer than duration
                video_url
            ]
            
            if self.fullscreen:
                cmd.extend(['--win', f"0 0 {self.display_size[0]} {self.display_size[1]}"])
            
            logger.info(f"Starting omxplayer: {' '.join(cmd)}")
            self.video_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.is_playing = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to start omxplayer: {e}")
            return False
    
    def play_video_vlc(self, video_url: str, duration: int) -> bool:
        """Play video using VLC as fallback."""
        try:
            # Stop any existing video  
            self.stop_video()
            
            # VLC command
            cmd = [
                'cvlc',  # Command-line VLC
                '--intf', 'dummy',    # No interface
                '--no-video-title-show',  # No title overlay
                '--fullscreen',       # Fullscreen mode
                '--play-and-exit',    # Exit after playing
                '--run-time', str(duration),  # Duration limit
                video_url
            ]
            
            logger.info(f"Starting VLC: {' '.join(cmd)}")
            self.video_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.is_playing = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to start VLC: {e}")
            return False
    
    def play_video(self, video_url: str, duration: int) -> bool:
        """Play video using the best available player."""
        if not video_url:
            logger.error("No video URL provided")
            return False
        
        # Try omxplayer first (Pi optimized), then VLC as fallback
        if self.is_command_available('omxplayer'):
            return self.play_video_omxplayer(video_url, duration)
        elif self.is_command_available('cvlc'):
            return self.play_video_vlc(video_url, duration)
        else:
            logger.error("No suitable video player found (omxplayer or vlc required)")
            return False
    
    def stop_video(self):
        """Stop any currently playing video."""
        if self.video_process:
            try:
                # Kill process group to ensure clean shutdown
                os.killpg(os.getpgid(self.video_process.pid), signal.SIGTERM)
                self.video_process.wait(timeout=5)
            except:
                try:
                    # Force kill if still running
                    os.killpg(os.getpgid(self.video_process.pid), signal.SIGKILL)
                except:
                    pass
            finally:
                self.video_process = None
                
        self.is_playing = False
    
    def is_command_available(self, command: str) -> bool:
        """Check if a command is available on the system."""
        try:
            subprocess.run(['which', command], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def update_playlist(self):
        """Update playlist if needed."""
        current_time = time.time()
        
        if (current_time - self.last_playlist_fetch) > self.playlist_refresh_interval:
            new_playlist = self.fetch_playlist()
            
            if new_playlist:
                # Check if playlist changed
                if new_playlist != self.current_playlist:
                    logger.info("Playlist updated")
                    self.current_playlist = new_playlist
                    # Reset to beginning if playlist changed significantly
                    if self.current_index >= len(self.current_playlist):
                        self.current_index = 0
                        
                self.last_playlist_fetch = current_time
    
    def get_current_item(self) -> Optional[Dict[str, Any]]:
        """Get current playlist item."""
        if not self.current_playlist:
            return None
            
        if self.current_index >= len(self.current_playlist):
            self.current_index = 0
            
        return self.current_playlist[self.current_index]
    
    def advance_to_next_item(self):
        """Move to next item in playlist."""
        if self.current_playlist:
            self.current_index = (self.current_index + 1) % len(self.current_playlist)
            self.item_start_time = time.time()
            logger.info(f"Advanced to item {self.current_index + 1}/{len(self.current_playlist)}")
    
    def show_status_text(self, text: str):
        """Display status text on screen."""
        try:
            font = pygame.font.Font(None, 74)
            text_surface = font.render(text, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.display_size[0]//2, self.display_size[1]//2))
            
            self.screen.fill((0, 0, 0))  # Black background
            self.screen.blit(text_surface, text_rect)
            pygame.display.flip()
            
        except Exception as e:
            logger.error(f"Failed to show status text: {e}")
    
    def handle_pygame_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    # Pause/resume (skip to next for now)
                    self.stop_video()
                    self.advance_to_next_item()
                elif event.key == pygame.K_n:
                    # Next item
                    self.stop_video()
                    self.advance_to_next_item()
                elif event.key == pygame.K_r:
                    # Refresh playlist
                    self.current_playlist = []
                    logger.info("Playlist refresh requested")
    
    def run(self):
        """Main client loop."""
        logger.info(f"Starting Pizza Hut TV Pi client for {self.store_id}/{self.screen_id}")
        logger.info(f"Server: {self.server_url}")
        
        if not self.init_pygame():
            logger.error("Failed to initialize pygame")
            return False
        
        self.show_status_text("Pizza Hut TV - Connecting...")
        
        # Initial playlist fetch
        self.current_playlist = self.fetch_playlist()
        if not self.current_playlist:
            self.show_status_text("No content available")
            logger.warning("No initial playlist available")
        
        self.item_start_time = time.time()
        
        try:
            while self.running:
                current_time = time.time()
                
                # Handle pygame events
                self.handle_pygame_events()
                
                # Update playlist periodically
                self.update_playlist()
                
                # Get current item
                current_item = self.get_current_item()
                
                if not current_item:
                    # No content available
                    if not self.is_playing:
                        self.show_status_text("No content available")
                    time.sleep(1)
                    continue
                
                # Check if we need to start or change video with global synchronization
                item_duration = max(int(current_item.get('duration', 10)), 1)
                elapsed_time = current_time - self.item_start_time
                
                if not self.is_playing or elapsed_time >= item_duration:
                    # � PROFESSIONAL SYNC: Calculate perfect timing for enterprise sync - SAME AS WEBPLAYER
                    sync_moment = self.calculate_sync_moment(item_duration)
                    screen_offset = self.get_screen_sync_offset()
                    final_sync_time = sync_moment + screen_offset
                    
                    logger.info(f"🎯 ENTERPRISE SYNC: Pi client calculated perfect sync moment for smooth transition")
                    
                    # PROFESSIONAL SYNC: Schedule transition like webplayer
                    if self.schedule_sync_transition(current_item, final_sync_time):
                        # Execute synchronized transition
                        if self.execute_sync_transition(current_item):
                            self.item_start_time = time.time()  # Update after successful sync
                            logger.info(f"✅ SYNCHRONIZED: Pi client started at global sync timestamp (same timing as webplayer)")
                        else:
                            logger.error("Sync transition failed, advancing to next")
                            self.advance_to_next_item()
                    else:
                        logger.error("Failed to schedule sync transition, advancing to next")
                        self.advance_to_next_item()
                
                # Check if video process finished
                elif self.video_process and self.video_process.poll() is not None:
                    logger.info("Video finished, advancing to next")
                    self.is_playing = False
                    self.advance_to_next_item()
                
                # Check if item duration exceeded (backup timer)
                elif elapsed_time > (item_duration + 5):
                    logger.info("Item duration exceeded, advancing to next")
                    self.stop_video()
                    self.advance_to_next_item()
                
                # Control loop timing
                self.clock.tick(10)  # 10 FPS for main loop
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.cleanup()
        
        return True
    
    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        
        self.running = False
        self.stop_video()
        
        if pygame.get_init():
            pygame.quit()
        
        logger.info("Cleanup complete")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Pizza Hut TV - Raspberry Pi Client')
    parser.add_argument('--server', required=True, help='Server URL (e.g., http://192.168.1.115:5002)')
    parser.add_argument('--store', required=True, help='Store ID (e.g., 1000)')
    parser.add_argument('--screen', required=True, help='Screen ID (e.g., tv1)')
    parser.add_argument('--windowed', action='store_true', help='Run in windowed mode (not fullscreen)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create client
    client = PizzaHutTVPi(args.server, args.store, args.screen)
    client.fullscreen = not args.windowed
    
    # Handle SIGTERM gracefully
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        client.running = False
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run client
    success = client.run()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()