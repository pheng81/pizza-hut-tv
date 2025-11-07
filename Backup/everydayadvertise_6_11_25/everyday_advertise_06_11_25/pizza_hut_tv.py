#!/usr/bin/env python3
"""
Simple Pizza Hut TV Player - ONE file for all screens
Usage: python3 pizza_hut_tv.py --screen 2
"""
import subprocess
import sys
import argparse
import tempfile
import shutil

def main():
    parser = argparse.ArgumentParser(description="Pizza Hut TV Player")
    parser.add_argument('--screen', type=int, default=2, help='Screen number (1, 2, or 3)')
    parser.add_argument('--store', default='1000', help='Store code')
    parser.add_argument('--code', default='4682', help='Pairing code')
    args = parser.parse_args()
    
    print(f"🍕 Pizza Hut TV - Screen {args.screen}")
    print(f"🏪 Store: {args.store} | 🔑 Code: {args.code}")
    
    # Create temp directory for browser data
    temp_dir = tempfile.mkdtemp(prefix="pizza-hut-tv-")
    
    # Build URL with correct parameter names
    url = f"https://everydayadvertise.com/webplayer/play?store_id={args.store}&screen_id={args.screen}&code={args.code}"
    print(f"🔗 URL: {url}")
    
    # Simple browser command - less GPU intensive
    cmd = [
        "chromium-browser",
        f"--user-data-dir={temp_dir}",
        "--no-sandbox",
        "--disable-gpu",  # Force software rendering to avoid GPU issues
        "--disable-dev-shm-usage",
        "--start-fullscreen",
        "--incognito", 
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run",
        "--disable-infobars",
        "--mute-audio",
        url
    ]
    
    print("▶️ Starting browser...")
    print("💡 Press F11 to toggle fullscreen, Alt+F4 to exit")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("🛑 Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

if __name__ == "__main__":
    main()