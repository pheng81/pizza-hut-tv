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
import os
import subprocess
import tempfile

# Lazy/optional PIL import so module still loads when Pillow isn't installed
try:
    from PIL import Image, ImageGrab, ImageStat  # type: ignore
    _PIL_AVAILABLE = True
except Exception:
    Image = None  # type: ignore
    ImageGrab = None  # type: ignore
    ImageStat = None  # type: ignore
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

    def _capture_env(self):
        env = os.environ.copy()
        env.setdefault('DISPLAY', ':0')
        env.setdefault('XAUTHORITY', f"/home/{os.getenv('USER', 'everydayadvertise')}/.Xauthority")
        return env

    def _is_mostly_black(self, img) -> bool:
        if not _PIL_AVAILABLE or img is None or ImageStat is None:
            return False
        try:
            gray = img.convert('L')
            histogram = gray.histogram()
            total = sum(histogram)
            if total <= 0:
                return True
            very_dark = sum(histogram[:8])
            return (very_dark / total) >= 0.98
        except Exception:
            return False

    def _capture_with_scrot(self):
        if not _PIL_AVAILABLE:
            return None, 'scrot'

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            result = subprocess.run(
                ['scrot', '-q', '85', '-z', tmp_path],
                capture_output=True,
                timeout=3,
                env=self._capture_env(),
            )
            if result.returncode != 0 or not os.path.exists(tmp_path):
                return None, 'scrot'

            img = Image.open(tmp_path)
            img.load()
            if self._is_mostly_black(img):
                logging.warning('⚠️ scrot produced a mostly black capture')
                return None, 'scrot-black'
            return img.convert('RGB'), 'scrot'
        except FileNotFoundError:
            return None, 'scrot-missing'
        except Exception as e:
            logging.debug(f'scrot capture failed: {e}')
            return None, 'scrot-error'
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _capture_with_mss(self):
        if not _PIL_AVAILABLE:
            return None, 'mss'
        try:
            import mss  # type: ignore

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
            if self._is_mostly_black(img):
                logging.warning('⚠️ mss produced a mostly black capture')
                return None, 'mss-black'
            return img, 'mss'
        except Exception as e:
            logging.debug(f'mss capture failed: {e}')
            return None, 'mss-error'

    def _capture_with_imagegrab(self):
        if not _PIL_AVAILABLE:
            return None, 'imagegrab'
        try:
            img = ImageGrab.grab()
            if self._is_mostly_black(img):
                logging.warning('⚠️ ImageGrab produced a mostly black capture')
                return None, 'imagegrab-black'
            return img.convert('RGB'), 'imagegrab'
        except Exception as e:
            logging.debug(f'ImageGrab capture failed: {e}')
            return None, 'imagegrab-error'

    def _capture_with_framebuffer(self):
        if not _PIL_AVAILABLE:
            return None, 'framebuffer'
        try:
            import fcntl
            import struct

            with open('/dev/fb0', 'rb') as fb:
                FBIOGET_VSCREENINFO = 0x4600
                vinfo = fcntl.ioctl(fb, FBIOGET_VSCREENINFO, bytes(160))
                xres, yres, xres_virtual, _yres_virtual = struct.unpack('IIII', vinfo[:16])
                bits_per_pixel = struct.unpack('I', vinfo[24:28])[0]
                bytes_per_pixel = bits_per_pixel // 8
                frame_size = xres_virtual * yres * bytes_per_pixel
                fb.seek(0)
                fb_data = fb.read(frame_size)

            if bits_per_pixel == 32:
                img = Image.frombytes('RGBA', (xres, yres), fb_data, 'raw', 'BGRA').convert('RGB')
            elif bits_per_pixel == 24:
                img = Image.frombytes('RGB', (xres, yres), fb_data, 'raw', 'BGR')
            elif bits_per_pixel == 16:
                img = Image.frombytes('RGB', (xres, yres), fb_data, 'raw', 'BGR;16')
            else:
                return None, f'framebuffer-bpp-{bits_per_pixel}'

            if self._is_mostly_black(img):
                logging.warning('⚠️ framebuffer produced a mostly black capture')
                return None, 'framebuffer-black'
            return img, 'framebuffer'
        except Exception as e:
            logging.debug(f'framebuffer capture failed: {e}')
            return None, 'framebuffer-error'

    def _capture_frame_image(self):
        for capture_fn in (
            self._capture_with_scrot,
            self._capture_with_mss,
            self._capture_with_imagegrab,
            self._capture_with_framebuffer,
        ):
            img, source = capture_fn()
            if img is not None:
                return img, source
        return None, 'unavailable'
    
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
        env = self._capture_env()
        os.environ.update({k: v for k, v in env.items() if k in ('DISPLAY', 'XAUTHORITY')})
        logging.info('📺 VNC capture env DISPLAY=%s XAUTHORITY=%s', env.get('DISPLAY'), env.get('XAUTHORITY'))
        
        frame_count = 0
        last_frame_time = 0
        fps_limit = 30  # 30 FPS for smooth real-time VNC
        last_error_time = 0.0
        error_backoff_sec = 5.0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Limit frame rate
                if current_time - last_frame_time < (1.0 / fps_limit):
                    time.sleep(0.01)
                    continue
                
                last_frame_time = current_time
                
                img, capture_source = self._capture_frame_image()
                if img is None:
                    if (time.time() - last_error_time) > error_backoff_sec:
                        self._send_error('No usable display frame was captured from the Pi display session.')
                        last_error_time = time.time()
                    time.sleep(1)
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
                    logging.info(f'📺 VNC streaming at {img.width}x{img.height} via {capture_source}, quality=95%, {fps_limit} FPS, {len(jpeg_bytes)/1024:.1f} KB/frame')
                if frame_count % 100 == 0:
                    logging.debug(f'📺 VNC frames sent: {frame_count}')
                
            except Exception as e:
                logging.error(f'❌ VNC tunnel loop error: {e}')
                if (time.time() - last_error_time) > error_backoff_sec:
                    self._send_error(f'Capture loop error: {e}')
                    last_error_time = time.time()
                time.sleep(1)
        
        logging.info('🛑 VNC tunnel loop stopped')
    
    def _vnc_socket_stream(self):
        """Stream from VNC server using scrot screenshot tool"""
        import subprocess
        import tempfile
        
        logging.info('🎥 Starting VNC screenshot streaming (scrot)')
        
        frame_count = 0
        last_frame_time = 0
        fps_limit = 10  # 10 FPS for VNC viewing
        
        while self.running:
            try:
                current_time = time.time()
                
                # Limit frame rate
                if current_time - last_frame_time < (1.0 / fps_limit):
                    time.sleep(0.01)
                    continue
                
                last_frame_time = current_time
                
                # Use scrot to take screenshot (works with Wayland via XWayland)
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp_path = tmp.name
                
                result = subprocess.run(
                    ['scrot', '-o', '-q', '85', tmp_path],
                    capture_output=True,
                    timeout=2,
                    env={'DISPLAY': ':0'}
                )
                
                if result.returncode == 0:
                    try:
                        with open(tmp_path, 'rb') as f:
                            jpeg_data = f.read()
                        
                        if jpeg_data and _PIL_AVAILABLE:
                            # Resize using PIL
                            img = Image.open(io.BytesIO(jpeg_data))
                            if img.width > 1280 or img.height > 720:
                                img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
                            
                            buffer = io.BytesIO()
                            img.save(buffer, format='JPEG', quality=85)
                            jpeg_data = buffer.getvalue()
                        
                        frame_b64 = base64.b64encode(jpeg_data).decode('utf-8')
                        
                        self.socketio.emit('vnc_data', {
                            'pi_id': self.pi_id,
                            'target_sid': self.dashboard_sid,
                            'frame': frame_b64,
                            'width': 1280,
                            'height': 720
                        })
                        
                        frame_count += 1
                        if frame_count == 1:
                            logging.info(f'📺 VNC streaming via scrot at 1280x720, {fps_limit} FPS')
                        if frame_count % 50 == 0:
                            logging.debug(f'📺 VNC frames sent: {frame_count}')
                    finally:
                        import os
                        try:
                            os.unlink(tmp_path)
                        except:
                            pass
                else:
                    logging.error(f'❌ scrot failed: {result.stderr.decode() if result.stderr else "unknown error"}')
                    time.sleep(1)
                
            except Exception as e:
                logging.error(f'❌ VNC screenshot error: {e}')
                time.sleep(1)
    
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
