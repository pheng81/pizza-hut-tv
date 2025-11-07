#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Fixed Pi Client with Clear UI
Clean, user-friendly interface that clearly shows where to enter numbers
"""

import pygame
import requests
import json
import time
import threading
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FixedPiClient:
    """Fixed Pi client with crystal clear UI."""
    
    def __init__(self, server_url: str = "https://everydayadvertise.com"):
        self.server_url = server_url.rstrip('/')
        
        # Initialize pygame
        pygame.init()
        self.screen_info = pygame.display.Info()
        self.width = self.screen_info.current_w
        self.height = self.screen_info.current_h
        
        # Create display
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
        pygame.display.set_caption("Pizza Hut TV - Fixed Client")
        pygame.mouse.set_visible(False)
        
        # Colors - bright and clear
        self.colors = {
            'pizza_red': (227, 24, 55),
            'pizza_red_dark': (196, 30, 58),
            'gold': (255, 215, 0),
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'gray': (128, 128, 128),
            'light_gray': (200, 200, 200),
            'dark_gray': (64, 64, 64),
            'green': (34, 197, 94),
            'input_field': (40, 40, 40),
            'input_active': (60, 60, 60)
        }
        
        # Large, clear fonts
        try:
            self.font_huge = pygame.font.Font(None, 120)      # For big numbers
            self.font_large = pygame.font.Font(None, 72)      # For titles
            self.font_medium = pygame.font.Font(None, 48)     # For labels
            self.font_small = pygame.font.Font(None, 36)      # For instructions
        except:
            self.font_huge = pygame.font.SysFont('arial', 120, bold=True)
            self.font_large = pygame.font.SysFont('arial', 72, bold=True)
            self.font_medium = pygame.font.SysFont('arial', 48)
            self.font_small = pygame.font.SysFont('arial', 36)
        
        # State
        self.current_state = "setup"
        self.setup_step = "code"  # code, store, screen
        self.input_text = ""
        self.tv_code = ""
        self.store_id = ""
        self.screen_id = ""
        self.error_message = ""
        self.available_stores = []
        self.available_screens = {}
        
        # Animation
        self.cursor_blink = 0
        self.animation_time = 0
        
        logger.info(f"Fixed Pi Client initialized: {self.width}x{self.height}")
    
    def draw_gradient_background(self):
        """Draw Pizza Hut gradient background."""
        for y in range(self.height):
            ratio = y / self.height
            r = int(227 * (1 - ratio) + 196 * ratio)
            g = int(24 * (1 - ratio) + 30 * ratio)
            b = int(55 * (1 - ratio) + 58 * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.width, y))
    
    def draw_code_input_screen(self):
        """Draw SUPER CLEAR code input screen."""
        self.draw_gradient_background()
        
        # Main container - much bigger and clearer
        container_width = min(800, self.width - 100)
        container_height = min(600, self.height - 100)
        container_x = (self.width - container_width) // 2
        container_y = (self.height - container_height) // 2
        
        # Semi-transparent background
        container_surface = pygame.Surface((container_width, container_height), pygame.SRCALPHA)
        pygame.draw.rect(container_surface, (0, 0, 0, 128), (0, 0, container_width, container_height), border_radius=30)
        self.screen.blit(container_surface, (container_x, container_y))
        
        # Title - HUGE and clear
        title_text = self.font_large.render("🍕 PIZZA HUT TV", True, self.colors['white'])
        title_rect = title_text.get_rect(center=(self.width // 2, container_y + 80))
        self.screen.blit(title_text, title_rect)
        
        # Subtitle
        subtitle_text = self.font_medium.render("Connect to Android TV", True, self.colors['light_gray'])
        subtitle_rect = subtitle_text.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(subtitle_text, subtitle_rect)
        
        # SUPER CLEAR instruction
        instruction_text = self.font_medium.render("ENTER THE 4-DIGIT CODE FROM YOUR TV:", True, self.colors['gold'])
        instruction_rect = instruction_text.get_rect(center=(self.width // 2, container_y + 200))
        self.screen.blit(instruction_text, instruction_rect)
        
        # INPUT BOXES - Individual boxes for each digit (SUPER CLEAR!)
        box_size = 80
        box_spacing = 20
        total_width = 4 * box_size + 3 * box_spacing
        start_x = (self.width - total_width) // 2
        box_y = container_y + 260
        
        for i in range(4):
            box_x = start_x + i * (box_size + box_spacing)
            box_rect = pygame.Rect(box_x, box_y, box_size, box_size)
            
            # Box background - different color if filled
            if i < len(self.input_text):
                bg_color = self.colors['input_active']
                border_color = self.colors['gold']
                border_width = 4
            else:
                bg_color = self.colors['input_field']
                border_color = self.colors['white']
                border_width = 2
            
            pygame.draw.rect(self.screen, bg_color, box_rect, border_radius=15)
            pygame.draw.rect(self.screen, border_color, box_rect, border_width, border_radius=15)
            
            # Digit or cursor
            if i < len(self.input_text):
                digit_text = self.font_huge.render(self.input_text[i], True, self.colors['white'])
                digit_rect = digit_text.get_rect(center=box_rect.center)
                self.screen.blit(digit_text, digit_rect)
            elif i == len(self.input_text):
                # Blinking cursor
                if int(self.cursor_blink / 500) % 2:  # Blink every 500ms
                    cursor_text = self.font_huge.render("_", True, self.colors['gold'])
                    cursor_rect = cursor_text.get_rect(center=box_rect.center)
                    self.screen.blit(cursor_text, cursor_rect)
        
        # Connect button - only if 4 digits entered
        if len(self.input_text) == 4:
            button_width = 300
            button_height = 60
            button_x = (self.width - button_width) // 2
            button_y = container_y + 380
            button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            
            # Animated button
            glow_alpha = int(128 + 127 * abs(pygame.math.Vector2(1, 0).rotate(self.animation_time * 0.1).x))
            button_surface = pygame.Surface((button_width, button_height), pygame.SRCALPHA)
            pygame.draw.rect(button_surface, (*self.colors['gold'], glow_alpha), (0, 0, button_width, button_height), border_radius=20)
            self.screen.blit(button_surface, (button_x, button_y))
            
            button_text = self.font_medium.render("CONNECT TO TV", True, self.colors['pizza_red'])
            text_rect = button_text.get_rect(center=button_rect.center)
            self.screen.blit(button_text, text_rect)
        
        # Instructions at bottom
        instructions = [
            "• Look at your Android TV screen",
            "• Find the 4-digit code displayed",
            "• Type the numbers using your keyboard",
            "• Press ENTER to connect"
        ]
        
        for i, instruction in enumerate(instructions):
            inst_text = self.font_small.render(instruction, True, self.colors['light_gray'])
            inst_rect = inst_text.get_rect(center=(self.width // 2, container_y + 480 + i * 30))
            self.screen.blit(inst_text, inst_rect)
        
        # Error message
        if self.error_message:
            error_text = self.font_medium.render(f"❌ {self.error_message}", True, (255, 100, 100))
            error_rect = error_text.get_rect(center=(self.width // 2, self.height - 50))
            self.screen.blit(error_text, error_rect)
    
    def draw_store_input_screen(self):
        """Draw store input screen."""
        self.draw_gradient_background()
        
        # Container
        container_width = min(700, self.width - 100)
        container_height = min(500, self.height - 100)
        container_x = (self.width - container_width) // 2
        container_y = (self.height - container_height) // 2
        
        container_surface = pygame.Surface((container_width, container_height), pygame.SRCALPHA)
        pygame.draw.rect(container_surface, (0, 0, 0, 128), (0, 0, container_width, container_height), border_radius=30)
        self.screen.blit(container_surface, (container_x, container_y))
        
        # Title
        title_text = self.font_large.render("Enter Store Code", True, self.colors['white'])
        title_rect = title_text.get_rect(center=(self.width // 2, container_y + 80))
        self.screen.blit(title_text, title_rect)
        
        # TV code display
        tv_display = self.font_medium.render(f"TV Code: {self.tv_code}", True, self.colors['gold'])
        tv_rect = tv_display.get_rect(center=(self.width // 2, container_y + 140))
        self.screen.blit(tv_display, tv_rect)
        
        # Store input field
        input_width = 400
        input_height = 60
        input_x = (self.width - input_width) // 2
        input_y = container_y + 200
        input_rect = pygame.Rect(input_x, input_y, input_width, input_height)
        
        pygame.draw.rect(self.screen, self.colors['input_field'], input_rect, border_radius=15)
        pygame.draw.rect(self.screen, self.colors['gold'], input_rect, 3, border_radius=15)
        
        # Input text
        if self.input_text:
            text_surface = self.font_medium.render(self.input_text, True, self.colors['white'])
        else:
            text_surface = self.font_medium.render("Store Number (e.g. 1000)", True, self.colors['gray'])
        
        text_rect = text_surface.get_rect(centery=input_rect.centery, x=input_rect.x + 20)
        self.screen.blit(text_surface, text_rect)
        
        # Continue button
        if self.input_text:
            button_width = 200
            button_height = 50
            button_x = (self.width - button_width) // 2
            button_y = container_y + 300
            
            pygame.draw.rect(self.screen, self.colors['gold'], (button_x, button_y, button_width, button_height), border_radius=15)
            
            button_text = self.font_medium.render("CONTINUE", True, self.colors['pizza_red'])
            text_rect = button_text.get_rect(center=(button_x + button_width // 2, button_y + button_height // 2))
            self.screen.blit(button_text, text_rect)
        
        # Instructions
        inst_text = self.font_small.render("Enter your store number and press ENTER", True, self.colors['light_gray'])
        inst_rect = inst_text.get_rect(center=(self.width // 2, container_y + 380))
        self.screen.blit(inst_text, inst_rect)
        
        # Error message
        if self.error_message:
            error_text = self.font_medium.render(f"❌ {self.error_message}", True, (255, 100, 100))
            error_rect = error_text.get_rect(center=(self.width // 2, self.height - 50))
            self.screen.blit(error_text, error_rect)
    
    def draw_screen_select_screen(self):
        """Draw screen selection."""
        self.draw_gradient_background()
        
        # Title bar
        title_text = self.font_large.render("Select Screen", True, self.colors['white'])
        title_rect = title_text.get_rect(center=(self.width // 2, 80))
        self.screen.blit(title_text, title_rect)
        
        # Status
        status_text = f"TV: {self.tv_code} • Store: {self.store_id}"
        status_surface = self.font_small.render(status_text, True, self.colors['light_gray'])
        status_rect = status_surface.get_rect(center=(self.width // 2, 130))
        self.screen.blit(status_surface, status_rect)
        
        # Screen list
        if self.available_screens:
            y_offset = 200
            for i, (screen_id, screen_info) in enumerate(self.available_screens.items()):
                # Screen item
                item_width = min(600, self.width - 100)
                item_height = 60
                item_x = (self.width - item_width) // 2
                item_rect = pygame.Rect(item_x, y_offset, item_width, item_height)
                
                # Background
                bg_color = self.colors['input_active'] if i == 0 else self.colors['input_field']
                pygame.draw.rect(self.screen, bg_color, item_rect, border_radius=10)
                pygame.draw.rect(self.screen, self.colors['gold'], item_rect, 2, border_radius=10)
                
                # Screen name
                screen_name = screen_info.get('display_name', f"Screen {i + 1}")
                name_text = self.font_medium.render(f"{i + 1}. {screen_name}", True, self.colors['white'])
                name_rect = name_text.get_rect(centery=item_rect.centery, x=item_rect.x + 20)
                self.screen.blit(name_text, name_rect)
                
                # Screen ID
                id_text = self.font_small.render(screen_id, True, self.colors['light_gray'])
                id_rect = id_text.get_rect(centery=item_rect.centery, right=item_rect.right - 20)
                self.screen.blit(id_text, id_rect)
                
                y_offset += 80
        else:
            loading_text = self.font_medium.render("Loading screens...", True, self.colors['light_gray'])
            loading_rect = loading_text.get_rect(center=(self.width // 2, 300))
            self.screen.blit(loading_text, loading_rect)
        
        # Instructions
        inst_text = self.font_small.render("Press number key (1, 2, 3...) to select screen", True, self.colors['light_gray'])
        inst_rect = inst_text.get_rect(center=(self.width // 2, self.height - 100))
        self.screen.blit(inst_text, inst_rect)
        
        # Error message
        if self.error_message:
            error_text = self.font_medium.render(f"❌ {self.error_message}", True, (255, 100, 100))
            error_rect = error_text.get_rect(center=(self.width // 2, self.height - 50))
            self.screen.blit(error_text, error_rect)
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.setup_step == "code":
                        return False
                    elif self.setup_step == "store":
                        self.setup_step = "code"
                        self.input_text = self.tv_code
                    elif self.setup_step == "screen":
                        self.setup_step = "store"
                        self.input_text = self.store_id
                
                elif event.key == pygame.K_BACKSPACE:
                    if self.input_text:
                        self.input_text = self.input_text[:-1]
                        self.error_message = ""
                
                elif event.key == pygame.K_RETURN:
                    self.handle_enter()
                
                # Handle number input
                elif event.unicode.isdigit():
                    if self.setup_step == "code" and len(self.input_text) < 4:
                        self.input_text += event.unicode
                        self.error_message = ""
                    elif self.setup_step == "store":
                        self.input_text += event.unicode
                        self.error_message = ""
                    elif self.setup_step == "screen":
                        # Select screen by number
                        screen_num = int(event.unicode) - 1
                        screen_list = list(self.available_screens.keys())
                        if 0 <= screen_num < len(screen_list):
                            self.screen_id = screen_list[screen_num]
                            self.launch_player()
                
                # Handle letters for store codes
                elif self.setup_step == "store" and event.unicode.isalnum():
                    self.input_text += event.unicode.upper()
                    self.error_message = ""
        
        return True
    
    def handle_enter(self):
        """Handle enter key press."""
        if self.setup_step == "code":
            if len(self.input_text) == 4 and self.input_text.isdigit():
                self.validate_tv_code()
        elif self.setup_step == "store":
            if self.input_text:
                self.validate_store()
    
    def validate_tv_code(self):
        """Validate TV code with server."""
        self.error_message = "Connecting..."
        
        try:
            response = requests.get(
                f"{self.server_url}/api/stores_by_code/{self.input_text}",
                timeout=10,
                headers={'User-Agent': 'PizzaHutTV-FixedPi/1.0'}
            )
            
            if response.status_code == 200:
                stores_data = response.json()
                if stores_data:
                    self.tv_code = self.input_text
                    self.available_stores = stores_data
                    self.setup_step = "store"
                    self.input_text = ""
                    self.error_message = ""
                    logger.info(f"✅ TV code {self.tv_code} validated")
                else:
                    self.error_message = "Invalid TV code - not found"
            else:
                self.error_message = f"Connection failed ({response.status_code})"
                
        except Exception as e:
            self.error_message = f"Connection error: {str(e)[:50]}"
            logger.error(f"TV code validation error: {e}")
    
    def validate_store(self):
        """Validate store and load screens."""
        self.error_message = "Loading screens..."
        
        try:
            self.store_id = self.input_text
            
            # Load screens for the store
            response = requests.get(
                f"{self.server_url}/api/screens/{self.tv_code}/{self.store_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                screens_data = response.json()
                if screens_data:
                    self.available_screens = screens_data
                    self.setup_step = "screen"
                    self.input_text = ""
                    self.error_message = ""
                    logger.info(f"✅ Store {self.store_id} validated, {len(screens_data)} screens found")
                else:
                    self.error_message = "No screens found for this store"
            else:
                self.error_message = f"Failed to load screens ({response.status_code})"
                
        except Exception as e:
            self.error_message = f"Error loading screens: {str(e)[:50]}"
            logger.error(f"Store validation error: {e}")
    
    def launch_player(self):
        """Launch the media player."""
        logger.info(f"🚀 Launching player: TV={self.tv_code}, Store={self.store_id}, Screen={self.screen_id}")
        
        # Import and launch complete client
        try:
            from complete_pi_client import CompleteWebplayerClient
            
            # Create complete client with our validated settings
            complete_client = CompleteWebplayerClient(self.server_url)
            complete_client.pair_code = self.tv_code
            complete_client.store_id = self.store_id
            complete_client.screen_id = self.screen_id
            complete_client.current_state = "playing"
            
            # Close our setup screen
            pygame.quit()
            
            # Launch complete client
            complete_client.run()
            
        except Exception as e:
            logger.error(f"Failed to launch player: {e}")
            self.error_message = f"Failed to launch player: {str(e)[:50]}"
    
    def update(self, dt):
        """Update animations."""
        self.cursor_blink += dt
        self.animation_time += dt
    
    def draw(self):
        """Draw current screen."""
        if self.setup_step == "code":
            self.draw_code_input_screen()
        elif self.setup_step == "store":
            self.draw_store_input_screen()
        elif self.setup_step == "screen":
            self.draw_screen_select_screen()
    
    def run(self):
        """Main game loop."""
        clock = pygame.time.Clock()
        running = True
        
        logger.info("🍕 Fixed Pi Client started - Clear UI mode")
        
        while running:
            dt = clock.tick(60)
            
            # Handle events
            running = self.handle_events()
            if not running:
                break
            
            # Update
            self.update(dt)
            
            # Draw
            self.draw()
            pygame.display.flip()
        
        pygame.quit()
        logger.info("Fixed Pi Client stopped")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pizza Hut TV - Fixed Pi Client')
    parser.add_argument('--server', default='https://everydayadvertise.com', 
                       help='Server URL')
    args = parser.parse_args()
    
    try:
        client = FixedPiClient(args.server)
        client.run()
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Client error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()