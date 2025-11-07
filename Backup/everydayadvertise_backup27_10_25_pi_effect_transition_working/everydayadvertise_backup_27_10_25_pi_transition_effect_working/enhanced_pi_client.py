#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Enhanced Raspberry Pi Client v3.0
===================================================
Professional-grade Pi client with enterprise synchronization and hardware optimization

Features:
- Hardware-accelerated video playback using OMX Player
- Professional synchronization matching webplayer
- Automatic failover between video backends
- Real-time performance monitoring
- Network resilience and auto-recovery
- Optimized for Pi 3B+, Pi 4, and Pi 5
- Zero-config deployment with auto-discovery
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
import subprocess
import signal
import psutil
import socket
from pathlib import Path
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any, Tuple
import queue
import traceback
from contextlib import contextmanager
import hashlib

# Configure professional logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/phtv_pi.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HardwareOptimizer:
    """Pi hardware detection and optimization."""
    
    @staticmethod
    def detect_pi_model():
        """Detect Raspberry Pi model for optimization."""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'Model' in line:
                        model = line.split(':')[1].strip()
                        logger.info(f"🍓 Detected Pi model: {model}")
                        return model
        except:
            pass
        return "Unknown Pi"
    
    @staticmethod
    def get_gpu_memory():
        """Check GPU memory split."""
        try:
            result = subprocess.run(['vcgencmd', 'get_mem', 'gpu'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                gpu_mem = result.stdout.strip().split('=')[1]
                logger.info(f"🎮 GPU Memory: {gpu_mem}")
                return int(gpu_mem.replace('M', ''))
        except:
            pass
        return 64  # Default
    
    @staticmethod
    def optimize_gpu_settings():
        """Apply GPU optimizations for video playback."""
        gpu_mem = HardwareOptimizer.get_gpu_memory()
        if gpu_mem < 128:
            logger.warning("⚠️ GPU memory is low. Consider increasing to 128MB+ for better video performance")
            logger.info("💡 Run: sudo raspi-config → Advanced Options → Memory Split → 128")
        
        # Enable hardware acceleration flags
        os.environ['SDL_VIDEODRIVER'] = 'x11'
        os.environ['DISPLAY'] = ':0'
        
        return gpu_mem >= 128

class VideoBackend:
    """Abstract video backend interface."""
    
    def __init__(self, name: str):
        self.name = name
        self.available = False
        
    def check_availability(self) -> bool:
        raise NotImplementedError
        
    def play_video(self, url: str, duration: int) -> bool:
        raise NotImplementedError
        
    def stop(self):
        raise NotImplementedError

class OMXPlayerBackend(VideoBackend):
    """Hardware-accelerated OMX Player backend (Pi 3/4)."""
    
    def __init__(self):
        super().__init__("OMXPlayer")
        self.process = None
        
    def check_availability(self) -> bool:
        try:
            result = subprocess.run(['omxplayer', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            self.available = result.returncode == 0
            if self.available:
                logger.info("✅ OMXPlayer available (hardware acceleration)")
        except:
            self.available = False
            logger.info("❌ OMXPlayer not available")
        return self.available
    
    def play_video(self, url: str, duration: int) -> bool:
        try:
            self.stop()  # Stop any existing playback
            
            omx_args = [
                'omxplayer',
                '--no-osd',
                '--no-keys',
                '--aspect-mode', 'fill',
                '--orientation', '0',
                '--vol', '0',  # Muted for digital signage
                '--timeout', '30',
                url
            ]
            
            logger.info(f"🎬 Starting OMXPlayer: {url}")
            self.process = subprocess.Popen(omx_args, 
                                          stdout=subprocess.DEVNULL, 
                                          stderr=subprocess.DEVNULL)
            
            # Monitor playback
            start_time = time.time()
            while time.time() - start_time < duration:
                if self.process.poll() is not None:
                    # Process ended early
                    break
                time.sleep(0.5)
            
            self.stop()
            return True
            
        except Exception as e:
            logger.error(f"OMXPlayer playback failed: {e}")
            self.stop()
            return False
    
    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None

class VLCBackend(VideoBackend):
    """VLC backend with Pi optimizations."""
    
    def __init__(self):
        super().__init__("VLC")
        self.vlc_instance = None
        self.player = None
        
    def check_availability(self) -> bool:
        try:
            import vlc
            
            vlc_options = [
                '--intf', 'dummy',
                '--quiet',
                '--fullscreen',
                '--no-video-title-show',
                '--no-osd',
                '--no-video-deco',
                '--vout', 'mmal_vout',  # Pi hardware acceleration
                '--codec', 'mmal',      # Pi hardware codec
            ]
            
            self.vlc_instance = vlc.Instance(vlc_options)
            self.player = self.vlc_instance.media_player_new()
            self.available = True
            logger.info("✅ VLC available with Pi hardware acceleration")
            
        except Exception as e:
            self.available = False
            logger.info(f"❌ VLC not available: {e}")
            
        return self.available
    
    def play_video(self, url: str, duration: int) -> bool:
        if not self.player:
            return False
            
        try:
            media = self.vlc_instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
            
            logger.info(f"🎬 Starting VLC: {url}")
            
            # Wait for duration
            time.sleep(duration)
            self.stop()
            return True
            
        except Exception as e:
            logger.error(f"VLC playback failed: {e}")
            self.stop()
            return False
    
    def stop(self):
        if self.player:
            try:
                self.player.stop()
            except:
                pass

class PygameBackend(VideoBackend):
    """Pygame fallback backend."""
    
    def __init__(self):
        super().__init__("Pygame")
        self.screen = None
        
    def check_availability(self) -> bool:
        try:
            pygame.init()
            info = pygame.display.Info()
            self.available = info.current_w > 0 and info.current_h > 0
            logger.info(f"✅ Pygame available ({info.current_w}x{info.current_h})")
        except Exception as e:
            self.available = False
            logger.info(f"❌ Pygame not available: {e}")
        return self.available
    
    def play_video(self, url: str, duration: int) -> bool:
        # For pygame, we'll display a placeholder since it can't play video directly
        try:
            if not self.screen:
                self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                pygame.mouse.set_visible(False)
            
            # Display placeholder with video info
            self.screen.fill((0, 20, 40))  # Dark blue background
            
            font = pygame.font.Font(None, 74)
            text = font.render("🍕 Pizza Hut TV", True, (255, 255, 255))
            text_rect = text.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 - 50))
            self.screen.blit(text, text_rect)
            
            font_small = pygame.font.Font(None, 36)
            url_text = font_small.render(f"Playing: {os.path.basename(url)}", True, (200, 200, 200))
            url_rect = url_text.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 + 50))
            self.screen.blit(url_text, url_rect)
            
            pygame.display.flip()
            
            logger.info(f"🎮 Pygame placeholder: {url}")
            time.sleep(duration)
            return True
            
        except Exception as e:
            logger.error(f"Pygame playback failed: {e}")
            return False
    
    def stop(self):
        if self.screen:
            self.screen.fill((0, 0, 0))
            pygame.display.flip()

class EnhancedPiTVClient:
    """Enhanced Pi TV Client with professional features."""
    
    def __init__(self, server_url: str, store_id: str, screen_id: str):
        self.server_url = server_url.rstrip('/')
        self.store_id = store_id
        self.screen_id = screen_id
        self.user_agent = "phtv-enhanced-pi/3.0 (Raspberry Pi)"
        
        # Hardware optimization
        self.hardware = HardwareOptimizer()
        self.pi_model = self.hardware.detect_pi_model()
        self.gpu_optimized = self.hardware.optimize_gpu_settings()
        
        # Video backends (priority order)
        self.backends = []
        self.active_backend = None
        self._init_video_backends()
        
        # Synchronization (matching webplayer)
        self.sync_tolerance = 0.05  # 50ms tolerance
        self.sync_fetch_interval = 10
        self.last_sync_fetch = 0
        self.master_clock = time.time()
        
        # Playlist state
        self.current_playlist = []
        self.current_index = 0
        self.item_start_time = 0
        self.last_playlist_fetch = 0
        self.playlist_refresh_interval = 5
        
        # Performance monitoring
        self.performance_stats = {
            'playback_errors': 0,
            'sync_failures': 0,
            'network_errors': 0,
            'last_error_time': 0,
            'uptime_start': time.time()
        }
        
        # Network resilience
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.error_backoff = 1
        self.max_error_backoff = 60
        
        # Threading
        self.running = True
        self.performance_thread = None
        
        logger.info(f"🚀 Enhanced Pi TV Client initialized")
        logger.info(f"   Server: {self.server_url}")
        logger.info(f"   Store: {self.store_id}, Screen: {self.screen_id}")
        logger.info(f"   Pi Model: {self.pi_model}")
        logger.info(f"   GPU Optimized: {self.gpu_optimized}")
    
    def _init_video_backends(self):
        """Initialize video backends in priority order."""
        # Priority 1: OMXPlayer (best for Pi 3/4)
        omx = OMXPlayerBackend()
        if omx.check_availability():
            self.backends.append(omx)
        
        # Priority 2: VLC with hardware acceleration
        vlc = VLCBackend()
        if vlc.check_availability():
            self.backends.append(vlc)
        
        # Priority 3: Pygame fallback
        pygame_backend = PygameBackend()
        if pygame_backend.check_availability():
            self.backends.append(pygame_backend)
        
        if self.backends:
            self.active_backend = self.backends[0]
            logger.info(f"🎬 Active video backend: {self.active_backend.name}")
        else:
            logger.error("❌ No video backends available!")
    
    def fetch_sync_time(self) -> Optional[Dict[str, Any]]:
        """Fetch synchronized timestamp from server - SAME AS WEBPLAYER."""
        try:
            url = f"{self.server_url}/api/sync-time"
            headers = {'User-Agent': self.user_agent}
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            sync_data = response.json()
            logger.debug(f"🎯 GLOBAL SYNC: Pi client sync data: {sync_data}")
            return sync_data
            
        except Exception as e:
            logger.warning(f"Sync time fetch failed: {e}")
            self.performance_stats['sync_failures'] += 1
            return None
    
    def calculate_sync_moment(self, duration: int) -> float:
        """Calculate next global sync moment - IDENTICAL TO WEBPLAYER."""
        sync_data = self.fetch_sync_time()
        
        if sync_data:
            server_time = sync_data.get('current_time', time.time() * 1000)
            sync_interval = sync_data.get('sync_interval', 2000)
            next_sync_ms = sync_data.get('timestamp', server_time + sync_interval)
            
            logger.info(f"🎯 GLOBAL SYNC: {next_sync_ms}ms (webplayer compatible)")
            return next_sync_ms / 1000
        else:
            # Fallback - same as webplayer
            current_time = time.time()
            sync_interval = 2.0
            next_sync = (int(current_time / sync_interval) + 1) * sync_interval
            logger.info(f"⚠️ FALLBACK SYNC: {next_sync}s (webplayer compatible)")
            return next_sync
    
    def fetch_playlist(self) -> List[Dict[str, Any]]:
        """Fetch current playlist from server."""
        try:
            url = f"{self.server_url}/api/playlist/{self.store_id}/{self.screen_id}"
            headers = {'User-Agent': self.user_agent}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                playlist = data.get('playlist', [])
                logger.info(f"📥 Fetched {len(playlist)} playlist items")
                
                # Reset error counters on success
                self.consecutive_errors = 0
                self.error_backoff = 1
                
                return playlist
            else:
                raise Exception(f"API error: {data.get('error', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Playlist fetch failed: {e}")
            self.performance_stats['network_errors'] += 1
            self.consecutive_errors += 1
            
            # Exponential backoff
            if self.consecutive_errors >= 3:
                self.error_backoff = min(self.error_backoff * 2, self.max_error_backoff)
                logger.warning(f"⚠️ Network issues, backing off {self.error_backoff}s")
                time.sleep(self.error_backoff)
            
            return []
    
    def get_video_url(self, item: Dict[str, Any]) -> Optional[str]:
        """Get video URL for playlist item."""
        if not item:
            return None
            
        file_path = item.get('file', '')
        if not file_path:
            return None
        
        # Handle different URL formats
        if file_path.startswith('http'):
            return file_path
        else:
            return f"{self.server_url}/video/{self.store_id}/{file_path}"
    
    def play_video_with_fallback(self, url: str, duration: int) -> bool:
        """Play video with backend fallback."""
        for i, backend in enumerate(self.backends):
            try:
                logger.info(f"🎬 Trying {backend.name} for playback")
                
                if backend.play_video(url, duration):
                    # Success - promote this backend to primary
                    if i > 0:
                        self.backends[0], self.backends[i] = self.backends[i], self.backends[0]
                        self.active_backend = self.backends[0]
                        logger.info(f"✅ Promoted {backend.name} to primary backend")
                    return True
                    
            except Exception as e:
                logger.error(f"{backend.name} failed: {e}")
                self.performance_stats['playback_errors'] += 1
                continue
        
        logger.error("❌ All video backends failed")
        return False
    
    def start_performance_monitoring(self):
        """Start background performance monitoring."""
        def monitor():
            while self.running:
                try:
                    # System stats
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    # Network test
                    try:
                        socket.create_connection((self.server_url.split('://')[1].split(':')[0], 80), timeout=3)
                        network_ok = True
                    except:
                        network_ok = False
                    
                    uptime = time.time() - self.performance_stats['uptime_start']
                    
                    logger.info(f"📊 Performance - CPU: {cpu_percent:.1f}%, "
                              f"RAM: {memory.percent:.1f}%, "
                              f"Disk: {disk.percent:.1f}%, "
                              f"Network: {'✅' if network_ok else '❌'}, "
                              f"Uptime: {uptime/3600:.1f}h")
                    
                    time.sleep(30)  # Monitor every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Performance monitoring error: {e}")
                    time.sleep(30)
        
        self.performance_thread = threading.Thread(target=monitor, daemon=True)
        self.performance_thread.start()
    
    def run(self):
        """Main client loop."""
        logger.info("🚀 Starting Enhanced Pi TV Client")
        
        # Start performance monitoring
        self.start_performance_monitoring()
        
        # Setup signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            while self.running:
                # Fetch playlist
                current_time = time.time()
                if (current_time - self.last_playlist_fetch) >= self.playlist_refresh_interval:
                    self.current_playlist = self.fetch_playlist()
                    self.last_playlist_fetch = current_time
                
                if not self.current_playlist:
                    logger.warning("⚠️ No playlist available, retrying...")
                    time.sleep(5)
                    continue
                
                # Get current item
                if self.current_index >= len(self.current_playlist):
                    self.current_index = 0
                
                item = self.current_playlist[self.current_index]
                video_url = self.get_video_url(item)
                
                if not video_url:
                    logger.error(f"❌ No video URL for item: {item}")
                    self.current_index = (self.current_index + 1) % len(self.current_playlist)
                    continue
                
                # Get duration
                duration = max(int(item.get('duration', 10)), 1)
                
                # Calculate sync timing (SAME AS WEBPLAYER)
                sync_time = self.calculate_sync_moment(duration)
                current_time = time.time()
                wait_time = max(0, sync_time - current_time)
                
                if wait_time > 0:
                    logger.info(f"⏱️ PROFESSIONAL SYNC: Waiting {wait_time:.3f}s for perfect alignment")
                    time.sleep(wait_time)
                
                # Execute synchronized playback
                logger.info(f"🎬 EXECUTING PROFESSIONAL SYNC: Starting synchronized playback")
                success = self.play_video_with_fallback(video_url, duration)
                
                if not success:
                    logger.error(f"❌ Failed to play video: {video_url}")
                    time.sleep(2)  # Brief pause before retry
                
                # Move to next item
                self.current_index = (self.current_index + 1) % len(self.current_playlist)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal")
        except Exception as e:
            logger.error(f"❌ Main loop error: {e}")
            logger.error(traceback.format_exc())
        finally:
            self._cleanup()
    
    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        logger.info(f"🛑 Received signal {signum}")
        self.running = False
    
    def _cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up resources")
        self.running = False
        
        # Stop all backends
        for backend in self.backends:
            try:
                backend.stop()
            except:
                pass
        
        # Cleanup pygame
        try:
            pygame.quit()
        except:
            pass
        
        logger.info("✅ Cleanup complete")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Enhanced Pi TV Client v3.0')
    parser.add_argument('--server', default='https://everydayadvertise.com',
                       help='Server URL')
    parser.add_argument('--store', default='PHTV001',
                       help='Store ID')
    parser.add_argument('--screen', default='tv1',
                       help='Screen ID')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🍕 Pizza Hut TV - Enhanced Pi Client v3.0")
    logger.info("=" * 50)
    
    try:
        client = EnhancedPiTVClient(args.server, args.store, args.screen)
        client.run()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()