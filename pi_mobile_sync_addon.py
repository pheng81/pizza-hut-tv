#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Mobile Sync Add-on for Pi Client
Adds QR code and mobile synchronization to complete_pi_client.py WITHOUT modifying existing code
"""

import pygame
import qrcode
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MobileSyncAddon:
    """
    Add-on class that extends Pi client with mobile sync functionality.
    
    Usage:
        # In your Pi client initialization:
        from pi_mobile_sync_addon import MobileSyncAddon
        
        # After creating Pi client:
        mobile_sync = MobileSyncAddon(pi_client)
        
        # In your WebSocket setup (add to existing websocket handlers):
        mobile_sync.setup_websocket_handlers(sio)
        
        # In your draw_code_input_screen method (add at the end):
        mobile_sync.draw_qr_code(screen, session_id)
        
        # In your draw_store_selection_screen method (add at the end):
        mobile_sync.draw_qr_code(screen, session_id)
        
        # In your draw_screen_selection_screen method (add at the end):
        mobile_sync.draw_qr_code(screen, session_id)
    """
    
    def __init__(self, pi_client):
        """
        Initialize mobile sync add-on.
        
        Args:
            pi_client: Reference to the main CompleteWebplayerClient instance
        """
        self.pi_client = pi_client
        # Generate a session id immediately so we can join the room on first WS connect
        self.session_id = None
        self.qr_surface = None
        # Base QR size; dynamically scaled in draw_qr_code per screen resolution
        self.qr_size = 300
        self._render_qr_size = None
        self._last_qr_url = None
        
        # Mobile sync state
        self.mobile_connected = False
        self.received_code = None
        self.received_store = None
        self.received_screen = None
        self.logo_surface = None  # cached logo overlay for QR
        
        # Proactively generate a session so join_session can be emitted on first connect
        try:
            self.generate_session_id()
        except Exception:
            # If generation fails for any reason, we'll try again lazily
            pass

        logger.info("📱 Mobile Sync Add-on initialized")
    
    def generate_session_id(self, prefix: str = "pi") -> str:
        """Generate a unique session ID for this Pi."""
        import random
        import string
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
        self.session_id = f"{prefix}_{random_str}"
        logger.info(f"🔑 Generated session ID: {self.session_id}")
        return self.session_id
    
    def join_webplayer_session(self):
        """
        Join the webplayer session with the server.
        Call this from the Pi client's connect handler AFTER it registers.
        """
        # Ensure we have a session id before joining
        if not getattr(self, 'session_id', None):
            try:
                self.generate_session_id()
            except Exception as e:
                logger.error(f"❌ Could not generate session id: {e}")
                return

        if getattr(self, 'sio', None):
            try:
                self.sio.emit('join_session', {'session_id': self.session_id})
                logger.info(f"📡 Joined WebSocket session: {self.session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to join session: {e}")
        else:
            logger.warning("⚠️ Cannot join session - sio client not initialized yet")
    
    def create_qr_code(self, url: str) -> Optional[pygame.Surface]:
        """
        Create a QR code as a pygame surface.
        
        Args:
            url: The URL to encode in the QR code
            
        Returns:
            pygame.Surface containing the QR code, or None if failed
        """
        try:
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert PIL image to pygame surface
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            # Load as pygame surface and scale (convert to 24/32-bit for smoothscale)
            qr_surface = pygame.image.load(img_bytes)
            try:
                if qr_surface.get_bitsize() not in (24, 32):
                    qr_surface = qr_surface.convert_alpha() if qr_surface.get_alpha() else qr_surface.convert()
                qr_surface = pygame.transform.smoothscale(qr_surface, (self.qr_size, self.qr_size))
            except Exception:
                # Fallback if smoothscale not possible
                qr_surface = pygame.transform.scale(qr_surface, (self.qr_size, self.qr_size))

            # Overlay centered EA logo for branding (UI only)
            try:
                if self.logo_surface is None:
                    self.logo_surface = self._create_logo_surface(int(self.qr_size * 0.16))
                if self.logo_surface is not None:
                    lx = (self.qr_size - self.logo_surface.get_width()) // 2
                    ly = (self.qr_size - self.logo_surface.get_height()) // 2
                    qr_surface.blit(self.logo_surface, (lx, ly))
            except Exception as _e:
                # Non-fatal UI embellishment
                pass
            
            return qr_surface
            
        except Exception as e:
            logger.error(f"❌ Failed to create QR code: {e}")
            return None

    def _create_logo_surface(self, size: int) -> Optional[pygame.Surface]:
        """Create a small EA logo surface with rounded white background.
        UI embellishment only; does not affect behavior.
        """
        try:
            pad = max(2, size // 12)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            # White rounded square base
            pygame.draw.rect(surf, (255, 255, 255), (0, 0, size, size), border_radius=max(8, size // 4))
            # Inner colored monogram box for contrast
            inner = max(0, pad)
            inner_rect = (inner, inner, size - inner * 2, size - inner * 2)
            # Simple gradient approximation: split two tones
            mid = inner_rect[0] + inner_rect[2] // 2
            # Left half - pink
            pygame.draw.rect(surf, (255, 45, 132), (inner_rect[0], inner_rect[1], mid - inner_rect[0], inner_rect[3]), border_radius=max(6, size // 6))
            # Right half - blue
            pygame.draw.rect(surf, (60, 108, 255), (mid, inner_rect[1], inner_rect[0] + inner_rect[2] - mid, inner_rect[3]), border_radius=max(6, size // 6))
            # White 'EA' text centered
            try:
                font = pygame.font.Font(None, max(12, size // 3))
            except:
                font = pygame.font.SysFont('arial', max(12, size // 3), bold=True)
            text = font.render('EA', True, (255, 255, 255))
            tr = text.get_rect(center=(size // 2, size // 2))
            surf.blit(text, tr)
            # Add white ring effect by drawing slightly larger transparent border (subtle)
            ring = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.rect(ring, (255, 255, 255, 220), (0, 0, size, size), width=max(2, size // 18), border_radius=max(8, size // 4))
            surf.blit(ring, (0, 0))
            return surf
        except Exception as _e:
            return None
    
    def draw_qr_code(self, screen: pygame.Surface, step: str = "code", x: int = None, y: int = None, override_qr_size: int = None, draw_divider: bool = True, override_container_height: int = None):
        """
        Draw QR code on the screen with instructions.
        
        Args:
            screen: Pygame screen surface to draw on
            step: Current setup step ("code", "store", or "screen")
        """
        if not self.session_id:
            self.generate_session_id()
        
        # Build URL based on current step
        server_url = self.pi_client.server_url.replace('/api', '')
        
        if step == "claim":
            claim_code = getattr(self.pi_client, 'claim_code', '')
            url = getattr(self.pi_client, 'claim_url', '') or f"{server_url}/pi-manager"
            instruction_text = f"Scan to claim this Pi ({claim_code})"
        elif step == "code":
            url = f"{server_url}/webplayer/?session={self.session_id}"
            instruction_text = "Scan to enter code on your phone"
        elif step == "store":
            # Include code in URL if we have it
            code_param = f"&code={self.received_code}" if self.received_code else ""
            url = f"{server_url}/webplayer/store?session={self.session_id}{code_param}"
            instruction_text = "Scan to enter store code on your phone"
        elif step == "screen":
            # Include code and store in URL if we have them
            code_param = f"&code={self.received_code}" if self.received_code else ""
            store_param = f"&store_id={self.received_store}" if self.received_store else ""
            url = f"{server_url}/webplayer/browse?session={self.session_id}{code_param}{store_param}"
            instruction_text = "Scan to select screen on your phone"
        else:
            logger.warning(f"⚠️ Unknown step: {step}")
            return
        
        # Responsive scaling based on screen size (unless overridden)
        try:
            sw, sh = screen.get_width(), screen.get_height()
        except Exception:
            sw, sh = 1920, 1080
        rel_scale = min(sw / 1920.0, sh / 1080.0)
        rel_scale = max(0.8, min(1.8, rel_scale))
        target_qr = override_qr_size if override_qr_size else int(max(220, min(int(min(sw, sh) * 0.28), int(360 * rel_scale))))

        # If step or size or URL changed, regenerate QR surface at new size
        if (not self.qr_surface or step != getattr(self, '_last_step', None)
            or self._render_qr_size != target_qr or self._last_qr_url != url):
            self.qr_size = target_qr
            self._render_qr_size = target_qr
            self._last_qr_url = url
            self.qr_surface = self.create_qr_code(url)
            self._last_step = step
        
        if not self.qr_surface:
            logger.warning("⚠️ No QR code surface available")
            return
        
        # Draw QR code container (left side on wide screens, centered on narrow)
        pad = int(14 * rel_scale)
        container_padding = max(10, pad)
        container_width = self.qr_size + (container_padding * 2)

        # Prepare instruction text and measure to size so we can size the container tightly
        max_w = container_width - container_padding * 2 - 8
        size = max(12, min(20, int(self.qr_size * 0.06)))
        while size >= 12:
            try:
                f = self._get_font(size)
            except Exception:
                f = pygame.font.Font(None, size)
            text_surface = f.render(instruction_text, True, (255, 255, 255))
            if text_surface.get_width() <= max_w:
                break
            size -= 1

        # Spacing: move text a bit further down from QR, but reduce bottom padding
        top_gap = max(10, int(container_padding * 0.9))  # a bit more space from QR
        bottom_gap = max(10, int(container_padding * 0.6))  # less empty space at bottom

        # Allow forcing the container height to match a sibling form card; otherwise size tightly
        tight_height = self.qr_size + top_gap + text_surface.get_height() + bottom_gap
        container_height = override_container_height if override_container_height else tight_height

        # Decide layout or use manual coordinates
        side_by_side = sw >= 1100
        if x is not None and y is not None:
            container_x, container_y = x, y
        else:
            if side_by_side:
                # Left side with a margin
                margin_left = max(int(sw * 0.03), int(30 * rel_scale))
                container_x = margin_left
                container_y = (sh - container_height) // 2 - int(20 * rel_scale)
            else:
                # Centered near top
                container_x = (sw - container_width) // 2
                container_y = int(sh * 0.12)

        # Flatter container style; rely on QR's own white background; draw subtle outline
        try:
            pygame.draw.rect(screen, (34, 48, 65), (container_x-1, container_y-1, container_width+2, container_height+2), 1, border_radius=12)
        except Exception:
            pass
        
        # Draw QR code
        qr_x = container_x + container_padding
        qr_y = container_y + container_padding
        screen.blit(self.qr_surface, (qr_x, qr_y))
        
        # Draw instruction text below QR using measured surface
        # Position a bit further down from the QR (top_gap) but overall smaller bottom space
        text_rect = text_surface.get_rect(midtop=(container_x + container_width // 2, qr_y + self.qr_size + top_gap))
        screen.blit(text_surface, text_rect)
        
        # Draw mobile connection status indicator
        if self.mobile_connected:
            status_font = self._get_font(max(14, min(24, int(18 * rel_scale)))) if hasattr(self, '_get_font') else pygame.font.Font(None, max(14, min(24, int(18 * rel_scale))))
            status_text = status_font.render("✓ Phone Connected", True, (16, 185, 129))  # Green
            status_rect = status_text.get_rect(center=(container_x + container_width // 2, container_y + container_height - 15))
            screen.blit(status_text, status_rect)

        # Vertical divider to separate QR and form on wide screens (UI only)
        if draw_divider and side_by_side:
            try:
                divider_x = container_x + container_width + max(10, int(10 * rel_scale))
                top = max(int(40 * rel_scale), container_y - int(40 * rel_scale))
                bottom = min(sh - int(40 * rel_scale), container_y + container_height + int(40 * rel_scale))
                div_height = bottom - top
                if div_height > 0:
                    div_surface = pygame.Surface((1, div_height), pygame.SRCALPHA)
                    div_surface.fill((34, 48, 65, 200))
                    screen.blit(div_surface, (divider_x, top))
            except Exception:
                pass

    def _get_font(self, size: int) -> pygame.font.Font:
        """Try to use a clean sans font if available, fallback to default.
        On Raspberry Pi, DejaVu Sans is typically present.
        """
        try:
            # Prefer DejaVu Sans on Linux if available
            return pygame.font.Font('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
        except Exception:
            try:
                return pygame.font.SysFont('DejaVu Sans', size)
            except Exception:
                try:
                    return pygame.font.SysFont('Arial', size)
                except Exception:
                    return pygame.font.Font(None, size)
    
    def setup_websocket_handlers(self, sio):
        """
        Set up WebSocket event handlers for mobile sync.
        Call this in your Pi client's setup_websocket() method.
        
        Args:
            sio: socketio.Client instance
        """
        
        # Store sio reference for later use
        self.sio = sio
        
        @sio.on('code_entered')
        def on_code_entered(data):
            """Handle code entered from mobile."""
            session_id = data.get('session_id')
            code = data.get('code')
            
            if session_id == self.session_id and code:
                logger.info(f"📱 Received code from mobile: {code}")
                self.received_code = code
                self.mobile_connected = True
                
                # Auto-fill the code in Pi client
                self.pi_client.input_text = code
                
                # Auto-advance after short delay
                import threading
                def auto_advance():
                    import time
                    time.sleep(0.5)
                    # Trigger code submission and validation
                    if hasattr(self.pi_client, 'handle_code_submit'):
                        self.pi_client.handle_code_submit()
                    else:
                        logger.warning("⚠️ Pi client doesn't have handle_code_submit method")
                
                threading.Thread(target=auto_advance, daemon=True).start()
        
        @sio.on('store_code_entered')
        def on_store_code_entered(data):
            """Handle store code entered from mobile."""
            session_id = data.get('session_id')
            store_code = data.get('store_code')
            
            if session_id == self.session_id and store_code:
                logger.info(f"📱 Received store code from mobile: {store_code}")
                self.received_store = store_code
                self.mobile_connected = True
                
                # Auto-fill the store code in Pi client
                self.pi_client.input_text = store_code
                
                # Auto-advance after short delay
                import threading
                def auto_advance():
                    import time
                    time.sleep(0.5)
                    # Trigger store selection
                    if hasattr(self.pi_client, 'handle_store_select'):
                        self.pi_client.handle_store_select()
                    else:
                        logger.warning("⚠️ Pi client doesn't have handle_store_select method")
                
                threading.Thread(target=auto_advance, daemon=True).start()
        
        @sio.on('screen_selected')
        def on_screen_selected(data):
            """Handle screen selected from mobile."""
            session_id = data.get('session_id')
            screen_id = data.get('screen_id')
            store_id = data.get('store_id')
            
            if session_id == self.session_id and screen_id:
                logger.info(f"📱 Received screen selection from mobile: {screen_id}")
                self.received_screen = screen_id
                self.mobile_connected = True
                
                # Auto-advance to playing using the proper handler
                import threading
                def auto_advance():
                    import time
                    time.sleep(0.5)
                    # Use the Pi client's screen selection handler
                    if hasattr(self.pi_client, 'handle_screen_select'):
                        self.pi_client.handle_screen_select(screen_id)
                    else:
                        logger.warning("⚠️ Pi client doesn't have handle_screen_select method")
                
                threading.Thread(target=auto_advance, daemon=True).start()
        
        logger.info("📱 Mobile sync WebSocket handlers registered")
        logger.info(f"� Session ID: {self.session_id}")


def integrate_with_pi_client(pi_client):
    """
    Helper function to easily integrate mobile sync with an existing Pi client.
    
    Usage:
        from pi_mobile_sync_addon import integrate_with_pi_client
        
        # After creating your pi_client instance:
        mobile_sync = integrate_with_pi_client(pi_client)
    
    Args:
        pi_client: CompleteWebplayerClient instance
        
    Returns:
        MobileSyncAddon instance
    """
    mobile_sync = MobileSyncAddon(pi_client)
    
    # Setup WebSocket handlers (assumes pi_client has sio attribute)
    if hasattr(pi_client, 'sio'):
        mobile_sync.setup_websocket_handlers(pi_client.sio)
    else:
        logger.warning("⚠️ Pi client doesn't have 'sio' attribute - WebSocket handlers not registered")
    
    return mobile_sync


# Installation instructions stored in docstring for easy reference
INSTALLATION_INSTRUCTIONS = """
🔧 INSTALLATION INSTRUCTIONS
============================

To add mobile sync to complete_pi_client.py WITHOUT modifying existing code:

1. IMPORT the addon at the top of complete_pi_client.py:
   
   from pi_mobile_sync_addon import MobileSyncAddon

2. ADD mobile_sync attribute in CompleteWebplayerClient.__init__():
   
   # After existing initialization code:
   self.mobile_sync = MobileSyncAddon(self)

3. REGISTER WebSocket handlers in setup_websocket() method:
   
   # After existing WebSocket setup:
   self.mobile_sync.setup_websocket_handlers(self.sio)

4. ADD QR code display in draw_code_input_screen() method:
   
   # At the end of the method, after existing drawing code:
   if hasattr(self, 'mobile_sync'):
       self.mobile_sync.draw_qr_code(self.screen, "code")

5. ADD QR code display in draw_store_selection_screen() method:
   
   # At the end of the method, after existing drawing code:
   if hasattr(self, 'mobile_sync'):
       self.mobile_sync.draw_qr_code(self.screen, "store")

6. ADD QR code display in draw_screen_selection_screen() method:
   
   # At the end of the method, after existing drawing code:
   if hasattr(self, 'mobile_sync'):
       self.mobile_sync.draw_qr_code(self.screen, "screen")

7. INSTALL qrcode library on Pi:
   
   pip3 install qrcode[pil]

That's it! The mobile sync feature will be added without breaking existing keyboard input.
"""

if __name__ == "__main__":
    print(INSTALLATION_INSTRUCTIONS)
