#!/usr/bin/env python3
"""
Emergency Exit Daemon for Pizza Hut TV Pi Client
Provides multiple reliable ways to exit fullscreen VLC when trapped
"""

import time
import subprocess
import threading
import os
import signal
import json
from datetime import datetime

class EmergencyExitDaemon:
    def __init__(self):
        self.vlc_process = None
        self.exit_file = "/tmp/pizza_hut_emergency_exit"
        self.status_file = "/tmp/pizza_hut_daemon_status"
        self.running = True
        
        # Create named pipe for emergency commands
        try:
            os.mkfifo("/tmp/pizza_hut_emergency_pipe")
        except FileExistsError:
            pass
    
    def log_status(self, message):
        """Log daemon status with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = {
            "timestamp": timestamp,
            "message": message,
            "vlc_pid": self.vlc_process.pid if self.vlc_process else None
        }
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
            print(f"[{timestamp}] {message}")
        except Exception as e:
            print(f"[{timestamp}] {message} (logging error: {e})")
    
    def monitor_exit_signals(self):
        """Monitor for emergency exit signals"""
        while self.running:
            try:
                # Check for exit file
                if os.path.exists(self.exit_file):
                    self.log_status("Emergency exit file detected!")
                    self.emergency_exit()
                    os.remove(self.exit_file)
                
                # Check named pipe for commands
                try:
                    with open("/tmp/pizza_hut_emergency_pipe", 'r', timeout=0.1) as pipe:
                        command = pipe.read().strip()
                        if command == "EXIT":
                            self.log_status("Emergency exit command received via pipe!")
                            self.emergency_exit()
                        elif command == "FULLSCREEN_OFF":
                            self.log_status("Fullscreen off command received!")
                            self.exit_fullscreen()
                except:
                    pass
                
                time.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                self.log_status(f"Monitor error: {e}")
                time.sleep(1)
    
    def emergency_exit(self):
        """Forcibly terminate VLC using multiple methods"""
        self.log_status("EMERGENCY EXIT TRIGGERED!")
        
        # Method 1: Terminate our tracked process
        if self.vlc_process:
            try:
                self.vlc_process.terminate()
                self.log_status("Sent terminate to VLC process")
                time.sleep(1)
                if self.vlc_process.poll() is None:
                    self.vlc_process.kill()
                    self.log_status("Force killed VLC process")
            except:
                pass
        
        # Method 2: Kill all VLC processes system-wide
        try:
            subprocess.run(["pkill", "-9", "vlc"], check=False)
            self.log_status("Killed all VLC processes system-wide")
        except:
            pass
        
        # Method 3: Send window close signals
        try:
            # Try to close fullscreen window
            subprocess.run(["xdotool", "search", "--name", "VLC", "windowkill"], check=False)
            self.log_status("Attempted to kill VLC windows")
        except:
            pass
        
        # Method 4: Reset display if needed
        try:
            subprocess.run(["xset", "dpms", "force", "on"], check=False)
            self.log_status("Reset display power management")
        except:
            pass
    
    def exit_fullscreen(self):
        """Try to exit fullscreen without killing VLC"""
        self.log_status("Attempting to exit fullscreen...")
        
        if self.vlc_process:
            try:
                # Send Escape key to VLC
                subprocess.run(["xdotool", "search", "--name", "VLC", "key", "Escape"], check=False)
                self.log_status("Sent Escape key to VLC")
            except:
                pass
            
            try:
                # Send F11 to toggle fullscreen
                subprocess.run(["xdotool", "search", "--name", "VLC", "key", "F11"], check=False)
                self.log_status("Sent F11 to VLC")
            except:
                pass
    
    def set_vlc_process(self, process):
        """Set the VLC process to monitor"""
        self.vlc_process = process
        self.log_status(f"Now monitoring VLC process PID: {process.pid}")
    
    def start_daemon(self):
        """Start the emergency exit daemon"""
        self.log_status("Emergency Exit Daemon starting...")
        monitor_thread = threading.Thread(target=self.monitor_exit_signals, daemon=True)
        monitor_thread.start()
        return monitor_thread
    
    def stop_daemon(self):
        """Stop the daemon"""
        self.running = False
        self.log_status("Emergency Exit Daemon stopping...")

# Global daemon instance
daemon = None

def create_emergency_exit_file():
    """Create emergency exit file - can be called from anywhere"""
    with open("/tmp/pizza_hut_emergency_exit", 'w') as f:
        f.write("EMERGENCY_EXIT")

def send_emergency_command(command):
    """Send command via named pipe"""
    try:
        with open("/tmp/pizza_hut_emergency_pipe", 'w') as pipe:
            pipe.write(command)
        return True
    except:
        return False

if __name__ == "__main__":
    # Test mode - run daemon standalone
    daemon = EmergencyExitDaemon()
    print("Emergency Exit Daemon - Test Mode")
    print("Create file /tmp/pizza_hut_emergency_exit to trigger emergency exit")
    print("Or run: echo 'EXIT' > /tmp/pizza_hut_emergency_pipe")
    print("Press Ctrl+C to stop")
    
    daemon.start_daemon()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop_daemon()
        print("Daemon stopped")