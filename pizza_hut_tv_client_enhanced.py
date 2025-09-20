#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Enhanced Raspberry Pi Client
Universal client supporting dynamic store/screen selection like webplayer and Android TV
Supports production deployment with everydayadvertise.com
"""

import os
import sys
import json
import time
import requests
import subprocess
import threading
from datetime import datetime

class PizzaHutTVClient:
    def __init__(self):
        # Default to production server
        self.server_url = "https://everydayadvertise.com"
        self.store_id = None  # Dynamic selection
        self.screen_id = "tv1"
        self.user_code = None  # 4-digit link code
        self.username = None
        self.password = None
        self.current_stores = []
        self.current_screens = {}
        self.config_file = "client_config.txt"
        self.load_config()
        
    def show_status(self):
        """Display current configuration"""
        print("\n🍕 Pizza Hut TV Client Status")
        print("=" * 40)
        print(f"   Server: {self.server_url}")
        if self.store_id:
            print(f"   Store:  {self.store_id} | Screen: {self.screen_id}")
        else:
            print("   Store:  Not selected")
        if self.user_code:
            print(f"   Code:   {self.user_code}")
        if self.username:
            print(f"   User:   {self.username}")
        print("=" * 40)
        
    def test_connection(self):
        """Test connection to server and show available content"""
        print("🔍 Testing connection...")
        try:
            # Test basic server connectivity
            response = requests.get(f"{self.server_url.rstrip('/')}/health", timeout=10)
            if response.status_code == 200:
                print(f"✅ Server reachable: {self.server_url}")
            else:
                print(f"⚠️ Server responds but with status: {response.status_code}")
        except Exception as e:
            print(f"❌ Server unreachable: {e}")
            print("💡 Try: Configure server URL (option 3) or check network connection")
            return False
            
        # Test content availability
        if not self.store_id:
            print("⚠️ No store selected. Use option 5 to select store first.")
            return False
            
        try:
            headers = {'User-Agent': 'phtv-pi/1.0 (Raspberry Pi Client)'}
            if self.user_code:
                headers['X-User-Code'] = self.user_code
                
            url = f"{self.server_url.rstrip('/')}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('playlist'):
                    playlist = data['playlist']
                    print(f"✅ Content found: {len(playlist)} items in playlist")
                    
                    # Show first few items
                    for i, item in enumerate(playlist[:3]):
                        name = item.get('file', 'Unknown')
                        media_type = item.get('media_type', 'unknown')
                        print(f"   {i+1}. {name} ({media_type})")
                    
                    if len(playlist) > 3:
                        print(f"   ... and {len(playlist) - 3} more items")
                        
                    return True
                else:
                    print(f"⚠️ Server found but no content for store: {self.store_id}")
                    print("💡 Try: Select different store (option 5) or check content upload")
                    return False
            else:
                print(f"❌ API error: {response.status_code}")
                if response.text:
                    try:
                        error_data = response.json()
                        print(f"   {error_data.get('error', response.text[:100])}")
                    except:
                        print(f"   {response.text[:100]}")
                return False
                
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
            
    def discover_stores(self):
        """Discover available stores using multiple methods"""
        print("🔍 Discovering available stores...")
        
        stores_found = []
        screens_found = {}
        
        # Method 1: If we have a user code, use the stores API
        if self.user_code:
            try:
                url = f"{self.server_url.rstrip('/')}/api/stores_by_code/{self.user_code}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stores_found = data.get('stores', [])
                        screens_found = data.get('screens', {})
                        print(f"✅ Found {len(stores_found)} stores via user code")
                        return stores_found, screens_found
                        
            except Exception as e:
                print(f"⚠️ User code lookup failed: {e}")
        
        # Method 2: Try common store patterns (educated guessing based on email patterns)
        print("🔍 Scanning for common stores...")
        common_patterns = [
            'test5_at_hotmail.com',  # Known working store from conversation
            'heang2_at_gmail.com',   # Another known store
            'heang3_at_hotmail.com',
            'kayson2_at_gmail.com',
            'kalix2_at_gmail.com',
            '1000',  # Legacy store ID
            '1881',  # Legacy store ID
        ]
        
        headers = {'User-Agent': 'phtv-pi/1.0 (Raspberry Pi Client)'}
        if self.user_code:
            headers['X-User-Code'] = self.user_code
            
        for pattern in common_patterns:
            try:
                url = f"{self.server_url.rstrip('/')}/playlist/{pattern}/tv1"
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stores_found.append({'id': pattern, 'name': pattern})
                        # Check for screens
                        screens_found[pattern] = {'tv1': {'playlist': data.get('playlist', [])}}
                        print(f"   ✅ Found store: {pattern}")
                        
            except Exception:
                continue
                
        print(f"📊 Discovery complete: {len(stores_found)} stores found")
        return stores_found, screens_found
        
    def list_stores(self):
        """List and select available stores"""
        print("\n📋 Store Selection")
        print("=" * 40)
        
        self.current_stores, self.current_screens = self.discover_stores()
        
        if not self.current_stores:
            print("❌ No stores found!")
            print("💡 Possible solutions:")
            print("   1. Check server URL (option 3)")
            print("   2. Set user authentication (option 4)")
            print("   3. Verify network connection")
            return
            
        print("Available stores:")
        for i, store in enumerate(self.current_stores, 1):
            store_id = store.get('id', store.get('name', 'Unknown'))
            store_name = store.get('name', store_id)
            
            # Count content
            screens = self.current_screens.get(store_id, {})
            content_count = 0
            for screen_data in screens.values():
                content_count += len(screen_data.get('playlist', []))
                
            print(f"   {i}. {store_name}")
            print(f"      ID: {store_id}")
            print(f"      Content: {content_count} items")
            
        print("\nSelect store:")
        try:
            choice = input("Enter number (or 'q' to cancel): ").strip()
            if choice.lower() == 'q':
                return
                
            idx = int(choice) - 1
            if 0 <= idx < len(self.current_stores):
                selected_store = self.current_stores[idx]
                self.store_id = selected_store.get('id', selected_store.get('name'))
                
                # Auto-select screen or let user choose
                available_screens = list(self.current_screens.get(self.store_id, {}).keys())
                if available_screens:
                    if len(available_screens) == 1:
                        self.screen_id = available_screens[0]
                        print(f"✅ Selected: {self.store_id}/{self.screen_id}")
                    else:
                        print(f"\nAvailable screens for {self.store_id}:")
                        for i, screen in enumerate(available_screens, 1):
                            print(f"   {i}. {screen}")
                        screen_choice = input("Select screen number: ").strip()
                        try:
                            screen_idx = int(screen_choice) - 1
                            if 0 <= screen_idx < len(available_screens):
                                self.screen_id = available_screens[screen_idx]
                                print(f"✅ Selected: {self.store_id}/{self.screen_id}")
                        except ValueError:
                            print("❌ Invalid selection")
                            return
                else:
                    # Default to tv1
                    self.screen_id = "tv1"
                    print(f"✅ Selected: {self.store_id}/{self.screen_id} (default screen)")
                    
                self.save_config()
            else:
                print("❌ Invalid selection")
                
        except ValueError:
            print("❌ Please enter a valid number")
            
    def configure_settings(self):
        """Configure server and authentication settings"""
        print("\n⚙️ Configuration")
        print("=" * 40)
        
        # Server URL
        new_server = input(f"\nServer URL [{self.server_url}]: ").strip()
        if new_server:
            # Add https:// if not present
            if not new_server.startswith(('http://', 'https://')):
                new_server = 'https://' + new_server
            self.server_url = new_server
            
        # Store ID (manual entry option)
        if self.store_id:
            new_store = input(f"Store ID [{self.store_id}]: ").strip()
        else:
            new_store = input("Store ID [auto-detect]: ").strip()
        if new_store:
            self.store_id = new_store
            
        # Screen ID
        new_screen = input(f"Screen ID [{self.screen_id}]: ").strip()
        if new_screen:
            self.screen_id = new_screen
            
        self.save_config()
        print("✅ Configuration saved")
        
    def configure_authentication(self):
        """Configure user authentication"""
        print("\n🔐 Authentication Setup")
        print("=" * 40)
        print("Choose authentication method:")
        print("1. 4-digit user code (like Android TV)")
        print("2. Username/password") 
        print("3. Clear authentication")
        
        choice = input("Select method (1-3): ").strip()
        
        if choice == "1":
            code = input("Enter 4-digit user code: ").strip()
            if len(code) == 4 and code.isdigit():
                self.user_code = code
                self.username = None
                self.password = None
                print("✅ User code set")
            else:
                print("❌ Invalid code. Must be 4 digits.")
                return
                
        elif choice == "2":
            username = input("Username/email: ").strip()
            if username:
                # Note: Password storage would need proper hashing in production
                password = input("Password: ").strip()
                if password:
                    self.username = username
                    self.password = password
                    self.user_code = None
                    print("✅ Credentials set")
                    print("⚠️ Note: Password stored locally - ensure Pi is secure")
                    
        elif choice == "3":
            self.user_code = None
            self.username = None
            self.password = None
            print("✅ Authentication cleared")
            
        self.save_config()
        
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                f.write(f"SERVER_URL={self.server_url}\n")
                if self.store_id:
                    f.write(f"STORE_ID={self.store_id}\n")
                f.write(f"SCREEN_ID={self.screen_id}\n")
                if self.user_code:
                    f.write(f"USER_CODE={self.user_code}\n")
                if self.username:
                    f.write(f"USERNAME={self.username}\n")
                if self.password:
                    f.write(f"PASSWORD={self.password}\n")
        except Exception as e:
            print(f"⚠️ Could not save config: {e}")
            
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            if key == 'SERVER_URL':
                                self.server_url = value
                            elif key == 'STORE_ID':
                                self.store_id = value
                            elif key == 'SCREEN_ID':
                                self.screen_id = value
                            elif key == 'USER_CODE':
                                self.user_code = value
                            elif key == 'USERNAME':
                                self.username = value
                            elif key == 'PASSWORD':
                                self.password = value
            except Exception as e:
                print(f"⚠️ Could not load config: {e}")
                
    def get_playlist(self):
        """Get current playlist from server"""
        if not self.store_id:
            print("❌ No store selected. Use option 5 first.")
            return []
            
        try:
            headers = {'User-Agent': 'phtv-pi/1.0 (Raspberry Pi Client)'}
            if self.user_code:
                headers['X-User-Code'] = self.user_code
                
            url = f"{self.server_url.rstrip('/')}/playlist/{self.store_id}/{self.screen_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('playlist', [])
                    
        except Exception as e:
            print(f"❌ Error getting playlist: {e}")
            
        return []
        
    def play_media(self, url, media_type='video'):
        """Play media using VLC with Pi optimizations"""
        try:
            vlc_args = [
                'vlc',
                '--intf', 'dummy',  # No GUI
                '--fullscreen',     # Fullscreen
                '--loop',          # Loop playlist
                '--no-video-title-show',  # Hide title
                '--quiet'          # Reduce output
            ]
            
            # Pi-specific optimizations
            if media_type == 'video':
                vlc_args.extend([
                    '--avcodec-hw=mmal',  # Hardware acceleration
                    '--file-caching=2000'  # Buffer for network streams
                ])
                
            vlc_args.append(url)
            
            print(f"▶️ Playing: {url}")
            return subprocess.Popen(vlc_args)
            
        except Exception as e:
            print(f"❌ Error starting playback: {e}")
            return None
            
    def start_playback(self):
        """Start continuous playlist playback"""
        if not self.store_id:
            print("❌ No store selected. Use option 5 first.")
            return
            
        print("🎬 Starting playlist playback...")
        print("Press Ctrl+C to stop")
        
        vlc_process = None
        try:
            while True:
                playlist = self.get_playlist()
                if not playlist:
                    print("⚠️ No content found. Retrying in 30 seconds...")
                    time.sleep(30)
                    continue
                    
                for item in playlist:
                    if vlc_process:
                        vlc_process.terminate()
                        vlc_process = None
                        
                    url = item.get('url') or item.get('slice_url')
                    media_type = item.get('media_type', 'video')
                    duration = max(int(item.get('duration', 10)), 5)  # Minimum 5 seconds
                    
                    if url:
                        vlc_process = self.play_media(url, media_type)
                        if vlc_process:
                            # Wait for this item's duration
                            try:
                                vlc_process.wait(timeout=duration)
                            except subprocess.TimeoutExpired:
                                vlc_process.terminate()
                                
                    time.sleep(1)  # Brief pause between items
                    
        except KeyboardInterrupt:
            print("\n⏹️ Playback stopped by user")
        except Exception as e:
            print(f"❌ Playback error: {e}")
        finally:
            if vlc_process:
                vlc_process.terminate()
                
    def show_menu(self):
        """Display main menu"""
        while True:
            print("\n🍕 Pizza Hut TV - Pi Client")
            print("=" * 40)
            print("1. Test Connection & Show Content")
            print("2. Auto-Discover Network") 
            print("3. Configure Server & Settings")
            print("4. Setup Authentication")
            print("5. Select Store & Screen")
            print("6. Start Playback")
            print("7. Show Status")
            print("8. Exit")
            print("=" * 40)
            
            choice = input("Select option (1-8): ").strip()
            
            if choice == '1':
                self.test_connection()
            elif choice == '2':
                self.discover_stores()
            elif choice == '3':
                self.configure_settings()
            elif choice == '4':
                self.configure_authentication()
            elif choice == '5':
                self.list_stores()
            elif choice == '6':
                self.start_playback()
            elif choice == '7':
                self.show_status()
            elif choice == '8':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please try again.")

if __name__ == "__main__":
    print("🍕 Pizza Hut TV Client Starting...")
    
    # Check VLC installation
    try:
        subprocess.run(['vlc', '--version'], capture_output=True, check=True)
    except:
        print("⚠️ VLC not found. Install with: sudo apt install vlc")
        print("Continuing anyway - some features may not work.")
        
    client = PizzaHutTVClient()
    client.show_menu()