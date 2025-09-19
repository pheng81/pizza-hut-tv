# CustomCodecPlayerActivity (Experimental)

This activity implements a custom video pipeline using `MediaExtractor` + `MediaCodec` (no ExoPlayer).
Recent feature waves added progressively:
Wave 1 (Core):
1. Fetch & iterate entire playlist (videos + timed image placeholders)
2. Viewport cropping for multi-screen (`split-h` / `split-v`)
3. Honors `sync_ref.start_epoch` with sync barrier for first group item
4. Heartbeat & client events (item_start, item_end, load_fail)
5. Periodic playlist refresh (60s) with exponential backoff
6. Metrics overlay (FPS, est drops, avg frame delta)
7. Timestamp-aware pacing

Wave 2 (Enhancements A–D):
8. Actual image item rendering (Bitmap decode + scaling + crop)
9. UI controls overlay (play/pause, next, toggle metrics, quick help) via DPAD & media keys
10. Stall watchdog (detects no rendered frames for threshold, auto restart)
11. WebSocket sync scaffold (receives commands: refresh_playlist, jump_index, set_epoch, ping)
12. Launcher integration (select between Native / WebView / Custom modes)

## Current Capabilities
- Hardware decode: YES (MediaCodec)
- Multi-item playlist iteration (loops continuously)
- Image item rendering (Bitmap) with viewport crop
- Heartbeat (30s) & client event posting
- Sync barrier (start epoch) for first group item
- Exponential backoff on playlist fetch errors (2s -> 60s)
- Periodic playlist refresh (60s)
- Metrics overlay: FPS, drop estimate, avg frame delta
- Viewport cropping via `TextureView.setTransform(Matrix)` & ImageView matrix
- Basic pacing loop (sleep + timestamp alignment)
- Stall watchdog & auto-restart
- WebSocket command channel (basic scaffold)
- UI controls / key handling overlay

## Launch Example
```kotlin
val intent = Intent(this, CustomCodecPlayerActivity::class.java)
intent.putExtra("storeId", "0000")
intent.putExtra("screenId", "screen1")
startActivity(intent)
```

## Remaining Limitations / Potential Enhancements
1. Audio track enable/disable still placeholder (no mixing or volume UI)
2. No adaptive streaming (HLS/DASH) or trick-play
3. Limited surface lifecycle resilience (rotation / multi-window not primary target)
4. No prefetch / caching for next item (could warm extractor)
5. WebSocket channel: outbound events & auth not implemented yet
6. Metrics: drop estimate heuristic only (delta > 50ms)
7. No frame-accurate multi-device sync (epoch barrier only; WS commands coarse)
8. No vsync-aligned pacing (Choreographer not yet used)

## Suggested Future Improvements
- Next-item pre-buffering (parallel extractor warm-up)
- Replace sleep-based pacing with `Choreographer` frame callbacks
- Local disk/LRU caching for media + image assets
- WebSocket outbound event & auth handshake + JSON schema versioning
- Frame-accurate sync: timecode alignment + drift correction loop
- Enhanced metrics: real dropped frame count via surface callbacks
- Remote config (enable/disable metrics, watchdog thresholds)

## Launcher Integration
`PlayerModeLauncherActivity` lets you choose between:
1. Native ExoPlayer (`TvDisplayActivity`)
2. WebView Panorama Player (`WebPlayerActivity`)
3. Custom Codec Player (`CustomCodecPlayerActivity`)

If you launched via the new launcher, `storeId` & `screenId` extras are forwarded automatically.

## When To Use
Use this mode for R&D, low-level sync experiments, and exploring advanced diagnostics. For production robustness (adaptive streaming, DRM, wide device coverage), extending ExoPlayer generally remains safer.

