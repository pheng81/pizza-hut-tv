#!/usr/bin/env python3
"""
🎬 Media Player Module for Pi Webplayer Client
Handles video and image playback with webplayer-like behavior
"""

import pygame
import requests
import threading
import time
import logging
import os
import tempfile
from typing import Optional, Dict, Any, Callable
from io import BytesIO
from urllib.parse import urlparse
import hashlib

logger = logging.getLogger(__name__)

class MediaPlayer:
    """Handles media playback with caching and preloading."""
    
    def __init__(self, screen: pygame.Surface, cache_dir: str = None):
        self.screen = screen
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "phtv_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Media cache
        self.media_cache = {}  # url -> {'surface': surface, 'timestamp': time, 'type': str}
        self.download_cache = {}  # url -> local_file_path
        self.max_cache_items = 10
        self.max_cache_size_mb = 500
        
        # Current playback
        self.current_surface = None
        self.current_url = ""
        self.is_playing = False
        
        # Preloader
        self.preload_queue = []
        self.preload_thread = None
        self.preload_running = True
        
        # Effects
        self.transition_effects = {
            'fade': self._fade_transition,
            'slide-l': self._slide_left_transition,
            'slide-r': self._slide_right_transition, 
            'zoom-in': self._zoom_in_transition,
            'zoom-out': self._zoom_out_transition,
            'cut': self._cut_transition
        }
        
        self.start_preloader()
        logger.info(f"🎬 Media Player initialized: {self.screen_width}x{self.screen_height}")
        
    def start_preloader(self):
        """Start background preloader thread."""
        def preloader_loop():
            while self.preload_running:
                if self.preload_queue:
                    url = self.preload_queue.pop(0)
                    try:
                        self._preload_media(url)
                    except Exception as e:
                        logger.warning(f"Preload failed for {url}: {e}")
                else:
                    time.sleep(0.1)
                    
        self.preload_thread = threading.Thread(target=preloader_loop, daemon=True)
        self.preload_thread.start()
        
    def preload_media(self, url: str):
        """Add URL to preload queue."""
        if url and url not in self.preload_queue and url not in self.media_cache:
            self.preload_queue.append(url)
            logger.debug(f"📥 Queued for preload: {url}")
            
    def _preload_media(self, url: str) -> Optional[pygame.Surface]:
        """Preload media from URL."""
        try:
            # Check if already cached
            if url in self.media_cache:
                self.media_cache[url]['timestamp'] = time.time()
                return self.media_cache[url]['surface']
                
            logger.info(f"🔄 Preloading media: {url}")
            
            # Download or get from cache
            local_path = self._download_media(url) 
            if not local_path:
                return None
                
            # Determine media type
            media_type = self._get_media_type(local_path)
            
            if media_type == 'image':
                surface = self._load_image(local_path)
            elif media_type == 'video':
                surface = self._load_video_frame(local_path)
            else:
                logger.warning(f"Unknown media type for: {url}")
                return None
                
            if surface:
                # Scale to screen size
                scaled_surface = pygame.transform.scale(surface, (self.screen_width, self.screen_height))
                
                # Cache the scaled surface
                self.media_cache[url] = {
                    'surface': scaled_surface,
                    'timestamp': time.time(),
                    'type': media_type
                }
                
                self._trim_cache()
                logger.info(f"✅ Preloaded: {url} ({media_type})")
                return scaled_surface
                
        except Exception as e:
            logger.error(f"Preload error for {url}: {e}")
            
        return None
        
    def _download_media(self, url: str) -> Optional[str]:
        """Download media file to local cache."""
        # Create cache key
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        # Check if already downloaded
        if url in self.download_cache:
            cache_file = self.download_cache[url]
            if os.path.exists(cache_file):
                return cache_file
                
        try:
            # Download file
            logger.debug(f"⬇️ Downloading: {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Determine file extension
            parsed_url = urlparse(url)
            ext = os.path.splitext(parsed_url.path)[1] or '.tmp'
            
            # Save to cache
            cache_file = os.path.join(self.cache_dir, f"{url_hash}{ext}")
            
            with open(cache_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            self.download_cache[url] = cache_file
            logger.debug(f"✅ Downloaded: {cache_file}")
            
            # Clean up old downloads
            self._trim_download_cache()
            
            return cache_file
            
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return None
            
    def _get_media_type(self, file_path: str) -> str:
        """Determine media type from file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        
        video_exts = ['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv', '.m4v']
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        
        if ext in video_exts:
            return 'video'
        elif ext in image_exts:
            return 'image'
        else:
            return 'unknown'
            
    def _load_image(self, file_path: str) -> Optional[pygame.Surface]:
        """Load image file as pygame surface."""
        try:
            surface = pygame.image.load(file_path)
            return surface.convert()
        except Exception as e:
            logger.error(f"Image load error: {e}")
            return None
            
    def _load_video_frame(self, file_path: str) -> Optional[pygame.Surface]:
        """Load first frame of video as pygame surface."""
        try:
            # For now, create a placeholder surface with video info
            # In a full implementation, you'd use opencv-python or similar
            surface = pygame.Surface((1920, 1080))
            surface.fill((50, 50, 50))
            
            # Add video placeholder text
            font = pygame.font.Font(None, 48)
            text = font.render("🎬 VIDEO", True, (255, 255, 255))
            text_rect = text.get_rect(center=(surface.get_width()//2, surface.get_height()//2))
            surface.blit(text, text_rect)
            
            # Show filename
            filename = os.path.basename(file_path)
            filename_text = pygame.font.Font(None, 24).render(filename, True, (200, 200, 200))
            filename_rect = filename_text.get_rect(center=(surface.get_width()//2, surface.get_height()//2 + 60))
            surface.blit(filename_text, filename_rect)
            
            return surface.convert()
            
        except Exception as e:
            logger.error(f"Video frame load error: {e}")
            return None
            
    def play_media(self, url: str, effect: str = 'fade', duration: float = 10.0) -> bool:
        """Play media with specified transition effect."""
        try:
            logger.info(f"🎬 Playing media: {url} (effect: {effect}, duration: {duration}s)")
            
            # Get media surface (from cache or load)
            surface = self.media_cache.get(url, {}).get('surface')
            if not surface:
                surface = self._preload_media(url)
                
            if not surface:
                logger.error(f"Failed to load media: {url}")
                return False
                
            # Apply transition effect
            transition_func = self.transition_effects.get(effect, self._fade_transition)
            success = transition_func(surface, duration)
            
            if success:
                self.current_surface = surface
                self.current_url = url
                self.is_playing = True
                
            return success
            
        except Exception as e:
            logger.error(f"Play media error: {e}")
            return False
            
    def _fade_transition(self, new_surface: pygame.Surface, duration: float) -> bool:
        """Fade transition effect."""
        try:
            steps = 30  # Number of fade steps
            step_duration = 0.8 / steps  # 0.8 second fade like webplayer
            
            for i in range(steps + 1):
                alpha = int(255 * (i / steps))
                
                # Create transition surface
                transition_surface = new_surface.copy()
                transition_surface.set_alpha(alpha)
                
                # Draw current + transition
                if self.current_surface:
                    self.screen.blit(self.current_surface, (0, 0))
                else:
                    self.screen.fill((0, 0, 0))
                    
                self.screen.blit(transition_surface, (0, 0))
                pygame.display.flip()
                
                time.sleep(step_duration)
                
            return True
            
        except Exception as e:
            logger.error(f"Fade transition error: {e}")
            return False
            
    def _slide_left_transition(self, new_surface: pygame.Surface, duration: float) -> bool:
        """Slide left transition effect."""
        try:
            steps = 20
            step_duration = 0.8 / steps
            
            for i in range(steps + 1):
                progress = i / steps
                offset_x = int(self.screen_width * (1 - progress))
                
                # Clear screen
                self.screen.fill((0, 0, 0))
                
                # Draw current surface sliding out
                if self.current_surface:
                    self.screen.blit(self.current_surface, (-offset_x, 0))
                    
                # Draw new surface sliding in
                self.screen.blit(new_surface, (self.screen_width - offset_x, 0))
                
                pygame.display.flip()
                time.sleep(step_duration)
                
            return True
            
        except Exception as e:
            logger.error(f"Slide left transition error: {e}")
            return False
            
    def _slide_right_transition(self, new_surface: pygame.Surface, duration: float) -> bool:
        """Slide right transition effect."""
        try:
            steps = 20
            step_duration = 0.8 / steps
            
            for i in range(steps + 1):
                progress = i / steps
                offset_x = int(self.screen_width * (1 - progress))
                
                # Clear screen
                self.screen.fill((0, 0, 0))
                
                # Draw current surface sliding out
                if self.current_surface:
                    self.screen.blit(self.current_surface, (offset_x, 0))
                    
                # Draw new surface sliding in
                self.screen.blit(new_surface, (-self.screen_width + offset_x, 0))
                
                pygame.display.flip()
                time.sleep(step_duration)
                
            return True
            
        except Exception as e:
            logger.error(f"Slide right transition error: {e}")
            return False
            
    def _zoom_in_transition(self, new_surface: pygame.Surface, duration: float) -> bool:
        """Zoom in transition effect."""
        try:
            steps = 20
            step_duration = 0.8 / steps
            
            for i in range(steps + 1):
                progress = i / steps
                scale = 0.92 + (0.08 * progress)  # Start at 92%, end at 100%
                
                # Scale new surface
                scaled_width = int(self.screen_width * scale)
                scaled_height = int(self.screen_height * scale)
                scaled_surface = pygame.transform.scale(new_surface, (scaled_width, scaled_height))
                
                # Center the scaled surface
                x = (self.screen_width - scaled_width) // 2
                y = (self.screen_height - scaled_height) // 2
                
                # Clear and draw
                self.screen.fill((0, 0, 0))
                if self.current_surface and progress < 0.5:
                    self.screen.blit(self.current_surface, (0, 0))
                    
                alpha = int(255 * progress)
                scaled_surface.set_alpha(alpha)
                self.screen.blit(scaled_surface, (x, y))
                
                pygame.display.flip()
                time.sleep(step_duration)
                
            return True
            
        except Exception as e:
            logger.error(f"Zoom in transition error: {e}")
            return False
            
    def _zoom_out_transition(self, new_surface: pygame.Surface, duration: float) -> bool:
        """Zoom out transition effect."""
        try:
            steps = 20
            step_duration = 0.8 / steps
            
            for i in range(steps + 1):
                progress = i / steps
                scale = 1.08 - (0.08 * progress)  # Start at 108%, end at 100%
                
                # Scale new surface
                scaled_width = int(self.screen_width * scale)
                scaled_height = int(self.screen_height * scale)
                scaled_surface = pygame.transform.scale(new_surface, (scaled_width, scaled_height))
                
                # Center the scaled surface
                x = (self.screen_width - scaled_width) // 2
                y = (self.screen_height - scaled_height) // 2
                
                # Clear and draw
                self.screen.fill((0, 0, 0))
                if self.current_surface and progress < 0.5:
                    self.screen.blit(self.current_surface, (0, 0))
                    
                alpha = int(255 * progress)
                scaled_surface.set_alpha(alpha)
                self.screen.blit(scaled_surface, (x, y))
                
                pygame.display.flip()
                time.sleep(step_duration)
                
            return True
            
        except Exception as e:
            logger.error(f"Zoom out transition error: {e}")
            return False
            
    def _cut_transition(self, new_surface: pygame.Surface, duration: float) -> bool:
        """Instant cut transition (no animation)."""
        try:
            self.screen.blit(new_surface, (0, 0))
            pygame.display.flip()
            return True
            
        except Exception as e:
            logger.error(f"Cut transition error: {e}")
            return False
            
    def _trim_cache(self):
        """Remove old items from memory cache."""
        if len(self.media_cache) <= self.max_cache_items:
            return
            
        # Sort by timestamp and remove oldest
        items = list(self.media_cache.items())
        items.sort(key=lambda x: x[1]['timestamp'])
        
        while len(self.media_cache) > self.max_cache_items:
            url, _ = items.pop(0)
            del self.media_cache[url]
            logger.debug(f"🗑️ Removed from cache: {url}")
            
    def _trim_download_cache(self):
        """Remove old downloaded files."""
        try:
            # Get all cache files with their modification times
            cache_files = []
            total_size = 0
            
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    cache_files.append((filepath, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size
                    
            # Remove files if over size limit
            max_size = self.max_cache_size_mb * 1024 * 1024
            if total_size > max_size:
                # Sort by modification time (oldest first)
                cache_files.sort(key=lambda x: x[1])
                
                while total_size > max_size and cache_files:
                    filepath, _, size = cache_files.pop(0)
                    try:
                        os.remove(filepath)
                        total_size -= size
                        logger.debug(f"🗑️ Removed cache file: {filepath}")
                        
                        # Remove from download cache dict
                        for url, path in list(self.download_cache.items()):
                            if path == filepath:
                                del self.download_cache[url]
                                break
                                
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {filepath}: {e}")
                        
        except Exception as e:
            logger.warning(f"Cache trim error: {e}")
            
    def stop(self):
        """Stop media player and cleanup."""
        self.preload_running = False
        if self.preload_thread:
            self.preload_thread.join(timeout=1)
            
        self.is_playing = False
        logger.info("🛑 Media player stopped")
        
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache_size = 0
        try:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    cache_size += os.path.getsize(filepath)
        except:
            pass
            
        return {
            'memory_items': len(self.media_cache),
            'download_items': len(self.download_cache),
            'cache_size_mb': cache_size / (1024 * 1024),
            'preload_queue': len(self.preload_queue)
        }