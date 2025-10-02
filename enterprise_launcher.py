#!/usr/bin/env python3
"""
Enterprise Launcher
-------------------
Smart supervisor that decides (per screen) whether to:
  - Use Chromium webplayer (exact browser slice logic) for multi‑screen follower slices (order > 0)
  - Use existing Python VLC client for normal / primary screens (order == 0 or no sync group)

Rationale:
Server bypasses slice generation for slice_order >= 1, returning full panorama video.
Browser already implements correct CSS viewport logic; VLC cropping proved unstable.
This launcher gives production resilience: auto-retry, health logging, clean shutdown.

Usage example:
  python3 enterprise_launcher.py --store 1000 --screen 2 --code 4682 

Environment overrides:
  PHTV_SERVER_URL   (default: https://everydayadvertise.com)
  PHTV_PLAYER_PAGE  (default: https://everydayadvertise.com/player)
  PHTV_REFRESH_SECS (default: 120)  How often to re-check playlist to see if role changed

Exit codes:
  0 normal shutdown
  21 playlist fetch persistent failure

"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    print("ERROR: requests module not installed. pip install requests")
    sys.exit(1)

DEFAULT_SERVER = os.environ.get("PHTV_SERVER_URL", "https://everydayadvertise.com")
DEFAULT_PLAYER = os.environ.get("PHTV_PLAYER_PAGE", "https://everydayadvertise.com/player")
REFRESH_SECS   = int(os.environ.get("PHTV_REFRESH_SECS", "120"))

RUNNING = True
CHILD: Optional[subprocess.Popen] = None


def log(msg: str):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}Z] {msg}", flush=True)


def fetch_playlist(server: str, store: str, screen: str, timeout=10) -> Optional[dict]:
    # Playlist endpoint pattern matches existing clients: /playlist/{store}/{store}_screen{n}
    url = f"{server}/playlist/{store}/{store}_screen{screen}"
    ua = {"User-Agent": "phtv-pi-enterprise/1.0"}
    try:
        r = requests.get(url, headers=ua, timeout=timeout)
        if r.status_code != 200:
            log(f"WARN playlist HTTP {r.status_code} for {url}")
            return None
        return r.json()
    except Exception as e:
        log(f"WARN playlist fetch error: {e}")
        return None


def detect_slice_role(pl: dict) -> Tuple[int, int, str]:
    """Return (count, order, mode) or (1,0,'split-h') if not multi-slice."""
    try:
        items = pl.get('playlist') or []
        for it in items:
            if not isinstance(it, dict):
                continue
            sref = it.get('sync_ref')
            if isinstance(sref, dict):
                cnt = int(sref.get('count') or 1)
                order = int(sref.get('order') or 0)
                mode = str(sref.get('mode') or 'split-h').lower()
                if cnt > 1:
                    return cnt, order, mode
        return 1, 0, 'split-h'
    except Exception:
        return 1, 0, 'split-h'


def build_chromium_cmd(screen: str, store: str, code: str) -> list:
    # Reuse slice_kiosk style flags
    candidates = ["chromium-browser", "chromium", "/usr/bin/chromium-browser", "/usr/bin/chromium"]
    binary = None
    for c in candidates:
        if shutil.which(c):  # type: ignore # pylint: disable=undefined-variable
            binary = shutil.which(c)  # type: ignore
            break
    if not binary:
        raise RuntimeError("Chromium not found (install chromium-browser)")
    url = f"{DEFAULT_PLAYER}?store={store}&screen={screen}&code={code}"
    flags = [
        '--noerrdialogs', '--disable-infobars', '--kiosk', '--incognito',
        '--autoplay-policy=no-user-gesture-required', '--no-first-run',
        '--disable-features=Translate,Infobars,AutomationControlled',
        '--disable-session-crashed-bubble', '--disk-cache-size=104857600', '--mute-audio',
        '--window-position=0,0', '--window-size=1920,1080'
    ]
    return [binary, *flags, url]


def build_python_player_cmd(screen: str, store: str, code: str) -> list:
    # Use existing webplayer_style_pi_client in embedded mode (no cropping modifications needed)
    return [sys.executable, 'webplayer_style_pi_client.py', '--screen', screen, '--store', store, '--code', code]


def terminate_child():
    global CHILD
    if CHILD and CHILD.poll() is None:
        try:
            CHILD.terminate()
            CHILD.wait(timeout=6)
        except Exception:
            try:
                CHILD.kill()
            except Exception:
                pass
    CHILD = None


def sig_handler(signum, frame):  # noqa: ARG001
    global RUNNING
    log(f"Signal {signum} received; shutting down")
    RUNNING = False
    terminate_child()


def supervise(loop_args):
    global CHILD, RUNNING
    store = loop_args.store
    screen = loop_args.screen
    code = loop_args.code
    server = loop_args.server
    last_role = None
    last_check = 0
    retries = 0
    while RUNNING:
        now = time.time()
        need_role_check = (now - last_check) > REFRESH_SECS or last_role is None
        if need_role_check:
            pl = fetch_playlist(server, store, screen)
            if not pl:
                retries += 1
                if retries > 10:
                    log("ERROR persistent playlist failure; exiting with code 21")
                    return 21
                time.sleep(min(15, 2 * retries))
                continue
            retries = 0
            cnt, order, mode = detect_slice_role(pl)
            role = f"slice:{order}/{cnt}:{mode}" if cnt > 1 else "single"
            if role != last_role:
                log(f"Role change => {last_role} -> {role}")
                # Restart with new mode
                terminate_child()
                try:
                    if cnt > 1 and order > 0:
                        log(f"Launching Chromium webplayer for follower slice (order {order})")
                        cmd = build_chromium_cmd(screen, store, code)
                    else:
                        log("Launching Python VLC client for primary / single screen")
                        cmd = build_python_player_cmd(screen, store, code)
                except Exception as e:
                    log(f"Launch prep error: {e}")
                    time.sleep(10)
                    continue
                try:
                    CHILD = subprocess.Popen(cmd, stdout=None, stderr=None)
                    log(f"Spawned PID={CHILD.pid} cmd={' '.join(cmd)}")
                except Exception as e:
                    log(f"Child launch failed: {e}")
                    time.sleep(10)
                    continue
                last_role = role
            last_check = now

        # Monitor child
        if CHILD and CHILD.poll() is not None:
            rc = CHILD.returncode
            log(f"Child exited rc={rc}; restarting after short delay")
            CHILD = None
            time.sleep(5)
            continue
        time.sleep(2)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Enterprise multi-screen launcher")
    parser.add_argument('--store', required=True)
    parser.add_argument('--screen', required=True, help='Screen number (e.g. 1,2,3)')
    parser.add_argument('--code', required=True, help='Pair / auth code')
    parser.add_argument('--server', default=DEFAULT_SERVER)
    args = parser.parse_args()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, sig_handler)

    log("Enterprise launcher starting")
    log(f"Store={args.store} Screen={args.screen} Server={args.server}")
    rc = supervise(args)
    terminate_child()
    log(f"Exiting rc={rc}")
    sys.exit(rc)


if __name__ == '__main__':
    main()
