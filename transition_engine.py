#!/usr/bin/env python3
"""
Transition Effects Engine for Pizza Hut TV
Handles smooth visual transitions between media items
"""

import pygame
import logging
import time
from typing import Optional, Tuple
import math

logger = logging.getLogger(__name__)


class TransitionEngine:
    """Handles visual transitions between media items"""
    
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.width, self.height = screen.get_size()
        
        # Transition settings
        self.transition_duration = 0.8  # seconds
        self.fps = 60
        
        logger.info("🎨 Transition Engine initialized")
    
    def apply_transition(self, from_surface: Optional[pygame.Surface], 
                        to_surface: pygame.Surface, 
                        effect: str) -> bool:
        """
        Apply transition effect between two surfaces
        
        Args:
            from_surface: Current image/video frame (None for first item)
            to_surface: Next image/video frame
            effect: Transition type (fade, slide-l, slide-r, zoom-in, zoom-out, cut)
            
        Returns:
            True if transition completed successfully
        """
        try:
            # If no previous surface, just show the new one (first item)
            if from_surface is None:
                self.screen.blit(to_surface, (0, 0))
                pygame.display.flip()
                return True
            
            # Scale surfaces to screen size if needed
            from_surface = self._ensure_screen_size(from_surface)
            to_surface = self._ensure_screen_size(to_surface)
            
            # Apply the specified effect
            effect = effect.lower() if effect else 'fade'
            
            if effect == 'fade':
                return self._fade_transition(from_surface, to_surface)
            elif effect in ['slide-l', 'slide-left']:
                return self._slide_transition(from_surface, to_surface, 'left')
            elif effect in ['slide-r', 'slide-right']:
                return self._slide_transition(from_surface, to_surface, 'right')
            elif effect in ['slide-u', 'slide-up']:
                return self._slide_transition(from_surface, to_surface, 'up')
            elif effect in ['slide-d', 'slide-down']:
                return self._slide_transition(from_surface, to_surface, 'down')
            elif effect in ['zoom-in', 'zoom_in']:
                return self._zoom_transition(from_surface, to_surface, 'in')
            elif effect in ['zoom-out', 'zoom_out']:
                return self._zoom_transition(from_surface, to_surface, 'out')
            elif effect == 'cut':
                # Instant cut - no transition
                self.screen.blit(to_surface, (0, 0))
                pygame.display.flip()
                return True
            else:
                # Unknown effect - default to fade
                logger.warning(f"Unknown effect '{effect}', using fade")
                return self._fade_transition(from_surface, to_surface)
                
        except Exception as e:
            logger.error(f"❌ Transition error: {e}")
            # Fallback: just show new surface
            self.screen.blit(to_surface, (0, 0))
            pygame.display.flip()
            return False
    
    def _ensure_screen_size(self, surface: pygame.Surface) -> pygame.Surface:
        """Scale surface to screen size if needed"""
        if surface.get_size() != (self.width, self.height):
            return pygame.transform.scale(surface, (self.width, self.height))
        return surface
    
    def _fade_transition(self, from_surface: pygame.Surface, 
                        to_surface: pygame.Surface) -> bool:
        """
        Fade transition - alpha blend from old to new
        """
        logger.debug("🎨 Applying fade transition")
        
        steps = int(self.transition_duration * self.fps)
        
        for i in range(steps + 1):
            # Calculate alpha (0 to 255)
            alpha = int((i / steps) * 255)
            
            # Start with old surface
            self.screen.blit(from_surface, (0, 0))
            
            # Blend new surface on top with increasing alpha
            temp_surface = to_surface.copy()
            temp_surface.set_alpha(alpha)
            self.screen.blit(temp_surface, (0, 0))
            
            pygame.display.flip()
            
            # Control frame rate
            pygame.time.Clock().tick(self.fps)
        
        return True
    
    def _slide_transition(self, from_surface: pygame.Surface, 
                         to_surface: pygame.Surface, 
                         direction: str) -> bool:
        """
        Slide transition - new surface slides in from direction
        """
        logger.debug(f"🎨 Applying slide-{direction} transition")
        
        steps = int(self.transition_duration * self.fps)
        
        for i in range(steps + 1):
            # Calculate progress (0.0 to 1.0)
            progress = i / steps
            
            # Ease out cubic for smooth deceleration
            eased_progress = 1 - pow(1 - progress, 3)
            
            # Calculate positions based on direction
            if direction == 'left':
                old_x = -int(self.width * eased_progress)
                new_x = self.width - int(self.width * eased_progress)
                old_y = new_y = 0
            elif direction == 'right':
                old_x = int(self.width * eased_progress)
                new_x = -self.width + int(self.width * eased_progress)
                old_y = new_y = 0
            elif direction == 'up':
                old_y = -int(self.height * eased_progress)
                new_y = self.height - int(self.height * eased_progress)
                old_x = new_x = 0
            else:  # down
                old_y = int(self.height * eased_progress)
                new_y = -self.height + int(self.height * eased_progress)
                old_x = new_x = 0
            
            # Draw both surfaces
            self.screen.fill((0, 0, 0))  # Black background
            self.screen.blit(from_surface, (old_x, old_y))
            self.screen.blit(to_surface, (new_x, new_y))
            
            pygame.display.flip()
            pygame.time.Clock().tick(self.fps)
        
        return True
    
    def _zoom_transition(self, from_surface: pygame.Surface, 
                        to_surface: pygame.Surface, 
                        zoom_type: str) -> bool:
        """
        Zoom transition - zoom in or out
        """
        logger.debug(f"🎨 Applying zoom-{zoom_type} transition")
        
        steps = int(self.transition_duration * self.fps)
        
        for i in range(steps + 1):
            # Calculate progress (0.0 to 1.0)
            progress = i / steps
            
            # Ease in-out cubic
            if progress < 0.5:
                eased_progress = 4 * progress * progress * progress
            else:
                eased_progress = 1 - pow(-2 * progress + 2, 3) / 2
            
            if zoom_type == 'in':
                # Old surface stays, new zooms in from center
                # Alpha blend with increasing alpha on new
                alpha = int(eased_progress * 255)
                
                # Scale factor (0.5 to 1.0)
                scale = 0.5 + (eased_progress * 0.5)
                
                # Scale new surface
                scaled_width = int(self.width * scale)
                scaled_height = int(self.height * scale)
                scaled_new = pygame.transform.scale(to_surface, (scaled_width, scaled_height))
                
                # Center position
                x = (self.width - scaled_width) // 2
                y = (self.height - scaled_height) // 2
                
                # Draw old surface
                self.screen.blit(from_surface, (0, 0))
                
                # Draw scaled new surface with alpha
                scaled_new.set_alpha(alpha)
                self.screen.blit(scaled_new, (x, y))
                
            else:  # zoom out
                # Old surface zooms out, new fades in
                alpha_old = int((1 - eased_progress) * 255)
                alpha_new = int(eased_progress * 255)
                
                # Scale factor (1.0 to 1.5)
                scale = 1.0 + (eased_progress * 0.5)
                
                # Scale old surface
                scaled_width = int(self.width * scale)
                scaled_height = int(self.height * scale)
                scaled_old = pygame.transform.scale(from_surface, (scaled_width, scaled_height))
                
                # Center position
                x = (self.width - scaled_width) // 2
                y = (self.height - scaled_height) // 2
                
                # Draw new surface
                self.screen.blit(to_surface, (0, 0))
                
                # Draw scaled old surface with alpha on top
                scaled_old.set_alpha(alpha_old)
                self.screen.blit(scaled_old, (x, y))
            
            pygame.display.flip()
            pygame.time.Clock().tick(self.fps)
        
        return True
    
    def capture_screen(self) -> pygame.Surface:
        """Capture current screen as surface for transition"""
        return self.screen.copy()


# Quick test if run directly
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1920, 1080))
    
    # Create test surfaces
    surface1 = pygame.Surface((1920, 1080))
    surface1.fill((255, 0, 0))  # Red
    
    surface2 = pygame.Surface((1920, 1080))
    surface2.fill((0, 0, 255))  # Blue
    
    engine = TransitionEngine(screen)
    
    # Test transitions
    print("Testing fade...")
    engine.apply_transition(surface1, surface2, 'fade')
    time.sleep(1)
    
    print("Testing slide-left...")
    engine.apply_transition(surface2, surface1, 'slide-l')
    time.sleep(1)
    
    print("Testing zoom-in...")
    engine.apply_transition(surface1, surface2, 'zoom-in')
    time.sleep(1)
    
    print("Done!")
    pygame.quit()
