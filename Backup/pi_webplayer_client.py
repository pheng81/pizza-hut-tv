#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Pi Webplayer Client
Exact replica of webplayer functionality for Raspberry Pi
Matches webplayer API calls, timing, and behavior
"""

import pygame
import requests
import json
import time
import threading
import logging
import argparse
import sys
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PlaylistItem:
    """Represents a playlist item from the server."""
    id: str
    url: str
    file: str
    duration: float
    effect: str = "fade"
    media_type: str = "video"
    slice_aware: bool = False
    slice_url: Optional[str] = None
    sync_ref: Optional[Dict] = None

class ServerTimeSync:
    """Handles server time synchronization like webplayer."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.server_offset = 0.0
        self.last_sync = 0
        self.network_latency = 0.0
        self.sync_samples = []
        
    async def sync_time(self) -> float:
        """Sync with server time using multiple samples."""
        samples = []
        
        for attempt in range(3):
            try:
                start_time = time.time()
                response = requests.get(f"{self.server_url}/api/server_time", timeout=5)
                request_latency = (time.time() - start_time) * 1000  # ms
                
                if response.status_code == 200:
                    data = response.json()
                    client_time = time.time() * 1000  # ms
                    server_time = data['server_time_ms']
                    
                    # Compensate for network latency
                    adjusted_server_time = server_time + (request_latency / 2)
                    offset = adjusted_server_time - client_time
                    
                    samples.append({
                        'offset': offset,
                        'latency': request_latency,
                        'timestamp': client_time
                    })
                    
                    logger.info(f"🌐 SERVER TIME SAMPLE {attempt + 1}: offset={offset:.3f}ms, latency={request_latency:.1f}ms")
                    
            except Exception as e:
                logger.warn(f"Server time sync attempt {attempt + 1} failed: {e}")
                
        if samples:
            # Use median offset for better accuracy
            offsets = sorted([s['offset'] for s in samples])
            median_offset = offsets[len(offsets) // 2]
            avg_latency = sum(s['latency'] for s in samples) / len(samples)
            
            self.server_offset = median_offset
            self.network_latency = avg_latency
            self.last_sync = time.time()
            
            # Store samples for trend analysis
            self.sync_samples.append({
                'offset': median_offset,
                'latency': avg_latency,
                'timestamp': self.last_sync
            })
            
            # Keep only last 10 samples
            if len(self.sync_samples) > 10:
                self.sync_samples = self.sync_samples[-10:]
                
            logger.info(f"🌐 FINAL SERVER TIME SYNC: offset={median_offset:.3f}ms, latency={avg_latency:.1f}ms")
            return time.time() * 1000 + median_offset
            
        return time.time() * 1000  # Fallback to local time
        
    def get_server_time(self) -> float:
        """Get current server-synchronized time."""
        client_time = time.time() * 1000
        
        # Re-sync if needed (every 15 seconds like webplayer)
        if client_time - (self.last_sync * 1000) > 15000:
            threading.Thread(target=self.sync_time, daemon=True).start()
            
        return client_time + self.server_offset

class MediaCache:
    """Aggressive media caching like webplayer preloader."""
    
    def __init__(self, max_cache_size: int = 6):
        self.cache = {}  # url -> {'surface': surface, 'timestamp': time, 'type': 'video/image'}
        self.max_cache_size = max_cache_size
        
    def put(self, url: str, surface: pygame.Surface, media_type: str):
        """Add item to cache."""
        self.cache[url] = {
            'surface': surface,
            'timestamp': time.time(),
            'type': media_type
        }
        self._trim_cache()
        
    def get(self, url: str) -> Optional[pygame.Surface]:
        """Get item from cache."""
        item = self.cache.get(url)
        if item:
            item['timestamp'] = time.time()  # Update access time
            return item['surface']
        return None
        
    def _trim_cache(self):
        """Remove oldest items when cache is full."""
        if len(self.cache) <= self.max_cache_size:
            return
            
        # Sort by timestamp and remove oldest
        items = list(self.cache.items())
        items.sort(key=lambda x: x[1]['timestamp'])
        
        while len(self.cache) > self.max_cache_size:
            url, _ = items.pop(0)
            del self.cache[url]

class PiWebplayerClient:
    """Main Pi client that replicates webplayer functionality."""
    
    def __init__(self, server_url: str = "https://everydayadvertise.com"):
        # Core settings
        self.server_url = server_url.rstrip('/')
        self.store_id = ""
        self.screen_id = ""
        self.pair_code = ""
        
        # Initialize pygame
        pygame.init()
        self.screen_info = pygame.display.Info()
        self.width = self.screen_info.current_w
        self.height = self.screen_info.current_h
        
        # Create fullscreen display
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
        pygame.display.set_caption("Pizza Hut TV - Pi Client")
        pygame.mouse.set_visible(False)
        
        # Colors matching webplayer exactly
        self.colors = {
            'pizza_red': (227, 24, 55),      # #e31837
            'pizza_red_dark': (196, 30, 58), # #c41e3a  
            'gold': (255, 215, 0),           # #ffd700
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'container_bg': (0, 0, 0, 76),   # rgba(0,0,0,0.3) -> alpha 76
            'light_gray': (200, 200, 200),
            'input_bg': (255, 255, 255, 25)  # rgba(255,255,255,0.1)
        }
        
        # Fonts matching webplayer sizes
        try:
            self.font_logo = pygame.font.Font(None, 72)      # 48px scaled up
            self.font_large = pygame.font.Font(None, 48)     # 24px scaled up  
            self.font_medium = pygame.font.Font(None, 36)    # 18px scaled up
            self.font_small = pygame.font.Font(None, 24)     # 14px scaled up
        except:
            # Fallback to system font
            self.font_logo = pygame.font.SysFont('arial', 72, bold=True)
            self.font_large = pygame.font.SysFont('arial', 48)
            self.font_medium = pygame.font.SysFont('arial', 36)
            self.font_small = pygame.font.SysFont('arial', 24)
        
        # State management like webplayer
        self.current_state = "setup"  # setup, playing, error
        self.input_text = ""
        self.available_stores = []
        self.selected_store = None
        self.setup_step = "code"  # code, store, screen
        
        # Playback state
        self.playlist = []
        self.current_index = 0
        self.last_playlist_fetch = 0
        self.playlist_signature = ""
        self.current_item_key = ""
        
        # Timing like webplayer
        self.PLAYLIST_REFRESH_MIN_MS = 3000
        self.COMMANDS_POLL_MS = 1500
        self.PLAYLIST_REFRESH_INTERVAL_MS = 10000
        
        # Components
        self.time_sync = ServerTimeSync(self.server_url)
        self.media_cache = MediaCache()
        
        # Threading
        self.running = True
        self.playback_thread = None
        self.heartbeat_thread = None
        
        logger.info(f"🍕 Pi Webplayer Client initialized: {self.width}x{self.height}")
        
    def create_gradient_background(self) -> pygame.Surface:
        """Create Pizza Hut gradient background like webplayer."""
        background = pygame.Surface((self.width, self.height))
        
        # Linear gradient from pizza_red to pizza_red_dark (135deg approximation)
        for y in range(self.height):
            for x in range(self.width):
                # Calculate gradient progress (0.0 to 1.0)
                progress = (x + y) / (self.width + self.height)
                progress = max(0.0, min(1.0, progress))
                
                # Interpolate between colors
                r = int(self.colors['pizza_red'][0] * (1 - progress) + self.colors['pizza_red_dark'][0] * progress)
                g = int(self.colors['pizza_red'][1] * (1 - progress) + self.colors['pizza_red_dark'][1] * progress)
                b = int(self.colors['pizza_red'][2] * (1 - progress) + self.colors['pizza_red_dark'][2] * progress)
                
                background.set_at((x, y), (r, g, b))
                
        return background
        
    def create_container_surface(self, width: int, height: int) -> pygame.Surface:
        """Create container with background matching webplayer."""
        container = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Semi-transparent black background
        container.fill((0, 0, 0, 76))  # rgba(0,0,0,0.3)
        
        # Add border radius effect (simple corner rounding)
        corner_radius = 20
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, width, height), border_radius=corner_radius)
        
        result = pygame.Surface((width, height), pygame.SRCALPHA)
        result.blit(container, (0, 0))
        result.blit(mask, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        return result
        
    def draw_setup_screen(self):
        """Draw setup screen matching webplayer design exactly."""
        # Clear with gradient background
        background = self.create_gradient_background()
        self.screen.blit(background, (0, 0))
        
        # Container dimensions
        container_width = 600
        container_height = 500
        container_x = (self.width - container_width) // 2
        container_y = (self.height - container_height) // 2
        
        # Draw container
        container = self.create_container_surface(container_width, container_height)
        self.screen.blit(container, (container_x, container_y))
        
        # Logo
        logo_text = self.font_logo.render("🍕 PIZZA HUT TV", True, self.colors['white'])
        logo_rect = logo_text.get_rect(center=(self.width // 2, container_y + 80))
        self.screen.blit(logo_text, logo_rect)
        
        if self.setup_step == "code":
            self.draw_code_input_screen(container_x, container_y, container_width)
        elif self.setup_step == "store":
            self.draw_store_selection_screen(container_x, container_y, container_width)
        elif self.setup_step == "screen":
            self.draw_screen_selection_screen(container_x, container_y, container_width)
            
    def draw_code_input_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw 4-digit code input screen."""
        # Subtitle
        subtitle = self.font_medium.render("Connect to Android TV", True, self.colors['white'])
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Label
        label = self.font_medium.render("Enter 4-Digit TV Link Code:", True, self.colors['white'])
        label_rect = label.get_rect(center=(self.width // 2, container_y + 200))
        self.screen.blit(label, label_rect)
        
        # Input field with exact webplayer styling
        input_width = 300
        input_height = 60
        input_x = (self.width - input_width) // 2
        input_y = container_y + 240
        
        # Input background
        input_bg = pygame.Surface((input_width, input_height), pygame.SRCALPHA)
        input_bg.fill((255, 255, 255, 25))  # rgba(255,255,255,0.1)
        pygame.draw.rect(input_bg, self.colors['white'], (0, 0, input_width, input_height), 3, border_radius=10)
        self.screen.blit(input_bg, (input_x, input_y))
        
        # Input text with letter spacing like webplayer
        display_text = self.input_text.ljust(4, "_")  # Show underscores for empty positions
        spaced_text = "  ".join(display_text)  # Add spacing between characters
        
        input_text_surface = self.font_large.render(spaced_text, True, self.colors['white'])
        text_rect = input_text_surface.get_rect(center=(input_x + input_width // 2, input_y + input_height // 2))
        self.screen.blit(input_text_surface, text_rect)
        
        # Connect button
        self.draw_connect_button(container_y + 340)
        
        # Instructions
        instructions = [
            "1. Find the 4-digit code displayed on your Android TV",
            "2. Enter the code above to connect", 
            "3. Select your store and screen"
        ]
        
        for i, instruction in enumerate(instructions):
            inst_text = self.font_small.render(instruction, True, self.colors['light_gray'])
            inst_rect = inst_text.get_rect(center=(self.width // 2, container_y + 400 + i * 25))
            self.screen.blit(inst_text, inst_rect)
            
    def draw_connect_button(self, y_pos: int):
        """Draw connect button with webplayer styling."""
        button_width = 200
        button_height = 50
        button_x = (self.width - button_width) // 2
        
        # Button enabled/disabled state
        enabled = len(self.input_text) == 4 and self.input_text.isdigit()
        bg_color = self.colors['gold'] if enabled else (102, 102, 102)
        text_color = self.colors['pizza_red'] if enabled else (153, 153, 153)
        
        # Draw button
        pygame.draw.rect(self.screen, bg_color, (button_x, y_pos, button_width, button_height), border_radius=10)
        
        # Button text
        button_text = self.font_medium.render("CONNECT TO TV", True, text_color)
        text_rect = button_text.get_rect(center=(button_x + button_width // 2, y_pos + button_height // 2))
        self.screen.blit(button_text, text_rect)
        
    def draw_store_selection_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw store selection screen."""
        # Title
        title = self.font_large.render("Select Store", True, self.colors['white'])
        title_rect = title.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(title, title_rect)
        
        # Store list
        start_y = container_y + 200
        for i, store in enumerate(self.available_stores[:5]):  # Show max 5 stores
            store_y = start_y + i * 50
            
            # Store button
            button_width = container_width - 60
            button_height = 40
            button_x = container_x + 30
            
            # Highlight selected store
            bg_color = self.colors['gold'] if i == self.selected_store else (50, 50, 50)
            text_color = self.colors['pizza_red'] if i == self.selected_store else self.colors['white']
            
            pygame.draw.rect(self.screen, bg_color, (button_x, store_y, button_width, button_height), border_radius=5)
            
            # Store text
            store_name = store.get('store_name', f"Store {store.get('store_id', 'Unknown')}")
            store_text = self.font_medium.render(store_name, True, text_color)
            text_rect = store_text.get_rect(center=(button_x + button_width // 2, store_y + button_height // 2))
            self.screen.blit(store_text, text_rect)
            
    def draw_screen_selection_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw screen selection screen."""
        # Title
        title = self.font_large.render("Select Screen", True, self.colors['white'])
        title_rect = title.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(title, title_rect)
        
        # Screen options
        screens = ["tv1", "tv2", "tv3", "tv4"]
        start_y = container_y + 200
        
        for i, screen in enumerate(screens):
            screen_y = start_y + i * 50
            
            # Screen button
            button_width = container_width - 60
            button_height = 40
            button_x = container_x + 30
            
            bg_color = (50, 50, 50)
            pygame.draw.rect(self.screen, bg_color, (button_x, screen_y, button_width, button_height), border_radius=5)
            
            # Screen text
            screen_text = self.font_medium.render(f"Screen {screen.upper()}", True, self.colors['white'])
            text_rect = screen_text.get_rect(center=(button_x + button_width // 2, screen_y + button_height // 2))
            self.screen.blit(screen_text, text_rect)
            
    def draw_playing_screen(self):
        """Draw playing screen with current media."""
        # Fill with black background during playback
        self.screen.fill(self.colors['black'])
        
        if self.playlist and self.current_index < len(self.playlist):
            current_item = self.playlist[self.current_index]
            
            # Try to get media from cache
            media_url = self.get_media_url(current_item)
            cached_surface = self.media_cache.get(media_url)
            
            if cached_surface:
                # Scale to fit screen while maintaining aspect ratio
                scaled_surface = pygame.transform.scale(cached_surface, (self.width, self.height))
                self.screen.blit(scaled_surface, (0, 0))
            else:
                # Show loading message
                loading_text = self.font_large.render("Loading media...", True, self.colors['white'])
                loading_rect = loading_text.get_rect(center=(self.width // 2, self.height // 2))
                self.screen.blit(loading_text, loading_rect)
                
        else:
            # Show idle message like webplayer
            idle_text = self.font_large.render("Waiting for schedule...", True, self.colors['white'])
            idle_rect = idle_text.get_rect(center=(self.width // 2, self.height // 2))
            self.screen.blit(idle_text, idle_rect)
            
        # Overlay info
        self.draw_overlay_info()
        
    def draw_overlay_info(self):
        """Draw overlay information like webplayer."""
        info_text = f"Store {self.store_id} • Screen {self.screen_id}"
        if self.playlist:
            info_text += f" • Item {self.current_index + 1}/{len(self.playlist)}"
            
        overlay = self.font_small.render(info_text, True, (154, 167, 255, 56))  # Low opacity like webplayer
        self.screen.blit(overlay, (10, self.height - 30))
        
    def get_media_url(self, item: PlaylistItem) -> str:
        """Get media URL for playlist item like webplayer."""
        if hasattr(item, 'slice_url') and item.slice_url:
            return item.slice_url
            
        url = getattr(item, 'url', '') or getattr(item, 'file', '')
        if url.startswith('http'):
            return url
            
        # Construct full URL
        filename = url.lstrip('/')
        is_video = any(filename.lower().endswith(ext) for ext in ['.mp4', '.webm', '.ogg', '.mov', '.avi'])
        endpoint = 'media' if is_video else 'static/uploads'
        
        return f"{self.server_url}/{endpoint}/{filename}"
        
    async def fetch_playlist(self) -> List[Dict]:
        """Fetch playlist from server like webplayer."""
        try:
            url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            if self.pair_code:
                url += f"?user_code={self.pair_code}"
                
            headers = {}
            if self.pair_code:
                headers['X-User-Code'] = self.pair_code
                
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('playlist'):
                    logger.info(f"📥 Fetched {len(data['playlist'])} playlist items")
                    return data['playlist']
                    
        except Exception as e:
            logger.error(f"Playlist fetch failed: {e}")
            
        return []
        
    async def send_heartbeat(self):
        """Send heartbeat to server like webplayer."""
        try:
            params = {
                'store_id': self.store_id,
                'screen_id': self.screen_id
            }
            if self.pair_code:
                params['user_code'] = self.pair_code
                
            headers = {}
            if self.pair_code:
                headers['X-User-Code'] = self.pair_code
                
            response = requests.get(
                f"{self.server_url}/api/screen_heartbeat",
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.debug("💓 Heartbeat sent successfully")
                
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")
            
    async def validate_tv_code(self, code: str) -> List[Dict]:
        """Validate TV code and get available stores."""
        try:
            response = requests.get(f"{self.server_url}/api/stores_by_code/{code}", timeout=10)
            
            if response.status_code == 200:
                stores = response.json()
                logger.info(f"✅ Valid TV code: {len(stores)} stores available")
                return stores
            else:
                logger.warning(f"❌ Invalid TV code: {code}")
                return []
                
        except Exception as e:
            logger.error(f"TV code validation failed: {e}")
            return []
            
    def handle_keydown(self, event):
        """Handle keyboard input."""
        if self.current_state == "setup":
            if self.setup_step == "code":
                if event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if len(self.input_text) == 4 and self.input_text.isdigit():
                        self.handle_code_submit()
                elif event.unicode.isdigit() and len(self.input_text) < 4:
                    self.input_text += event.unicode
                    
            elif self.setup_step == "store":
                if event.key == pygame.K_UP:
                    self.selected_store = max(0, (self.selected_store or 0) - 1)
                elif event.key == pygame.K_DOWN:
                    max_store = min(4, len(self.available_stores) - 1)
                    self.selected_store = min(max_store, (self.selected_store or 0) + 1)
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    self.handle_store_select()
                    
            elif self.setup_step == "screen":
                if event.key in [pygame.K_1, pygame.K_KP1]:
                    self.handle_screen_select("tv1")
                elif event.key in [pygame.K_2, pygame.K_KP2]:
                    self.handle_screen_select("tv2")
                elif event.key in [pygame.K_3, pygame.K_KP3]:
                    self.handle_screen_select("tv3")
                elif event.key in [pygame.K_4, pygame.K_KP4]:
                    self.handle_screen_select("tv4")
                    
        # Global keys
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            
    def handle_code_submit(self):
        """Handle TV code submission."""
        logger.info(f"🔍 Validating TV code: {self.input_text}")
        
        # Validate code in separate thread to avoid blocking
        def validate_code():
            stores = []
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stores = loop.run_until_complete(self.validate_tv_code(self.input_text))
                loop.close()
            except Exception as e:
                logger.error(f"Code validation error: {e}")
                
            if stores:
                self.available_stores = stores
                self.pair_code = self.input_text
                self.setup_step = "store"
                self.selected_store = 0
                logger.info("✅ Moving to store selection")
            else:
                logger.warning("❌ Invalid code, staying on code input")
                self.input_text = ""  # Clear invalid code
                
        threading.Thread(target=validate_code, daemon=True).start()
        
    def handle_store_select(self):
        """Handle store selection."""
        if self.selected_store is not None and self.selected_store < len(self.available_stores):
            store = self.available_stores[self.selected_store]
            self.store_id = store.get('store_id', '')
            logger.info(f"✅ Selected store: {self.store_id}")
            self.setup_step = "screen"
            
    def handle_screen_select(self, screen_id: str):
        """Handle screen selection."""
        self.screen_id = screen_id
        logger.info(f"✅ Selected screen: {screen_id}")
        logger.info(f"🚀 Starting playback mode...")
        
        # Start playback mode
        self.current_state = "playing"
        self.start_playback_services()
        
    def start_playback_services(self):
        """Start background services for playback."""
        # Start time synchronization
        def sync_loop():
            while self.running:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.time_sync.sync_time())
                    loop.close()
                except Exception as e:
                    logger.warning(f"Time sync error: {e}")
                time.sleep(15)  # Sync every 15 seconds like webplayer
                
        # Start heartbeat
        def heartbeat_loop():
            while self.running:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.send_heartbeat())
                    loop.close()
                except Exception as e:
                    logger.warning(f"Heartbeat error: {e}")
                time.sleep(30)  # Every 30 seconds like webplayer
                
        # Start playlist updates
        def playlist_loop():
            while self.running:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    new_playlist = loop.run_until_complete(self.fetch_playlist())
                    loop.close()
                    
                    if new_playlist:
                        self.playlist = new_playlist
                        logger.info(f"📋 Updated playlist: {len(new_playlist)} items")
                        
                except Exception as e:
                    logger.warning(f"Playlist update error: {e}")
                    
                time.sleep(10)  # Every 10 seconds like webplayer
                
        # Start threads
        threading.Thread(target=sync_loop, daemon=True).start()
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=playlist_loop, daemon=True).start()
        
        logger.info("🎬 All playback services started")
        
    def run(self):
        """Main event loop."""
        clock = pygame.time.Clock()
        logger.info("🍕 Starting Pizza Hut TV Pi Client")
        
        # Initial server time sync
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.time_sync.sync_time())
            loop.close()
            logger.info("🌐 Initial server time sync completed")
        except Exception as e:
            logger.warning(f"Initial time sync failed: {e}")
            
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event)
                    
            # Draw current screen
            if self.current_state == "setup":
                self.draw_setup_screen()
            elif self.current_state == "playing":
                self.draw_playing_screen()
                
            # Update display
            pygame.display.flip()
            clock.tick(60)  # 60 FPS for smooth UI
            
        logger.info("🛑 Shutting down Pi Client")
        pygame.quit()
        
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pizza Hut TV Pi Webplayer Client")
    parser.add_argument("--server", default="https://everydayadvertise.com", 
                       help="Server URL (default: https://everydayadvertise.com)")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Create and run client
    client = PiWebplayerClient(server_url=args.server)
    
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()