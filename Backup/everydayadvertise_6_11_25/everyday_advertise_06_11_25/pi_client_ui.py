#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Pi Client with Webplayer-Style UI
===================================================
Enhanced Pi client with UI matching the webplayer design exactly
Includes proper setup flow: Connect to Android TV → Enter Store → Select Screen
"""

import pygame
import requests
import json
import time
import sys
import os
import threading
import logging
import subprocess
import argparse
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/phtv_pi_ui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebplayerSetupUI:
    """Setup UI matching webplayer flow exactly."""
    
    def __init__(self, width=1920, height=1080, server_url="https://everydayadvertise.com"):
        self.width = width
        self.height = height
        self.server_url = server_url
        self.screen = None
        self.clock = None
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        
        # Setup flow state
        self.setup_stage = "tv_code"  # tv_code → store_id → screen_select → playing
        self.tv_code = ""
        self.store_id = ""
        self.screen_id = ""
        self.available_stores = []
        self.available_screens = {}
        self.error_message = ""
        self.input_text = ""
        
        # UI Colors - Modern Pizza Hut TV Design
        self.colors = {
            'bg_red1': (227, 24, 55),         # Red gradient start #e31837
            'bg_red2': (196, 30, 58),         # Red gradient end #c41e3a  
            'container_bg': (0, 0, 0),        # Black container background
            'white': (255, 255, 255),         # White text
            'light_gray': (255, 255, 255, 179), # Light white text for placeholders
            'input_border': (255, 255, 255),   # White input borders
            'input_bg': (255, 255, 255, 26),   # Semi-transparent white input bg
            'gold_button': (255, 215, 0),      # Golden button #ffd700
            'gold_hover': (255, 237, 78),      # Golden hover #ffed4e
            'button_text': (227, 24, 55),      # Red text on golden button
            'button_text_disabled': (153, 153, 153), # Disabled button text
            'error_red': (255, 107, 107),      # Error red
            'success_green': (40, 167, 69),    # Success green
            'focus_gold': (255, 215, 0),       # Golden focus color
            'shadow': (0, 0, 0, 100),          # Drop shadow
        }
        
        # Animation state
        self.animation_time = 0
        self.typing_cursor_visible = True
        self.cursor_blink_time = 0
        
    def init_pygame(self):
        """Initialize pygame with webplayer-style settings."""
        try:
            pygame.init()
            pygame.mixer.quit()  # Don't need audio mixer
            
            # Get display info
            info = pygame.display.Info()
            if info.current_w > 0 and info.current_h > 0:
                self.width = info.current_w
                self.height = info.current_h
            
            # Create fullscreen display
            self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
            pygame.display.set_caption("🍕 Pizza Hut TV Setup")
            pygame.mouse.set_visible(False)
            
            self.clock = pygame.time.Clock()
            
            # Initialize fonts (EXACT webplayer sizes)
            try:
                self.font_large = pygame.font.Font(None, 72)    # Logo: 48px scaled for Pi
                self.font_medium = pygame.font.Font(None, 42)   # Subtitle: 18px scaled
                self.font_small = pygame.font.Font(None, 28)    # Instructions: 14px scaled  
                self.font_input = pygame.font.Font(None, 48)    # Input: 24px scaled
                self.font_label = pygame.font.Font(None, 32)    # Label: 16px scaled
            except:
                # Fallback fonts (EXACT webplayer sizes)
                self.font_large = pygame.font.SysFont('arial', 72, bold=True)
                self.font_medium = pygame.font.SysFont('arial', 42)
                self.font_small = pygame.font.SysFont('arial', 28)
                self.font_input = pygame.font.SysFont('arial', 48)
                self.font_label = pygame.font.SysFont('arial', 32, bold=True)
            
            logger.info(f"Setup UI initialized: {self.width}x{self.height}")
            return True
            
        except Exception as e:
            logger.error(f"UI initialization failed: {e}")
            return False
    
    def draw_background(self):
        """Draw webplayer-exact gradient: linear-gradient(135deg, #e31837, #c41e3a)."""
        # Fast approximation of 135deg diagonal gradient
        # Use vertical gradient that's close to the webplayer look
        for y in range(self.height):
            ratio = y / self.height
            # Exact webplayer colors: #e31837 to #c41e3a
            r = int(227 * (1 - ratio) + 196 * ratio)  # 227 -> 196
            g = int(24 * (1 - ratio) + 30 * ratio)    # 24 -> 30  
            b = int(55 * (1 - ratio) + 58 * ratio)    # 55 -> 58
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.width, y))
    
    def draw_container(self, y_offset=0):
        """Draw beautiful modern container with shadow and blur effect."""
        try:
            # Container dimensions - responsive design
            container_width = min(600, self.width - 100)  # Slightly wider for better UX
            container_height = min(500, self.height - 200)
            container_x = (self.width - container_width) // 2
            container_y = (self.height - container_height) // 2 + y_offset
            
            container_rect = pygame.Rect(container_x, container_y, container_width, container_height)
            
            # Draw shadow for depth (offset by 8px)
            shadow_surface = pygame.Surface((container_width + 16, container_height + 16), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surface, (0, 0, 0, 50), (0, 0, container_width + 16, container_height + 16), border_radius=28)
            self.screen.blit(shadow_surface, (container_x - 8, container_y - 8))
            
            # Main container with semi-transparent background
            container_surface = pygame.Surface((container_width, container_height), pygame.SRCALPHA)
            container_surface.fill((0, 0, 0, 77))  # rgba(0, 0, 0, 0.3)
            
            # Draw rounded rectangle
            pygame.draw.rect(container_surface, (0, 0, 0, 77), (0, 0, container_width, container_height), border_radius=20)
            
            # Add subtle border highlight
            pygame.draw.rect(container_surface, (255, 255, 255, 30), (0, 0, container_width, container_height), width=2, border_radius=20)
            
            self.screen.blit(container_surface, (container_x, container_y))
            
            return container_rect
            
        except Exception as e:
            # Fallback simple container
            container_rect = pygame.Rect(container_x, container_y, container_width, container_height)
            pygame.draw.rect(self.screen, (0, 0, 0, 77), container_rect, border_radius=20)
            return container_rect
    
    def draw_title(self, container_rect, title):
        """Draw screen title matching webplayer exactly."""
        # Main title - clean white text like webplayer
        title_text = self.font_large.render(title, True, self.colors['white'])
        title_rect = title_text.get_rect(center=(container_rect.centerx, container_rect.y + 60))
        self.screen.blit(title_text, title_rect)
    
    def draw_tv_code_screen(self):
        """Draw TV code screen EXACTLY matching webplayer HTML/CSS."""
        # Draw exact webplayer gradient background
        self.draw_background()
        
        # Container exactly like webplayer: max-width: 500px, padding: 40px, rgba(0,0,0,0.3)
        container_width = 500
        container_height = 400  
        container_x = (self.width - container_width) // 2
        container_y = (self.height - container_height) // 2
        container = pygame.Rect(container_x, container_y, container_width, container_height)
        
        # Draw container with exact webplayer styling
        # background: rgba(0, 0, 0, 0.3); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        
        # Drop shadow: 0 10px 30px rgba(0, 0, 0, 0.5)
        shadow_surface = pygame.Surface((container_width + 20, container_height + 40), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surface, (0, 0, 0, 127), (0, 20, container_width + 20, container_height + 20), border_radius=20)
        self.screen.blit(shadow_surface, (container_x - 10, container_y - 10))
        
        # Main container: rgba(0, 0, 0, 0.3), border-radius: 20px
        container_surface = pygame.Surface((container_width, container_height), pygame.SRCALPHA)
        pygame.draw.rect(container_surface, (0, 0, 0, 77), (0, 0, container_width, container_height), border_radius=20)
        self.screen.blit(container_surface, (container_x, container_y))
        
        # Logo: font-size: 48px, font-weight: bold, text-shadow: 2px 2px 4px rgba(0,0,0,0.5)
        logo_text = "🍕 PIZZA HUT TV"
        # Text shadow
        shadow_logo = self.font_large.render(logo_text, True, (0, 0, 0, 127))
        main_logo = self.font_large.render(logo_text, True, (255, 255, 255))
        
        logo_y = container_y + 50
        shadow_rect = shadow_logo.get_rect(center=(container.centerx + 2, logo_y + 2))
        main_rect = main_logo.get_rect(center=(container.centerx, logo_y))
        self.screen.blit(shadow_logo, shadow_rect)
        self.screen.blit(main_logo, main_rect)
        
        # Subtitle: font-size: 18px, margin-bottom: 40px, opacity: 0.9
        subtitle_text = self.font_medium.render("Connect to Android TV", True, (255, 255, 255, 230))  # 0.9 opacity
        subtitle_rect = subtitle_text.get_rect(center=(container.centerx, container_y + 100))
        self.screen.blit(subtitle_text, subtitle_rect)
        
        # Form group with label: font-size: 16px, font-weight: bold, margin-bottom: 10px
        label_text = self.font_label.render("Enter 4-Digit TV Link Code:", True, (255, 255, 255))
        label_rect = label_text.get_rect(center=(container.centerx, container_y + 140))
        self.screen.blit(label_text, label_rect)
        
        # Input field EXACTLY like webplayer CSS
        # width: 100%, padding: 15px, font-size: 24px, text-align: center
        # border: 3px solid #fff, border-radius: 10px
        # background: rgba(255, 255, 255, 0.1), color: white, letter-spacing: 5px
        input_width = 400  # Full width within container padding
        input_height = 50  # 15px padding * 2 + font height
        input_x = container.centerx - input_width // 2
        input_y = container_y + 160
        input_rect = pygame.Rect(input_x, input_y, input_width, input_height)
        
        # Background: rgba(255, 255, 255, 0.1)
        input_bg_surface = pygame.Surface((input_width, input_height), pygame.SRCALPHA)
        pygame.draw.rect(input_bg_surface, (255, 255, 255, 26), (0, 0, input_width, input_height), border_radius=10)
        self.screen.blit(input_bg_surface, (input_x, input_y))
        
        # Border: 3px solid #fff (or #ffd700 on focus)
        border_color = (255, 215, 0) if len(self.input_text) > 0 else (255, 255, 255)  # Gold when focused
        pygame.draw.rect(self.screen, border_color, input_rect, 3, border_radius=10)
        
        # Input text with letter-spacing: 5px
        if self.input_text:
            # Add spaces for letter-spacing (webplayer has 5px spacing)
            display_text = '  '.join(self.input_text)
            text_color = (255, 255, 255)
        else:
            display_text = "0000"  # Webplayer placeholder  
            text_color = (255, 255, 255, 179)  # rgba(255, 255, 255, 0.7)
        
        input_text_surface = self.font_input.render(display_text, True, text_color)
        input_text_rect = input_text_surface.get_rect(center=input_rect.center)
        self.screen.blit(input_text_surface, input_text_rect)
        
        # Button EXACTLY like webplayer CSS
        # background: #ffd700, color: #e31837, padding: 15px 40px, font-size: 18px
        # font-weight: bold, border-radius: 10px, text-transform: uppercase, letter-spacing: 1px
        btn_width = 280
        btn_height = 50  # 15px padding * 2 + font height
        btn_x = container.centerx - btn_width // 2
        btn_y = container_y + 240
        btn_rect = pygame.Rect(btn_x, btn_y, btn_width, btn_height)
        
        btn_enabled = len(self.input_text) == 4
        if btn_enabled:
            btn_bg_color = (255, 215, 0)  # #ffd700
            btn_text_color = (227, 24, 55)  # #e31837
            
            # Add hover effect: background: #ffed4e, transform: translateY(-2px)
            btn_y_offset = -2  # Simulated hover lift
            btn_rect.y += btn_y_offset
            
            # Shadow for lifted button: 0 5px 15px rgba(255, 215, 0, 0.4)
            shadow_rect = pygame.Rect(btn_x + 2, btn_y + 5, btn_width, btn_height)
            shadow_surface = pygame.Surface((btn_width, btn_height), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surface, (255, 215, 0, 102), (0, 0, btn_width, btn_height), border_radius=10)
            self.screen.blit(shadow_surface, (shadow_rect.x, shadow_rect.y))
            
        else:
            # Disabled: background: #666, color: #999
            btn_bg_color = (102, 102, 102)  # #666
            btn_text_color = (153, 153, 153)  # #999

        # Draw button background
        pygame.draw.rect(self.screen, btn_bg_color, btn_rect, border_radius=10)
        
        # Button text: "Connect to TV" (uppercase with letter-spacing)
        btn_text = self.font_medium.render("CONNECT TO TV", True, btn_text_color)
        btn_text_rect = btn_text.get_rect(center=btn_rect.center)
        self.screen.blit(btn_text, btn_text_rect)
        
        # Instructions exactly like webplayer HTML
        # font-size: 14px, opacity: 0.8, line-height: 1.5, margin-top: 30px
        instructions = [
            "1. Find the 4-digit code displayed on your Android TV",
            "2. Enter the code above to connect",
            "3. Select your store and screen"
        ]
        
        instructions_y = container_y + 300
        for i, instruction in enumerate(instructions):
            instruction_surface = self.font_small.render(instruction, True, (255, 255, 255, 204))  # 0.8 opacity
            instruction_rect = instruction_surface.get_rect(center=(container.centerx, instructions_y + i * 25))
            self.screen.blit(instruction_surface, instruction_rect)
        
        # Error message (if any) - webplayer style: color: #ff6b6b, font-weight: bold
        if self.error_message:
            error_surface = self.font_small.render(self.error_message, True, (255, 107, 107))  # #ff6b6b
            error_rect = error_surface.get_rect(center=(container.centerx, container_y + 390))
            self.screen.blit(error_surface, error_rect)
    
    def draw_store_screen(self):
        """Draw store selection screen matching webplayer exactly."""
        container = self.draw_container()
        
        # Title - "Enter store code"
        self.draw_title(container, "Enter store code")
        
        # TV code display - "TV code: 4682"
        tv_code_text = self.font_small.render(f"TV code: {self.tv_code}", True, self.colors['light_gray'])
        tv_code_rect = tv_code_text.get_rect(center=(container.centerx, container.y + 110))
        self.screen.blit(tv_code_text, tv_code_rect)
        
        # Input label - "Store code"
        label_text = self.font_small.render("Store code", True, self.colors['light_gray'])
        label_rect = label_text.get_rect(centerx=container.centerx, y=container.y + 150)
        label_rect.x = container.centerx - 140  # Left align
        self.screen.blit(label_text, label_rect)
        
        # Input field with red border like webplayer
        input_rect = pygame.Rect(container.centerx - 140, container.y + 175, 280, 50)
        pygame.draw.rect(self.screen, self.colors['input_bg'], input_rect, border_radius=5)
        pygame.draw.rect(self.screen, self.colors['input_border'], input_rect, 2, border_radius=5)
        
        # Input text or placeholder
        if self.input_text:
            display_text = self.input_text
            text_color = self.colors['white']
        else:
            display_text = "Store code (e.g. 1000)"
            text_color = self.colors['light_gray']
            
        if self.typing_cursor_visible and self.input_text:
            display_text += "_"
        
        input_surface = self.font_medium.render(display_text, True, text_color)
        input_text_rect = input_surface.get_rect(centery=input_rect.centery, x=input_rect.x + 15)
        self.screen.blit(input_surface, input_text_rect)
        
        # "Continue" button - red like webplayer
        btn_rect = pygame.Rect(container.centerx - 140, container.y + 245, 280, 50)
        btn_enabled = len(self.input_text) > 0
        btn_color = self.colors['gold_button'] if btn_enabled else (100, 100, 100)
        
        pygame.draw.rect(self.screen, btn_color, btn_rect, border_radius=5)
        btn_text = self.font_medium.render("Continue", True, self.colors['white'])
        btn_text_rect = btn_text.get_rect(center=btn_rect.center)
        self.screen.blit(btn_text, btn_text_rect)
        
        # Bottom instruction - "You'll choose a screen next."
        instruction_text = self.font_small.render("You'll choose a screen next.", True, self.colors['light_gray'])
        instruction_rect = instruction_text.get_rect(center=(container.centerx, container.y + 320))
        self.screen.blit(instruction_text, instruction_rect)
        
        # Error message
        if self.error_message:
            error_text = self.font_small.render(self.error_message, True, self.colors['error_red'])
            error_rect = error_text.get_rect(center=(container.centerx, container.bottom - 30))
            self.screen.blit(error_text, error_rect)
    
    def draw_screen_select_screen(self):
        """Draw screen selection matching webplayer exactly."""
        # Full width layout like webplayer screen list
        
        # Top status bar - "TV code: 4682 • Store: 1000"
        status_text = f"TV code: {self.tv_code} • Store: {self.store_id}"
        status_surface = self.font_small.render(status_text, True, self.colors['white'])
        status_rect = status_surface.get_rect(topright=(self.width - 50, 20))
        self.screen.blit(status_surface, status_rect)
        
        # "Screens" title
        screens_title = self.font_large.render("Screens", True, self.colors['white'])
        title_rect = screens_title.get_rect(topleft=(50, 80))
        self.screen.blit(screens_title, title_rect)
        
        # Screen list - matching webplayer exactly
        if not self.available_screens:
            loading_text = "Loading screens..."
            loading_surface = self.font_medium.render(loading_text, True, self.colors['light_gray'])
            loading_rect = loading_surface.get_rect(topleft=(50, 150))
            self.screen.blit(loading_surface, loading_rect)
        else:
            y_offset = 150
            screen_items = list(self.available_screens.items())
            
            for i, (screen_id, screen_config) in enumerate(screen_items):
                # Screen row background (like webplayer list items)
                row_rect = pygame.Rect(20, y_offset - 10, self.width - 40, 60)
                
                # Highlight first item with red border (like webplayer)
                if i == 0:
                    pygame.draw.rect(self.screen, self.colors['input_border'], row_rect, 2, border_radius=5)
                
                # Screen number/name
                screen_name = screen_config.get('display_name', screen_id)
                if screen_name == screen_id:
                    display_text = f"{i + 1}"  # Just show number like webplayer
                else:
                    display_text = screen_name
                    
                screen_surface = self.font_medium.render(display_text, True, self.colors['white'])
                screen_rect = screen_surface.get_rect(topleft=(50, y_offset))
                self.screen.blit(screen_surface, screen_rect)
                
                # Screen ID on the right (smaller text)
                id_surface = self.font_small.render(screen_id, True, self.colors['light_gray'])
                id_rect = id_surface.get_rect(topright=(self.width - 50, y_offset + 5))
                self.screen.blit(id_surface, id_rect)
                
                y_offset += 70
        
        # Error message
        if self.error_message:
            error_text = self.font_small.render(self.error_message, True, self.colors['error_red'])
            error_rect = error_text.get_rect(center=(self.width // 2, self.height - 50))
            self.screen.blit(error_text, error_rect)
    
    def update_animations(self, dt):
        """Update UI animations."""
        self.animation_time += dt
        
        # Cursor blinking
        self.cursor_blink_time += dt
        if self.cursor_blink_time > 500:  # Blink every 500ms
            self.typing_cursor_visible = not self.typing_cursor_visible
            self.cursor_blink_time = 0
    
    def handle_input_events(self, events):
        """Handle input events for setup flow."""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.setup_stage == "tv_code":
                        return "quit"
                    elif self.setup_stage == "store_id":
                        self.setup_stage = "tv_code"
                        self.input_text = self.tv_code
                        self.error_message = ""
                    elif self.setup_stage == "screen_select":
                        self.setup_stage = "store_id"
                        self.input_text = self.store_id
                        self.error_message = ""
                
                elif event.key == pygame.K_BACKSPACE:
                    if self.input_text:
                        self.input_text = self.input_text[:-1]
                        self.error_message = ""
                
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    return self.handle_enter_key()
                
                # Handle number keys directly
                elif event.key >= pygame.K_0 and event.key <= pygame.K_9:
                    digit = str(event.key - pygame.K_0)
                    if self.setup_stage == "tv_code" and len(self.input_text) < 4:
                        self.input_text += digit
                        self.error_message = ""
                    elif self.setup_stage == "store_id":
                        self.input_text += digit
                        self.error_message = ""
                    elif self.setup_stage == "screen_select":
                        # Handle number keys for screen selection
                        screen_num = int(digit) - 1
                        screen_items = list(self.available_screens.items())
                        if 0 <= screen_num < len(screen_items):
                            self.screen_id = screen_items[screen_num][0]
                            return "launch_player"
                
                # Handle keypad numbers
                elif event.key >= pygame.K_KP0 and event.key <= pygame.K_KP9:
                    digit = str(event.key - pygame.K_KP0)
                    if self.setup_stage == "tv_code" and len(self.input_text) < 4:
                        self.input_text += digit
                        self.error_message = ""
                    elif self.setup_stage == "store_id":
                        self.input_text += digit
                        self.error_message = ""
                    elif self.setup_stage == "screen_select":
                        # Handle number keys for screen selection
                        screen_num = int(digit) - 1
                        screen_items = list(self.available_screens.items())
                        if 0 <= screen_num < len(screen_items):
                            self.screen_id = screen_items[screen_num][0]
                            return "launch_player"
                
                # Handle letter keys for store names
                elif event.unicode and event.unicode.isalnum() and self.setup_stage == "store_id":
                    self.input_text += event.unicode.upper()
                    self.error_message = ""
        
        return None
    
    def handle_enter_key(self):
        """Handle enter key press based on current stage."""
        if self.setup_stage == "tv_code":
            if len(self.input_text) == 4:
                return self.validate_tv_code()
        elif self.setup_stage == "store_id":
            if self.input_text:
                return self.validate_store_id()
        
        return None
    
    def validate_tv_code(self):
        """Validate TV code with server - improved error handling."""
        if not self.input_text or len(self.input_text) != 4:
            self.error_message = "Please enter a 4-digit code"
            return None
            
        if not self.input_text.isdigit():
            self.error_message = "Code must contain only numbers"
            return None
            
        # Show loading state
        self.error_message = "Connecting..."
        
        try:
            logger.info(f"Validating TV code: {self.input_text} with server: {self.server_url}")
            
            response = requests.get(
                f"{self.server_url}/api/stores_by_code/{self.input_text}", 
                timeout=15,
                headers={'User-Agent': 'PizzaHutTV-Pi/1.0'}
            )
            
            logger.info(f"Server response: {response.status_code}")
            
            if response.status_code == 200:
                stores_data = response.json()
                logger.info(f"Stores data received: {len(stores_data) if stores_data else 0} stores")
                
                if stores_data and len(stores_data) > 0:
                    self.tv_code = self.input_text
                    self.available_stores = stores_data
                    self.setup_stage = "store_id"
                    self.input_text = ""
                    self.error_message = ""
                    logger.info("✅ TV code validation successful")
                    return "tv_code_valid"
                else:
                    self.error_message = "❌ Invalid TV code - not found in system"
                    
            elif response.status_code == 404:
                self.error_message = "❌ TV code not found - check your display"
            elif response.status_code == 500:
                self.error_message = "🔧 Server error - please try again"
            else:
                self.error_message = f"❌ Connection failed ({response.status_code})"
                
        except requests.ConnectionError:
            self.error_message = "🌐 Cannot connect to server - check internet"
            logger.error("Connection error to server")
        except requests.Timeout:
            self.error_message = "⏱️ Connection timeout - server slow"
            logger.error("Timeout connecting to server")
        except requests.RequestException as e:
            self.error_message = f"🔧 Network error: {str(e)[:50]}"
            logger.error(f"Request error: {e}")
        except ValueError as e:
            self.error_message = "📡 Invalid server response"
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            self.error_message = f"💥 Unexpected error: {str(e)[:50]}"
            logger.error(f"Unexpected error in validate_tv_code: {e}")
        
        return None
    
    def validate_store_id(self):
        """Validate store ID and load screens."""
        try:
            # Check if store exists in available stores
            store_exists = any(
                store.get('store_id', '').lower() == self.input_text.lower() 
                for store in self.available_stores
            )
            
            if store_exists or not self.available_stores:  # Allow any store if no restrictions
                self.store_id = self.input_text
                return self.load_screens()
            else:
                self.error_message = "Store not found for this TV code."
        except Exception as e:
            self.error_message = f"Error validating store: {str(e)}"
        
        return None
    
    def load_screens(self):
        """Load available screens for the store."""
        try:
            response = requests.get(f"{self.server_url}/api/store_config/{self.store_id}", timeout=10)
            if response.ok:
                store_config = response.json()
                screens = store_config.get('screens', {})
                
                if screens:
                    self.available_screens = screens
                    self.setup_stage = "screen_select"
                    self.input_text = ""
                    self.error_message = ""
                    return "screens_loaded"
                else:
                    self.error_message = "No screens configured for this store."
            else:
                self.error_message = "Failed to load store configuration."
        except requests.RequestException:
            self.error_message = "Network error loading screens."
        except Exception as e:
            self.error_message = f"Error loading screens: {str(e)}"
        
        return None
    
    def run_setup(self):
        """Run the setup flow matching webplayer exactly."""
        if not self.init_pygame():
            return None, None, None
        
        clock = pygame.time.Clock()
        running = True
        
        logger.info("🍕 Starting Pizza Hut TV Setup Flow")
        
        try:
            while running:
                dt = clock.tick(60)  # 60 FPS
                
                # Handle events
                events = pygame.event.get()
                for event in events:
                    if event.type == pygame.QUIT:
                        running = False
                
                # Handle input
                result = self.handle_input_events(events)
                if result == "quit":
                    running = False
                elif result == "launch_player":
                    logger.info(f"✅ Setup complete: TV:{self.tv_code}, Store:{self.store_id}, Screen:{self.screen_id}")
                    return self.tv_code, self.store_id, self.screen_id
                
                # Update animations
                self.update_animations(dt)
                
                # Draw current screen (background is drawn in each screen function)
                if self.setup_stage == "tv_code":
                    self.draw_tv_code_screen()
                elif self.setup_stage == "store_id":
                    self.draw_store_screen()
                elif self.setup_stage == "screen_select":
                    self.draw_screen_select_screen()
                
                pygame.display.flip()
        
        except KeyboardInterrupt:
            logger.info("Setup interrupted by user")
        except Exception as e:
            logger.error(f"Setup error: {e}")
            traceback.print_exc()
        finally:
            pygame.quit()
        
        return None, None, None

class WebplayerStyleUI:
    """Webplayer-style UI for Pi client."""
    
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.screen = None
        self.clock = None
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        
        # UI Colors (matching webplayer)
        self.colors = {
            'background': (0, 20, 40),      # Dark blue like webplayer
            'pizza_red': (215, 25, 32),     # Pizza Hut red
            'white': (255, 255, 255),
            'light_gray': (200, 200, 200),
            'dark_gray': (100, 100, 100),
            'green': (40, 167, 69),         # Success green
            'yellow': (255, 193, 7),        # Warning yellow
            'blue': (0, 123, 255)           # Info blue
        }
        
        # UI State
        self.current_video_title = "Loading..."
        self.playlist_items = []
        self.current_index = 0
        self.connection_status = "Connecting..."
        self.sync_status = "Syncing..."
        self.performance_stats = {}
        self.show_overlay = True
        self.overlay_timeout = 5000  # 5 seconds
        self.last_activity = time.time()
        
    def init_pygame(self):
        """Initialize pygame with webplayer-style settings."""
        try:
            pygame.init()
            pygame.mixer.quit()  # Don't need audio mixer
            
            # Get display info
            info = pygame.display.Info()
            if info.current_w > 0 and info.current_h > 0:
                self.width = info.current_w
                self.height = info.current_h
            
            # Create fullscreen display
            self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
            pygame.display.set_caption("🍕 Pizza Hut TV")
            pygame.mouse.set_visible(False)
            
            self.clock = pygame.time.Clock()
            
            # Initialize fonts
            try:
                self.font_large = pygame.font.Font(None, 74)    # Main title
                self.font_medium = pygame.font.Font(None, 48)   # Subtitles
                self.font_small = pygame.font.Font(None, 32)    # Status text
            except:
                # Fallback fonts
                self.font_large = pygame.font.SysFont('arial', 74, bold=True)
                self.font_medium = pygame.font.SysFont('arial', 48)
                self.font_small = pygame.font.SysFont('arial', 32)
            
            logger.info(f"UI initialized: {self.width}x{self.height}")
            return True
            
        except Exception as e:
            logger.error(f"UI initialization failed: {e}")
            return False
    
    def draw_background(self):
        """Draw webplayer-style background."""
        # Fill with dark blue background
        self.screen.fill(self.colors['background'])
        
        # Add subtle gradient effect
        for y in range(0, self.height, 4):
            alpha = int(20 * (1 - y / self.height))
            color = (
                self.colors['background'][0] + alpha,
                self.colors['background'][1] + alpha,
                self.colors['background'][2] + alpha
            )
            pygame.draw.line(self.screen, color, (0, y), (self.width, y), 4)
    
    def draw_pizza_hut_logo(self):
        """Draw Pizza Hut TV logo area."""
        # Logo background
        logo_rect = pygame.Rect(50, 50, 400, 120)
        pygame.draw.rect(self.screen, self.colors['pizza_red'], logo_rect, border_radius=15)
        
        # Logo text
        logo_text = self.font_large.render("🍕 Pizza Hut TV", True, self.colors['white'])
        logo_pos = (logo_rect.x + 20, logo_rect.y + 30)
        self.screen.blit(logo_text, logo_pos)
        
        # Tagline
        tagline = self.font_small.render("Digital Signage Player", True, self.colors['light_gray'])
        tagline_pos = (logo_rect.x + 25, logo_rect.y + 85)
        self.screen.blit(tagline, tagline_pos)
    
    def draw_video_area(self):
        """Draw main video display area."""
        # Video container (like webplayer)
        video_rect = pygame.Rect(50, 200, self.width - 100, self.height - 400)
        pygame.draw.rect(self.screen, (0, 0, 0), video_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.colors['dark_gray'], video_rect, 3, border_radius=10)
        
        # Current video title
        title_text = self.font_medium.render(self.current_video_title, True, self.colors['white'])
        title_rect = title_text.get_rect(center=(self.width // 2, video_rect.y + 50))
        self.screen.blit(title_text, title_rect)
        
        # Video placeholder (when no video is playing)
        if self.current_video_title == "Loading..." or "Placeholder" in self.current_video_title:
            # Draw large play icon
            play_center = (self.width // 2, self.height // 2)
            play_radius = 80
            
            # Play button circle
            pygame.draw.circle(self.screen, self.colors['pizza_red'], play_center, play_radius)
            pygame.draw.circle(self.screen, self.colors['white'], play_center, play_radius, 4)
            
            # Play triangle
            triangle_points = [
                (play_center[0] - 25, play_center[1] - 30),
                (play_center[0] - 25, play_center[1] + 30),
                (play_center[0] + 35, play_center[1])
            ]
            pygame.draw.polygon(self.screen, self.colors['white'], triangle_points)
    
    def draw_status_bar(self):
        """Draw status bar (like webplayer footer)."""
        # Status bar background
        status_rect = pygame.Rect(0, self.height - 150, self.width, 150)
        pygame.draw.rect(self.screen, (20, 20, 20), status_rect)  # Dark background
        
        # Connection status
        conn_color = self.colors['green'] if "Connected" in self.connection_status else self.colors['yellow']
        conn_text = self.font_small.render(f"🌐 {self.connection_status}", True, conn_color)
        self.screen.blit(conn_text, (50, self.height - 130))
        
        # Sync status
        sync_color = self.colors['green'] if "Synced" in self.sync_status else self.colors['blue']
        sync_text = self.font_small.render(f"🎯 {self.sync_status}", True, sync_color)
        self.screen.blit(sync_text, (50, self.height - 100))
        
        # Performance stats
        if self.performance_stats:
            cpu = self.performance_stats.get('cpu', 0)
            memory = self.performance_stats.get('memory', 0)
            perf_text = self.font_small.render(f"📊 CPU: {cpu:.1f}% | RAM: {memory:.1f}%", True, self.colors['light_gray'])
            self.screen.blit(perf_text, (50, self.height - 70))
        
        # Playlist info
        if self.playlist_items:
            playlist_info = f"📋 Item {self.current_index + 1} of {len(self.playlist_items)}"
            playlist_text = self.font_small.render(playlist_info, True, self.colors['light_gray'])
            self.screen.blit(playlist_text, (self.width - 300, self.height - 130))
        
        # Current time
        current_time = time.strftime("%I:%M %p")
        time_text = self.font_small.render(f"🕐 {current_time}", True, self.colors['light_gray'])
        self.screen.blit(time_text, (self.width - 200, self.height - 100))
    
    def draw_playlist_sidebar(self):
        """Draw playlist sidebar (like webplayer)."""
        if not self.playlist_items:
            return
        
        # Sidebar background
        sidebar_rect = pygame.Rect(self.width - 350, 200, 300, self.height - 400)
        pygame.draw.rect(self.screen, (30, 30, 30), sidebar_rect)  # Dark background
        pygame.draw.rect(self.screen, self.colors['dark_gray'], sidebar_rect, 2)
        
        # Sidebar title
        title_text = self.font_medium.render("Playlist", True, self.colors['white'])
        self.screen.blit(title_text, (sidebar_rect.x + 20, sidebar_rect.y + 20))
        
        # Playlist items (show up to 10)
        y_offset = sidebar_rect.y + 70
        for i, item in enumerate(self.playlist_items[:10]):
            # Highlight current item
            if i == self.current_index:
                highlight_rect = pygame.Rect(sidebar_rect.x + 10, y_offset - 5, 280, 35)
                pygame.draw.rect(self.screen, self.colors['pizza_red'], highlight_rect, border_radius=5)
            
            # Item name
            item_name = item.get('file', 'Unknown')[:30]  # Truncate long names
            item_color = self.colors['white'] if i == self.current_index else self.colors['light_gray']
            item_text = self.font_small.render(f"{i+1}. {item_name}", True, item_color)
            self.screen.blit(item_text, (sidebar_rect.x + 20, y_offset))
            
            y_offset += 40
            if y_offset > sidebar_rect.bottom - 50:
                break
    
    def draw_sync_indicator(self):
        """Draw sync indicator (like webplayer)."""
        # Sync indicator circle in top-right
        sync_pos = (self.width - 100, 100)
        sync_radius = 25
        
        # Determine sync color
        if "Synced" in self.sync_status:
            sync_color = self.colors['green']
        elif "Syncing" in self.sync_status:
            sync_color = self.colors['yellow']
        else:
            sync_color = self.colors['pizza_red']
        
        # Draw sync indicator
        pygame.draw.circle(self.screen, sync_color, sync_pos, sync_radius)
        pygame.draw.circle(self.screen, self.colors['white'], sync_pos, sync_radius, 3)
        
        # Sync icon (simplified)
        sync_text = self.font_small.render("⟲", True, self.colors['white'])
        sync_rect = sync_text.get_rect(center=sync_pos)
        self.screen.blit(sync_text, sync_rect)
    
    def draw_overlay(self):
        """Draw information overlay (auto-hide like webplayer)."""
        if not self.show_overlay:
            return
        
        # Check if overlay should be hidden
        if time.time() - self.last_activity > (self.overlay_timeout / 1000):
            self.show_overlay = False
            return
        
        # Draw semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(80)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Overlay content
        self.draw_pizza_hut_logo()
        self.draw_status_bar()
        self.draw_playlist_sidebar()
        self.draw_sync_indicator()
    
    def update_display(self):
        """Update the display (like webplayer refresh)."""
        self.draw_background()
        self.draw_video_area()
        
        # Always show overlay initially or when activated
        if self.show_overlay:
            self.draw_overlay()
        
        pygame.display.flip()
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    return False
                elif event.key == pygame.K_SPACE or event.key == pygame.K_o:
                    # Toggle overlay (like webplayer)
                    self.show_overlay = not self.show_overlay
                    self.last_activity = time.time()
                elif event.key == pygame.K_i:
                    # Show info overlay
                    self.show_overlay = True
                    self.last_activity = time.time()
            elif event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEMOTION:
                # Show overlay on mouse activity
                self.show_overlay = True
                self.last_activity = time.time()
        
        return True
    
    def update_status(self, connection_status="", sync_status="", current_video="", playlist=None, current_index=0, perf_stats=None):
        """Update UI status information."""
        if connection_status:
            self.connection_status = connection_status
        if sync_status:
            self.sync_status = sync_status
        if current_video:
            self.current_video_title = current_video
        if playlist:
            self.playlist_items = playlist
        if current_index is not None:
            self.current_index = current_index
        if perf_stats:
            self.performance_stats = perf_stats

class EnhancedPiClientWithUI:
    """Enhanced Pi client with webplayer-style UI."""
    
    def __init__(self, server_url: str, store_id: str, screen_id: str):
        self.server_url = server_url.rstrip('/')
        self.store_id = store_id
        self.screen_id = screen_id
        self.user_agent = "phtv-pi-ui/1.0 (Raspberry Pi)"
        
        # Initialize UI
        self.ui = WebplayerStyleUI()
        
        # Client state
        self.current_playlist = []
        self.current_index = 0
        self.running = True
        self.last_playlist_fetch = 0
        self.playlist_refresh_interval = 5
        
        # Performance monitoring
        self.performance_stats = {}
        
        logger.info(f"Enhanced Pi Client with UI initialized")
        logger.info(f"Server: {self.server_url}, Store: {self.store_id}, Screen: {self.screen_id}")
    
    def fetch_playlist(self) -> List[Dict[str, Any]]:
        """Fetch playlist from server."""
        try:
            url = f"{self.server_url}/api/playlist/{self.store_id}/{self.screen_id}"
            headers = {'User-Agent': self.user_agent}
            
            logger.debug(f"Fetching playlist from: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                playlist = data.get('playlist', [])
                logger.info(f"Fetched {len(playlist)} playlist items")
                self.ui.update_status(connection_status="Connected ✅")
                return playlist
            else:
                raise Exception(f"API error: {data.get('error', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Playlist fetch failed: {e}")
            self.ui.update_status(connection_status="Connection Failed ❌")
            return []
    
    def get_performance_stats(self):
        """Get system performance stats."""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            self.performance_stats = {
                'cpu': cpu_percent,
                'memory': memory.percent,
                'uptime': time.time() - getattr(self, 'start_time', time.time())
            }
            
            return self.performance_stats
            
        except ImportError:
            return {'cpu': 0, 'memory': 0, 'uptime': 0}
    
    def simulate_video_playback(self, video_item):
        """Simulate video playback with UI updates."""
        video_name = os.path.basename(video_item.get('file', 'Unknown Video'))
        duration = int(video_item.get('duration', 10))
        
        logger.info(f"Playing: {video_name} ({duration}s)")
        
        # Update UI
        self.ui.update_status(
            current_video=f"🎬 {video_name}",
            sync_status="Synced ✅",
            playlist=self.current_playlist,
            current_index=self.current_index
        )
        
        # Simulate playback with UI updates
        start_time = time.time()
        while time.time() - start_time < duration and self.running:
            # Handle UI events
            if not self.ui.handle_events():
                self.running = False
                break
            
            # Update performance stats
            perf_stats = self.get_performance_stats()
            self.ui.update_status(perf_stats=perf_stats)
            
            # Update display
            self.ui.update_display()
            self.ui.clock.tick(30)  # 30 FPS like webplayer
            
            time.sleep(0.1)
    
    def run(self):
        """Main client loop with UI."""
        logger.info("Starting Enhanced Pi Client with Webplayer-Style UI")
        
        # Initialize UI
        if not self.ui.init_pygame():
            logger.error("Failed to initialize UI")
            return
        
        self.start_time = time.time()
        self.ui.update_status(connection_status="Connecting...", sync_status="Initializing...")
        
        try:
            while self.running:
                # Handle UI events
                if not self.ui.handle_events():
                    break
                
                # Fetch playlist periodically
                current_time = time.time()
                if (current_time - self.last_playlist_fetch) >= self.playlist_refresh_interval:
                    self.current_playlist = self.fetch_playlist()
                    self.last_playlist_fetch = current_time
                
                if not self.current_playlist:
                    # No playlist - show loading screen
                    self.ui.update_status(
                        current_video="Loading playlist...",
                        sync_status="Waiting for content",
                        connection_status="Retrying connection..."
                    )
                    self.ui.update_display()
                    self.ui.clock.tick(30)
                    time.sleep(1)
                    continue
                
                # Reset index if needed
                if self.current_index >= len(self.current_playlist):
                    self.current_index = 0
                
                # Get current item
                current_item = self.current_playlist[self.current_index]
                
                # Simulate video playback with UI
                self.simulate_video_playback(current_item)
                
                # Move to next item
                if self.running:
                    self.current_index = (self.current_index + 1) % len(self.current_playlist)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up UI client")
        self.running = False
        
        try:
            pygame.quit()
        except:
            pass

class PizzaHutPlayerUI:
    """Pizza Hut branded player UI maintaining setup flow branding."""
    
    def __init__(self, server_url, store_id, screen_id):
        self.server_url = server_url
        self.store_id = store_id
        self.screen_id = screen_id
        
        # Initialize UI matching setup flow
        self.width = 1920
        self.height = 1080
        self.screen = None
        self.clock = None
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        
        # Colors matching webplayer dark theme
        self.colors = {
            'background': (17, 17, 17),     # Dark black background like webplayer
            'white': (255, 255, 255),       # White text
            'light_gray': (170, 170, 170),  # Light gray text
            'red_accent': (220, 53, 69),    # Red accents
            'green': (40, 167, 69),         # Success green
        }
        
        # Player state
        self.current_video = "Connecting to Pizza Hut TV..."
        self.connection_status = "Connecting..."
        self.show_overlay = True
        self.last_activity = time.time()
    
    def init_pygame(self):
        """Initialize pygame matching setup flow."""
        try:
            pygame.init()
            pygame.mixer.quit()
            
            # Get display info
            info = pygame.display.Info()
            if info.current_w > 0 and info.current_h > 0:
                self.width = info.current_w
                self.height = info.current_h
            
            # Create fullscreen display
            self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
            pygame.display.set_caption("🍕 Pizza Hut TV Player")
            pygame.mouse.set_visible(False)
            
            self.clock = pygame.time.Clock()
            
            # Initialize fonts (same as setup flow)
            try:
                self.font_large = pygame.font.Font(None, 96)
                self.font_medium = pygame.font.Font(None, 56)
                self.font_small = pygame.font.Font(None, 36)
            except:
                self.font_large = pygame.font.SysFont('arial', 96, bold=True)
                self.font_medium = pygame.font.SysFont('arial', 56)
                self.font_small = pygame.font.SysFont('arial', 36)
            
            logger.info(f"Pizza Hut Player UI initialized: {self.width}x{self.height}")
            return True
            
        except Exception as e:
            logger.error(f"Player UI initialization failed: {e}")
            return False
    
    def draw_background(self):
        """Draw dark background matching webplayer."""
        self.screen.fill(self.colors['background'])
    
    def draw_player_overlay(self):
        """Draw player overlay with Pizza Hut branding."""
        if not self.show_overlay:
            return
        
        # Logo area
        logo_text = self.font_large.render("🍕 PIZZA HUT TV", True, self.colors['white'])
        logo_rect = logo_text.get_rect(center=(self.width // 2, 100))
        
        # Add shadow
        shadow_text = self.font_large.render("🍕 PIZZA HUT TV", True, (0, 0, 0))
        shadow_rect = logo_rect.copy()
        shadow_rect.x += 3
        shadow_rect.y += 3
        self.screen.blit(shadow_text, shadow_rect)
        self.screen.blit(logo_text, logo_rect)
        
        # Connection info
        status_text = f"🏪 Store: {self.store_id} | 📺 Screen: {self.screen_id}"
        status_surface = self.font_medium.render(status_text, True, self.colors['light_gray'])
        status_rect = status_surface.get_rect(center=(self.width // 2, 180))
        self.screen.blit(status_surface, status_rect)
        
        # Current video info
        video_surface = self.font_small.render(self.current_video, True, self.colors['white'])
        video_rect = video_surface.get_rect(center=(self.width // 2, self.height - 100))
        self.screen.blit(video_surface, video_rect)
        
        # Connection status
        conn_surface = self.font_small.render(f"🌐 {self.connection_status}", True, self.colors['green'])
        conn_rect = conn_surface.get_rect(center=(self.width // 2, self.height - 60))
        self.screen.blit(conn_surface, conn_rect)
    
    def handle_events(self):
        """Handle player events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    return False
                elif event.key == pygame.K_SPACE or event.key == pygame.K_o:
                    self.show_overlay = not self.show_overlay
                    self.last_activity = time.time()
                elif event.key == pygame.K_i:
                    self.show_overlay = True
                    self.last_activity = time.time()
        return True
    
    def run(self):
        """Run the Pizza Hut branded player."""
        if not self.init_pygame():
            logger.error("Failed to initialize Pizza Hut player UI")
            return
        
        logger.info(f"🍕 Starting Pizza Hut TV Player - Store: {self.store_id}, Screen: {self.screen_id}")
        
        # Update status
        self.current_video = f"Loading content for {self.store_id}..."
        self.connection_status = "Connected to Pizza Hut TV"
        
        running = True
        try:
            while running:
                # Handle events
                if not self.handle_events():
                    break
                
                # Draw webplayer-style interface
                self.draw_background()
                self.draw_player_overlay()
                
                pygame.display.flip()
                self.clock.tick(60)
                
                # Simulate loading and then actual playback
                # (In real implementation, this would integrate with the enhanced client)
                
        except KeyboardInterrupt:
            logger.info("Pizza Hut player stopped by user")
        except Exception as e:
            logger.error(f"Pizza Hut player error: {e}")
        finally:
            pygame.quit()

def main():
    """Main entry point with webplayer-style setup flow."""
    parser = argparse.ArgumentParser(description='Pizza Hut TV Pi Client with Webplayer Setup Flow')
    parser.add_argument('--server', default='https://everydayadvertise.com',
                       help='Server URL (default: https://everydayadvertise.com)')
    parser.add_argument('--skip-setup', action='store_true',
                       help='Skip setup flow and use provided store/screen')
    parser.add_argument('--store', default='',
                       help='Store ID (used with --skip-setup)')  
    parser.add_argument('--screen', default='',
                       help='Screen ID (used with --skip-setup)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("🍕 Pizza Hut TV - Pi Client with Webplayer Setup Flow")
    print("=" * 60)
    
    server_url = args.server
    store_id = args.store
    screen_id = args.screen
    
    # Run setup flow if not skipped
    if not args.skip_setup or not store_id or not screen_id:
        print("Starting webplayer-style setup flow...")
        print("1. Connect to Android TV (enter 4-digit code)")
        print("2. Select your store")
        print("3. Choose screen to launch")
        print("=" * 60)
        
        try:
            setup_ui = WebplayerSetupUI(server_url=server_url)
            tv_code, store_id, screen_id = setup_ui.run_setup()
            
            if not all([tv_code, store_id, screen_id]):
                print("Setup cancelled or failed.")
                sys.exit(0)
                
            print(f"✅ Setup complete!")
            print(f"   TV Code: {tv_code}")
            print(f"   Store: {store_id}")
            print(f"   Screen: {screen_id}")
            print("=" * 60)
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    else:
        print(f"Skipping setup - using Store: {store_id}, Screen: {screen_id}")
        print("=" * 60)
    
    # Launch main player with Pizza Hut branding
    print("Launching Pizza Hut TV player...")
    print("Controls:")
    print("  O or SPACE - Toggle overlay")
    print("  I - Show info overlay")
    print("  ESC or Q - Quit")
    print("=" * 60)
    
    try:
        # Create a new Pizza Hut branded player UI
        player_ui = PizzaHutPlayerUI(server_url, store_id, screen_id)
        player_ui.run()
    except Exception as e:
        logger.error(f"Player error: {e}")
        logger.error(traceback.format_exc())
        # Fallback to old UI if new one fails
        try:
            client = EnhancedPiClientWithUI(server_url, store_id, screen_id)
            client.run()
        except Exception as e2:
            logger.error(f"Fallback player also failed: {e2}")
            sys.exit(1)

if __name__ == '__main__':
    main()