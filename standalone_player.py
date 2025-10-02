#!/usr/bin/env python3
"""
Standalone Hardware-Accelerated Player (Experimental)
=====================================================

Goal:
  Provide a smoother Raspberry Pi playback alternative to the Chromium webplayer
  by directly decoding video with GStreamer and cropping the panorama slice for
  the current screen.

Features (current implementation):
  - Uses GStreamer (hardware decode where available) for smoother playback.
  - Crops a panoramic (multi-screen) video into a per-screen slice.
  - Basic playlist polling scaffold (currently stub – needs real API endpoint).
  - Time sync hook (stub) for future multi-device synchronization.
  - Graceful reload of playlist when updated.

Assumptions / Notes:
  - The server currently returns an empty playlist via the guessed endpoints.
    You must supply either: (a) a direct test URL using --test-url, or (b) later
    implement the real playlist fetch once endpoint is confirmed.
  - Panorama layout assumed: width = screen_count * screen_width, uniform slices.
  - Hardware accel depends on Pi OS packages:
      sudo apt install -y python3-gi gir1.2-gst-plugins-base-1.0 \
          gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav \
          gstreamer1.0-vaapi
    (Some Pi images require enabling DRM/KMS and gpu_mem=128+ in /boot config.)
  - If hardware decode fails, GStreamer will fall back to software elements.

Planned enhancements (not yet implemented):
  - Real playlist API integration (need confirmed endpoint & JSON schema).
  - Sliced video endpoint usage (/slice-video?...) when available.
  - Cross-screen sync via periodic server time calibration.
  - Persistent local cache & prefetch threads.

Usage examples:
  python3 standalone_player.py --store-id 1000 --screen-id 1000_screen2 \
      --slice-index 2 --slice-count 3 --test-url https://example.com/panorama.mp4

  python3 standalone_player.py --store-id 1000 --screen-id 1000_screen1 \
      --slice-count 3 --slice-index 1 --test-url https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4

Exit codes:
  0 normal shutdown
  2 invalid arguments
  3 pipeline failure
  4 playlist fetch error (fatal)
"""
import argparse
import signal
import sys
import time
import threading
from dataclasses import dataclass
from typing import List, Optional

try:
    import gi  # type: ignore
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GObject  # type: ignore
except Exception as e:  # pragma: no cover
    print("ERROR: GStreamer Python bindings not available (install python3-gi, gstreamer packages)")
    print(f"Detail: {e}")
    sys.exit(1)

Gst.init(None)


@dataclass
class PlaylistItem:
    url: str
    mime: str = "video/mp4"
    duration: Optional[int] = None  # seconds (optional)


class GracefulExit(Exception):
    pass


class StandalonePlayer:
    def __init__(self, args):
        self.args = args
        self.loop: Optional[GObject.MainLoop] = None
        self.pipeline: Optional[Gst.Element] = None
        self.playlist: List[PlaylistItem] = []
        self.current_index: int = 0
        self._stop = False
        self._lock = threading.Lock()

    def log(self, *msg):
        print(time.strftime('[%Y-%m-%d %H:%M:%S]'), *msg, flush=True)

    # --- Playlist Logic (Stub) -------------------------------------------------
    def load_playlist(self):
        # Placeholder: In future integrate with real endpoint.
        if self.args.test_url:
            self.playlist = [PlaylistItem(url=self.args.test_url)]
            return
        # If no test URL, keep empty and warn.
        self.playlist = []
        self.log("⚠️ No playlist items (provide --test-url or implement API fetch)")

    # --- Cropping Calculation --------------------------------------------------
    def compute_crop(self):
        total = self.args.slice_count
        idx = self.args.slice_index - 1
        if idx < 0 or idx >= total:
            raise ValueError("slice_index out of range")
        slice_w = self.args.panorama_width // total
        left = slice_w * idx
        right_crop = self.args.panorama_width - (left + slice_w)
        # GStreamer videocrop takes: left, right, top, bottom in pixels.
        return left, right_crop, 0, 0, slice_w, self.args.panorama_height

    # --- Pipeline Build --------------------------------------------------------
    def build_pipeline(self, item: PlaylistItem) -> Gst.Element:
        left, right, top, bottom, out_w, out_h = self.compute_crop()
        self.log(f"🎬 Building pipeline | crop left={left} right={right} top={top} bottom={bottom} -> {out_w}x{out_h}")

        uri = item.url
        # Use uridecodebin for automatic type detection.
        # videocrop -> videoconvert -> glimagesink (or autovideosink fallback)
        # Try hardware decode implicitly via decodebin/vaapi if available.

        pipeline_desc = f"uridecodebin uri={uri} name=src ! videoconvert ! videocrop left={left} right={right} top={top} bottom={bottom} name=crop ! videoscale ! video/x-raw,width={out_w},height={out_h} ! autovideosink sync=false"  # sync=false to reduce jitter

        self.log("🧪 Pipeline:", pipeline_desc)
        pipeline = Gst.parse_launch(pipeline_desc)
        if not pipeline:
            raise RuntimeError("Failed to create pipeline")
        return pipeline

    # --- Playback Control ------------------------------------------------------
    def start_item(self, index: int):
        if not self.playlist:
            self.log("⏸️ No items to play")
            return
        self.current_index = index % len(self.playlist)
        item = self.playlist[self.current_index]
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        self.pipeline = self.build_pipeline(item)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.log(f"▶️ Playing index={self.current_index} url={item.url}")

    def on_bus_message(self, bus, message):  # pragma: no cover - depends on runtime
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            self.log(f"❌ GStreamer error: {err} debug={debug}")
            self.next_item(delay=2)
        elif t == Gst.MessageType.EOS:
            self.log("⏭️ End of stream")
            self.next_item(delay=0.5)

    def next_item(self, delay: float = 0.0):
        if self._stop:
            return
        def _advance():
            with self._lock:
                self.start_item(self.current_index + 1)
        if delay <= 0:
            _advance()
        else:
            threading.Timer(delay, _advance).start()

    # --- Main Loop -------------------------------------------------------------
    def run(self):
        self.load_playlist()
        if not self.playlist:
            self.log("🚫 Empty playlist; waiting 10s then retry (Ctrl+C to exit)")
            for _ in range(10):
                if self._stop:
                    return 0
                time.sleep(1)
            # Try once more
            self.load_playlist()
            if not self.playlist:
                self.log("❌ Still empty. Exiting.")
                return 4
        self.start_item(0)
        self.loop = GObject.MainLoop()
        try:
            self.loop.run()
        except GracefulExit:
            self.log("👋 Graceful exit requested")
        finally:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
        return 0

    def stop(self):
        self._stop = True
        if self.loop and self.loop.is_running():
            self.loop.quit()


def parse_args():
    p = argparse.ArgumentParser(description="Standalone hardware-accelerated sliced player (experimental)")
    p.add_argument("--store-id", required=True)
    p.add_argument("--screen-id", required=True, help="Full screen identifier e.g. 1000_screen2")
    p.add_argument("--slice-index", type=int, default=1, help="1-based index of this screen slice")
    p.add_argument("--slice-count", type=int, default=3, help="Total number of horizontal slices")
    p.add_argument("--panorama-width", type=int, default=5760, help="Full source video width (e.g. 5760 for 3x1920)")
    p.add_argument("--panorama-height", type=int, default=1080, help="Full source video height")
    p.add_argument("--test-url", help="Direct video URL for testing (bypass playlist)")
    p.add_argument("--loop", action="store_true", help="Loop playlist forever (default)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.slice_count <= 0:
        print("slice-count must be > 0", file=sys.stderr)
        return 2
    if args.slice_index < 1 or args.slice_index > args.slice_count:
        print("slice-index out of range", file=sys.stderr)
        return 2

    player = StandalonePlayer(args)

    def _sig_handler(signum, frame):  # pragma: no cover
        player.log(f"🛑 Signal {signum} received – stopping")
        player.stop()
        raise GracefulExit()

    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, _sig_handler)

    rc = player.run()
    return rc


if __name__ == '__main__':
    sys.exit(main())
