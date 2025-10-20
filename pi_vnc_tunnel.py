#!/usr/bin/env python3
"""
VNC Tunnel Module for Pi Client
Tunnels VNC protocol through WebSocket connection to server
"""

import socket
import threading
import logging
import base64
import time
import io

# Lazy/optional PIL import so module still loads when Pillow isn't installed
try:
    from PIL import Image, ImageGrab  # type: ignore
    _PIL_AVAILABLE = True
except Exception:
    Image = None  # type: ignore
    ImageGrab = None  # type: ignore
    _PIL_AVAILABLE = False

class VNCTunnel:
    """Handles VNC connection tunneling through WebSocket"""
    
    def __init__(self, socketio, pi_id):
        self.socketio = socketio
        self.pi_id = pi_id
        self.vnc_socket = None
        self.dashboard_sid = None
        self.running = False
        self.tunnel_thread = None
        logging.info(f'🖥️ VNC Tunnel initialized for Pi: {pi_id}')
    
    def connect(self, dashboard_sid):
        """Start VNC tunnel to local VNC server"""
        self.dashboard_sid = dashboard_sid
        
        try:
            # Try to connect to local VNC server
            logging.info('🖥️ Connecting to local VNC server (localhost:5900)...')
            self.vnc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.vnc_socket.settimeout(5)
            self.vnc_socket.connect(('localhost', 5900))
            self.vnc_socket.settimeout(None)
            
            logging.info('✅ Connected to local VNC server')
            
            # Start tunnel thread
            self.running = True
            self.tunnel_thread = threading.Thread(target=self._tunnel_loop, daemon=True)
            self.tunnel_thread.start()
            
            # Send success to dashboard
            self.socketio.emit('vnc_connected', {
                'pi_id': self.pi_id,
                'target_sid': dashboard_sid,
                'width': 1920,
                'height': 1080,
                'message': 'VNC connected successfully'
            })
            
            logging.info(f'✅ VNC tunnel started for dashboard {dashboard_sid}')
            return True
            
        except ConnectionRefusedError:
            # Fallback to capture-only mode (no x11vnc). Still stream frames.
            logging.warning('⚠️ VNC server not running on localhost:5900 — starting capture-only mode')
            self.vnc_socket = None
            self.running = True
            self.tunnel_thread = threading.Thread(target=self._tunnel_loop, daemon=True)
            self.tunnel_thread.start()
            # Notify dashboard as "connected" so viewer sizes canvas and shows frames
            self.socketio.emit('vnc_connected', {
                'pi_id': self.pi_id,
                'target_sid': dashboard_sid,
                'width': 1280,
                'height': 720,
                'message': 'Capture-only mode (no VNC server)'
            })
            return True
            
        except Exception as e:
            logging.error(f'❌ VNC connection error: {e}')
            self._send_error(f'VNC connection failed: {str(e)}')
            return False
    
    def disconnect(self):
        """Stop VNC tunnel"""
        logging.info('🖥️ Disconnecting VNC tunnel...')
        self.running = False
        
        if self.vnc_socket:
            try:
                self.vnc_socket.close()
            except:
                pass
        
        if self.tunnel_thread:
            self.tunnel_thread.join(timeout=2)
        
        logging.info('✅ VNC tunnel disconnected')
    
    def send_to_vnc(self, data):
        """Send data from dashboard to VNC server"""
        if not self.vnc_socket or not self.running:
            return
        
        try:
            # Handle mouse/keyboard events
            event_type = data.get('type')
            
            if event_type == 'mouse_move':
                # Send mouse move to VNC
                x = data.get('x', 0)
                y = data.get('y', 0)
                # VNC protocol: mouse position packet
                packet = self._create_vnc_mouse_packet(x, y, 0)
                self.vnc_socket.send(packet)
                
            elif event_type == 'mouse_down':
                button = data.get('button', 0)
                # VNC protocol: mouse button down
                # Implementation depends on VNC protocol version
                pass
                
            elif event_type == 'mouse_up':
                button = data.get('button', 0)
                # VNC protocol: mouse button up
                pass
                
            elif event_type == 'key_down':
                key = data.get('key', '')
                # VNC protocol: key press
                pass
                
            elif event_type == 'key_up':
                key = data.get('key', '')
                # VNC protocol: key release
                pass
                
        except Exception as e:
            logging.error(f'❌ Error sending to VNC: {e}')
    
    def _tunnel_loop(self):
        """Main tunnel loop - reads from VNC and sends to dashboard"""
        logging.info('🔄 VNC tunnel loop started')
        
        # Set DISPLAY environment variable if not set
        import os
        if 'DISPLAY' not in os.environ:
            os.environ['DISPLAY'] = ':0'
            logging.info('📺 Set DISPLAY=:0 for screen capture')
        
        # For simplicity, we'll capture screen periodically instead of full VNC protocol
        # This is easier than implementing full RFB protocol
        
        try:
            import mss  # type: ignore
            has_mss = True
            logging.info('✅ Using mss for screen capture')
        except Exception:
            has_mss = False
            if _PIL_AVAILABLE:
                logging.warning('⚠️ mss not installed, using PIL ImageGrab fallback')
            else:
                logging.error('❌ Neither mss nor Pillow are available for capture')
        
        frame_count = 0
        last_frame_time = 0
        fps_limit = 30  # 30 FPS for smooth real-time VNC
        
        while self.running:
            try:
                current_time = time.time()
                
                # Limit frame rate
                if current_time - last_frame_time < (1.0 / fps_limit):
                    time.sleep(0.01)
                    continue
                
                last_frame_time = current_time
                
                # Capture screen
                if has_mss:
                    with mss.mss() as sct:
                        monitor = sct.monitors[1]  # Primary monitor
                        screenshot = sct.grab(monitor)
                        # Build PIL Image if available; else build bytes->JPEG via raw conversion
                        if _PIL_AVAILABLE:
                            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
                        else:
                            # Minimal dependency path: convert BGRA to RGB bytes using Python only
                            # This is slower; if Pillow missing, emit an error and pause instead
                            self._send_error('Pillow not installed on Pi. Install python3-pil for streaming.')
                            time.sleep(2)
                            continue
                else:
                    if _PIL_AVAILABLE:
                        # Fallback to PIL (slower)
                        img = ImageGrab.grab()
                    else:
                        # No capture path available
                        self._send_error('Screen capture unavailable (install mss or Pillow)')
                        time.sleep(2)
                        continue
                
                # Keep original resolution (no downscaling for better quality)
                # Only resize if screen is larger than 1920x1080
                if img.width > 1920 or img.height > 1080:
                    img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                
                # Encode as JPEG with HIGH quality (95% for VNC clarity)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=95, optimize=True)
                jpeg_bytes = buffer.getvalue()
                
                # Encode to base64
                frame_b64 = base64.b64encode(jpeg_bytes).decode('utf-8')
                
                # Send to dashboard via WebSocket
                self.socketio.emit('vnc_data', {
                    'pi_id': self.pi_id,
                    'target_sid': self.dashboard_sid,
                    'frame': frame_b64,
                    'width': img.width,
                    'height': img.height
                })
                
                frame_count += 1
                if frame_count == 1:
                    logging.info(f'📺 VNC streaming at {img.width}x{img.height}, quality=95%, {fps_limit} FPS, {len(jpeg_bytes)/1024:.1f} KB/frame')
                if frame_count % 100 == 0:
                    logging.debug(f'📺 VNC frames sent: {frame_count}')
                
            except Exception as e:
                logging.error(f'❌ VNC tunnel loop error: {e}')
                time.sleep(1)
        
        logging.info('🛑 VNC tunnel loop stopped')
    
    def _create_vnc_mouse_packet(self, x, y, button_mask):
        """Create VNC RFB mouse event packet"""
        # VNC PointerEvent: [type=5][button-mask][x-position][y-position]
        # This is simplified - real implementation needs full RFB protocol
        return bytes([5, button_mask, x >> 8, x & 0xFF, y >> 8, y & 0xFF])
    
    def _send_error(self, message):
        """Send error message to dashboard"""
        if self.dashboard_sid:
            self.socketio.emit('vnc_error', {
                'pi_id': self.pi_id,
                'target_sid': self.dashboard_sid,
                'message': message
            })


# Singleton instance
vnc_tunnel = None

def init_vnc_tunnel(socketio, pi_id):
    """Initialize VNC tunnel"""
    global vnc_tunnel
    vnc_tunnel = VNCTunnel(socketio, pi_id)
    return vnc_tunnel

def get_vnc_tunnel():
    """Get VNC tunnel instance"""
    return vnc_tunnel
