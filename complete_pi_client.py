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
import socket
import socketio
import subprocess
from datetime import datetime, timedelta, time as dtime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Set SDL environment variables BEFORE pygame.init() for proper display handling on Pi
# Force software renderer instead of GL to avoid context issues
os.environ.setdefault('SDL_VIDEODRIVER', 'x11')  # X11 for Pi display
os.environ.setdefault('SDL_RENDER_DRIVER', 'software')  # Use software renderer, not GL
os.environ.setdefault('SDL_RENDER_SCALE_QUALITY', '2')  # Linear scaling for better quality
os.environ.setdefault('DISPLAY', ':0')  # Ensure DISPLAY is set

# Import our SEAMLESS media player (no flicker!)
from seamless_video_player import SeamlessMediaPlayer as MediaPlayer

# Client version identifier for logs, status, and WebSocket registration
VERSION = "v2.1.2"  # Timer deduplication fix - prevent multiple overlapping timers

# MOBILE SYNC ADDON: Import mobile sync functionality (optional - degrades gracefully if not available)
try:
    from pi_mobile_sync_addon import MobileSyncAddon
    MOBILE_SYNC_AVAILABLE = True
    print("✅ MOBILE SYNC ADDON IMPORTED SUCCESSFULLY")
except ImportError as e:
    MOBILE_SYNC_AVAILABLE = False
    print(f"❌ MOBILE SYNC ADDON IMPORT FAILED: {e}")
except Exception as e:
    MOBILE_SYNC_AVAILABLE = False
    print(f"❌ MOBILE SYNC ADDON UNEXPECTED ERROR: {e}")

# Configure logging with FILE output for debugging
log_file = os.path.expanduser('~/pi_client_debug.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 Logging to {log_file}")

def get_local_ip():
    """Get the local IP address of this device."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_public_ip():
    """Get the public IP address of this device (what the internet sees)."""
    try:
        # Try multiple services for redundancy
        services = [
            'https://api.ipify.org',
            'https://ifconfig.me/ip',
            'https://icanhazip.com',
        ]
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    public_ip = response.text.strip()
                    logger.info(f"🌐 Detected public IP: {public_ip}")
                    return public_ip
            except Exception:
                continue
        # Fallback to local IP if all services fail
        logger.warning("⚠️ Could not detect public IP, using local IP as fallback")
        return get_local_ip()
    except Exception as e:
        logger.warning(f"⚠️ Error getting public IP: {e}")
        return get_local_ip()

def register_pi_with_server(pi_id, server_url):
    """Register Pi identifier and IP with the server automatically."""
    try:
        pi_ip = get_public_ip()  # Changed to use public IP instead of local IP
        url = f"{server_url}/api/register_pi"
        payload = {"pi_id": pi_id, "pi_ip": pi_ip}
        
        logger.info(f"📡 Registering Pi with server: {pi_id} -> {pi_ip}")
        resp = requests.post(url, json=payload, timeout=5)
        
        if resp.status_code == 200:
            logger.info(f"✅ Pi registered successfully: {resp.json().get('message', 'OK')}")
        else:
            logger.warning(f"⚠️ Pi registration failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.warning(f"⚠️ Could not register Pi with server: {e}")

@dataclass
class PlaylistItem:
    """Playlist item matching webplayer structure."""
    id: Optional[str] = None
    url: Optional[str] = None
    file: Optional[str] = None
    duration: float = 10.0
    effect: Optional[str] = None  # None means no effect set, use default
    media_type: str = "video"
    slice_aware: bool = False
    slice_url: Optional[str] = None
    sync_ref: Optional[Dict] = None
    rotation: int = 0  # NEW: Media rotation (0, 90, 180, 270)
    enabled: bool = True  # NEW: Item enable/disable flag
    schedule: Optional[List[Dict]] = None  # NEW: Schedule windows
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PlaylistItem':
        """Create PlaylistItem from server data."""
        # DEBUG: Log the raw data we're parsing
        logger.debug(f"🔍 Parsing item from_dict: id={data.get('id')}, file={data.get('file')}, effect={data.get('effect', 'NOT IN DATA')}")
        
        return cls(
            id=str(data.get('id', '')),
            url=data.get('url', ''),
            file=data.get('file', ''),
            duration=float(data.get('duration', 10.0)),
            effect=data.get('effect'),  # Don't use default here - None means not set
            media_type=data.get('media_type', 'video'),
            slice_aware=bool(data.get('slice_aware', False)),
            slice_url=data.get('slice_url'),
            sync_ref=data.get('sync_ref'),
            rotation=int(data.get('rotation', 0)),
            enabled=bool(data.get('enabled', True)),
            schedule=data.get('schedule', [])
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


class PiConfigHandler(BaseHTTPRequestHandler):
    """HTTP request handler for remote Pi configuration."""

    def do_POST(self):
        """Handle POST requests for Pi configuration."""
        try:
            if self.path == '/configure':
                # Parse JSON body
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                config_data = json.loads(post_data.decode('utf-8'))
    
                # Get Pi client instance from server
                pi_client = self.server.pi_client
                
                # Extract configuration
                pair_code = config_data.get('pair_code', '').strip()
                store_id = config_data.get('store_id', '').strip()
                screen_id = config_data.get('screen_id', '').strip()
                
                # Validate pair code format
                if not pair_code or len(pair_code) != 4 or not pair_code.isdigit():
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {'success': False, 'error': f'Invalid pair code format: {pair_code}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                # Verify store and screen belong to this pairing code
                logger.info(f"� Verifying configuration against API...")
                verify_url = f"{pi_client.server_url}/api/stores_by_code/{pair_code}"
                response_obj = requests.get(verify_url, timeout=10)
                
                if response_obj.status_code != 200:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {'success': False, 'error': f'Pair code not found or invalid: {pair_code}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                api_data = response_obj.json()
                if not api_data.get('success'):
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {'success': False, 'error': f"API error: {api_data.get('error', 'Unknown error')}"}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                # Check if store_id exists in user's stores
                user_stores = api_data.get('stores', [])
                store_ids = [str(s.get('id')) for s in user_stores]
                
                if store_id not in store_ids:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {'success': False, 'error': f'Store {store_id} not found for pair code {pair_code}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                # Check if screen_id exists for this store
                user_screens = api_data.get('screens', {})
                store_screens = user_screens.get(store_id, {})
                
                if screen_id not in store_screens:
                    available_screens = list(store_screens.keys())
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {'success': False, 'error': f'Screen {screen_id} not found for store {store_id}. Available: {available_screens}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                logger.info(f"✅ Configuration verified successfully!")
                logger.info(f"   User: {api_data.get('user', {}).get('username', 'Unknown')}")
                logger.info(f"   Store: {store_id} (from {len(user_stores)} stores)")
                logger.info(f"   Screen: {screen_id} (from {len(store_screens)} screens)")
    
                # Apply validated configuration
                pi_client.pair_code = pair_code
                pi_client.store_id = store_id
                pi_client.screen_id = screen_id
                logger.info(f"🔧 Remote config applied: pair_code={pi_client.pair_code}, store={pi_client.store_id}, screen={pi_client.screen_id}")
    
                # If all required fields are set, start playback
                if pi_client.pair_code and pi_client.store_id and pi_client.screen_id:
                    logger.info("🚀 All config received, starting playback mode...")
                    pi_client.current_state = "playing"
                    pi_client.setup_step = "complete"
                    
                    # CRITICAL: Hide Pi ID overlay IMMEDIATELY before starting playback
                    pi_client.show_pi_id = False
                    logger.info("👁️  Pi ID hidden for video playback")
                    
                    # Force restart playback services (even if already started)
                    pi_client.services_started = False
                    threading.Thread(target=pi_client.start_playback_services, daemon=True).start()
    
                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    'success': True,
                    'message': 'Configuration applied successfully',
                    'pi_id': pi_client.pi_id,
                    'state': pi_client.current_state
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
    
            elif self.path == '/status':
                # Return Pi status
                pi_client = self.server.pi_client
    
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    'pi_id': pi_client.pi_id,
                    'status': 'online',
                    'current_state': pi_client.current_state,
                    'pair_code': pi_client.pair_code,
                    'store_id': pi_client.store_id,
                    'screen_id': pi_client.screen_id,
                    'version': VERSION,
                    'last_seen': datetime.now().isoformat()
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self.send_error(404, "Endpoint not found")
    
        except Exception as e:
            logger.error(f"❌ Config server error: {e}")
            self.send_error(500, f"Internal server error: {e}")

    def do_GET(self):
        """Handle GET requests (status only)."""
        if self.path == '/status':
            self.do_POST()  # Reuse POST logic for status
        else:
            self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass


class CompleteWebplayerClient:
    """Complete Pi client with full webplayer functionality."""
    
    def _get_or_create_pi_id(self) -> str:
        """
        Generate or load a persistent Pi ID for this device.
        The ID is stored in ~/.pizza_hut_tv_id and persists across reboots.
        """
        id_file = os.path.expanduser('~/.pizza_hut_tv_id')
        
        # Try to load existing ID
        if os.path.exists(id_file):
            try:
                with open(id_file, 'r') as f:
                    pi_id = f.read().strip()
                    if pi_id:
                        logger.info(f"📟 Pi ID loaded: {pi_id}")
                        return pi_id
            except Exception as e:
                logger.warning(f"Failed to load Pi ID: {e}")
        
        # Generate new ID based on hostname + MAC address
        import socket
        import uuid
        
        try:
            hostname = socket.gethostname()
        except:
            hostname = "raspberrypi"
        
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0,2*6,2)][::-1])
            # Use last 4 characters of MAC for uniqueness
            mac_suffix = mac.replace(':', '')[-4:]
        except:
            # Fallback to random if MAC unavailable
            import random
            mac_suffix = ''.join(random.choices('0123456789abcdef', k=4))
        
        # Create Pi ID: hostname-XXXX (e.g., raspberrypi-a1b2)
        pi_id = f"{hostname}-{mac_suffix}"
        
        # Save to file for persistence
        try:
            with open(id_file, 'w') as f:
                f.write(pi_id)
            logger.info(f"📟 New Pi ID generated and saved: {pi_id}")
        except Exception as e:
            logger.error(f"Failed to save Pi ID: {e}")
        
        return pi_id
    
    def __init__(self, server_url: str = "https://everydayadvertise.com"):
        # Core settings
        self.server_url = server_url.rstrip('/')
        self.store_id = ""
        self.screen_id = ""
        self.pair_code = ""
        
        # Pi ID - unique identifier for this device
        self.pi_id = self._get_or_create_pi_id()
        self.show_pi_id = True  # Toggle visibility (press 'I' to toggle)
        self.pi_id_last_shown = time.time()  # Track when last shown
        self.pi_id_auto_hide_seconds = 300  # Auto-hide after 5 minutes (0 = never hide)
        
        # Initialize pygame
        pygame.init()
        self.screen_info = pygame.display.Info()
        self.width = self.screen_info.current_w
        self.height = self.screen_info.current_h
        
        # Create fullscreen display with software rendering (no GL)
        # Use FULLSCREEN | DOUBLEBUF | HWSURFACE for Pi compatibility
        self.screen = pygame.display.set_mode((self.width, self.height), 
                                              pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
        pygame.display.set_caption("Pizza Hut TV - Complete Pi Client")
        pygame.mouse.set_visible(False)
        
        # TEST MODE: Draw a test pattern to verify display is working
        if os.getenv('PHTV_TEST_DISPLAY'):
            logger.warning("🧪 TEST MODE: Drawing test pattern to verify display")
            # Draw colored rectangles so you can see if display is working
            self.screen.fill((0, 0, 0))  # Black
            pygame.draw.rect(self.screen, (255, 0, 0), (10, 10, 200, 200))  # Red
            pygame.draw.rect(self.screen, (0, 255, 0), (220, 10, 200, 200))  # Green
            pygame.draw.rect(self.screen, (0, 0, 255), (430, 10, 200, 200))  # Blue
            pygame.display.flip()
            logger.warning("🧪 Test pattern drawn - you should see Red, Green, Blue rectangles in top-left")
        
        # Colors matching custom_player.py dark theme EXACTLY
        self.colors = {
            'background': (13, 13, 13),           # #0d0d0d - main background
            'black': (0, 0, 0),                   # #000000 - pure black
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
        self.pair_code = ""  # TV code (4 digits)
        self.store_id = ""   # Store code (numeric)
        self.available_screens = {}  # Screen data from API
        self.selected_store = None
        self.setup_step = "code"  # code, store, screen
        
        # Active timer for current item (to prevent overlapping timers)
        self._current_item_timer = None
        self._timer_lock = threading.Lock()
        
        # Button position tracking for mouse clicks
        self.link_button_rect = None
        self.store_button_rects = []
        self.screen_button_rects = {}
        
        # Playback state like webplayer
        self.playlist = []
        self.current_index = 0
        self.last_playlist_fetch = 0
        self.playlist_signature = ""
        
        # Screen orientation and rotation (from dashboard)
        self.screen_orientation = None  # 'vertical', 'horizontal', or 'default' (None = not fetched yet)
        self.screen_rotation = None  # 0, 90, 180, 270 degrees (None = not fetched yet)
        # Concurrency + change-tracking helpers
        import threading as _thr
        self._playlist_lock = _thr.Lock()  # Serialize fetch/update to avoid races masking rotation changes
        self._last_rotation_seen = None    # Separate tracker for rotation change detection
        self.current_item_key = ""
        self._advance_lock = _thr.Lock()   # Serialize advancing to next item to prevent double-triggers
        
        # Timing constants like webplayer
        self.PLAYLIST_REFRESH_MIN_MS = 3000
        self.COMMANDS_POLL_MS = 1500
        self.PLAYLIST_REFRESH_INTERVAL_MS = 10000  # 10 seconds to avoid thrashing (was 3s)
        self.PRELOAD_AHEAD = 4  # Preload next 4 items
        # Anti-thrashing and duration safety
        import os as _os
        try:
            self.MIN_ADVANCE_GAP = float(_os.getenv('PHTV_MIN_ADVANCE_GAP', '5.0'))
        except Exception:
            self.MIN_ADVANCE_GAP = 5.0
        self._last_advance_time = 0.0
        try:
            self.MIN_ITEM_DURATION = float(_os.getenv('PHTV_MIN_ITEM_SEC', '5'))
        except Exception:
            self.MIN_ITEM_DURATION = 5.0
        
        # Scheduling strategy: default to server-side filtering unless opt-in override
        try:
            self.use_local_schedule_filter = bool(
                str(os.getenv('PHTV_LOCAL_SCHEDULE_FILTER', '')).strip().lower() in ('1', 'true', 'yes', 'on')
            )
        except Exception:
            self.use_local_schedule_filter = False

        # Global effect synchronization
        self.current_global_effect = 'fade'
        # Transitions master toggle from server (dashboard button)
        # Default to ON since dashboard no longer has a global toggle
        self.transitions_master_enabled = True
        # Optional env override to FORCE transitions on regardless of server flags
        try:
            _force_env = os.getenv('PHTV_FORCE_TRANSITIONS', '')
            self.force_transitions_on = str(_force_env).strip().lower() in ('1','true','yes','on')
        except Exception:
            self.force_transitions_on = False
        if self.force_transitions_on:
            logger.info("🎛️ Transitions forced ON via PHTV_FORCE_TRANSITIONS")
            self.transitions_master_enabled = True
        # Transition safety controls
        # Allow environment to force-disable transitions if hardware/driver is unstable
        env_disable = os.getenv('PHTV_DISABLE_TRANSITIONS', '')
        env_enable = os.getenv('PHTV_ENABLE_TRANSITIONS', '')
        self.disable_transitions = str(env_disable).lower() in ('1', 'true', 'yes', 'on') and not (
            str(env_enable).lower() in ('1', 'true', 'yes', 'on')
        )
        self._transitions_faulted = False  # Set to True if we detect a transition failure and auto-disable
        self._stop_video_on_timer = False  # Track when we need to cut a video because a schedule window ended
        
        # Components
        self.time_sync = ServerTimeSync(self.server_url)
        self.media_player = MediaPlayer(self.screen)
        
        # 🎯 Link time_sync to media player for video synchronization
        if hasattr(self.media_player, 'video_player'):
            self.media_player.video_player.time_sync = self.time_sync
            logger.info("✅ Time sync linked to media player for multi-screen synchronization")
        
        # Threading
        self.running = True
        self.services_started = False
        
        # Start FREE VNC server for remote desktop access (gated by env PHTV_ENABLE_VNC)
        self.vnc_process = None
        enable_vnc = os.getenv('PHTV_ENABLE_VNC', '1')
        self.enable_vnc = (enable_vnc == '1' or enable_vnc.lower() == 'true')
        # File-based kill switch for VNC if env isn't passed by systemd
        try:
            flag_files = [
                '/etc/pizza-hut-tv/disable_vnc',
                os.path.expanduser('~/.disable_phtv_vnc')
            ]
            if any(os.path.exists(p) for p in flag_files):
                self.enable_vnc = False
                logger.info("🛑 VNC disabled via flag file (disable_vnc)")
        except Exception:
            pass
        if self.enable_vnc:
            self._start_vnc_server()
        else:
            logger.info("🛑 VNC server disabled via PHTV_ENABLE_VNC environment variable")
        
        # Remote configuration server
        self.config_server = None
        self.config_port = 8080
        self.start_config_server()
        
        # WebSocket connection for relay (TeamViewer-style)
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # Infinite
            reconnection_delay=5,
            reconnection_delay_max=30,
            logger=True,
            engineio_logger=True,
            ssl_verify=False  # Disable SSL verification for Cloudflare certificates
        )
        self.websocket_connected = False
        self.streaming_active = False  # Flag for live streaming
        
        # MOBILE SYNC ADDON: Initialize BEFORE WebSocket setup so handlers are registered first
        self.mobile_sync = None  # Initialize to None first
        if MOBILE_SYNC_AVAILABLE:
            try:
                logger.info("🔄 Initializing mobile sync addon...")
                self.mobile_sync = MobileSyncAddon(self)
                logger.info(" Mobile sync addon created successfully!")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize mobile sync: {e}")
                logger.error(f"⚠️ Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"⚠️ Traceback: {traceback.format_exc()}")
                self.mobile_sync = None
        else:
            logger.warning("📱 Mobile sync not available - MOBILE_SYNC_AVAILABLE={MOBILE_SYNC_AVAILABLE}")
            self.mobile_sync = None
        
        # Setup WebSocket (this will register mobile sync handlers via the connect event)
        self.setup_websocket()
        
        # Register mobile sync WebSocket handlers AFTER setup_websocket but BEFORE connection
        if self.mobile_sync:
            try:
                logger.info("🔄 Registering mobile sync WebSocket handlers...")
                self.mobile_sync.setup_websocket_handlers(self.sio)
                logger.info("📱 Mobile sync WebSocket handlers registered!")
            except Exception as e:
                logger.error(f"⚠️ Failed to register mobile sync handlers: {e}")
        
        self.start_websocket_connection()
        
        logger.info(f"🍕 Complete Pi Webplayer Client initialized: {self.width}x{self.height}")
        logger.info(f"📟 Pi ID: {self.pi_id}")  # Log Pi ID on startup
        
        # Register Pi with server automatically (legacy HTTP method)
        threading.Thread(target=register_pi_with_server, args=(self.pi_id, self.server_url), daemon=True).start()
    
    def start_config_server(self):
        """Start HTTP server for remote configuration."""
        def run_server():
            try:
                # Create custom HTTP server with reference to pi client
                class ConfigServer(HTTPServer):
                    def __init__(self, server_address, RequestHandlerClass, pi_client):
                        super().__init__(server_address, RequestHandlerClass)
                        self.pi_client = pi_client
                
                self.config_server = ConfigServer(('0.0.0.0', self.config_port), PiConfigHandler, self)
                logger.info(f"🌐 Remote configuration server started on port {self.config_port}")
                self.config_server.serve_forever()
            except Exception as e:
                logger.error(f"❌ Failed to start config server: {e}")
        
        # Start server in background thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
    
    def save_config(self):
        """Save current configuration to a file for persistence."""
        try:
            config_file = os.path.expanduser('~/.pizza_hut_tv_config.json')
            config_data = {
                'pair_code': self.pair_code,
                'store_id': self.store_id,
                'screen_id': self.screen_id,
                'pi_id': self.pi_id,
                'last_updated': time.time()
            }
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            logger.info(f"💾 Configuration saved: {config_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save config: {e}")
    
    def load_config(self):
        """Load saved configuration from file."""
        try:
            config_file = os.path.expanduser('~/.pizza_hut_tv_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                self.pair_code = config_data.get('pair_code', '')
                self.store_id = config_data.get('store_id', '')
                self.screen_id = config_data.get('screen_id', '')
                logger.info(f"📂 Configuration loaded: pair_code={self.pair_code}, store={self.store_id}, screen={self.screen_id}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Could not load config: {e}")
        return False
    
    def _start_vnc_server(self):
        """Start x11vnc server for free VNC-style remote access"""
        try:
            import subprocess
            
            # Kill any existing x11vnc processes
            subprocess.run(['pkill', '-9', 'x11vnc'], capture_output=True)
            
            # Start x11vnc server
            # -forever: keep running for multiple connections
            # -shared: allow multiple viewers
            # -nopw: no password (since we're behind dashboard auth)
            # -display :0: capture main display
            # -rfbport 5900: standard VNC port
            logger.info("🖥️  Starting FREE VNC server (x11vnc)...")
            
            self.vnc_process = subprocess.Popen(
                ['x11vnc', '-display', ':0', '-forever', '-shared', '-nopw',
                 '-rfbport', '5900', '-quiet', '-bg', '-o', '/dev/null'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info("✅ VNC Server started on port 5900 (FREE remote desktop access!)")
            logger.info("📱 Connect with any VNC client to: <PI_IP>:5900")
            
        except Exception as e:
            logger.error(f"❌ Failed to start VNC server: {e}")
            self.vnc_process = None
    
    def _stop_vnc_server(self):
        """Stop the VNC server"""
        try:
            if self.vnc_process:
                self.vnc_process.terminate()
                self.vnc_process.wait(timeout=5)
            import subprocess
            subprocess.run(['pkill', '-9', 'x11vnc'], capture_output=True)
            logger.info("🛑 VNC server stopped")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping VNC server: {e}")


    def setup_websocket(self):
        """Set up WebSocket event handlers (TeamViewer-style relay)"""
        
        @self.sio.on('*')
        def catch_all(event, data):
            logger.info(f'🔔 WebSocket event received: {event} with data: {data}')
        
        @self.sio.on('connect')
        def on_connect():
            logger.info(f'🌐 WebSocket connected to {self.server_url}')
            self.websocket_connected = True
            # Register this Pi with server
            self.sio.emit('register_pi', {
                'pi_id': self.pi_id,
                'version': f"{VERSION}-websocket"
            })
            
            # MOBILE SYNC: Join webplayer session after registering
            if hasattr(self, 'mobile_sync') and self.mobile_sync:
                self.mobile_sync.join_webplayer_session()
        
        @self.sio.on('registered')
        def on_registered(data):
            logger.info(f'✅ Registered with server via WebSocket: {data}')
        
        @self.sio.on('registration_failed')
        def on_registration_failed(data):
            logger.error(f'❌ Registration failed: {data.get("message", "Unknown error")}')
        
        @self.sio.on('configure')
        def on_configure(config):
            """Receive configuration from dashboard via WebSocket relay - EXACT same logic as HTTP handler"""
            logger.info(f'📡 Configuration received via WebSocket: {config}')
            
            # Filter - only process if this config is for THIS Pi
            target_pi_id = config.get('target_pi_id')
            if target_pi_id and target_pi_id != self.pi_id:
                logger.info(f'ℹ️  Config is for {target_pi_id}, ignoring (my ID: {self.pi_id})')
                return
            
            logger.info(f'✅ This configuration is for ME ({self.pi_id}), processing...')
            
            try:
                # Extract configuration
                pair_code = config.get('pair_code', '').strip()
                store_id = config.get('store_id', '').strip()
                screen_id = config.get('screen_id', '').strip()
                
                # Validate pair code format
                if not pair_code or len(pair_code) != 4 or not pair_code.isdigit():
                    raise ValueError(f"Invalid pair code format: {pair_code}")
                
                # Verify store and screen belong to this pairing code
                logger.info(f"� Verifying configuration against API...")
                verify_url = f"{self.server_url}/api/stores_by_code/{pair_code}"
                response = requests.get(verify_url, timeout=10)
                
                if response.status_code != 200:
                    raise ValueError(f"Pair code not found or invalid: {pair_code}")
                
                api_data = response.json()
                if not api_data.get('success'):
                    raise ValueError(f"API error: {api_data.get('error', 'Unknown error')}")
                
                # Check if store_id exists in user's stores
                user_stores = api_data.get('stores', [])
                store_ids = [str(s.get('id')) for s in user_stores]
                
                if store_id not in store_ids:
                    raise ValueError(f"Store {store_id} not found for pair code {pair_code}. Available: {store_ids}")
                
                # Check if screen_id exists for this store
                user_screens = api_data.get('screens', {})
                store_screens = user_screens.get(store_id, {})
                
                if screen_id not in store_screens:
                    available_screens = list(store_screens.keys())
                    raise ValueError(f"Screen {screen_id} not found for store {store_id}. Available: {available_screens}")
                
                logger.info(f"✅ Configuration verified successfully!")
                logger.info(f"   User: {api_data.get('user', {}).get('username', 'Unknown')}")
                logger.info(f"   Store: {store_id} (from {len(user_stores)} stores)")
                logger.info(f"   Screen: {screen_id} (from {len(store_screens)} screens)")
                
                # Apply validated configuration
                self.pair_code = pair_code
                self.store_id = store_id
                self.screen_id = screen_id
                logger.info(f"🔧 Remote config applied: pair_code={self.pair_code}, store={self.store_id}, screen={self.screen_id}")
                
                # Save to config file for persistence
                self.save_config()
                
                # Send acknowledgment back to server
                self.sio.emit('config_applied', {
                    'pi_id': self.pi_id,
                    'status': 'success',
                    'config': {
                        'pair_code': self.pair_code,
                        'store_id': self.store_id,
                        'screen_id': self.screen_id
                    }
                })
                
                # If all required fields are set, start playback - EXACT same as HTTP handler
                if self.pair_code and self.store_id and self.screen_id:
                    logger.info("🚀 All config received, starting playback mode...")
                    self.current_state = "playing"
                    self.setup_step = "complete"
                    
                    # CRITICAL: Hide Pi ID overlay IMMEDIATELY before starting playback
                    self.show_pi_id = False
                    logger.info("👁️  Pi ID hidden for video playback")
                    
                    # Force restart playback services (even if already started)
                    self.services_started = False
                    threading.Thread(target=self.start_playback_services, daemon=True).start()
                    
                    # IMMEDIATELY fetch new playlist with new config - FORCE advance to start playback
                    logger.info("🔄 Fetching playlist with new configuration...")
                    threading.Thread(target=lambda: self.fetch_and_update_playlist(force_advance=True), daemon=True).start()
                
            except Exception as e:
                logger.error(f'❌ Configuration error: {e}', exc_info=True)
                self.sio.emit('config_applied', {
                    'pi_id': self.pi_id,
                    'status': 'error',
                    'error': str(e)
                })

        @self.sio.on('reload_client')
        def on_reload_client(data):
            """Instant reload trigger sent by server (e.g., rotation/orientation changed)."""
            logger.info(f"📨 WebSocket event received: reload_client with data={data}")
            try:
                reason = (data or {}).get('reason', 'unknown')
                store_id = (data or {}).get('store_id')
                screen_id = (data or {}).get('screen_id')
                logger.info(f"📋 Parsed: reason={reason}, store={store_id}, screen={screen_id}, my_store={self.store_id}, my_screen={self.screen_id}")

                def _norm_token(x: Optional[str]) -> str:
                    try:
                        t = (x or '').strip().lower()
                        # unify separators and remove spaces
                        t = t.replace(' ', '').replace('-', '').replace('__', '_')
                        return t
                    except Exception:
                        return ''

                def ids_equivalent(a: Optional[str], b: Optional[str], store: Optional[str]) -> bool:
                    """Return True if screen IDs are effectively the same.
                    Normalizes case, strips store prefix, and tolerates spaces/dashes.
                    Accepts variations like '1787_promo1' vs 'Promo 1' vs 'promo1'.
                    """
                    if not a or not b:
                        return False
                    a_s = str(a)
                    b_s = str(b)
                    if _norm_token(a_s) == _norm_token(b_s):
                        return True
                    try:
                        s = (store or '')
                        s_norm = _norm_token(s)
                        a_norm = _norm_token(a_s)
                        b_norm = _norm_token(b_s)
                        # Strip store prefix if present like '1787_'
                        sp = s_norm + '_'
                        if s_norm and a_norm.startswith(sp):
                            a_norm = a_norm[len(sp):]
                        if s_norm and b_norm.startswith(sp):
                            b_norm = b_norm[len(sp):]
                        return a_norm == b_norm
                    except Exception:
                        return False

                # Filter: if store provided and differs from ours, ignore
                if store_id and self.store_id and str(store_id) != str(self.store_id):
                    logger.info(f"↩️  Reload ignored: store mismatch event={store_id} me={self.store_id}")
                    return

                # Filter: if screen provided and we have a screen_id, accept if equivalent, else ignore
                if screen_id and self.screen_id and not ids_equivalent(screen_id, self.screen_id, store_id or self.store_id):
                    logger.info(f"↩️  Reload ignored: screen mismatch event={screen_id} me={self.screen_id} (store={store_id or self.store_id})")
                    return

                logger.info(f"🔁 Reload command received via WebSocket (reason={reason}) — fetching playlist and forcing advance…")
                # Hot-sync latest effect BEFORE advancing so the new effect applies immediately
                try:
                    self.sync_effect_from_server()
                except Exception as e_sync:
                    logger.debug(f"Effect sync during reload failed: {e_sync}")
                # Force fetch latest playlist and immediately apply (advance) so rotation/orientation/effect take effect
                threading.Thread(target=lambda: self.fetch_and_update_playlist(force_advance=True), daemon=True).start()
            except Exception as e:
                logger.error(f"❌ Error processing reload_client event: {e}", exc_info=True)
        
        @self.sio.on('close_screen')
        def on_close_screen(data):
            """Handle close screen command from dashboard - Restart Pi client"""
            try:
                logger.info('⏹️  CLOSE SCREEN command received from dashboard')
                logger.info('🔄 Restarting Pi client...')
                
                # Send acknowledgment before restarting
                self.sio.emit('screen_closed', {
                    'pi_id': self.pi_id,
                    'status': 'restarting',
                    'timestamp': time.time()
                })
                
                # Stop media player
                self.media_player.stop()
                
                # Clear any saved configuration
                config_file = os.path.expanduser('~/.pizza_hut_tv_config.json')
                if os.path.exists(config_file):
                    os.remove(config_file)
                    logger.info('🗑️  Cleared saved configuration')
                
                # Give time for acknowledgment to be sent
                time.sleep(1)
                
                # Restart the Pi client by exiting - systemd/autostart will restart it
                logger.info('🔄 Exiting to restart Pi client...')
                os._exit(0)  # Force exit to trigger restart
                
            except Exception as e:
                logger.error(f'❌ Close screen error: {e}', exc_info=True)
                self.sio.emit('screen_closed', {
                    'pi_id': self.pi_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        @self.sio.on('restart_pi')
        def on_restart_pi(data):
            """Handle restart Pi command from dashboard"""
            try:
                logger.warning('🔄 RESTART PI command received from dashboard')
                
                # Stop playback first
                self.media_player.stop()
                
                # Send acknowledgment before restarting
                self.sio.emit('pi_restarting', {
                    'pi_id': self.pi_id,
                    'status': 'restarting',
                    'timestamp': time.time()
                })
                
                logger.warning('🔄 Executing system reboot in 2 seconds...')
                time.sleep(2)
                
                # Execute reboot command
                subprocess.run(['sudo', 'reboot'], check=False)
                
            except Exception as e:
                logger.error(f'❌ Restart Pi error: {e}', exc_info=True)
                self.sio.emit('pi_restarting', {
                    'pi_id': self.pi_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        @self.sio.on('restart_client')
        def on_restart_client(data):
            """Restart the complete_pi_client.py process"""
            logger.info(f'🔄 Client restart request received: {data}')
            try:
                # Send acknowledgment
                self.sio.emit('client_restarting', {
                    'pi_id': self.pi_id,
                    'status': 'restarting',
                    'message': 'Client is restarting...'
                })
                
                # Wait a moment to send the response
                time.sleep(0.5)
                
                # Restart the Python process
                import sys
                import os
                logger.info('🔄 Restarting client process...')
                
                # Get the current script path
                script_path = os.path.abspath(__file__)
                
                # Close pygame and cleanup
                if hasattr(self, 'screen'):
                    pygame.quit()
                
                # Execute restart using systemctl if available, otherwise re-exec
                try:
                    # Try systemctl first (if running as service)
                    subprocess.run(['systemctl', '--user', 'restart', 'complete_pi_client'], check=False)
                except:
                    # Fallback: restart current process
                    os.execv(sys.executable, ['python3', script_path])
                    
            except Exception as e:
                logger.error(f'❌ Client restart error: {e}', exc_info=True)
                self.sio.emit('client_restarting', {
                    'pi_id': self.pi_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        @self.sio.on('start_live_stream')
        def on_start_live_stream(data):
            """Start continuous live screen streaming"""
            logger.info(f'📺 Live stream START request: {data}')
            self.streaming_active = True
            # Start streaming thread
            threading.Thread(target=self.live_stream_loop, daemon=True).start()
        
        @self.sio.on('stop_live_stream')
        def on_stop_live_stream(data):
            """Stop continuous live screen streaming"""
            logger.info(f'📺 Live stream STOP request: {data}')
            self.streaming_active = False
        
        @self.sio.on('request_screenshot')
        def on_request_screenshot(data):
            """Handle screenshot request from dashboard (legacy/fallback)"""
            logger.info(f'📸 Screenshot request received: {data}')
            try:
                # Capture screenshot using pygame or scrot
                screenshot_base64 = self.capture_screenshot()
                
                if screenshot_base64:
                    # Send screenshot back via WebSocket
                    self.sio.emit('screenshot_data', {
                        'pi_id': self.pi_id,
                        'screenshot': screenshot_base64,
                        'timestamp': time.time()
                    })
                    logger.info('📸 Screenshot sent successfully')
                else:
                    self.sio.emit('screenshot_data', {
                        'pi_id': self.pi_id,
                        'error': 'Failed to capture screenshot',
                        'timestamp': time.time()
                    })
                    logger.error('❌ Screenshot capture failed')
                    
            except Exception as e:
                logger.error(f'❌ Screenshot error: {e}', exc_info=True)
                self.sio.emit('screenshot_data', {
                    'pi_id': self.pi_id,
                    'error': str(e),
                    'timestamp': time.time()
                })
        
        @self.sio.on('disconnect')
        def on_disconnect():
            logger.warning('❌ WebSocket disconnected from server')
            self.websocket_connected = False
            # Auto-reconnect is handled by Socket.IO client
        
        @self.sio.on('heartbeat_ack')
        def on_heartbeat_ack(data):
            logger.debug('💓 Heartbeat acknowledged by server')
    
    def start_websocket_connection(self):
        """Start WebSocket connection in background thread"""
        def connect_loop():
            while self.running:
                try:
                    if not self.websocket_connected:
                        logger.info(f'🔄 Connecting to WebSocket server: {self.server_url}')
                        self.sio.connect(
                            self.server_url,
                            wait_timeout=10,
                            transports=['polling', 'websocket']  # Try polling first, then upgrade
                        )
                        # Start heartbeat thread
                        threading.Thread(target=self.websocket_heartbeat, daemon=True).start()
                    time.sleep(5)  # Check connection every 5 seconds
                except Exception as e:
                    logger.error(f'❌ WebSocket connection error: {e}')
                    time.sleep(10)  # Wait before retry
        
        ws_thread = threading.Thread(target=connect_loop, daemon=True)
        ws_thread.start()
    
    def websocket_heartbeat(self):
        """Send periodic heartbeat to maintain connection"""
        while self.running and self.websocket_connected:
            try:
                self.sio.emit('pi_heartbeat', {
                    'pi_id': self.pi_id,
                    'state': self.current_state,
                    'timestamp': time.time()
                })
                time.sleep(30)  # Heartbeat every 30 seconds
            except Exception as e:
                logger.error(f'❌ Heartbeat error: {e}')
                break
    
    def capture_screenshot(self) -> str:
        """
        Capture screenshot using x11vnc snapshot or scrot
        True VNC-style remote access capture
        """
        try:
            import io
            import base64
            from PIL import Image
            import subprocess
            import tempfile
            import os
            
            logger.debug("📸 Capturing screen...")
            
            # Try scrot first (fast and reliable for X11)
            try:
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp_path = tmp.name
                
                # Prepare environment with DISPLAY
                env = os.environ.copy()
                env['DISPLAY'] = ':0'
                if 'XAUTHORITY' not in env:
                    env['XAUTHORITY'] = f"/home/{os.getenv('USER', 'everydayadvertise')}/.Xauthority"
                
                logger.debug(f"Running scrot with DISPLAY={env.get('DISPLAY')}, XAUTHORITY={env.get('XAUTHORITY')}")
                
                # Capture with scrot (fast X11 screenshot)
                result = subprocess.run(
                    ['scrot', '-q', '75', '-z', tmp_path],
                    capture_output=True,
                    timeout=2,
                    env=env
                )
                
                if result.returncode == 0:
                    # Read and check if image is valid
                    img = Image.open(tmp_path)
                    logger.info(f"✅ scrot captured {img.size} screenshot")
                    
                    # Check if image is all black (invalid capture)
                    import numpy as np
                    img_array = np.array(img)
                    if np.mean(img_array) < 5:  # Almost completely black
                        logger.warning("⚠️ scrot returned black image, trying fallback...")
                        raise Exception("Black image captured")
                    
                    if img.width > 800:
                        ratio = 800 / img.width
                        new_size = (800, int(img.height * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Convert to JPEG
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=75)
                    buffer.seek(0)
                    
                    screenshot_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                    
                    # Cleanup
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                    
                    logger.info(f"📸 Screenshot captured successfully ({len(screenshot_base64)} bytes)")
                    return screenshot_base64
                else:
                    logger.error(f"❌ scrot failed with code {result.returncode}: {result.stderr.decode()}")
                    
            except Exception as e:
                logger.warning(f"⚠️ scrot capture failed: {e}, trying pygame fallback")
            
            # Try framebuffer capture (fallback)
            try:
                # Read directly from framebuffer device
                with open('/dev/fb0', 'rb') as fb:
                    # Get framebuffer info
                    import fcntl
                    import struct
                    
                    # FBIOGET_VSCREENINFO ioctl
                    FBIOGET_VSCREENINFO = 0x4600
                    
                    # Get screen info
                    vinfo = fcntl.ioctl(fb, FBIOGET_VSCREENINFO, bytes(160))
                    
                    # Parse screen info (first 8 uint32_t values)
                    xres, yres, xres_virtual, yres_virtual = struct.unpack('IIII', vinfo[:16])
                    bits_per_pixel = struct.unpack('I', vinfo[24:28])[0]
                    
                    # Calculate bytes per pixel and frame size
                    bytes_per_pixel = bits_per_pixel // 8
                    frame_size = xres_virtual * yres * bytes_per_pixel
                    
                    # Read framebuffer data
                    fb.seek(0)
                    fb_data = fb.read(frame_size)
                    
                    # Convert to PIL Image based on format
                    if bits_per_pixel == 32:
                        img = Image.frombytes('RGBA', (xres, yres), fb_data, 'raw', 'BGRA')
                        img = img.convert('RGB')
                    elif bits_per_pixel == 24:
                        img = Image.frombytes('RGB', (xres, yres), fb_data, 'raw', 'BGR')
                    elif bits_per_pixel == 16:
                        img = Image.frombytes('RGB', (xres, yres), fb_data, 'raw', 'BGR;16')
                    else:
                        raise Exception(f"Unsupported bpp: {bits_per_pixel}")
                    
                    # Resize for bandwidth efficiency
                    if img.width > 800:
                        ratio = 800 / img.width
                        new_size = (800, int(img.height * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Convert to JPEG
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=75)
                    buffer.seek(0)
                    
                    screenshot_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                    return screenshot_base64
                    
            except Exception as e:
                logger.debug(f"Framebuffer capture failed: {e}, trying pygame")
            
            # Fallback to pygame screen capture for images/UI
            logger.warning("⚠️ Using pygame fallback for screenshot")
            if hasattr(self, 'screen') and self.screen:
                try:
                    # Get pygame surface
                    screen_data = pygame.image.tostring(self.screen, 'RGB')
                    size = self.screen.get_size()
                    
                    # Convert to PIL Image for JPEG compression
                    img = Image.frombytes('RGB', size, screen_data)
                    
                    # Resize for bandwidth efficiency (max 800px wide)
                    if img.width > 800:
                        ratio = 800 / img.width
                        new_size = (800, int(img.height * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Convert to JPEG with compression
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=70)
                    buffer.seek(0)
                    
                    # Encode to base64
                    screenshot_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                    logger.info(f"✅ Pygame screenshot captured ({len(screenshot_base64)} bytes)")
                    return screenshot_base64
                    
                except Exception as e:
                    logger.warning(f'Pygame screenshot failed: {e}')
                    return None
                
        except Exception as e:
            logger.error(f'Screenshot capture failed: {e}', exc_info=True)
            return None
    
    def live_stream_loop(self):
        """Continuously capture and stream frames for live remote viewing"""
        logger.info('📺 Live streaming started')
        frame_count = 0
        target_fps = 15  # 15 FPS for smooth viewing without overwhelming bandwidth
        frame_delay = 1.0 / target_fps
        
        while self.streaming_active and self.websocket_connected:
            try:
                start_time = time.time()
                # If a transition is active, throttle streaming to avoid contention
                try:
                    if hasattr(self, 'media_player') and self.media_player and hasattr(self.media_player, 'is_in_transition'):
                        if self.media_player.is_in_transition():
                            time.sleep(0.2)  # Briefly back off during transitions
                            continue
                except Exception:
                    pass
                
                # Capture frame
                frame_base64 = self.capture_screenshot()
                
                if frame_base64:
                    # Send frame via WebSocket
                    self.sio.emit('live_frame', {
                        'pi_id': self.pi_id,
                        'frame': frame_base64,
                        'frame_number': frame_count,
                        'timestamp': time.time()
                    })
                    frame_count += 1
                    
                    # Calculate delay to maintain target FPS
                    elapsed = time.time() - start_time
                    sleep_time = max(0, frame_delay - elapsed)
                    time.sleep(sleep_time)
                else:
                    logger.warning('Frame capture failed, retrying...')
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f'Live streaming error: {e}')
                time.sleep(1)
        
        logger.info(f'📺 Live streaming stopped (streamed {frame_count} frames)')
        
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
        
        # Calculate a centered two-column layout (QR left, form right) with equal heights
        container_width = 600
        container_height = 500
        try:
            side_by_side = (self.width >= 1100) and getattr(self, 'mobile_sync', None)
        except Exception:
            side_by_side = False
        # Track whether we drew the QR as part of the outer layout
        self._drew_outer_qr = False

        if side_by_side:
            # Compute sizes to center the whole two-column group
            # _render_qr_size may be None until first render; fall back to base size
            qr_size = getattr(self.mobile_sync, '_render_qr_size', None)
            if not qr_size:
                qr_size = getattr(self.mobile_sync, 'qr_size', 300) or 300
            try:
                qr_size = int(qr_size)
            except Exception:
                qr_size = 300
            qr_pad = 30
            divider_w = 10
            gutter = 20
            qr_container_w = qr_size + qr_pad * 2
            group_w = qr_container_w + divider_w + gutter + container_width
            group_x = (self.width - group_w) // 2
            container_y = (self.height - container_height) // 2
            # Ask QR drawer to render with matching container height and no extra divider (we draw it here)
            try:
                self.mobile_sync.draw_qr_code(
                    self.screen,
                    "code" if self.setup_step == "code" else ("store" if self.setup_step == "store" else "screen"),
                    x=group_x,
                    y=container_y,
                    override_qr_size=qr_size,
                    draw_divider=False,
                    override_container_height=container_height
                )
            except Exception:
                pass
            # Divider
            try:
                div_x = group_x + qr_container_w + gutter
                pygame.draw.line(self.screen, (34,48,65), (div_x, max(40, container_y-20)), (div_x, min(self.height-40, container_y+container_height+20)), 1)
            except Exception:
                pass
            # Form container sits immediately to the right of divider
            container_x = group_x + qr_container_w + gutter + divider_w
            self._drew_outer_qr = True
        else:
            # Fallback: center form alone
            container_x = (self.width - container_width) // 2
            container_y = (self.height - container_height) // 2
        container_y = (self.height - container_height) // 2
        
        container = self.create_container_surface(container_width, container_height)
        self.screen.blit(container, (container_x, container_y))
        
        # Title - matching custom_player.py style
        # Slightly larger/bolder title look (UI only)
        title_text = self.font_title.render("Enter your Android TV pairing code", True, self.colors['light_gray'])
        title_rect = title_text.get_rect(center=(container_x + container_width // 2, container_y + 60))
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
        subtitle_rect = subtitle.get_rect(center=(container_x + container_width // 2, container_y + 100))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Input label - LEFT ALIGNED like custom_player.py
        label = self.font_label.render("4-digit code", True, self.colors['medium_gray'])
        label_rect = label.get_rect(topleft=(container_x + 40, container_y + 150))
        self.screen.blit(label, label_rect)
        
        # Input field with custom_player.py styling
        input_width = 300
        input_height = 60
        input_x = container_x + (container_width - input_width) // 2
        input_y = container_y + 180
        
        # Black background with border
        pygame.draw.rect(self.screen, self.colors['input_bg'], (input_x, input_y, input_width, input_height), border_radius=8)
        border_color = self.colors['input_border_focus'] if len(self.input_text) > 0 else self.colors['input_border']
        pygame.draw.rect(self.screen, border_color, (input_x, input_y, input_width, input_height), 2, border_radius=8)
        
        # Input text centered
        # Segmented visual hint: add subtle separators without changing input behavior
        display_text = self.input_text if self.input_text else "____"
        spaced_text = "  ".join(display_text)
        
        input_text_surface = self.font_input.render(spaced_text, True, self.colors['white'])
        text_rect = input_text_surface.get_rect(center=(input_x + input_width // 2, input_y + input_height // 2))
        self.screen.blit(input_text_surface, text_rect)

        # Draw faint internal separators at 1/4, 2/4, 3/4 of the input box (UI only)
        try:
            sep_color = (59, 130, 246)  # blue accent similar to web
            alpha = 70
            overlay = pygame.Surface((input_width, input_height), pygame.SRCALPHA)
            for i in (1,2,3):
                x = int(input_width * i / 4)
                pygame.draw.line(overlay, (*sep_color, alpha), (x, 8), (x, input_height - 8), width=1)
            self.screen.blit(overlay, (input_x, input_y))
        except Exception:
            pass
        
        # Link Code button - center within the form container
        try:
            self._form_center_x = container_x + container_width // 2
        except Exception:
            self._form_center_x = None
        self.draw_link_button(container_y + 280)
        
        # Status message
        if hasattr(self, 'status_message'):
            status_color = self.colors['success'] if 'accepted' in self.status_message else self.colors['error']
            status_text = self.font_small.render(self.status_message, True, status_color)
            status_rect = status_text.get_rect(center=(self.width // 2, container_y + 350))
            self.screen.blit(status_text, status_rect)
        
        # MOBILE SYNC ADDON: Draw QR code for mobile input
        if hasattr(self, 'mobile_sync') and self.mobile_sync and not getattr(self, '_drew_outer_qr', False):
            self.mobile_sync.draw_qr_code(self.screen, "code")
            
    def draw_link_button(self, y_pos: int):
        """Draw Link Code button matching custom_player.py style."""
        button_width = 200
        button_height = 50
        # Center within form container when available
        try:
            if getattr(self, '_form_center_x', None) is not None:
                button_x = int(self._form_center_x - button_width // 2)
            else:
                button_x = (self.width - button_width) // 2
        except Exception:
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
        """Draw store code entry screen matching custom_player.py."""
        # Title
        title = self.font_title.render("Enter Store ID", True, self.colors['light_gray'])
        title_rect = title.get_rect(center=(self.width // 2, container_y + 100))
        self.screen.blit(title, title_rect)
        
        # Subtitle showing TV code
        subtitle = self.font_subtitle.render(f"TV Code: {self.pair_code}", True, self.colors['gray'])
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Input label
        input_label = self.font_label.render("Store code", True, self.colors['light_gray'])
        input_rect_x = (self.width - 400) // 2
        input_rect_y = container_y + 200
        self.screen.blit(input_label, (input_rect_x, input_rect_y))
        
        # Input field
        input_width = 400
        input_height = 50
        input_x = (self.width - input_width) // 2
        input_y = input_rect_y + 35
        
        pygame.draw.rect(self.screen, self.colors['black'], 
                        (input_x, input_y, input_width, input_height), border_radius=5)
        pygame.draw.rect(self.screen, self.colors['input_border'], 
                        (input_x, input_y, input_width, input_height), 2, border_radius=5)
        
        # Display store ID input
        input_display = self.input_text
        input_surface = self.font_input.render(input_display, True, self.colors['white'])
        input_text_rect = input_surface.get_rect(center=(input_x + input_width // 2, input_y + input_height // 2))
        self.screen.blit(input_surface, input_text_rect)
        
        # Continue button
        button_width = 200
        button_height = 50
        button_x = (self.width - button_width) // 2
        button_y = input_y + 80
        
        enabled = len(self.input_text) > 0 and self.input_text.isdigit()
        bg_color = self.colors['pizza_red'] if enabled else (102, 102, 102)
        
        button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
        pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=8)
        
        # Store button rect for click detection
        self.link_button_rect = button_rect if enabled else None
        
        button_text = self.font_button.render("Continue", True, self.colors['white'])
        text_rect = button_text.get_rect(center=(button_x + button_width // 2, button_y + button_height // 2))
        self.screen.blit(button_text, text_rect)
        
        # Note
        note = self.font_small.render("You'll choose a screen next", True, self.colors['gray'])
        note_rect = note.get_rect(center=(self.width // 2, button_y + 70))
        self.screen.blit(note, note_rect)
        
        # MOBILE SYNC ADDON: Draw QR code for mobile store input
        if hasattr(self, 'mobile_sync') and self.mobile_sync and not getattr(self, '_drew_outer_qr', False):
            self.mobile_sync.draw_qr_code(self.screen, "store")
            
    def draw_screen_selection_screen(self, container_x: int, container_y: int, container_width: int):
        """Draw screen selection screen - shows screens available for this store."""
        # Title
        title = self.font_title.render("Select Screen", True, self.colors['white'])
        title_rect = title.get_rect(center=(self.width // 2, container_y + 80))
        self.screen.blit(title, title_rect)
        
        # Subtitle showing store code
        subtitle = self.font_subtitle.render(f"Store: {self.store_id} | TV Code: {self.pair_code}", True, self.colors['gray'])
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, container_y + 120))
        self.screen.blit(subtitle, subtitle_rect)
        
        start_y = container_y + 180
        
        # Clear and rebuild screen button rects
        self.screen_button_rects = {}
        
        # Show available screens (or default TV1-TV4 if fetching)
        if self.available_screens:
            # API returns screens with store prefix like "1000_screen1"
            # Strip the store prefix for display and use
            screen_ids = []
            for full_screen_id in self.available_screens.keys():
                # Extract just the screen part (e.g., "screen1" from "1000_screen1")
                if '_' in full_screen_id:
                    screen_id = full_screen_id.split('_', 1)[1]
                else:
                    screen_id = full_screen_id
                screen_ids.append(screen_id)
        else:
            screen_ids = ["tv1", "tv2", "tv3", "tv4"]
        
        # Show all screens with scrollable layout
        button_height = 50
        button_spacing = 10
        max_visible = min(len(screen_ids), 8)  # Show up to 8 screens at once
        
        for i, screen_id in enumerate(screen_ids[:max_visible]):
            screen_y = start_y + i * (button_height + button_spacing)
            
            button_width = container_width - 60
            button_x = container_x + 30
            
            bg_color = (50, 50, 50)
            button_rect = pygame.Rect(button_x, screen_y, button_width, button_height)
            pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=5)
            
            # Store button rect with screen_id for click detection
            self.screen_button_rects[screen_id] = button_rect
            
            # Display screen name
            screen_display = f"Screen {screen_id.upper()}"
            # Check if we have screen info from API
            full_screen_id = f"{self.store_id}_{screen_id}"
            if self.available_screens and full_screen_id in self.available_screens:
                screen_info = self.available_screens[full_screen_id]
                if isinstance(screen_info, dict) and 'name' in screen_info:
                    screen_display = screen_info['name']
            
            screen_text = self.font_button.render(screen_display, True, self.colors['white'])
            text_rect = screen_text.get_rect(center=(button_x + button_width // 2, screen_y + button_height // 2))
            self.screen.blit(screen_text, text_rect)
        
        # Show count if more screens available
        if len(screen_ids) > max_visible:
            note = self.font_small.render(f"Showing {max_visible} of {len(screen_ids)} screens", True, self.colors['gray'])
            note_rect = note.get_rect(center=(self.width // 2, start_y + (max_visible * (button_height + button_spacing)) + 20))
            self.screen.blit(note, note_rect)
        
        # MOBILE SYNC ADDON: Draw QR code for mobile screen selection
        if hasattr(self, 'mobile_sync') and self.mobile_sync and not getattr(self, '_drew_outer_qr', False):
            self.mobile_sync.draw_qr_code(self.screen, "screen")
            
    def draw_playing_screen(self):
        """Draw playing screen - let media player handle the display."""
        if not self.playlist:
            # Show idle message like webplayer
            self.screen.fill(self.colors['black'])
            idle_text = self.font_subtitle.render("Waiting for schedule...", True, self.colors['white'])
            idle_rect = idle_text.get_rect(center=(self.width // 2, self.height // 2))
            self.screen.blit(idle_text, idle_rect)
            
        # NOTE: Overlay info removed to prevent flicker during video playback
        # Only Pi ID overlay is shown occasionally (every 3 seconds)
    
    def draw_pi_id_overlay(self):
        """Draw Pi ID overlay - called separately to ensure it's always on top."""
        # Check visibility and auto-hide
        should_show_pi_id = self.show_pi_id
        
        # Auto-hide after specified time (if enabled)
        if self.pi_id_auto_hide_seconds > 0 and self.show_pi_id:
            elapsed = time.time() - self.pi_id_last_shown
            if elapsed > self.pi_id_auto_hide_seconds:
                should_show_pi_id = False
        
        if should_show_pi_id:
            # Pi ID watermark at bottom center (LARGE and visible)
            try:
                # Create a large font for Pi ID (36px, bold)
                pi_id_font = pygame.font.SysFont('arial', 36, bold=True)
            except:
                pi_id_font = pygame.font.Font(None, 36)
            
            pi_id_text = f"Pi ID: {self.pi_id}"
            hint_text = "[Press 'I' to hide]"
            
            # Render main Pi ID text (white, bold, large)
            pi_id_surface = pi_id_font.render(pi_id_text, True, (255, 255, 255))
            pi_id_rect = pi_id_surface.get_rect()
            pi_id_rect.centerx = self.width // 2
            pi_id_rect.bottom = self.height - 50
            
            # Render hint text (smaller, gray)
            hint_surface = self.font_small.render(hint_text, True, (170, 170, 170))
            hint_rect = hint_surface.get_rect()
            hint_rect.centerx = self.width // 2
            hint_rect.top = pi_id_rect.bottom + 5
            
            # Add background for better visibility (larger padding)
            bg_width = max(pi_id_rect.width, hint_rect.width) + 40
            bg_height = (hint_rect.bottom - pi_id_rect.top) + 20
            bg_rect = pygame.Rect(
                (self.width - bg_width) // 2,
                pi_id_rect.top - 10,
                bg_width,
                bg_height
            )
            bg_surface = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 200))  # More opaque black background
            pygame.draw.rect(bg_surface, (200, 16, 46), bg_surface.get_rect(), 2, border_radius=8)  # Red border
            self.screen.blit(bg_surface, bg_rect)
            
            # Draw Pi ID text
            self.screen.blit(pi_id_surface, pi_id_rect)
            self.screen.blit(hint_surface, hint_rect)
        
    def draw_overlay_info(self):
        """Draw overlay information like webplayer."""
        # Top info
        info_text = f"Store {self.store_id} • Screen {self.screen_id}"
        if self.playlist:
            info_text += f" • Item {self.current_index + 1}/{len(self.playlist)}"
            
        # Get cache info for debugging
        cache_info = self.media_player.get_cache_info()
        debug_text = f"Cache: {cache_info['memory_items']}mem/{cache_info['download_items']}dl/{cache_info['cache_size_mb']:.1f}MB"
        
        # Top overlay
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
            if self.use_local_schedule_filter:
                params['skip_schedule_filter'] = '1'
            headers = {
                'Cache-Control': 'no-store, no-cache, must-revalidate',
                'Pragma': 'no-cache'
            }
            
            if self.pair_code:
                params['user_code'] = self.pair_code
                headers['X-User-Code'] = self.pair_code
            
            logger.info(f"📡 Fetching playlist: {url}")
            logger.info(f"   Params: {params}")
            
            # CRITICAL: Use a fresh session to avoid sending cached cookies
            # The server prioritizes session cookies over pair codes, which causes wrong config to load
            session = requests.Session()
            session.cookies.clear()  # Ensure no cookies are sent
                
            response = session.get(url, params=params, headers=headers, timeout=10)
            
            logger.info(f"📡 Playlist response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"📡 Playlist data: success={data.get('success')}, items={len(data.get('playlist', []))}")
                
                # Parse screen orientation and rotation
                new_orientation = data.get('orientation', 'default')
                new_rotation = int(data.get('rotation', 0))
                
                # Detect rotation or orientation changes
                old_orientation = getattr(self, 'screen_orientation', None)
                # Use dedicated last-seen tracker to avoid masking changes by early assignment
                old_rotation = getattr(self, '_last_rotation_seen', None)
                orientation_changed = (new_orientation != old_orientation)
                rotation_changed = (new_rotation != old_rotation)
                
                print(f"🔍 ROTATION CHECK: old={old_rotation}° new={new_rotation}° changed={rotation_changed}", flush=True)
                logger.info(f"🔍 Rotation check: old={old_rotation}° new={new_rotation}° changed={rotation_changed}")
                logger.info(f"🔍 Orientation check: old={old_orientation} new={new_orientation} changed={orientation_changed}")
                
                self.screen_orientation = new_orientation
                self.screen_rotation = new_rotation
                logger.info(f"🔄 Screen config: orientation={self.screen_orientation}, rotation={self.screen_rotation}°")
                
                # NUCLEAR FIX: If rotation changed, completely restart playback FIRST
                if rotation_changed or orientation_changed:
                    logger.info(f"🔄🔄🔄 ROTATION CHANGED! Forcing complete playback restart...")
                    try:
                        # Apply the new display rotation immediately so next frames use it
                        try:
                            base = 90 if str(new_orientation or 'default') == 'vertical' else 0
                            total = ((base + (new_rotation or 0)) % 360 + 360) % 360
                            if hasattr(self.media_player, 'set_display_rotation'):
                                self.media_player.set_display_rotation(total)
                                logger.info(f"📐 Applied display rotation before reload: total={total}°")
                        except Exception as e_apply_first:
                            logger.warning(f"⚠️ Could not apply rotation pre-reload: {e_apply_first}")

                        # Clear cached images so they re-render with new rotation
                        try:
                            if hasattr(self.media_player, 'image_cache') and isinstance(self.media_player.image_cache, dict):
                                self.media_player.image_cache.clear()
                                logger.info("🧹 Cleared image cache due to rotation change")
                        except Exception as e_cache:
                            logger.warning(f"⚠️ Could not clear image cache: {e_cache}")

                        # Stop everything
                        self.media_player.stop()
                        logger.info("✋ Stopped media player")
                        
                        # Reset current state
                        self.current_item_key = None
                        logger.info("🔄 Reset current item key")
                        
                        # Force advance in a new thread to avoid blocking
                        import threading
                        def force_reload():
                            import time
                            time.sleep(0.5)  # Small delay to ensure stop completes
                            logger.info("🚀 Forcing advance to reload with new rotation")
                            self.current_index = 0
                            self.advance_to_next_item()
                        threading.Thread(target=force_reload, daemon=True).start()
                        logger.info("✅ Reload thread started")
                    except Exception as e_reload:
                        logger.error(f"❌ Failed to reload after rotation change: {e_reload}", exc_info=True)
                
                # Update last-seen rotation AFTER applying any restarts to ensure next comparison is correct
                self._last_rotation_seen = self.screen_rotation
                
                # Apply orientation+rotation to media player (like webplayer)
                try:
                    base = 90 if str(self.screen_orientation or 'default') == 'vertical' else 0
                    total = ((base + (self.screen_rotation or 0)) % 360 + 360) % 360
                    if hasattr(self.media_player, 'set_display_rotation'):
                        self.media_player.set_display_rotation(total)
                        logger.info(f"📐 Applied display rotation: total={total}°")
                except Exception as e:
                    logger.error(f"❌ Rotation apply failed: {e}", exc_info=True)
                
                if data.get('success') and data.get('playlist'):
                    playlist_data = data['playlist']
                    playlist = [PlaylistItem.from_dict(item) for item in playlist_data]
                    logger.info(f"📥 Fetched {len(playlist)} playlist items")
                    if playlist:
                        logger.info(f"   First item: {playlist[0].file}")
                    return playlist
                else:
                    logger.warning(f"⚠️ Playlist API returned error: {data.get('error', 'unknown')}")
            else:
                logger.warning(f"⚠️ Playlist API returned {response.status_code}: {response.text[:200]}")
                    
        except Exception as e:
            logger.error(f"❌ Playlist fetch failed: {e}", exc_info=True)
            
        return []
    
    def filter_playlist_by_schedule(self, playlist: List[PlaylistItem]) -> List[PlaylistItem]:
        """
        Filter playlist items based on schedule settings from dashboard.
        Respects: enabled flag, start/end times, days of week, schedule windows
        """
        if not playlist:
            logger.info("📋 No playlist items to filter")
            return []
        
        logger.info(f"📋 Filtering {len(playlist)} playlist items by schedule")
        
        # Get current server time
        server_time_ms = self.time_sync.get_server_time()
        dt = datetime.fromtimestamp(server_time_ms / 1000)
        current_day = dt.isoweekday()  # 1=Monday, 7=Sunday
        current_time = dt.time()
        current_date = dt.date()
        
        logger.info(f"📅 Current time: {dt.strftime('%Y-%m-%d %H:%M:%S')} (Day: {current_day})")
        
        filtered = []
        
        for item in playlist:
            # Get raw dict data for schedule checking
            item_dict = asdict(item) if hasattr(item, '__dataclass_fields__') else {}
            
            logger.info(f"🔍 Checking item: {item.file}")
            logger.info(f"   enabled: {item_dict.get('enabled', True)}, schedule: {item_dict.get('schedule', 'none')}")
            
            # Check enabled flag (tick checkbox in dashboard)
            if not item_dict.get('enabled', True):
                logger.info(f"⏭️  Skipping disabled item: {item.file}")
                continue
            
            # Check schedule windows
            if not self.is_within_schedule(item_dict, current_day, current_time, current_date):
                logger.info(f"⏰ Item {item.file} not scheduled for current time")
                continue
            
            logger.info(f"✅ Item {item.file} passed schedule check")
            filtered.append(item)
        
        if len(filtered) < len(playlist):
            logger.info(f"📋 Schedule filtered: {len(filtered)}/{len(playlist)} items active")
        else:
            logger.info(f"📋 All {len(filtered)} items passed schedule filter")
        
        return filtered
    
    def is_within_schedule(self, item_dict: Dict, current_day: int, current_time, current_date) -> bool:
        """
        Check if item should play at current time.
        Handles: schedule array, legacy start/end, days of week
        """
        # Get schedule windows from item
        schedules = item_dict.get('schedule', [])
        
        # If no schedule array, check legacy start/end fields
        if not schedules:
            return self.check_legacy_schedule(item_dict, current_time, current_date)
        
        # Check if ANY schedule window matches
        for sched in schedules:
            if self.matches_schedule_window(sched, current_day, current_time, current_date):
                return True
        
        # No windows matched
        return False
    
    def matches_schedule_window(self, sched: Dict, current_day: int, current_time, current_date) -> bool:
        """Check if current time matches a single schedule window"""
        
        # Check days of week (M T W T F S S from dashboard)
        days = sched.get('days', [])  # [1,2,3,4,5] = Mon-Fri
        if days and current_day not in days:
            return False
        
        # Check start date/time
        start_str = sched.get('start', '')
        start_dt = None
        if start_str:
            try:
                # Parse "mm/dd/yyyy HH:MM:SS" or "HH:MM:SS" or "HH:MM" or date-only
                start_dt = self.parse_datetime(start_str)
                if start_dt:
                    if isinstance(start_dt, datetime):
                        # Full datetime comparison
                        current_dt = datetime.combine(current_date, current_time)
                        if current_dt < start_dt:
                            return False
                    else:
                        # Time-only start handled with end below (supports overnight)
                        pass
            except:
                pass
        
        # Check end date/time
        end_str = sched.get('end', '')
        if end_str:
            try:
                end_dt = self.parse_datetime(end_str)
                if end_dt:
                    if isinstance(end_dt, datetime):
                        # Full datetime comparison
                        current_dt = datetime.combine(current_date, current_time)
                        if current_dt > end_dt:
                            return False
                    else:
                        # Time-only comparison with optional overnight handling when start is also time-only
                        if isinstance(start_dt, datetime):
                            # Mixed types already handled above
                            pass
                        else:
                            st_t = start_dt if start_dt else None
                            en_t = end_dt
                            if st_t is None:
                                # Only end provided: allow midnight..end
                                if current_time > en_t:
                                    return False
                            else:
                                if st_t <= en_t:
                                    # Normal window within same day
                                    if not (st_t <= current_time <= en_t):
                                        return False
                                else:
                                    # Overnight (e.g., 23:00 -> 02:00)
                                    if not (current_time >= st_t or current_time <= en_t):
                                        return False
            except:
                pass
        
        # All checks passed!
        return True
    
    def get_time_until_schedule_end(self, item: PlaylistItem) -> Optional[float]:
        """Return seconds remaining in the active schedule window for this item, if any."""
        try:
            item_dict = asdict(item) if hasattr(item, '__dataclass_fields__') else dict(item or {})
        except Exception:
            item_dict = {}

        if not item_dict:
            return None

        server_ms = self.time_sync.get_server_time()
        current_dt = datetime.fromtimestamp(server_ms / 1000.0)
        current_day = current_dt.isoweekday()
        current_time = current_dt.time()
        current_date = current_dt.date()

        def _delta_from_window(start_raw: Optional[str], end_raw: Optional[str]) -> Optional[float]:
            if not end_raw:
                return None

            try:
                end_val = self.parse_datetime(end_raw)
            except Exception:
                return None

            try:
                start_val = self.parse_datetime(start_raw) if start_raw else None
            except Exception:
                start_val = None

            target_dt = None
            if isinstance(end_val, datetime):
                target_dt = end_val
            elif isinstance(end_val, dtime):
                ref_date = current_date
                start_time = None
                if isinstance(start_val, datetime):
                    start_time = start_val.time()
                elif isinstance(start_val, dtime):
                    start_time = start_val

                if start_time and start_time > end_val:
                    if current_time >= start_time:
                        ref_date = current_date + timedelta(days=1)
                elif not start_time and end_val <= current_time:
                    ref_date = current_date + timedelta(days=1)

                target_dt = datetime.combine(ref_date, end_val)

            if not target_dt:
                return None

            delta = (target_dt - current_dt).total_seconds()
            return max(delta, 0.0)

        best_delta = None
        schedules = item_dict.get('schedule') or []
        if schedules:
            for sched in schedules:
                if not isinstance(sched, dict):
                    continue
                if not self.matches_schedule_window(sched, current_day, current_time, current_date):
                    continue
                delta = _delta_from_window(sched.get('start'), sched.get('end'))
                if delta is None:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta = delta
            if best_delta is not None:
                return best_delta

        # Legacy start/end fields
        legacy_start = item_dict.get('start')
        legacy_end = item_dict.get('end')
        if legacy_end:
            # Legacy schedule assumes always active if item passed filtering, so just compute delta
            return _delta_from_window(legacy_start, legacy_end)

        return None

    def check_legacy_schedule(self, item_dict: Dict, current_time, current_date) -> bool:
        """Check legacy start/end fields (not in schedule array)"""
        
        start_str = item_dict.get('start', '')
        end_str = item_dict.get('end', '')
        
        # If no start/end, item is always active
        if not start_str and not end_str:
            return True
        
        # Check start time
        if start_str:
            try:
                start_dt = self.parse_datetime(start_str)
                if start_dt:
                    if isinstance(start_dt, datetime):
                        current_dt = datetime.combine(current_date, current_time)
                        if current_dt < start_dt:
                            return False
                    elif current_time < start_dt:
                        return False
            except:
                pass
        
        # Check end time
        if end_str:
            try:
                end_dt = self.parse_datetime(end_str)
                if end_dt:
                    if isinstance(end_dt, datetime):
                        current_dt = datetime.combine(current_date, current_time)
                        if current_dt > end_dt:
                            return False
                    elif current_time > end_dt:
                        return False
            except:
                pass
        
        return True
    
    def parse_datetime(self, time_str: str):
        """
        Parse time string from dashboard.
        Supports: "HH:MM:SS", "HH:MM", "mm/dd/yyyy HH:MM:SS"
        Returns: datetime, time, or None
        """
        if not time_str:
            return None
        
        time_str = time_str.strip()
        
        # Try full datetime: "mm/dd/yyyy HH:MM:SS"
        try:
            return datetime.strptime(time_str, "%m/%d/%Y %H:%M:%S")
        except:
            pass
        # Try date only: "mm/dd/yyyy" (treated as that day at 00:00)
        try:
            d = datetime.strptime(time_str, "%m/%d/%Y").date()
            from datetime import time as _t
            return datetime.combine(d, _t(0,0,0))
        except:
            pass
        
        # Try time with seconds: "HH:MM:SS"
        try:
            return datetime.strptime(time_str, "%H:%M:%S").time()
        except:
            pass
        
        # Try time without seconds: "HH:MM"
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except:
            pass
        
        return None
        
    def sync_effect_from_server(self):
        """Sync global effect from server like webplayer."""
        try:
            if not self.store_id:
                return
                
            response = requests.get(f"{self.server_url}/api/get-effect/{self.store_id}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                effect_name = data.get('effect_name')
                # Master toggle detection: only respect explicit 'transitions_enabled' unless forced ON via env
                master_flag = None
                if not getattr(self, 'force_transitions_on', False):
                    # Prefer explicit 'transitions_enabled', fallback to 'enabled' if present
                    if 'transitions_enabled' in data or 'enabled' in data:
                        val = data.get('transitions_enabled') if 'transitions_enabled' in data else data.get('enabled')
                        if isinstance(val, bool):
                            master_flag = val
                        elif isinstance(val, (int, float)):
                            master_flag = bool(val)
                        elif isinstance(val, str):
                            master_flag = val.strip().lower() in ('1','true','on','enabled','yes')
                    # If server explicitly returns 'cut' and provides no transitions_enabled flag, leave master as-is
                else:
                    if not self.transitions_master_enabled:
                        self.transitions_master_enabled = True
                    if data.get('transitions_enabled') is False:
                        logger.info("🎛️ Server transitions_enabled=False ignored due to PHTV_FORCE_TRANSITIONS")
                # Update master flag if found
                if master_flag is not None and master_flag != self.transitions_master_enabled:
                    self.transitions_master_enabled = master_flag
                    logger.info(f"🎛️  Transitions master toggle set to: {'ON' if self.transitions_master_enabled else 'OFF'} (from server)")
                
                if not effect_name and data.get('effect_id'):
                    # Map effect_id to our new 10-effect canonical names
                    # 1..10 correspond to: cut, fade, dissolve, slide-l, slide-r, slide-up, slide-down, zoom-in, zoom-out, wipe-lr
                    effect_map = {
                        '1': 'cut',
                        '2': 'fade',
                        '3': 'dissolve',
                        '4': 'slide-l',
                        '5': 'slide-r',
                        '6': 'slide-up',
                        '7': 'slide-down',
                        '8': 'zoom-in',
                        '9': 'zoom-out',
                        '10': 'wipe-lr',
                    }
                    effect_name = effect_map.get(str(data['effect_id']), 'fade')
                    
                # Detect change and hot-apply like rotation
                if effect_name and effect_name != self.current_global_effect:
                    prev = self.current_global_effect
                    self.current_global_effect = effect_name
                    logger.info(f"🎨 Effect synchronized from server: {prev} -> {self.current_global_effect}")
                    # If we're actively playing and transitions are enabled (or forced), advance once to show effect now
                    try:
                        if self.current_state == 'playing' and (self.transitions_master_enabled or self.force_transitions_on):
                            self._force_advance(reason="effect_change")
                    except Exception as e_adv:
                        logger.debug(f"Effect change advance skipped: {e_adv}")
                    
        except Exception as e:
            logger.debug(f"Effect sync failed: {e}")

    def _force_advance(self, reason: str = ""):
        """Safely force an advance to next item, respecting anti-thrashing gap."""
        try:
            if not self.playlist:
                return
            now_ts = time.time()
            gap_ok = (now_ts - getattr(self, '_last_advance_time', 0.0)) >= self.MIN_ADVANCE_GAP
            if not gap_ok:
                logger.info(f"⏳ Skip forced advance ({reason}); within min advance gap {self.MIN_ADVANCE_GAP}s")
                return
            self._last_advance_time = now_ts
            # Move to next index and play
            self.current_index = (self.current_index + 1) % len(self.playlist)
            logger.info(f"⏩ Forced advance triggered ({reason})")
            self.advance_to_next_item()
        except Exception as e:
            logger.debug(f"_force_advance error: {e}")
            
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
                        # Sync effect first so it applies immediately like rotation hot-apply
                        try:
                            self.sync_effect_from_server()
                        except Exception as e_sync:
                            logger.debug(f"Effect sync before reload failed: {e_sync}")
                        self.fetch_and_update_playlist(force_advance=True)
                        
        except Exception as e:
            logger.debug(f"Commands poll failed: {e}")
            
    def validate_tv_code(self, code: str) -> bool:
        """Validate TV code with API."""
        try:
            response = requests.get(f"{self.server_url}/api/stores_by_code/{code}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # API returns {success, user, stores, screens}
                if data.get('success'):
                    logger.info(f"✅ Valid TV code: {code}")
                    return True
                else:
                    logger.warning(f"❌ Invalid TV code response: {data}")
                    return False
            else:
                logger.warning(f"❌ Invalid TV code HTTP {response.status_code}: {code}")
                return False
                
        except Exception as e:
            logger.error(f"TV code validation failed: {e}")
            return False
    
    def fetch_available_screens(self, store_code: str) -> Dict:
        """Fetch available screens for a store from API."""
        try:
            # Use the same endpoint as webplayer browse page
            response = requests.get(
                f"{self.server_url}/api/stores_by_code/{self.pair_code}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'screens' in data:
                    # screens format: {store_id: {screen_id: screen_data}}
                    all_screens = data['screens']
                    if store_code in all_screens:
                        logger.info(f"✅ Found {len(all_screens[store_code])} screens for store {store_code}")
                        return all_screens[store_code]
                    else:
                        logger.warning(f"⚠️ Store {store_code} not in screens data")
                        return {}
                else:
                    logger.warning(f"❌ No screens data in response")
                    return {}
            else:
                logger.warning(f"❌ Failed to fetch screens: HTTP {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to fetch screens: {e}")
            return {}
            
    def fetch_and_update_playlist(self, force_advance: bool = False):
        """Fetch playlist and update if changed."""
        # Serialize to avoid concurrent fetch/update masking rotation changes
        acquired = self._playlist_lock.acquire(blocking=False)
        if not acquired:
            logger.info("⏳ Skipping fetch: previous fetch still in progress")
            return
        try:
            raw_playlist = self.fetch_playlist()
            
            if raw_playlist:
                # Apply schedule filtering (respects enabled flag, start/end times, days of week)
                new_playlist = self.filter_playlist_by_schedule(raw_playlist)
                
                # Show waiting screen if nothing scheduled
                if not new_playlist:
                    logger.info("⏰ No items scheduled for current time - showing waiting screen")
                    self.playlist = []
                    self.playlist_signature = ""
                    return
                
                # Compute signature to detect changes (include last-seen rotation, not the just-read value)
                new_signature = self.compute_playlist_signature(new_playlist)
                signature_changed = bool(self.playlist_signature) and new_signature != self.playlist_signature
                
                # Track keys for current/next validation
                new_keys = set()
                for it in new_playlist:
                    if it.id:
                        new_keys.add(f"id:{it.id}")
                    elif it.url:
                        new_keys.add(f"url:{it.url}")
                    elif it.file:
                        new_keys.add(f"file:{it.file}")

                self.playlist = new_playlist
                self.playlist_signature = new_signature
                
                # Preload upcoming items
                self.preload_upcoming_items()
                
                # Handle playlist changes OR start playback if nothing is playing
                # Hysteresis: only advance if forced OR current item removed. If signature changed but
                # current item still valid, keep playing to avoid rapid switching.
                should_advance = bool(force_advance)
                advance_reason = "forced" if force_advance else ""

                # If the currently playing item is no longer scheduled, advance
                if self.current_item_key and self.current_item_key not in new_keys:
                    logger.info("⏭️ Current item no longer scheduled — advancing")
                    should_advance = True
                    advance_reason = "item_removed"
                
                # Debug summary (reduced verbosity)
                logger.info(f"Playlist check: changed={signature_changed}, forced={force_advance}, items={len(self.playlist)}, current_key={self.current_item_key}")
                
                # **TESTING FIX**: If we have a playlist but nothing is playing, force start
                if not should_advance and self.playlist and not self.current_item_key:
                    logger.info("Starting playback: have playlist but nothing is currently playing")
                    should_advance = True
                    advance_reason = "start_playback"
                
                logger.info(f"Advance decision: should_advance={should_advance}, reason={advance_reason}")
                
                if should_advance:
                    # Anti-thrashing: require a gap between advances triggered by updates
                    now_ts = time.time()
                    if (now_ts - getattr(self, '_last_advance_time', 0.0)) < self.MIN_ADVANCE_GAP:
                        logger.info(f"⏳ Skip advance; within min advance gap {self.MIN_ADVANCE_GAP}s")
                        return
                    self._last_advance_time = now_ts
                    logger.info("📋 Playlist changed - advancing to new content")
                    self.current_index = 0
                    self.advance_to_next_item()
            else:
                # No playlist from server
                self.playlist = []
                self.playlist_signature = ""
        finally:
            try:
                self._playlist_lock.release()
            except Exception:
                pass
                
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
                    
            # Include orientation and display rotation so layout changes trigger update
            rot = getattr(self, 'screen_rotation', 0) or 0
            ori = getattr(self, 'screen_orientation', '') or ''
            signature = "|".join(keys + [f"ori:{ori}", f"rot:{rot}"])
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

        # Prevent overlapping advances which can cause flicker/double starts
        acquired = self._advance_lock.acquire(blocking=False)
        if not acquired:
            logger.info("⏳ Skipping advance: previous advance still in progress")
            return
        try:
            if self.current_index >= len(self.playlist):
                self.current_index = 0
                
            current_item = self.playlist[self.current_index]
            media_url = self.get_media_url(current_item)
            self._stop_video_on_timer = False

            is_video_item = False
            try:
                is_video_item = str(getattr(current_item, 'media_type', '')).lower() == 'video'
            except Exception:
                is_video_item = False

            if not is_video_item and media_url:
                try:
                    parsed_path = urlparse(media_url)
                    candidate_path = parsed_path.path or ''
                except Exception:
                    candidate_path = media_url
                lower_candidate = (candidate_path or '').lower()
                if lower_candidate.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    is_video_item = True
            
            # DEBUG: Log the raw item data to see what effect we got from server
            try:
                logger.info(f"🔍 DEBUG Item data: id={current_item.id}, file={current_item.file}, effect={getattr(current_item, 'effect', 'NOT SET')}, enabled={getattr(current_item, 'enabled', 'NOT SET')}")
            except Exception as e_dbg:
                logger.debug(f"Debug log failed: {e_dbg}")
            
            if media_url:
                try:
                    duration = float(getattr(current_item, 'duration', 10.0) or 10.0)
                except Exception:
                    duration = 10.0

                schedule_remaining = self.get_time_until_schedule_end(current_item)
                stop_video_early = is_video_item

                if schedule_remaining is not None:
                    if schedule_remaining < duration:
                        logger.info(
                            f"⏰ Schedule window ends in {schedule_remaining:.2f}s; overriding duration {duration:.2f}s"
                        )
                        duration = max(schedule_remaining, 0.1)
                        if is_video_item:
                            stop_video_early = True
                try:
                    if (schedule_remaining is None or schedule_remaining >= self.MIN_ITEM_DURATION) and duration < self.MIN_ITEM_DURATION:
                        logger.info(f"⏱️ Requested duration {duration}s < min {self.MIN_ITEM_DURATION}s; clamping")
                        duration = self.MIN_ITEM_DURATION
                except Exception:
                    pass

                if is_video_item:
                    stop_video_early = True
                self._stop_video_on_timer = stop_video_early
                if duration <= 0:
                    duration = 0.1

                # Determine the effect to use: item effect > global effect > default 'fade'
                # Item effect is the PRIMARY source (set per-item in dashboard)
                item_effect = getattr(current_item, 'effect', None)
                if item_effect:
                    desired_effect_raw = item_effect
                else:
                    # Fallback to global effect (synced from server)
                    desired_effect_raw = self.current_global_effect or 'fade'
                desired_effect = self._normalize_effect(desired_effect_raw)

                # Decide media type of next item (by extension), ignore query params
                try:
                    _parsed = urlparse(media_url)
                    _path = _parsed.path or ''
                except Exception:
                    _path = media_url
                _lower = _path.lower()
                next_is_video = _lower.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov'))
                if next_is_video and not is_video_item:
                    is_video_item = True
                try:
                    prev_media_type = getattr(self.media_player, 'current_media_type', None)
                    boundary = f"{prev_media_type or 'none'} -> {'video' if next_is_video else 'image'}"
                    logger.info(f"🔀 Boundary: {boundary}")
                except Exception:
                    pass

                # If master is OFF or transitions disabled (env/fault), force cut
                # Otherwise allow selected effect even for video->video (handled safely in player)
                effect = desired_effect
                # Respect forced transitions override for debugging/validation
                if not self.force_transitions_on:
                    if not self.transitions_master_enabled:
                        effect = 'cut'
                    elif self.disable_transitions or self._transitions_faulted:
                        effect = 'cut'
                else:
                    if (self.disable_transitions or self._transitions_faulted) and effect == 'cut':
                        logger.info("🎛️ PHTV_FORCE_TRANSITIONS overriding disabled/faulted state; using requested effect")

                logger.info(f"🎬 Playing item {self.current_index + 1}/{len(self.playlist)}: {media_url}")
                logger.info(
                    f"🎨 Effect source: {'per-item' if item_effect else 'global'} | "
                    f"raw='{desired_effect_raw}' -> normalized='{desired_effect}' -> using='{effect}' | "
                    f"master={'ON' if self.transitions_master_enabled else 'OFF'}"
                )

                # 🎯 Pass item to player for sync monitoring
                success = False
                try:
                    success = self.media_player.play_media(media_url, effect, duration, item=current_item)
                except Exception as e:
                    logger.error(f"❌ play_media raised exception with effect='{effect}': {e}", exc_info=True)
                    success = False

                # Fallback: if transition failed and we weren't using cut, retry once with cut and disable transitions for session
                if not success and effect != 'cut':
                    logger.warning("⚠️ Transition playback failed, retrying with 'cut' and disabling transitions for this session")
                    try:
                        success = self.media_player.play_media(media_url, 'cut', duration, item=current_item)
                        self._transitions_faulted = True
                    except Exception as e2:
                        logger.error(f"❌ Fallback 'cut' playback also failed: {e2}", exc_info=True)
                        success = False
                
                if success:
                    # Use prefixed key to align with playlist signature/new_keys
                    if current_item.id:
                        self.current_item_key = f"id:{current_item.id}"
                    elif current_item.url:
                        self.current_item_key = f"url:{current_item.url}"
                    elif current_item.file:
                        self.current_item_key = f"file:{current_item.file}"
                    else:
                        self.current_item_key = ""

                    # Cancel any existing timer and schedule next item
                    with self._timer_lock:
                        if self._current_item_timer is not None:
                            logger.debug(f"[⏰ TIMER] Cancelling previous timer")
                            self._current_item_timer.cancel()
                        self._current_item_timer = threading.Timer(duration, self.on_item_finished)
                        self._current_item_timer.start()
                        logger.debug(f"[⏰ TIMER] Started new timer for {duration}s")
                    
                    # Preload upcoming items
                    self.preload_upcoming_items()
        finally:
            try:
                self._advance_lock.release()
            except Exception:
                pass
    def on_item_finished(self):
        """Handle when current item finishes playing."""
        logger.info(f"⏰ Item duration expired, advancing to next item (was at index {self.current_index})")
        with self._timer_lock:
            self._current_item_timer = None  # Timer has fired, clear reference
        if getattr(self, '_stop_video_on_timer', False):
            try:
                if str(getattr(self.media_player, 'current_media_type', '')).lower() == 'video':
                    logger.info("⏹️  Stopping video early due to schedule change")
                    self.media_player.stop()
            except Exception as stop_err:
                logger.debug(f"Video stop after schedule boundary failed: {stop_err}")
        self._stop_video_on_timer = False
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.advance_to_next_item()
    
    def _normalize_effect(self, eff) -> str:
        """Map to new 10-effect system: cut, fade, dissolve, slide_left, slide_right, slide_up, slide_down, zoom_in, zoom_out, wipe"""
        try:
            # String but not digits
            if isinstance(eff, str) and not eff.strip().isdigit():
                val = eff.strip().lower()
                aliases = {
                    'cut': 'cut', 'none': 'cut', '': 'cut',
                    'fade': 'fade',
                    'dissolve': 'dissolve', 'crossfade': 'dissolve',
                    'slide_left': 'slide_left', 'slide-left': 'slide_left', 'slide-l': 'slide_left', 'left': 'slide_left',
                    'slide_right': 'slide_right', 'slide-right': 'slide_right', 'slide-r': 'slide_right', 'right': 'slide_right',
                    'slide_up': 'slide_up', 'slide-up': 'slide_up', 'up': 'slide_up',
                    'slide_down': 'slide_down', 'slide-down': 'slide_down', 'down': 'slide_down',
                    'zoom_in': 'zoom_in', 'zoom-in': 'zoom_in', 'zoomin': 'zoom_in',
                    'zoom_out': 'zoom_out', 'zoom-out': 'zoom_out', 'zoomout': 'zoom_out',
                    'wipe': 'wipe', 'wipe-lr': 'wipe', 'wipe_l_r': 'wipe', 'wipe-left-right': 'wipe',
                    'button-1': 'cut', 'button-2': 'fade', 'button-3': 'dissolve',
                    'button-4': 'slide_left', 'button-5': 'slide_right', 'button-6': 'slide_up',
                    'button-7': 'slide_down', 'button-8': 'zoom_in', 'button-9': 'zoom_out',
                    'button-10': 'wipe',
                }
                return aliases.get(val, val)
            # Numeric
            try:
                num = int(str(eff).strip())
            except Exception:
                num = None
            if num is None:
                return str(eff).strip().lower() if eff else 'cut'
            # New 10-effect mapping
            mapping = {
                1: 'cut',
                2: 'fade',
                3: 'dissolve',
                4: 'slide_left',
                5: 'slide_right',
                6: 'slide_up',
                7: 'slide_down',
                8: 'zoom_in',
                9: 'zoom_out',
                10: 'wipe',
            }
            return mapping.get(num, 'cut')
        except Exception:
            return 'cut'
        
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
                if event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if len(self.input_text) > 0 and self.input_text.isdigit():
                        self.handle_store_select()
                elif event.unicode.isdigit() and len(self.input_text) < 8:  # Max 8 digits for store code
                    self.input_text += event.unicode
                    
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
        elif event.key == pygame.K_i:  # Press 'I' to toggle Pi ID visibility
            self.show_pi_id = not self.show_pi_id
            if self.show_pi_id:
                self.pi_id_last_shown = time.time()  # Reset timer
                logger.info(f"📟 Pi ID visibility: ON (ID: {self.pi_id})")
            else:
                logger.info("📟 Pi ID visibility: OFF")
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
                # Check Continue button click
                if self.link_button_rect and self.link_button_rect.collidepoint(event.pos):
                    if len(self.input_text) > 0 and self.input_text.isdigit():
                        self.handle_store_select()
                        
            elif self.setup_step == "screen":
                # Check screen button clicks
                for screen_id, button_rect in self.screen_button_rects.items():
                    if button_rect.collidepoint(event.pos):
                        self.handle_screen_select(screen_id)
                        break
            
    def handle_code_submit(self):
        """Handle TV code submission."""
        logger.info(f"🔍 Validating TV code: {self.input_text}")
        
        def validate_code():
            try:
                is_valid = self.validate_tv_code(self.input_text)
                
                if is_valid:
                    self.pair_code = self.input_text
                    self.setup_step = "store"
                    self.input_text = ""  # Clear for store code entry
                    logger.info("✅ Moving to store code entry")
                else:
                    logger.warning("❌ Invalid code, staying on code input")
                    self.input_text = ""
            except Exception as e:
                logger.error(f"❌ Error validating code: {e}")
                import traceback
                traceback.print_exc()
                self.input_text = ""
                
        threading.Thread(target=validate_code, daemon=True).start()
        
    def handle_store_select(self):
        """Handle store code submission."""
        if len(self.input_text) > 0 and self.input_text.isdigit():
            self.store_id = self.input_text
            logger.info(f"✅ Store code entered: {self.store_id}")
            
            # Fetch available screens for this store
            def fetch_screens():
                try:
                    screens = self.fetch_available_screens(self.store_id)
                    self.available_screens = screens
                    self.setup_step = "screen"
                    logger.info("✅ Moving to screen selection")
                except Exception as e:
                    logger.error(f"❌ Error fetching screens: {e}")
                    import traceback
                    traceback.print_exc()
                
            threading.Thread(target=fetch_screens, daemon=True).start()
            
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
            print(f"🔄 PLAYLIST LOOP STARTED - will poll every {self.PLAYLIST_REFRESH_INTERVAL_MS}ms", flush=True)
            while self.running:
                try:
                    print(f"🔄 Calling fetch_and_update_playlist...", flush=True)
                    self.fetch_and_update_playlist()
                    print(f"🔄 fetch_and_update_playlist completed", flush=True)
                except Exception as e:
                    print(f"❌ Playlist update error: {e}", flush=True)
                    logger.warning(f"Playlist update error: {e}")
                time.sleep(self.PLAYLIST_REFRESH_INTERVAL_MS / 1000)  # 3 seconds
                
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
        
        # Hide Pi ID overlay since we're about to start playing
        self.show_pi_id = False
        logger.info("👁️  Pi ID hidden - starting content playback")
        
        # Initial playlist fetch and start playback
        logger.info("📥 Fetching initial playlist for playback...")
        self.fetch_and_update_playlist(force_advance=True)  # Force initial playback
        logger.info(f"📋 Playlist has {len(self.playlist)} items after fetch")
            
    def run(self):
        """Main event loop."""
        clock = pygame.time.Clock()
        logger.info("🍕 Starting Complete Pi Webplayer Client")
        
        # Track display updates for debugging
        display_flip_count = 0
        last_flip_log = 0
        
        # Initial server time sync
        try:
            self.time_sync.sync_time()
            logger.info("🌐 Initial server time sync completed")
        except Exception as e:
            logger.warning(f"Initial time sync failed: {e}")
            
        try:
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
                    # Draw Pi ID overlay on setup screen
                    self.draw_pi_id_overlay()
                    # Update display for setup screen
                    try:
                        pygame.display.flip()
                        display_flip_count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Display.flip() error (GL context): {e}")
                    clock.tick(60)  # 60 FPS
                elif self.current_state == "playing":
                    # In playing mode, framebuffer capture works like VNC - zero overhead!
                    if not hasattr(self, '_pygame_cleared'):
                        logger.info("🎬 Clearing pygame setup UI - preparing for content display")
                        # Fill screen with black to hide setup UI
                        self.screen.fill((0, 0, 0))
                        try:
                            pygame.display.flip()
                            display_flip_count += 1
                            logger.info("✅ Display cleared successfully")
                        except Exception as e:
                            logger.error(f"❌ Display.flip() ERROR during clear: {type(e).__name__}: {e}")
                        self._pygame_cleared = True
                        logger.info("✅ Pygame UI cleared - displaying media")
                    
                    # Avoid background flips while a transition is in progress to prevent contention
                    in_transition = False
                    try:
                        if hasattr(self, 'media_player') and self.media_player and hasattr(self.media_player, 'is_in_transition'):
                            in_transition = self.media_player.is_in_transition()
                    except Exception:
                        pass
                    if not in_transition:
                        # Update display for static images at a steady pace
                        try:
                            pygame.display.flip()
                            display_flip_count += 1
                            if time.time() - last_flip_log > 5:  # Log every 5 seconds
                                logger.info(f"📺 Display updates: {display_flip_count} flips (120 FPS main loop)")
                                last_flip_log = time.time()
                        except Exception as e:
                            logger.error(f"❌ Display.flip() ERROR: {type(e).__name__}: {e}")
                    
                    # 120 FPS for ultra-smooth video playback
                    clock.tick(120 if not in_transition else 60)
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in main loop: {e}")
            import traceback
            traceback.print_exc()
            
        logger.info("🛑 Shutting down Complete Pi Client")
        self.media_player.stop()
        self._stop_vnc_server()  # Stop FREE VNC server
        pygame.quit()
        
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pizza Hut TV Complete Pi Webplayer Client")
    parser.add_argument("--server", default="https://everydayadvertise.com", 
                       help="Server URL")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug logging")
    parser.add_argument("--hide-pi-id", action="store_true",
                       help="Start with Pi ID hidden (press 'I' to show)")
    parser.add_argument("--pi-id-auto-hide", type=int, default=300,
                       help="Auto-hide Pi ID after N seconds (0=never, default=300)")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        client = CompleteWebplayerClient(server_url=args.server)
        
        # Apply Pi ID visibility settings
        if args.hide_pi_id:
            client.show_pi_id = False
            logger.info("📟 Pi ID starts hidden (press 'I' to show)")
        
        client.pi_id_auto_hide_seconds = args.pi_id_auto_hide
        if args.pi_id_auto_hide > 0:
            logger.info(f"📟 Pi ID will auto-hide after {args.pi_id_auto_hide} seconds")
        else:
            logger.info("📟 Pi ID auto-hide disabled")
        
        client.run()
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
if __name__ == "__main__":
    main()