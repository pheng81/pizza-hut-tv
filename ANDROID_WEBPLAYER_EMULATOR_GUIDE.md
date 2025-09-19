# Android WebPlayer Emulator Guide

## Emulator Networking
When running the Flask server on your Windows host (e.g., http://127.0.0.1:5000 or http://localhost:5000), the Android emulator cannot use `localhost` directly. Use the special alias:

- Host loopback inside emulator: `http://10.0.2.2:5000`

The new `WebPlayerActivity` code auto-rewrites `localhost` to `10.0.2.2` if needed.

## Flask Route
The embedded player template is exposed at:
```
/webplayer_embed.html?store=<STORE_ID>&screen=<SCREEN_ID>&debug=1
```
Example:
```
http://10.0.2.2:5000/webplayer_embed.html?store=0000&screen=screen1&debug=1
```

## Test Steps
1. Start Flask server (ensure `deploy/templates/webplayer_embed.html` is on PYTHONPATH template search path; if using root `app.py`, just run it):
2. Launch Android emulator (Cold Boot recommended if media issues appear).
3. From setup / existing activity, launch `WebPlayerActivity` with intent extras:
   - `storeId` = your store code
   - `screenId` = screen identifier used in playlist
4. Observe playback:
   - First playlist fetch occurs; status overlay logs in bottom-left.
   - Video loads and cropping applied if `sync_ref` indicates multi-screen.
5. Add additional emulator instances or physical devices for multi-screen group (each uses different `screenId` but same sync group).

## Multi-Screen Sync Tips
- Ensure each playlist item in the group has identical `sync_ref.group`, `mode`, `count`, and distinct `order`.
- If one device shows full panorama instead of slice, confirm `count > 1` and `order` is within range.

## Debugging
- Append `&debug=1` to keep status overlay visible.
- Use `adb logcat | findstr WebPlayer` (Windows PowerShell: `adb logcat WebPlayer*:V WebPlayerConsole*:V *:S`).
- Network errors: check CORS, ensure playlist endpoint returns HTTP 200.

## Common Issues
| Symptom | Fix |
|---------|-----|
| Black screen, no logs | Confirm JavaScript enabled and URL is reachable (open in desktop browser). |
| Loads but wrong slice | Verify `sync_ref.count` correct and all group members defined. |
| Multiple full panoramas (no crop) | `sync_ref` missing on item; ensure server group configuration applied. |
| Frequent reloads | Network instability; inspect server logs for 500 errors. |

## Next Enhancements (Optional)
- Heartbeat JS -> native bridge
- Error recovery with stalled event
- Service Worker caching
- WebSocket trigger for frame-aligned transitions

