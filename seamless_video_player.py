#!/usr/bin/env python3
"""
Seamless Video Player using python-mpv bindings
NO FLICKER - videos transition smoothly using internal playlist
"""

import mpv
import pygame
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SeamlessVideoPlayer:
    """Custom video player with zero-flicker transitions"""
    
    def __init__(self, window_size=(2560, 1440), screen=None):
        self.window_size = window_size
        self.player: Optional[mpv.MPV] = None
        self.current_video: Optional[str] = None
        self.next_video: Optional[str] = None
        self.is_playing = False
        self.playback_lock = threading.Lock()
        self.on_video_end: Optional[Callable] = None
        
        # Use existing pygame screen if provided (don't create a new one)
        if screen:
            self.screen = screen
        else:
            # Only create pygame window if not provided
            pygame.init()
            self.screen = pygame.display.set_mode(window_size, pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
            pygame.display.set_caption("Pizza Hut TV")
            pygame.mouse.set_visible(False)
        
        self._init_player()
        
    def _init_player(self):
        """Initialize MPV player with optimal settings"""
        try:
            self.player = mpv.MPV(
                # Video output
                vo='gpu',
                hwdec='auto',
                
                # Window settings
                fullscreen=True,
                ontop=True,
                
                # No UI elements
                osc=False,
                osd_level=0,
                cursor_autohide='always',
                
                # Audio
                audio='auto',
                volume=100,
                
                # Performance
                video_sync='display-resample',
                interpolation=True,
                tscale='oversample',
                
                # Background
                background='#000000',
                
                # Keep window open between videos
                keep_open='always',
                idle='yes',
                
                # Logging
                msg_level='all=info',
            )
            
            # Register event handlers
            @self.player.event_callback('end-file')
            def on_end_file(event):
                logger.info(f"🎬 Video ended: {event}")
                if self.on_video_end:
                    self.on_video_end()
            
            @self.player.event_callback('file-loaded')
            def on_file_loaded(event):
                logger.info(f"✅ Video loaded successfully")
                self.is_playing = True
            
            logger.info("✅ MPV player initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize MPV player: {e}")
            raise
    
    def play_video(self, video_path: str, duration: Optional[float] = None):
        """
        Play a video with seamless transition
        
        Args:
            video_path: Path to video file
            duration: Optional duration limit in seconds
        """
        with self.playback_lock:
            try:
                if not Path(video_path).exists():
                    logger.error(f"❌ Video file not found: {video_path}")
                    return False
                
                logger.info(f"▶️  Playing video: {video_path}")
                
                # If already playing, this creates seamless transition
                if self.is_playing and self.player:
                    logger.info("🔄 Seamless transition to next video...")
                    # MPV internally handles smooth transition
                    self.player.play(video_path)
                else:
                    # First video
                    logger.info("🎬 Starting first video...")
                    self.player.play(video_path)
                
                # Set duration limit if specified
                if duration:
                    self.player.length = duration
                
                self.current_video = video_path
                self.is_playing = True
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error playing video: {e}")
                self.is_playing = False
                return False
    
    def queue_next_video(self, video_path: str):
        """
        Queue next video for absolutely seamless transition
        MPV will automatically start it when current finishes
        """
        try:
            if not Path(video_path).exists():
                logger.error(f"❌ Video file not found: {video_path}")
                return False
            
            logger.info(f"📋 Queuing next video: {video_path}")
            
            # Append to MPV's internal playlist
            self.player.playlist_append(video_path)
            self.next_video = video_path
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error queuing video: {e}")
            return False
    
    def show_image(self, image_surface: pygame.Surface, duration: float):
        """
        Show an image (pauses video playback)
        
        Args:
            image_surface: Pygame surface with image
            duration: How long to show image in seconds
        """
        with self.playback_lock:
            try:
                # Pause video playback
                if self.is_playing and self.player:
                    self.player.pause = True
                    logger.info("⏸️  Paused video for image display")
                
                # Display image on pygame surface
                self.screen.blit(image_surface, (0, 0))
                pygame.display.flip()
                
                # Wait for duration
                time.sleep(duration)
                
                # Resume video if was playing
                if self.is_playing and self.player:
                    self.player.pause = False
                    logger.info("▶️  Resumed video after image")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error showing image: {e}")
                return False
    
    def pause(self):
        """Pause playback"""
        if self.player:
            self.player.pause = True
            logger.info("⏸️  Paused")
    
    def resume(self):
        """Resume playback"""
        if self.player:
            self.player.pause = False
            logger.info("▶️  Resumed")
    
    def stop(self):
        """Stop playback and show black screen"""
        with self.playback_lock:
            if self.player:
                try:
                    self.player.stop()
                    self.is_playing = False
                    self.current_video = None
                    logger.info("⏹️  Stopped")
                except:
                    pass
    
    def set_volume(self, volume: int):
        """
        Set volume (0-100)
        """
        if self.player:
            self.player.volume = max(0, min(100, volume))
            logger.info(f"🔊 Volume set to {volume}%")
    
    def get_playback_time(self) -> float:
        """Get current playback position in seconds"""
        if self.player and self.is_playing:
            try:
                return self.player.time_pos or 0.0
            except:
                return 0.0
        return 0.0
    
    def get_duration(self) -> float:
        """Get total video duration in seconds"""
        if self.player and self.is_playing:
            try:
                return self.player.duration or 0.0
            except:
                return 0.0
        return 0.0
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up player...")
        self.stop()
        
        if self.player:
            try:
                self.player.terminate()
            except:
                pass
        
        pygame.quit()
        logger.info("✅ Player cleaned up")


class SeamlessMediaPlayer:
    """
    Drop-in replacement for media_player.py with zero-flicker transitions
    Compatible with complete_pi_client.py interface
    """
    
    def __init__(self, screen_or_size=(2560, 1440), cache_dir="cache"):
        # Handle both pygame screen object and window_size tuple
        if isinstance(screen_or_size, tuple):
            self.window_size = screen_or_size
            self.external_screen = None
        else:
            # It's a pygame screen object
            self.external_screen = screen_or_size
            self.window_size = screen_or_size.get_size()
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize seamless video player, pass screen if we have one
        self.video_player = SeamlessVideoPlayer(self.window_size, screen=self.external_screen)
        
        # Use the video player's screen for drawing
        self.screen = self.video_player.screen
        
        # Image cache
        self.image_cache = {}
        
        # State
        self.is_playing = False
        self.current_media_type = None
        
        logger.info("✅ Seamless Media Player initialized")
    
    def play_media(self, url: str, effect: str, duration: float) -> bool:
        """
        Play media with seamless transitions
        
        Args:
            url: URL or local path to media
            effect: Transition effect (ignored for seamless playback)
            duration: Duration in seconds
            
        Returns:
            True if successful
        """
        try:
            # Determine media type
            if url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                media_type = 'video'
            else:
                media_type = 'image'
            
            logger.info(f"🎬 Playing {media_type}: {url} for {duration}s")
            
            # Get local path (download if URL)
            if url.startswith('http'):
                local_path = self._download_media(url, media_type)
                if not local_path:
                    return False
            else:
                local_path = url
            
            # Play based on type
            if media_type == 'video':
                success = self.video_player.play_video(local_path, duration)
                if success:
                    self.current_media_type = 'video'
                    self.is_playing = True
                return success
                
            else:  # image
                image_surface = self._load_image(local_path)
                if image_surface:
                    success = self.video_player.show_image(image_surface, duration)
                    if success:
                        self.current_media_type = 'image'
                        self.is_playing = True
                    return success
                return False
                
        except Exception as e:
            logger.error(f"❌ Error playing media: {e}")
            return False
    
    def queue_next(self, url: str) -> bool:
        """
        Queue next video for seamless transition
        Only works for video-to-video
        """
        try:
            if not url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                return False  # Only queue videos
            
            # Get local path
            if url.startswith('http'):
                local_path = self._download_media(url, 'video')
                if not local_path:
                    return False
            else:
                local_path = url
            
            return self.video_player.queue_next_video(local_path)
            
        except Exception as e:
            logger.error(f"❌ Error queuing next video: {e}")
            return False
    
    def _load_image(self, image_path: str) -> Optional[pygame.Surface]:
        """Load and cache image"""
        try:
            if image_path in self.image_cache:
                return self.image_cache[image_path]
            
            # Load and scale image
            image = pygame.image.load(image_path)
            image = pygame.transform.scale(image, self.window_size)
            
            # Cache it
            self.image_cache[image_path] = image
            
            return image
            
        except Exception as e:
            logger.error(f"❌ Error loading image: {e}")
            return None
    
    def _download_media(self, url: str, media_type: str) -> Optional[str]:
        """Download media to cache"""
        try:
            import hashlib
            import requests
            
            # Create cache filename
            url_hash = hashlib.md5(url.encode()).hexdigest()
            ext = Path(url).suffix or ('.mp4' if media_type == 'video' else '.jpg')
            cache_path = self.cache_dir / f"{url_hash}{ext}"
            
            # Return if already cached
            if cache_path.exists():
                logger.info(f"📦 Using cached: {cache_path}")
                return str(cache_path)
            
            # Download
            logger.info(f"⬇️  Downloading: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ Downloaded: {cache_path}")
            return str(cache_path)
            
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None
    
    def preload_media(self, url: str):
        """
        Preload media (download to cache)
        This is called by complete_pi_client to preload upcoming items
        """
        try:
            if not url or not url.startswith('http'):
                return  # Only preload remote URLs
            
            # Determine media type from URL
            if url.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                media_type = 'video'
            else:
                media_type = 'image'
            
            # Download to cache (will be used later when play_media is called)
            local_path = self._download_media(url, media_type)
            if local_path:
                logger.debug(f"📥 Preloaded: {url}")
            
        except Exception as e:
            logger.error(f"❌ Error preloading media: {e}")
    
    def stop(self):
        """Stop playback"""
        self.video_player.stop()
        self.is_playing = False
        self.current_media_type = None
    
    def pause(self):
        """Pause playback"""
        self.video_player.pause()
    
    def resume(self):
        """Resume playback"""
        self.video_player.resume()
    
    def cleanup(self):
        """Clean up resources"""
        self.video_player.cleanup()
        self.image_cache.clear()


# Example usage
if __name__ == "__main__":
    player = SeamlessMediaPlayer()
    
    # Test with multiple videos - should have ZERO flicker
    test_videos = [
        "/path/to/video1.mp4",
        "/path/to/video2.mp4",
        "/path/to/video3.mp4",
    ]
    
    try:
        for i, video in enumerate(test_videos):
            print(f"\n🎬 Playing video {i+1}/{len(test_videos)}")
            
            # Queue next video for seamless transition
            if i < len(test_videos) - 1:
                player.queue_next(test_videos[i + 1])
            
            player.play_media(video, 'fade', 10.0)
            time.sleep(10)
        
        print("\n✅ All videos played seamlessly!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    finally:
        player.cleanup()
