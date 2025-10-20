# SocketIO Crash Fix - October 18, 2025

## Problem
Website was experiencing periodic crashes (Cloudflare 524 errors) due to **unhandled exceptions in SocketIO event handlers**.

### Symptoms
- App crashes every 1-2 hours
- "Connection refused (111)" in Nginx logs
- "Exception in thread Thread-XXX (_handle_event_internal)" in application logs
- Service auto-restarts but causes downtime

### Root Cause
All 20 SocketIO event handlers were missing error handling. When any handler encountered an exception:
1. The thread crashed
2. SocketIO became unresponsive
3. Gunicorn worker hung
4. Nginx couldn't connect to upstream (127.0.0.1:5002)
5. Cloudflare returned 524 (timeout)
6. Systemd eventually restarted the service

## Solution Implemented

### Added Error Handler Decorator
Created `@socketio_error_handler` decorator that:
- Wraps all SocketIO handlers in try/except
- Logs full exception traceback
- Prevents thread crashes
- Optionally emits error back to client

### Handlers Protected (20 total)
1. `handle_connect` - WebSocket connection
2. `handle_disconnect` - WebSocket disconnection
3. `handle_pi_registration` - Pi registration
4. `handle_pi_heartbeat` - Pi heartbeat
5. `handle_pi_status_update` - Pi status updates
6. `handle_config_applied` - Config confirmation
7. `handle_join_session` - WebPlayer session join
8. `handle_send_code` - Mobile code sharing
9. `handle_send_store_code` - Store code sharing
10. `handle_send_screen_selection` - Screen selection
11. `handle_leave_session` - Session cleanup
12. `handle_screenshot_request` - Screenshot request
13. `handle_start_live_stream` - Start live stream
14. `handle_stop_live_stream` - Stop live stream
15. `handle_live_frame` - Live frame relay
16. `handle_screenshot_data` - Screenshot data
17. `handle_vnc_connect` - VNC connection
18. `handle_vnc_data` - VNC data relay
19. `handle_vnc_disconnect` - VNC disconnect
20. `handle_restart_client` - Client restart
21. `handle_client_restarting` - Restart confirmation

## Deployment
- **File Modified:** `app.py`
- **Deployed:** October 18, 2025 23:01 UTC
- **Service Restart:** Successful
- **Status:** Active (running)

## Verification
✅ Service started successfully  
✅ Website responding (HTTP 200)  
✅ No startup errors in logs  
✅ Playlist endpoints working  

## Monitoring
Monitor for next 2-3 hours to confirm:
- No more thread exceptions in logs
- No service restarts
- Stable uptime
- No 524 errors from Cloudflare

## Command to Check Logs
```bash
ssh -i key.pem ubuntu@54.252.90.27 "sudo journalctl -u pizza-hut-tv -f"
```

Look for:
- ✅ No "Exception in thread" messages
- ✅ Continuous heartbeat/playlist requests
- ✅ Stable uptime

## Fallback Plan
If crashes continue:
1. Increase workers from 1 to 2 (redundancy)
2. Add connection pooling
3. Implement circuit breaker pattern
