#!/usr/bin/env python3
"""
🍕 Pizza Hut TV - Pi Configuration Tool
======================================
Interactive configuration tool for Pi clients
"""

import json
import os
import sys
import subprocess
import requests
from pathlib import Path
import socket
import time

class PiConfigurator:
    def __init__(self):
        self.config_file = "/home/pi/pizza-hut-tv/config.json"
        self.config = self.load_config()
        
    def load_config(self):
        """Load existing configuration or create default."""
        default_config = {
            "server_url": "https://everydayadvertise.com",
            "store_id": "PHTV001",
            "screen_id": "tv1",
            "fullscreen": True,
            "auto_start": True,
            "sync_enabled": True,
            "performance_monitoring": True,
            "debug_mode": False,
            "video_backend": "auto",  # auto, omxplayer, vlc, pygame
            "network_timeout": 10,
            "playlist_refresh_interval": 5,
            "sync_tolerance": 0.05
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                # Merge with defaults for new keys
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
        
        return default_config
    
    def save_config(self):
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print("✅ Configuration saved")
            return True
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False
    
    def test_server_connection(self, server_url=None):
        """Test connection to server."""
        if not server_url:
            server_url = self.config["server_url"]
        
        print(f"🌐 Testing connection to {server_url}...")
        
        try:
            # Test basic connectivity
            response = requests.get(f"{server_url}/api/health", timeout=10)
            if response.status_code == 200:
                print("✅ Server connection successful")
                
                # Test playlist API
                store_id = self.config["store_id"]
                screen_id = self.config["screen_id"]
                playlist_url = f"{server_url}/api/playlist/{store_id}/{screen_id}"
                
                playlist_response = requests.get(playlist_url, timeout=10)
                if playlist_response.status_code == 200:
                    data = playlist_response.json()
                    if data.get('success'):
                        playlist_count = len(data.get('playlist', []))
                        print(f"✅ Playlist API working ({playlist_count} items)")
                        return True
                    else:
                        print(f"⚠️ Playlist API error: {data.get('error', 'Unknown')}")
                else:
                    print(f"⚠️ Playlist API returned {playlist_response.status_code}")
            else:
                print(f"❌ Server returned {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("❌ Connection timeout")
        except requests.exceptions.ConnectionError:
            print("❌ Connection failed")
        except Exception as e:
            print(f"❌ Connection error: {e}")
        
        return False
    
    def detect_network_settings(self):
        """Auto-detect network settings."""
        print("🔍 Detecting network settings...")
        
        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            print(f"📍 Local IP: {local_ip}")
        except:
            local_ip = "Unknown"
        
        # Scan for local servers
        local_servers = []
        base_ip = ".".join(local_ip.split(".")[:-1]) + "."
        common_ports = [5000, 5001, 5002, 8000, 8080, 3000]
        
        print("🔍 Scanning for local servers...")
        for i in [1, 115, 100, 200]:  # Common server IPs
            for port in common_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((f"{base_ip}{i}", port))
                    if result == 0:
                        server_url = f"http://{base_ip}{i}:{port}"
                        local_servers.append(server_url)
                        print(f"   Found: {server_url}")
                    sock.close()
                except:
                    pass
        
        return local_servers
    
    def interactive_setup(self):
        """Interactive configuration setup."""
        print("🍕 Pizza Hut TV - Pi Configuration Setup")
        print("=" * 40)
        
        # Server URL
        print(f"\n1. Server Configuration")
        print(f"   Current: {self.config['server_url']}")
        
        # Auto-detect local servers
        local_servers = self.detect_network_settings()
        if local_servers:
            print("   Detected local servers:")
            for i, server in enumerate(local_servers, 1):
                print(f"     {i}. {server}")
            print(f"     {len(local_servers)+1}. Keep current")
            print(f"     {len(local_servers)+2}. Enter manually")
            
            choice = input(f"   Choose option (1-{len(local_servers)+2}): ").strip()
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(local_servers):
                    self.config['server_url'] = local_servers[choice_num - 1]
                elif choice_num == len(local_servers) + 2:
                    new_url = input("   Enter server URL: ").strip()
                    if new_url:
                        self.config['server_url'] = new_url
            except ValueError:
                pass
        else:
            new_url = input("   Enter new server URL (or press Enter to keep current): ").strip()
            if new_url:
                self.config['server_url'] = new_url
        
        # Test connection
        if self.test_server_connection():
            print("✅ Server connection verified")
        else:
            print("⚠️ Server connection failed - please check settings")
        
        # Store and Screen ID
        print(f"\n2. Store Configuration")
        print(f"   Current Store ID: {self.config['store_id']}")
        new_store = input("   Enter new Store ID (or press Enter to keep current): ").strip()
        if new_store:
            self.config['store_id'] = new_store
        
        print(f"   Current Screen ID: {self.config['screen_id']}")
        new_screen = input("   Enter new Screen ID (or press Enter to keep current): ").strip()
        if new_screen:
            self.config['screen_id'] = new_screen
        
        # Video Backend
        print(f"\n3. Video Backend")
        print(f"   Current: {self.config['video_backend']}")
        print("   Options: auto, omxplayer, vlc, pygame")
        new_backend = input("   Choose backend (or press Enter to keep current): ").strip()
        if new_backend in ['auto', 'omxplayer', 'vlc', 'pygame']:
            self.config['video_backend'] = new_backend
        
        # Other settings
        print(f"\n4. Other Settings")
        
        debug = input(f"   Enable debug mode? (y/N): ").strip().lower()
        self.config['debug_mode'] = debug == 'y'
        
        monitoring = input(f"   Enable performance monitoring? (Y/n): ").strip().lower()
        self.config['performance_monitoring'] = monitoring != 'n'
        
        # Save configuration
        print(f"\n5. Save Configuration")
        if self.save_config():
            print("✅ Configuration saved successfully")
            print(f"📁 Config file: {self.config_file}")
        else:
            print("❌ Failed to save configuration")
    
    def show_current_config(self):
        """Display current configuration."""
        print("🍕 Current Configuration")
        print("=" * 25)
        
        for key, value in self.config.items():
            if key == "server_url":
                # Test server connection
                status = "✅" if self.test_server_connection(value) else "❌"
                print(f"   {key:25}: {value} {status}")
            else:
                print(f"   {key:25}: {value}")
    
    def system_info(self):
        """Display system information."""
        print("🍓 Raspberry Pi System Information")
        print("=" * 35)
        
        # Pi model
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'Model' in line:
                        model = line.split(':')[1].strip()
                        print(f"   Model: {model}")
                        break
        except:
            print("   Model: Unknown")
        
        # GPU memory
        try:
            result = subprocess.run(['vcgencmd', 'get_mem', 'gpu'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                gpu_mem = result.stdout.strip().split('=')[1]
                print(f"   GPU Memory: {gpu_mem}")
        except:
            print("   GPU Memory: Unknown")
        
        # Temperature
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                temp = result.stdout.strip().split('=')[1]
                print(f"   Temperature: {temp}")
        except:
            print("   Temperature: Unknown")
        
        # Available video backends
        print("   Video Backends:")
        
        # Check OMXPlayer
        try:
            subprocess.run(['omxplayer', '--version'], 
                         capture_output=True, timeout=5)
            print("     OMXPlayer: ✅ Available")
        except:
            print("     OMXPlayer: ❌ Not available")
        
        # Check VLC
        try:
            import vlc
            print("     VLC: ✅ Available")
        except ImportError:
            print("     VLC: ❌ Not available")
        
        # Check pygame
        try:
            import pygame
            print("     Pygame: ✅ Available")
        except ImportError:
            print("     Pygame: ❌ Not available")
    
    def service_control(self):
        """Control Pi TV service."""
        service_name = "phtv-client"
        
        print("🔧 Service Control")
        print("=" * 16)
        print("1. Start service")
        print("2. Stop service")
        print("3. Restart service")
        print("4. Service status")
        print("5. View logs")
        print("6. Back to main menu")
        
        choice = input("Choose option (1-6): ").strip()
        
        try:
            if choice == '1':
                subprocess.run(['sudo', 'systemctl', 'start', service_name])
                print("✅ Service started")
            elif choice == '2':
                subprocess.run(['sudo', 'systemctl', 'stop', service_name])
                print("✅ Service stopped")
            elif choice == '3':
                subprocess.run(['sudo', 'systemctl', 'restart', service_name])
                print("✅ Service restarted")
            elif choice == '4':
                subprocess.run(['sudo', 'systemctl', 'status', service_name, '--no-pager'])
            elif choice == '5':
                subprocess.run(['journalctl', '-u', service_name, '-n', '50', '--no-pager'])
            elif choice == '6':
                return
        except Exception as e:
            print(f"❌ Error: {e}")
        
        input("\nPress Enter to continue...")
    
    def main_menu(self):
        """Main menu."""
        while True:
            print("\n🍕 Pizza Hut TV - Pi Configuration Tool")
            print("=" * 40)
            print("1. Interactive Setup")
            print("2. Show Current Configuration")
            print("3. Test Server Connection")
            print("4. System Information")
            print("5. Service Control")
            print("6. Exit")
            
            choice = input("\nChoose option (1-6): ").strip()
            
            if choice == '1':
                self.interactive_setup()
            elif choice == '2':
                self.show_current_config()
            elif choice == '3':
                self.test_server_connection()
            elif choice == '4':
                self.system_info()
            elif choice == '5':
                self.service_control()
            elif choice == '6':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid option")
            
            if choice != '6':
                input("\nPress Enter to continue...")

def main():
    """Main entry point."""
    if os.geteuid() != 0:
        print("⚠️ Note: Some features require sudo privileges")
    
    configurator = PiConfigurator()
    configurator.main_menu()

if __name__ == '__main__':
    main()