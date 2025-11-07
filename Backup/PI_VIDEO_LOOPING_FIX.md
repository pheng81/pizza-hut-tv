# VIDEO LOOPING FIX - Pi Client Not Playing Correctly

## Problem
Pi clients play videos once and then stop (black screen), while Android TV plays videos continuously.

## Root Cause
**Android TV (Web Browser)**:
- Uses HTML5 `<video>` element with `loop` attribute
- Code: `node.loop = (item.repeat !== false);` (defaults to true)
- Videos loop automatically within the browser

**Raspberry Pi (MPV Player)**:
- Uses MPV media player via python-mpv bindings  
- No loop setting was configured
- Videos play once, reach end, MPV goes idle → black screen
- Timer eventually advances to next item, but gap shows black screen

## Solution
Added video looping to MPV player in `seamless_video_player.py`:

```python
# CRITICAL FIX: Enable looping to prevent black screen
try:
    self.player['loop-file'] = 'inf'  # Loop current file infinitely
    logger.info("🔁 Enabled video looping to prevent black screen")
except Exception as loop_err:
    logger.warning(f"⚠️ Could not enable loop-file: {loop_err}")
```

This was added after line 245 in the `play_video()` function, right after `self.player.play(video_path)`.

## How It Works
1. **Web Player**: HTML5 video loops natively until JavaScript timer advances playlist
2. **Pi Client (Fixed)**: MPV loops current video infinitely until Python timer advances playlist
3. Both systems use timers to control when to move to the next item (based on configured duration)
4. Videos shorter than their duration now loop seamlessly instead of stopping

## Deployment
Run `deploy_pi_fix.ps1` to deploy the fix to your Raspberry Pi, or manually:
1. Copy updated `seamless_video_player.py` to Pi: `~/pizzahut-client/`
2. Restart client: `pkill -f complete_pi_client` (auto-restarts via bashrc)

## Technical Details
- File modified: `seamless_video_player.py` (line ~250)
- MPV option: `loop-file=inf` (loop current file indefinitely)
- Matches Android TV behavior where `node.loop = true` by default
- Timer-based advancement works identically on both platforms
- No server changes required (repeat field not sent, defaults to true behavior)
