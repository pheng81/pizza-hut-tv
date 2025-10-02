#!/usr/bin/env python3
"""
Pi-optimized slice kiosk with software rendering and better compatibility
"""
import subprocess
import sys
import os

def create_user_data_dir():
    """Create a temporary user data directory"""
    import tempfile
    return tempfile.mkdtemp(prefix="pizza-hut-tv-")

def launch_pi_optimized_browser(store, screen, code):
    """Launch browser with Pi-optimized settings"""
    
    user_data_dir = create_user_data_dir()
    url = f"https://everydayadvertise.com/webplayer/play?store={store}&screen={screen}&code={code}"
    
    print(f"🍕 Launching Pizza Hut TV - Screen {screen}")
    print(f"🔗 URL: {url}")
    print(f"📁 User data: {user_data_dir}")
    
    # Pi-optimized Chrome flags for better performance
    cmd = [
        "chromium-browser",
        f"--user-data-dir={user_data_dir}",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--enable-gpu-rasterization",  # Enable GPU for better performance
        "--enable-zero-copy",
        "--enable-hardware-overlays",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows", 
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--enable-features=VaapiVideoDecoder,CanvasOopRasterization",
        "--max_old_space_size=512",  # Limit memory usage
        "--memory-pressure-off",
        "--start-fullscreen",
        "--kiosk",
        "--incognito",
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run", 
        "--disable-infobars",
        "--disable-session-crashed-bubble",
        "--mute-audio",
        "--force-gpu-mem-available-mb=128",
        url
    ]
    
    print("▶️ Starting browser...")
    try:
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        print("🛑 Interrupted by user")
        process.terminate()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Cleanup
        import shutil
        try:
            shutil.rmtree(user_data_dir)
        except:
            pass

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pi-optimized Pizza Hut TV Player")
    parser.add_argument('--store', required=True, help='Store code')
    parser.add_argument('--screen', required=True, help='Screen number')
    parser.add_argument('--code', required=True, help='Pairing code')
    
    args = parser.parse_args()
    
    launch_pi_optimized_browser(args.store, args.screen, args.code)