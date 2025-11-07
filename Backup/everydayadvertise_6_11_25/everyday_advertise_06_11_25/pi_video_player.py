#!/usr/bin/env python3
"""
🎬 Raspberry Pi Video Player for Complete Pi Client
Custom video player using OMXPlayer or VLC for hardware-accelerated playback
"""

import os
import subprocess
import threading
import time
import logging
from typing import Optional
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

class PiVideoPlayer:
    """Hardware-accelerated video player for Raspberry Pi."""
    
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.current_process = None
        self.is_playing = False
        self.current_url = None
        self.cache_dir = Path("/tmp/pizza_hut_tv_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Detect available player
        self.player_type = self._detect_player()
        logger.info(f"🎬 Pi Video Player initialized using {self.player_type}: {width}x{height}")
        
    def _detect_player(self) -> str:
        """Detect which video player is available."""
        # Check for omxplayer (best for Pi)
        try:
            result = subprocess.run(['which', 'omxplayer'], capture_output=True, timeout=2)
            if result.returncode == 0:
                return 'omxplayer'
        except:
            pass
            
        # Check for vlc
        try:
            result = subprocess.run(['which', 'cvlc'], capture_output=True, timeout=2)
            if result.returncode == 0:
                return 'vlc'
        except:
            pass
            
        # Check for mpv
        try:
            result = subprocess.run(['which', 'mpv'], capture_output=True, timeout=2)
            if result.returncode == 0:
                return 'mpv'
        except:
            pass
            
        logger.warning("⚠️ No video player found, using fallback")
        return 'none'
        
    def play_video(self, url: str, duration: float = 10.0) -> bool:
        """Play a video from URL."""
        try:
            # Stop any currently playing video
            self.stop()
            
            logger.info(f"🎬 Playing video: {url}")
            self.current_url = url
            
            # Download video to cache if it's a URL
            local_path = self._get_cached_video(url)
            
            if not local_path:
                logger.error(f"❌ Failed to get video: {url}")
                return False
                
            # Play based on available player
            if self.player_type == 'omxplayer':
                success = self._play_omxplayer(local_path, duration)
            elif self.player_type == 'vlc':
                success = self._play_vlc(local_path, duration)
            elif self.player_type == 'mpv':
                success = self._play_mpv(local_path, duration)
            else:
                logger.warning("⚠️ No video player available")
                return False
                
            if success:
                self.is_playing = True
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Video playback error: {e}")
            return False
            
    def _get_cached_video(self, url: str) -> Optional[str]:
        """Download video to cache or return cached path."""
        try:
            # Generate cache filename from URL
            filename = url.split('/')[-1]
            if not filename:
                filename = f"video_{hash(url)}.mp4"
                
            cache_path = self.cache_dir / filename
            
            # Return if already cached
            if cache_path.exists():
                logger.info(f"✅ Using cached video: {cache_path}")
                return str(cache_path)
                
            # Download video
            logger.info(f"📥 Downloading video: {url}")
            response = requests.get(url, stream=True, timeout=30)
            
            if response.status_code == 200:
                with open(cache_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                logger.info(f"✅ Downloaded to cache: {cache_path}")
                return str(cache_path)
            else:
                logger.error(f"❌ Failed to download video: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Cache error: {e}")
            return None
            
    def _play_omxplayer(self, video_path: str, duration: float) -> bool:
        """Play video using OMXPlayer (best for Raspberry Pi)."""
        try:
            cmd = [
                'omxplayer',
                '--no-osd',           # No on-screen display
                '--blank',            # Blank screen before playing
                '--loop',             # Loop video if shorter than duration
                '--aspect-mode', 'fill',  # Fill screen
                '--no-keys',          # Disable keyboard
                '--orientation', '0', # Normal orientation
                video_path
            ]
            
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info(f"✅ OMXPlayer started (PID: {self.current_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ OMXPlayer error: {e}")
            return False
            
    def _play_vlc(self, video_path: str, duration: float) -> bool:
        """Play video using VLC."""
        try:
            cmd = [
                'cvlc',
                '--play-and-exit',
                '--fullscreen',
                '--no-video-title-show',
                '--no-osd',
                '--loop',
                video_path
            ]
            
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info(f"✅ VLC started (PID: {self.current_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ VLC error: {e}")
            return False
            
    def _play_mpv(self, video_path: str, duration: float) -> bool:
        """Play video using MPV."""
        try:
            cmd = [
                'mpv',
                '--fullscreen',
                '--loop=inf',
                '--no-osc',
                '--no-osd-bar',
                video_path
            ]
            
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info(f"✅ MPV started (PID: {self.current_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ MPV error: {e}")
            return False
            
    def stop(self):
        """Stop currently playing video."""
        if self.current_process:
            try:
                self.current_process.terminate()
                time.sleep(0.1)
                if self.current_process.poll() is None:
                    self.current_process.kill()
                logger.info("🛑 Video stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping video: {e}")
            finally:
                self.current_process = None
                
        self.is_playing = False
        self.current_url = None
        
    def cleanup_cache(self, max_size_mb: int = 500):
        """Clean up old cache files if cache size exceeds limit."""
        try:
            total_size = 0
            files = []
            
            # Get all cached files with their sizes
            for file in self.cache_dir.glob('*'):
                if file.is_file():
                    size = file.stat().st_size
                    total_size += size
                    files.append((file, size, file.stat().st_mtime))
                    
            # If over limit, delete oldest files
            if total_size > max_size_mb * 1024 * 1024:
                logger.info(f"🧹 Cache size {total_size / 1024 / 1024:.1f}MB exceeds {max_size_mb}MB, cleaning...")
                files.sort(key=lambda x: x[2])  # Sort by modification time
                
                while total_size > max_size_mb * 1024 * 1024 * 0.8 and files:
                    file, size, _ = files.pop(0)
                    file.unlink()
                    total_size -= size
                    logger.info(f"🗑️ Deleted: {file.name}")
                    
        except Exception as e:
            logger.error(f"❌ Cache cleanup error: {e}")
            
    def __del__(self):
        """Cleanup on deletion."""
        self.stop()
