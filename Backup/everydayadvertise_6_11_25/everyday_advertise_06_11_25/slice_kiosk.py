#!/usr/bin/env python3
"""
Slice Kiosk Player (Chromium-based) for secondary screens (screen2, screen3, ...)

This mimics the webplayer's slice logic exactly by letting the existing
player.html handle CSS transform / pixel fallback. No VLC cropping.

Usage:
  python3 slice_kiosk.py --screen 2 --store 1000 --code 4682

Recommended to run via systemd for resiliency.

Features:
- Auto-detects chromium binary name (chromium-browser / chromium)
- Auto-restars on crash (internal loop + suggest systemd Restart=on-failure)
- Health check: (optional future) can probe window via ps list
- Clean shutdown on SIGTERM

"""
import argparse
import os
import signal
import sys
import time
import shutil
import subprocess
import threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# -------- Configuration Defaults --------
DEFAULT_BASE_URL = "https://everydayadvertise.com/webplayer/play"  # Correct player route
CHROMIUM_CANDIDATES = [
    "chromium-browser",
    "chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
]
# Flag groups
BASE_FLAGS = [
    "--noerrdialogs",
    "--disable-infobars",
    "--incognito",
    "--autoplay-policy=no-user-gesture-required",
    "--no-first-run",
    "--disable-features=Translate,Infobars",
    "--disable-session-crashed-bubble",
    "--disk-cache-size=134217728",  # 128MB cache
    "--mute-audio",
    "--disable-web-security",
    "--allow-running-insecure-content",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--force-color-profile=srgb",
]

# Safe (software) mode – stable but slower decoding
SAFE_EXTRA_FLAGS = [
    "--disable-gpu",
    "--disable-gpu-compositing",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-features=BackForwardCache,MediaHistory"
]

# Performance (hardware attempt) mode – may require proper firmware + gpu_mem + mesa/va-api packages
PERF_EXTRA_FLAGS = [
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--ignore-gpu-blocklist",
    "--enable-features=VaapiVideoDecoder,CanvasOopRasterization",
    "--use-gl=egl",
    "--use-angle=gles",
    "--no-sandbox",
    # Larger shared memory segment usage still; keep dev shm disabled only if low RAM issues
]

def assemble_flags(performance: bool) -> list:
    if performance:
        return BASE_FLAGS + PERF_EXTRA_FLAGS
    return BASE_FLAGS + SAFE_EXTRA_FLAGS

EXIT_OK = (0, 10)  # Treat code 10 (some chromium closures) as soft exit

_running = True
_child_proc = None


def log(msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)


def find_chromium() -> str:
    for c in CHROMIUM_CANDIDATES:
        if shutil.which(c):
            return shutil.which(c)
    log("❌ Chromium not found. Please install with: sudo apt install -y chromium-browser")
    sys.exit(1)


def derive_screen_id(store: str, screen_arg: str) -> str:
    """Return the proper screen_id value expected by the server.

    Rules:
    - If user already passed a full identifier containing an underscore (e.g. 1000_screen1), use it verbatim.
    - If it already starts with the store id + '_' use verbatim.
    - If it's just a number (e.g. '1', '2'), map to f"{store}_screen{N}".
    - Otherwise (custom string), return as-is.
    """
    s = str(screen_arg).strip()
    if s.startswith(f"{store}_"):
        return s
    if '_' in s:  # assume caller provided full pattern
        return s
    if s.isdigit():
        return f"{store}_screen{s}"
    return s


def build_url(base: str, store: str, screen_id: str, code: str) -> str:
    """Assemble the canonical webplayer URL.

    NOTE: The server expects store_id, screen_id, code.
    This function does not URL-encode since values are safe (alnum + underscore).
    """
    return f"{base}?store_id={store}&screen_id={screen_id}&code={code}"


def parse_play_url(play_url: str) -> dict:
    """Parse a full /webplayer/play? ... style URL and extract parameters.

    Returns dict with keys (store_id, screen_id, code). Missing keys = None.
    Useful for dynamic scenario where user pastes full link instead of separate args.
    """
    try:
        parts = urlparse(play_url)
        qs = parse_qs(parts.query)
        return {
            'store_id': qs.get('store_id', [None])[0],
            'screen_id': qs.get('screen_id', [None])[0],
            'code': qs.get('code', [None])[0],
        }
    except Exception:
        return {'store_id': None, 'screen_id': None, 'code': None}


def make_command(binary: str, url: str, *, kiosk: bool, demo_extra: str | None, resolution: tuple[int, int], performance: bool) -> list:
    cmd = [binary]
    cmd.extend(assemble_flags(performance))
    if kiosk:
        cmd.append("--kiosk")
    else:
        cmd.append("--start-fullscreen")
    # Position / size only when not pure kiosk (some window managers need this anyway)
    w, h = resolution
    cmd.append(f"--window-position=0,0")
    cmd.append(f"--window-size={w},{h}")
    # User data dir isolated per screen id for clean state
    # Derive temp directory name from screen id embedded in URL to prevent profile lock clashes
    screen_token = 'screen'
    if 'screen_id=' in url:
        screen_token = url.split('screen_id=')[1].split('&')[0]
    cmd.append(f"--user-data-dir=/tmp/pizza-hut-tv-{screen_token}")
    cmd.append(url)
    if demo_extra:
        # Open a new tab with test media so user sees *something* if schedule empty
        cmd.append(demo_extra)
    return cmd


def terminate_child():
    global _child_proc
    if _child_proc and _child_proc.poll() is None:
        try:
            log("🔻 Sending SIGTERM to chromium child")
            _child_proc.terminate()
            try:
                _child_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log("⏱️ Child unresponsive; killing")
                _child_proc.kill()
        except Exception as e:
            # Ensure we don't introduce newline-related syntax issues
            log(f"⚠️ Error terminating child: {e}")


def handle_signal(signum, frame):
    global _running
    log(f"🛑 Received signal {signum}; shutting down")
    _running = False
    terminate_child()


def main():
    parser = argparse.ArgumentParser(description="Chromium slice kiosk player")
    # Two primary input modes:
    #  A) Separate arguments: --store 1000 --screen 2 --code 4682
    #  B) Direct: --play-url 'https://everydayadvertise.com/webplayer/play?store_id=1000&screen_id=1000_screen2&code=4682'
    parser.add_argument("--play-url", dest="play_url", help="Full webplayer play URL (overrides --store/--screen/--screen-id/--code if provided)")
    parser.add_argument("--screen", help="Screen short value (e.g. 1,2,3) OR already formatted like 1000_screen1")
    parser.add_argument("--screen-id", dest="screen_id", help="Explicit full screen_id (e.g. 1000_screen1). Overrides --screen if provided.")
    parser.add_argument("--store", help="Store code / id")
    parser.add_argument("--code", help="Android TV code / pairing code")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for player page")
    parser.add_argument("--restart-delay", type=int, default=5, help="Seconds to wait before restarting on crash")
    parser.add_argument("--max-restarts", type=int, default=0, help="Optional cap on restart attempts (0 = unlimited)")
    parser.add_argument("--kiosk", action="store_true", help="Force Chromium kiosk mode (default on if neither --kiosk nor --no-kiosk given)")
    parser.add_argument("--no-kiosk", action="store_true", help="Explicitly disable kiosk; will use start-fullscreen instead")
    parser.add_argument("--force-f11", action="store_true", help="After launch attempt to send F11 with xdotool (extra fullscreen enforcement)")
    parser.add_argument("--resolution", default="1920x1080", help="Display resolution WxH (default 1920x1080)")
    parser.add_argument("--demo-fallback", action="store_true", help="Open a second tab with a demo video to verify playback when schedule empty")
    parser.add_argument("--perf", action="store_true", help="Enable performance mode (attempt hardware decode & GPU acceleration)")
    parser.add_argument("--print-only", action="store_true", help="Resolve and print the final URL / params then exit (diagnostic)")
    args = parser.parse_args()

    # Input validation / resolution logic
    if args.play_url:
        parsed = parse_play_url(args.play_url)
        # If user gave play_url but some params missing, allow explicit overrides
        if parsed['store_id'] is None and args.store:
            parsed['store_id'] = args.store
        if parsed['screen_id'] is None and (args.screen_id or args.screen):
            parsed['screen_id'] = args.screen_id or (derive_screen_id(args.store, args.screen) if args.store and args.screen else None)
        if parsed['code'] is None and args.code:
            parsed['code'] = args.code
        # Now assign back for uniform downstream usage
        args.store = parsed['store_id']
        args.screen_id = parsed['screen_id']
        args.code = parsed['code']
        # Derive --screen numeric if possible from screen_id pattern
        if args.screen_id and '_' in args.screen_id:
            tail = args.screen_id.rsplit('_', 1)[-1]
            if tail.startswith('screen'):
                maybe_num = tail.replace('screen', '')
                if maybe_num.isdigit():
                    args.screen = maybe_num
    else:
        # Must have separate required args
        missing = []
        if not args.store:
            missing.append('--store')
        if not (args.screen or args.screen_id):
            missing.append('--screen/--screen-id')
        if not args.code:
            missing.append('--code')
        if missing:
            parser.error("Missing required arguments: " + ', '.join(missing) + " (or provide --play-url)")

    if not os.environ.get("DISPLAY"):
        # Fallback to :0
        os.environ["DISPLAY"] = ":0"
        log("ℹ️ DISPLAY not set; defaulting to :0")

    # Signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    chromium_bin = find_chromium()

    # Decide effective kiosk flag: default to kiosk unless user explicitly used --no-kiosk
    effective_kiosk = True
    if args.no_kiosk:
        effective_kiosk = False
    elif args.kiosk:
        effective_kiosk = True

    # Determine final screen_id / URL
    if args.play_url:
        # Trust provided play URL (still log resolution)
        final_screen_id = args.screen_id or '(unknown)'
        url = args.play_url
        # Normalize if user passed short numeric screen but full screen_id missing
        if (not args.screen_id) and args.store and args.screen:
            final_screen_id = derive_screen_id(args.store, args.screen)
            # Rebuild canonical URL for safety (server should treat both same)
            url = build_url(args.base_url, args.store, final_screen_id, args.code)
    else:
        final_screen_id = args.screen_id if args.screen_id else derive_screen_id(args.store, args.screen)
        url = build_url(args.base_url, args.store, final_screen_id, args.code)
    try:
        res_parts = args.resolution.lower().split('x')
        res_w, res_h = int(res_parts[0]), int(res_parts[1])
    except Exception:
        log(f"⚠️ Bad --resolution value '{args.resolution}', falling back to 1920x1080")
        res_w, res_h = 1920, 1080

    demo_url = None
    if args.demo_fallback:
        demo_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

    if args.print_only:
        log("🔎 Diagnostic Mode (--print-only)")
        log(f"Store: {args.store}")
        log(f"Screen input: {args.screen}")
        log(f"Resolved screen_id: {final_screen_id}")
        log(f"Code: {args.code}")
        log(f"Final URL: {url}")
        log("Exiting early due to diagnostic mode.")
        return

    log("🚀 Starting Chromium Slice Kiosk")
    log(f"🖥️ Screen input: {args.screen}")
    log(f"🪪 Resolved screen_id: {final_screen_id}")
    log(f"🖼️ Resolution: {res_w}x{res_h}")
    log(f"🛠️ Mode: {'kiosk' if effective_kiosk else 'fullscreen'} | Demo tab: {'on' if demo_url else 'off'} | Force F11: {'yes' if args.force_f11 else 'no'} | Performance: {'on' if args.perf else 'off'}")
    log(f"🏪 Store: {args.store}")
    log(f"🔗 URL: {url}")

    restarts = 0
    global _running, _child_proc

    while _running:
        cmd = make_command(
            chromium_bin,
            url,
            kiosk=effective_kiosk,
            demo_extra=demo_url,
            resolution=(res_w, res_h),
            performance=args.perf
        )
        log(f"▶️ Launching: {' '.join(cmd)}")
        try:
            _child_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Optional post-launch fullscreen enforcement thread
            if args.force_f11:
                def enforce_fullscreen():
                    try:
                        time.sleep(6)  # allow window to appear
                        # Try xdotool (install if missing: sudo apt install -y xdotool)
                        for attempt in range(3):
                            rc = subprocess.call([
                                'xdotool','search','--onlyvisible','--class','chromium','windowactivate','--sync','key','F11'
                            ])
                            if rc == 0:
                                log(f"🟢 F11 fullscreen enforcement success (attempt {attempt+1})")
                                break
                            time.sleep(2)
                        else:
                            log("⚠️ Could not enforce F11 fullscreen (xdotool missing or window not found)")
                    except Exception as e:
                        log(f"⚠️ F11 enforcement error: {e}")
                threading.Thread(target=enforce_fullscreen, daemon=True).start()
            rc = _child_proc.wait()
            log(f"💥 Chromium exited with code {rc}")
            if rc in EXIT_OK:
                log("✅ Exit considered clean; stopping loop")
                break
        except Exception as e:
            log(f"❌ Failed to launch chromium: {e}")
        finally:
            _child_proc = None

        if not _running:
            break

        restarts += 1
        if args.max_restarts and restarts > args.max_restarts:
            log("🚫 Max restarts reached. Exiting kiosk supervisor.")
            break

        log(f"⏳ Restarting in {args.restart_delay}s (attempt {restarts})")
        for _ in range(args.restart_delay):
            if not _running:
                break
            time.sleep(1)

    log("👋 Kiosk supervisor exiting cleanly")

if __name__ == "__main__":
    main()
