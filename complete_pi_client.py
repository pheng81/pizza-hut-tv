#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Complete Pi Webplayer Client
Full webplayer functionality with media playback and synchronization
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
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
import hashlib

# Import our media player
from media_player import MediaPlayer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PlaylistItem:
    """Playlist item matching webplayer structure."""
    id: Optional[str] = None
    url: Optional[str] = None
    file: Optional[str] = None
    duration: float = 10.0
    effect: str = "fade"
    media_type: str = "video"
    slice_aware: bool = False
    slice_url: Optional[str] = None
    sync_ref: Optional[Dict] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PlaylistItem':
        """Create PlaylistItem from server data."""
        return cls(
            id=str(data.get('id', '')),
            url=data.get('url', ''),
            file=data.get('file', ''),
            duration=float(data.get('duration', 10.0)),
            effect=data.get('effect', 'fade'),
            media_type=data.get('media_type', 'video'),
            slice_aware=bool(data.get('slice_aware', False)),
            slice_url=data.get('slice_url'),
            sync_ref=data.get('sync_ref')
        )

class ServerTimeSync:
    """Server time synchronization like webplayer."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.server_offset = 0.0
        self.last_sync = 0
        self.network_latency = 0.0
        self.sync_samples = []
        
    def sync_time(self) -> float:
        """Sync with server time using multiple samples."""
        samples = []
        
        for attempt in range(3):
            try:
                start_time = time.time()
                response = requests.get(
                    f"{self.server_url}/api/server_time", 
                    timeout=5,
                    headers={'Cache-Control': 'no-cache'}
                )
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
                    
                    logger.debug(f"🌐 SERVER TIME SAMPLE {attempt + 1}: offset={offset:.3f}ms, latency={request_latency:.1f}ms")
                    
            except Exception as e:
                logger.warning(f"Server time sync attempt {attempt + 1} failed: {e}")
                
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
                
            logger.info(f"🌐 SERVER TIME SYNC: offset={median_offset:.3f}ms, latency={avg_latency:.1f}ms")
            return time.time() * 1000 + median_offset
            
        return time.time() * 1000  # Fallback to local time
        
    def get_server_time(self) -> float:
        """Get current server-synchronized time."""
        client_time = time.time() * 1000
        
        # Re-sync if needed (every 15 seconds like webplayer)
        if client_time - (self.last_sync * 1000) > 15000:
            threading.Thread(target=self.sync_time, daemon=True).start()
            
        return client_time + self.server_offset

class CompleteWebplayerClient:
    """Complete Pi client with full webplayer functionality."""
    
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
        pygame.display.set_caption("Pizza Hut TV - Complete Pi Client")
        pygame.mouse.set_visible(False)
        
        # Colors matching custom_player.py dark theme EXACTLY
        self.colors = {
            'background': (13, 13, 13),           # #0d0d0d - main background
            'pizza_red': (200, 16, 46),           # #c8102e - primary red (EA TV branding)
            'pizza_red_hover': (160, 13, 36),     # #a00d24 - hover/active state
            'white': (255, 255, 255),             # #ffffff - primary text
            'light_gray': (244, 244, 244),        # #f4f4f4 - title text
            'medium_gray': (204, 204, 204),       # #cccccc - label text
            'gray': (187, 187, 187),              # #bbbbbb - subtitle text
            'dark_gray': (153, 153, 153),         # #999999 - status text
            'input_bg': (0, 0, 0),                # #000000 - input background
            'input_border': (51, 51, 51),         # #333333 - input border
            'input_border_focus': (200, 16, 46),  # #c8102e - input border on focus
            'success': (0, 255, 0),               # #00ff00 - success messages
            'error': (255, 68, 68)                # #ff4444 - error messages
        }
        
        # Fonts matching custom_player.py (Arial, similar sizes)
        # Tkinter pt to Pygame px conversion: ~1.4x multiplier
        try:
            self.font_title = pygame.font.Font(None, 28)      # Title: 20pt Tkinter → 28px Pygame
            self.font_subtitle = pygame.font.Font(None, 18)   # Subtitle: 12pt Tkinter → 18px Pygame
            self.font_label = pygame.font.Font(None, 16)      # Label: 11pt Tkinter → 16px Pygame
            self.font_input = pygame.font.Font(None, 22)      # Input: 14pt Tkinter → 22px Pygame (bold)
            self.font_button = pygame.font.Font(None, 18)     # Button: 12pt Tkinter → 18px Pygame (bold)
            self.font_small = pygame.font.Font(None, 14)      # Small text: 10pt Tkinter → 14px Pygame
        except:
            self.font_title = pygame.font.SysFont('arial', 28, bold=True)
            self.font_subtitle = pygame.font.SysFont('arial', 18)
            self.font_label = pygame.font.SysFont('arial', 16)
            self.font_input = pygame.font.SysFont('arial', 22, bold=True)
            self.font_button = pygame.font.SysFont('arial', 18, bold=True)
            self.font_small = pygame.font.SysFont('arial', 14)
        
        # State management
        self.current_state = "setup"  # setup, playing, error
        self.input_text = ""
        self.available_stores = []
        self.selected_store = None
        self.setup_step = "code"  # code, store, screen
        
        # Button position tracking for mouse clicks
        self.link_button_rect = None
        self.store_button_rects = []
        self.screen_button_rects = {}
        
        # Playback state like webplayer
        self.playlist = []
        self.current_index = 0
        self.last_playlist_fetch = 0
        self.playlist_signature = ""
        self.current_item_key = ""
        
        # Timing constants like webplayer
        self.PLAYLIST_REFRESH_MIN_MS = 3000
        self.COMMANDS_POLL_MS = 1500
        self.PLAYLIST_REFRESH_INTERVAL_MS = 10000
        self.PRELOAD_AHEAD = 4  # Preload next 4 items
        
        # Global effect synchronization
        self.current_global_effect = 'fade'
        
        # Components
        self.time_sync = ServerTimeSync(self.server_url)
        self.media_player = MediaPlayer(self.screen)
        
        # Threading
        self.running = True
        self.services_started = False
        
        logger.info(f"🍕 Complete Pi Webplayer Client initialized: {self.width}x{self.height}")
        
    def create_gradient_background(self) -> pygame.Surface:
        """Create solid dark background like custom_player.py (#0d0d0d)."""
        background = pygame.Surface((self.width, self.height))
        background.fill(self.colors['background'])  # Solid #0d0d0d
        return background
        
    def create_container_surface(self, width: int, height: int) -> pygame.Surface:
        """Create container with custom_player.py dark styling."""
        container = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Solid black background with padding (matching Tkinter panel)
        pygame.draw.rect(container, self.colors['background'], (0, 0, width, height), border_radius=8)
        
        # Subtle border
        pygame.draw.rect(container, (30, 30, 30), (0, 0, width, height), 2, border_radius=8)
        
        return container
        
    def draw_setup_screen(self):
        """Draw setup screen matching webplayer design."""
        background = self.create_gradient_background()
        self.screen.blit(background, (0, 0))
        
        container_width = 600
        container_height = 500
        container_x = (self.width - container_width) // 2
        container_y = (self.height - container_height) // 2
        
        container = self.create_container_surface(container_width, container_height)
        self.screen.blit(container, (container_x, container_y))
        
        # Title - matching custom_player.py style
        title_text = self.font_title.render("Enter your Android TV pairing code", True, self.colors['light_gray'])
        title_rect = title_text.get_rect(center=(self.width // 2, container_y + 60))
        self.screen.blit(title_text, title_rect)
        
        if self.setup_step == "code":
            self.draw_code_input_screen(container_x, container_y, container_width)
        elif self.setup_step == "store":
            self.draw_store_selection_screen(container_x, container_y, container_width)
        elif self.setup_step == "screen":
            self.draw_screen_selection_screen(container_x, container_y, container_width)
            
    def draw_code_input_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw 4-digit code input screen matching custom_player.py."""
        # Subtitle
        subtitle = self.font_subtitle.render("Type the 4-digit code from dashboard", True, self.colors['gray'])
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, container_y + 100))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Input label - LEFT ALIGNED like custom_player.py
        label = self.font_label.render("4-digit code", True, self.colors['medium_gray'])
        label_rect = label.get_rect(topleft=(container_x + 40, container_y + 150))
        self.screen.blit(label, label_rect)
        
        # Input field with custom_player.py styling
        input_width = 300
        input_height = 60
        input_x = (self.width - input_width) // 2
        input_y = container_y + 180
        
        # Black background with border
        pygame.draw.rect(self.screen, self.colors['input_bg'], (input_x, input_y, input_width, input_height), border_radius=8)
        border_color = self.colors['input_border_focus'] if len(self.input_text) > 0 else self.colors['input_border']
        pygame.draw.rect(self.screen, border_color, (input_x, input_y, input_width, input_height), 2, border_radius=8)
        
        # Input text centered
        display_text = self.input_text if self.input_text else "____"
        spaced_text = "  ".join(display_text)
        
        input_text_surface = self.font_input.render(spaced_text, True, self.colors['white'])
        text_rect = input_text_surface.get_rect(center=(input_x + input_width // 2, input_y + input_height // 2))
        self.screen.blit(input_text_surface, text_rect)
        
        # Link Code button
        self.draw_link_button(container_y + 280)
        
        # Status message
        if hasattr(self, 'status_message'):
            status_color = self.colors['success'] if 'accepted' in self.status_message else self.colors['error']
            status_text = self.font_small.render(self.status_message, True, status_color)
            status_rect = status_text.get_rect(center=(self.width // 2, container_y + 350))
            self.screen.blit(status_text, status_rect)
            
    def draw_link_button(self, y_pos: int):
        """Draw Link Code button matching custom_player.py style."""
        button_width = 200
        button_height = 50
        button_x = (self.width - button_width) // 2
        
        enabled = len(self.input_text) == 4 and self.input_text.isdigit()
        bg_color = self.colors['pizza_red'] if enabled else (102, 102, 102)
        text_color = self.colors['white']
        
        # Draw button with rounded corners
        button_rect = pygame.Rect(button_x, y_pos, button_width, button_height)
        pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=8)
        
        # Store button rect for click detection
        self.link_button_rect = button_rect if enabled else None
        
        button_text = self.font_button.render("Link Code", True, text_color)
        text_rect = button_text.get_rect(center=(button_x + button_width // 2, y_pos + button_height // 2))
        self.screen.blit(button_text, text_rect)
        
    def draw_store_selection_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw store selection screen matching custom_player.py."""
        # Title
        title = self.font_title.render("Select Store", True, self.colors['light_gray'])
        title_rect = title.get_rect(center=(self.width // 2, container_y + 100))
        self.screen.blit(title, title_rect)
        
        # Subtitle
        subtitle = self.font_subtitle.render("Choose your store location", True, self.colors['gray'])
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(subtitle, subtitle_rect)
        
        start_y = container_y + 200
        # Ensure available_stores is a list before slicing
        stores_list = list(self.available_stores) if self.available_stores else []
        
        # Clear and rebuild store button rects
        self.store_button_rects = []
        
        for i, store in enumerate(stores_list[:5]):
            store_y = start_y + i * 60
            
            button_width = container_width - 100
            button_height = 50
            button_x = container_x + 50
            
            # Selected state with EA TV red
            bg_color = self.colors['pizza_red'] if i == self.selected_store else (30, 30, 30)
            text_color = self.colors['white']
            border_color = self.colors['pizza_red'] if i == self.selected_store else self.colors['input_border']
            
            button_rect = pygame.Rect(button_x, store_y, button_width, button_height)
            pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=5)
            
            # Store button rect with store index for click detection
            self.store_button_rects.append((button_rect, i))
            
            store_name = store.get('store_name', f"Store {store.get('store_id', 'Unknown')}")
            store_text = self.font_button.render(store_name, True, text_color)
            text_rect = store_text.get_rect(center=(button_x + button_width // 2, store_y + button_height // 2))
            self.screen.blit(store_text, text_rect)
            
    def draw_screen_selection_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw screen selection screen."""
        title = self.font_title.render("Select Screen", True, self.colors['white'])
        title_rect = title.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(title, title_rect)
        
        screens = ["tv1", "tv2", "tv3", "tv4"]
        start_y = container_y + 200
        
        # Clear and rebuild screen button rects
        self.screen_button_rects = {}
        
        for i, screen in enumerate(screens):
            screen_y = start_y + i * 50
            
            button_width = container_width - 60
            button_height = 40
            button_x = container_x + 30
            
            bg_color = (50, 50, 50)
            button_rect = pygame.Rect(button_x, screen_y, button_width, button_height)
            pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=5)
            
            # Store button rect with screen_id for click detection
            self.screen_button_rects[screen] = button_rect
            
            screen_text = self.font_button.render(f"Screen {screen.upper()}", True, self.colors['white'])
            text_rect = screen_text.get_rect(center=(button_x + button_width // 2, screen_y + button_height // 2))
            self.screen.blit(screen_text, text_rect)
            
    def draw_playing_screen(self):
        """Draw playing screen - let media player handle the display."""
        if not self.playlist:
            # Show idle message like webplayer
            self.screen.fill(self.colors['black'])
            idle_text = self.font_subtitle.render("Waiting for schedule...", True, self.colors['white'])
            idle_rect = idle_text.get_rect(center=(self.width // 2, self.height // 2))
            self.screen.blit(idle_text, idle_rect)
            
        # Overlay info
        self.draw_overlay_info()
        
    def draw_overlay_info(self):
        """Draw overlay information like webplayer."""
        info_text = f"Store {self.store_id} • Screen {self.screen_id}"
        if self.playlist:
            info_text += f" • Item {self.current_index + 1}/{len(self.playlist)}"
            
        # Get cache info for debugging
        cache_info = self.media_player.get_cache_info()
        debug_text = f"Cache: {cache_info['memory_items']}mem/{cache_info['download_items']}dl/{cache_info['cache_size_mb']:.1f}MB"
        
        overlay = self.font_small.render(info_text, True, (154, 167, 255, 56))
        debug_overlay = self.font_small.render(debug_text, True, (100, 100, 100))
        
        self.screen.blit(overlay, (10, self.height - 50))
        self.screen.blit(debug_overlay, (10, self.height - 25))
        
    def get_media_url(self, item: PlaylistItem) -> str:
        """Get media URL for playlist item like webplayer."""
        if item.slice_url:
            return item.slice_url
            
        url = item.url or item.file or ""
        if url.startswith('http'):
            return url
            
        # Construct full URL
        filename = url.lstrip('/')
        is_video = any(filename.lower().endswith(ext) for ext in ['.mp4', '.webm', '.ogg', '.mov', '.avi'])
        endpoint = 'media' if is_video else 'static/uploads'
        
        return f"{self.server_url}/{endpoint}/{filename}"
        
    def fetch_playlist(self) -> List[PlaylistItem]:
        """Fetch playlist from server like webplayer."""
        try:
            url = f"{self.server_url}/playlist/{self.store_id}/{self.screen_id}"
            params = {}
            headers = {}
            
            if self.pair_code:
                params['user_code'] = self.pair_code
                headers['X-User-Code'] = self.pair_code
                
            response = requests.get(url, params=params, headers=headers, timeout=10, cache_no_store=True)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('playlist'):
                    playlist_data = data['playlist']
                    playlist = [PlaylistItem.from_dict(item) for item in playlist_data]
                    logger.info(f"📥 Fetched {len(playlist)} playlist items")
                    return playlist
                    
        except Exception as e:
            logger.warning(f"Playlist fetch failed: {e}")
            
        return []
        
    def sync_effect_from_server(self):
        """Sync global effect from server like webplayer."""
        try:
            if not self.store_id:
                return
                
            response = requests.get(f"{self.server_url}/api/get-effect/{self.store_id}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                effect_name = data.get('effect_name')
                
                if not effect_name and data.get('effect_id'):
                    # Map effect_id to effect name
                    effect_map = {
                        '1': 'fade', '2': 'slide-l', '3': 'slide-r',
                        '4': 'zoom-in', '5': 'zoom-out', '6': 'cut'
                    }
                    effect_name = effect_map.get(str(data['effect_id']), 'fade')
                    
                if effect_name and effect_name != self.current_global_effect:
                    self.current_global_effect = effect_name
                    logger.info(f"🎨 Effect synchronized from server: {self.current_global_effect}")
                    
        except Exception as e:
            logger.debug(f"Effect sync failed: {e}")
            
    def send_heartbeat(self):
        """Send heartbeat to server like webplayer."""
        try:
            params = {
                'store_id': self.store_id,
                'screen_id': self.screen_id
            }
            headers = {}
            
            if self.pair_code:
                params['user_code'] = self.pair_code
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
            
    def poll_commands(self):
        """Poll for server commands like webplayer."""
        try:
            params = {
                'store_id': self.store_id,
                'screen_id': self.screen_id,
                'limit': '5',
                'pop': '1'
            }
            headers = {}
            
            if self.pair_code:
                params['user_code'] = self.pair_code
                headers['X-User-Code'] = self.pair_code
                
            response = requests.get(
                f"{self.server_url}/api/commands",
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('commands'):
                    commands = data['commands']
                    
                    # Check for reload command
                    has_reload = any(
                        cmd and cmd.get('type', '').lower() == 'reload' 
                        for cmd in commands
                    )
                    
                    if has_reload:
                        logger.info("🔄 Reload command received - fetching playlist")
                        self.fetch_and_update_playlist(force_advance=True)
                        
        except Exception as e:
            logger.debug(f"Commands poll failed: {e}")
            
    def validate_tv_code(self, code: str) -> List[Dict]:
        """Validate TV code and get available stores."""
        try:
            response = requests.get(f"{self.server_url}/api/stores_by_code/{code}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # API returns {success, user, stores, screens}
                if data.get('success') and 'stores' in data:
                    stores = data['stores']
                    logger.info(f"✅ Valid TV code: {len(stores)} stores available")
                    return stores
                else:
                    logger.warning(f"❌ Invalid response format: {data}")
                    return []
            else:
                logger.warning(f"❌ Invalid TV code: {code}")
                return []
                
        except Exception as e:
            logger.error(f"TV code validation failed: {e}")
            return []
            
    def fetch_and_update_playlist(self, force_advance: bool = False):
        """Fetch playlist and update if changed."""
        new_playlist = self.fetch_playlist()
        
        if new_playlist:
            # Compute signature to detect changes
            new_signature = self.compute_playlist_signature(new_playlist)
            signature_changed = bool(self.playlist_signature) and new_signature != self.playlist_signature
            
            self.playlist = new_playlist
            self.playlist_signature = new_signature
            
            # Preload upcoming items
            self.preload_upcoming_items()
            
            # Handle playlist changes
            if signature_changed or force_advance:
                logger.info("📋 Playlist changed - advancing to new content")
                self.current_index = 0
                self.advance_to_next_item()
                
    def compute_playlist_signature(self, playlist: List[PlaylistItem]) -> str:
        """Compute playlist signature for change detection."""
        try:
            keys = []
            for item in playlist:
                if item.id:
                    keys.append(f"id:{item.id}")
                elif item.url:
                    keys.append(f"url:{item.url}")
                elif item.file:
                    keys.append(f"file:{item.file}")
                    
            signature = "|".join(keys)
            return hashlib.md5(signature.encode()).hexdigest()[:16]
            
        except Exception:
            return f"sig:{int(time.time())}"
            
    def preload_upcoming_items(self):
        """Preload next items like webplayer."""
        if not self.playlist:
            return
            
        # Preload next PRELOAD_AHEAD items
        for i in range(self.PRELOAD_AHEAD):
            idx = (self.current_index + i) % len(self.playlist)
            item = self.playlist[idx]
            media_url = self.get_media_url(item)
            
            if media_url:
                self.media_player.preload_media(media_url)
                
    def advance_to_next_item(self):
        """Advance to next playlist item."""
        if not self.playlist:
            return
            
        if self.current_index >= len(self.playlist):
            self.current_index = 0
            
        current_item = self.playlist[self.current_index]
        media_url = self.get_media_url(current_item)
        
        if media_url:
            # Use global effect or item effect
            effect = self.current_global_effect or current_item.effect or 'fade'
            duration = current_item.duration or 10.0
            
            logger.info(f"🎬 Playing item {self.current_index + 1}/{len(self.playlist)}: {media_url}")
            success = self.media_player.play_media(media_url, effect, duration)
            
            if success:
                self.current_item_key = f"{current_item.id or current_item.url or current_item.file}"
                
                # Schedule next item
                threading.Timer(duration, self.on_item_finished).start()
                
                # Preload upcoming items
                self.preload_upcoming_items()
                
    def on_item_finished(self):
        """Handle when current item finishes playing."""
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.advance_to_next_item()
        
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
        elif event.key == pygame.K_SPACE and self.current_state == "playing":
            # Manual advance for testing
            self.current_index = (self.current_index + 1) % len(self.playlist) if self.playlist else 0
            
    def handle_mousedown(self, event):
        """Handle mouse button clicks."""
        if event.button != 1:  # Only handle left clicks
            return
            
        if self.current_state == "setup":
            if self.setup_step == "code":
                # Check Link Code button click
                if self.link_button_rect and self.link_button_rect.collidepoint(event.pos):
                    if len(self.input_text) == 4 and self.input_text.isdigit():
                        self.handle_code_submit()
                        
            elif self.setup_step == "store":
                # Check store button clicks
                for button_rect, store_index in self.store_button_rects:
                    if button_rect.collidepoint(event.pos):
                        self.selected_store = store_index
                        self.handle_store_select()
                        break
                        
            elif self.setup_step == "screen":
                # Check screen button clicks
                for screen_id, button_rect in self.screen_button_rects.items():
                    if button_rect.collidepoint(event.pos):
                        self.handle_screen_select(screen_id)
                        break
            self.advance_to_next_item()
            
    def handle_code_submit(self):
        """Handle TV code submission."""
        logger.info(f"🔍 Validating TV code: {self.input_text}")
        
        def validate_code():
            stores = self.validate_tv_code(self.input_text)
            
            if stores:
                self.available_stores = stores
                self.pair_code = self.input_text
                self.setup_step = "store"
                self.selected_store = 0
                logger.info("✅ Moving to store selection")
            else:
                logger.warning("❌ Invalid code, staying on code input")
                self.input_text = ""
                
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
        
        self.current_state = "playing"
        self.start_playback_services()
        
    def start_playback_services(self):
        """Start background services for playback like webplayer."""
        if self.services_started:
            return
            
        self.services_started = True
        
        # Time synchronization thread
        def sync_loop():
            while self.running:
                try:
                    self.time_sync.sync_time()
                except Exception as e:
                    logger.warning(f"Time sync error: {e}")
                time.sleep(15)  # Every 15 seconds like webplayer
                
        # Heartbeat thread
        def heartbeat_loop():
            while self.running:
                try:
                    self.send_heartbeat()
                except Exception as e:
                    logger.warning(f"Heartbeat error: {e}")
                time.sleep(30)  # Every 30 seconds like webplayer
                
        # Playlist refresh thread
        def playlist_loop():
            while self.running:
                try:
                    self.fetch_and_update_playlist()
                except Exception as e:
                    logger.warning(f"Playlist update error: {e}")
                time.sleep(self.PLAYLIST_REFRESH_INTERVAL_MS / 1000)  # 10 seconds
                
        # Effect sync thread
        def effect_loop():
            while self.running:
                try:
                    self.sync_effect_from_server()
                except Exception as e:
                    logger.debug(f"Effect sync error: {e}")
                time.sleep(3)  # Every 3 seconds like webplayer
                
        # Commands polling thread
        def commands_loop():
            while self.running:
                try:
                    self.poll_commands()
                except Exception as e:
                    logger.debug(f"Commands poll error: {e}")
                time.sleep(self.COMMANDS_POLL_MS / 1000)  # 1.5 seconds
                
        # Start all service threads
        threading.Thread(target=sync_loop, daemon=True).start()
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=playlist_loop, daemon=True).start()
        threading.Thread(target=effect_loop, daemon=True).start()
        threading.Thread(target=commands_loop, daemon=True).start()
        
        logger.info("🎬 All playback services started")
        
        # Initial playlist fetch and start playback
        self.fetch_and_update_playlist()
        if self.playlist:
            self.advance_to_next_item()
            
    def run(self):
        """Main event loop."""
        clock = pygame.time.Clock()
        logger.info("🍕 Starting Complete Pi Webplayer Client")
        
        # Initial server time sync
        try:
            self.time_sync.sync_time()
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
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mousedown(event)
                    
            # Draw current screen
            if self.current_state == "setup":
                self.draw_setup_screen()
            elif self.current_state == "playing":
                self.draw_playing_screen()
                
            # Update display
            pygame.display.flip()
            clock.tick(60)  # 60 FPS
            
        logger.info("🛑 Shutting down Complete Pi Client")
        self.media_player.stop()
        pygame.quit()
        
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pizza Hut TV Complete Pi Webplayer Client")
    parser.add_argument("--server", default="https://everydayadvertise.com", 
                       help="Server URL")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    client = CompleteWebplayerClient(server_url=args.server)
    
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()