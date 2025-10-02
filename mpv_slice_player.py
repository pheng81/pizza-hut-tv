#!/usr/bin/env python3
"""
mpv_slice_player.py
====================

Lightweight panorama slice player using mpv for Raspberry Pi.

Why mpv?
  - Lower overhead than running a full browser.
  - Mature hardware decoding paths ( --hwdec=auto-safe / v4l2-request / vaapi ).
  - Accurate timing & smooth playback with --video-sync=display / --interpolation.
  - Simple cropping filter for multi-screen panorama splitting.

Usage examples:
  1) Simple single file test (middle screen of 3 wide screens, 5760x1080 total):
     python3 mpv_slice_player.py \
        --url https://example.com/panorama.mp4 \
        --slice-index 2 --slice-count 3 --height 1080 --total-width 5760

  2) With store/screen identifiers & restart supervision:
     python3 mpv_slice_player.py --store-id 1000 --screen-id 1000_screen2 \
        --url https://cdn.example.com/panorama.mp4 --slice-index 2 --slice-count 3 --loop

  3) Provide multiple URLs (playlist):
     python3 mpv_slice_player.py --url file1.mp4 --url file2.mp4 --slice-index 1 --slice-count 3

Notes:
  - Scheduling/playlist fetch from server is NOT implemented here; this script
    focuses on smooth decode + cropping. You can wrap with a higher-level
    controller that regenerates a temporary playlist file & signals reload.
  - For true sync across devices, an external clock coordination layer is needed.
  - Uses a supervision loop to auto-restart mpv if it crashes.
  - For best performance ensure GPU memory >= 128MB and KMS/DRM enabled.

Exit codes:
  0 Normal exit requested (e.g., signal)
  2 Bad arguments
  5 Failed to launch mpv repeatedly
"""
import argparse
import os
import signal
import sys
import time
import shutil
import subprocess
from datetime import datetime
from typing import List


def log(*msg):
    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), *msg, flush=True)


def compute_crop(slice_index: int, slice_count: int, total_width: int, height: int):
    if slice_count <= 0:
        raise ValueError("slice-count must be > 0")
    if slice_index < 1 or slice_index > slice_count:
        raise ValueError("slice-index out of range")
    per_w = total_width // slice_count
    x = per_w * (slice_index - 1)
    return per_w, height, x, 0  # width, height, x, y


def build_mpv_command(urls: List[str], width: int, height: int, x: int, y: int, args) -> List[str]:
    crop_filter = f"crop={width}:{height}:{x}:{y}"
    cmd = [args.mpv_bin]

    # Window / fullscreen behavior
    if args.fullscreen:
        cmd.append('--fullscreen')
    else:
        cmd.extend(['--geometry', f"{width}x{height}+0+0"])
        cmd.append('--autofit-larger=100%x100%')

    # Performance & smoothness flags
    cmd.extend([
        '--no-osc',
        '--no-input-default-bindings',
        '--force-window=yes',
        '--keep-open=no',
        '--really-quiet' if args.quiet else '--msg-level=all=v',
        '--loop-playlist=yes' if args.loop else '--loop-playlist=no',
        '--hwdec=auto-safe' if args.hwdec == 'auto' else f'--hwdec={args.hwdec}',
        '--video-sync=display-resample',
        '--interpolation' if args.interp else '--no-interpolation',
        '--cache=yes',
        '--cache-secs=20',
        '--demuxer-max-bytes=200M',
        '--demuxer-max-back-bytes=50M',
        '--keep-open=no',
        '--title', f"{args.screen_id or 'screen'} | slice {args.slice_index}/{args.slice_count}",
        '--vf', crop_filter,
    ])

    if args.scale:
        cmd.extend(['--scale', args.scale])
    if args.profile:
        cmd.extend(['--profile', args.profile])
    if args.extra:
        cmd.extend(args.extra)

    cmd.extend(urls)
    return cmd


def parse_args():
    p = argparse.ArgumentParser(description='mpv panorama slice player')
    p.add_argument('--store-id')
    p.add_argument('--screen-id')
    p.add_argument('--slice-index', type=int, required=True, help='1-based slice number for this screen')
    p.add_argument('--slice-count', type=int, required=True, help='Total number of horizontal slices')
    p.add_argument('--total-width', type=int, default=5760, help='Full panorama width')
    p.add_argument('--height', type=int, default=1080, help='Full panorama height')
    p.add_argument('--url', action='append', help='Video URL / file (repeat for playlist)')
    p.add_argument('--playlist-file', help='Plain text file with one URL per line')
    p.add_argument('--fullscreen', action='store_true', help='Launch fullscreen')
    p.add_argument('--loop', action='store_true', help='Loop playlist forever')
    p.add_argument('--hwdec', default='auto', help='mpv hwdec mode (auto, auto-safe, drm, vaapi, v4l2-request, no)')
    p.add_argument('--interp', action='store_true', help='Enable frame interpolation (higher CPU)')
    p.add_argument('--scale', help='scaler (e.g. lanczos, spline36, nearest)')
    p.add_argument('--profile', help='mpv profile')
    p.add_argument('--extra', nargs='*', help='Extra raw mpv arguments appended as-is')
    p.add_argument('--restart-delay', type=int, default=5, help='Seconds before restart if crash')
    p.add_argument('--max-restarts', type=int, default=0, help='Max restarts (0=unlimited)')
    p.add_argument('--quiet', action='store_true', help='Reduce console noise')
    p.add_argument('--mpv-bin', default='mpv', help='Path to mpv binary')
    return p.parse_args()


def collect_urls(args) -> List[str]:
    urls = []
    if args.url:
        urls.extend(args.url)
    if args.playlist_file and os.path.isfile(args.playlist_file):
        with open(args.playlist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
    return urls


def main():
    args = parse_args()
    urls = collect_urls(args)
    if not urls:
        log('❌ No media URLs provided. Use --url or --playlist-file.')
        return 2
    try:
        width, height, x, y = compute_crop(args.slice_index, args.slice_count, args.total_width, args.height)
    except Exception as e:
        log('❌ Crop error:', e)
        return 2

    if not shutil.which(args.mpv_bin):
        log(f"❌ mpv not found. Install with: sudo apt install -y mpv")
        return 2

    stop_flag = {'stop': False}

    def handle_sig(signum, frame):
        log(f"🛑 Signal {signum} received; stopping after current mpv exits.")
        stop_flag['stop'] = True

    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, handle_sig)

    restarts = 0
    while not stop_flag['stop']:
        cmd = build_mpv_command(urls, width, height, x, y, args)
        log('▶️ Launching mpv:', ' '.join(cmd))
        try:
            proc = subprocess.Popen(cmd)
            rc = proc.wait()
            log(f"💥 mpv exited with code {rc}")
        except Exception as e:
            log('❌ Failed to start mpv:', e)
            rc = -1

        if stop_flag['stop']:
            break
        if rc == 0 and not args.loop:
            log('✅ Normal exit (no loop); stopping.')
            break

        restarts += 1
        if args.max_restarts and restarts > args.max_restarts:
            log('🚫 Max restarts reached; giving up.')
            return 5
        log(f"⏳ Restarting in {args.restart_delay}s (attempt {restarts})")
        for _ in range(args.restart_delay):
            if stop_flag['stop']:
                break
            time.sleep(1)

    log('👋 Exiting mpv slice player.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
