# Android TV Device Tracking

## Overview
Added comprehensive Android TV device tracking to the Pi Manager dashboard. Android TV devices are now tracked alongside Raspberry Pi devices with real-time status updates, remote control capabilities, and device management.

## Features Implemented

### 1. Backend Tracking Infrastructure
- **`connected_android_tvs` dict**: Global dictionary tracking active Android TV devices
  - Key: `device_id` (unique identifier per device)
  - Value: `{'store_id', 'screen_id', 'last_seen', 'ip', 'user_key', 'socket_id'}`
  
- **Enhanced `/api/screen_heartbeat` endpoint**:
  - Now tracks Android TV devices in `connected_android_tvs`
  - Records device_id, store assignment, IP address, and last_seen timestamp
  - Supports fallback device_id generation from store+screen if not provided

### 2. Status API Endpoint
- **`GET /api/android_tv_status`**: Returns list of Android TV devices with:
  - Device ID, online/offline status (120s timeout)
  - Store and screen assignments (with friendly names)
  - Last seen timestamp (formatted)
  - IP address
  - Location name (if set)
  - Filtered by current user's devices only

### 3. Dashboard UI
- **New "Android TV Devices" section in Pi Manager**:
  - Device cards matching Pi device design
  - Shows: Device ID, status badge, store/screen, last seen, IP, location
  - Auto-refresh every 10 seconds
  - Real-time counters: online/offline/total counts
  - Empty state message when no devices found

### 4. Remote Control Capabilities
- **Socket.IO Handlers**:
  - `android_tv_register`: Device registration with server
  - `android_tv_command`: Send commands from dashboard to devices
  - `remote_command`: Broadcast command to specific device via Socket.IO

- **HTTP API Endpoints**:
  - `POST /api/android_tv_command`: Send commands (refresh_screen, reload_playlist, restart_app)
  - `POST /api/android_tv_remove`: Remove device from tracking

- **UI Actions**:
  - **Refresh Screen**: Sends refresh command to Android TV
  - **View Details**: Shows device information (placeholder)
  - **Remove**: Removes device from tracking

## How It Works

### Device Registration Flow
1. Android TV app sends heartbeat to `/api/screen_heartbeat`
2. Heartbeat includes: `store_id`, `screen_id`, `device_id` (optional), `session_id` (optional)
3. Server records device in `connected_android_tvs` dict
4. Device appears in Pi Manager dashboard within 2 seconds (auto-refresh)

### Status Updates
- Dashboard polls `/api/android_tv_status` every 10 seconds
- Devices offline for >120 seconds show as "offline"
- Last seen timestamp updates in real-time

### Remote Commands
1. User clicks "Refresh Screen" button in dashboard
2. Browser sends POST to `/api/android_tv_command` with device_id and command
3. Server looks up device's socket_id in `connected_android_tvs`
4. Sends `remote_command` event via Socket.IO to device
5. Android TV app receives event and executes command

## Technical Details

### Timeout Configuration
- **Heartbeat Interval**: Android TVs send heartbeats every ~30 seconds
- **Offline Timeout**: 120 seconds (allows 3 missed heartbeats)
- **Consistent with Pi timeout**: Same 120s timeout as Raspberry Pi devices

### Device Identification
- **Primary**: `device_id` sent by Android TV app
- **Fallback 1**: `session_id` from pairing system
- **Fallback 2**: Generated from `{store_id}_{screen_id}`

### Thread Safety
- Uses `android_tv_lock` threading.Lock() for concurrent access
- Prevents race conditions during heartbeat updates and status queries

### User Isolation
- Devices filtered by `user_key` to ensure multi-tenant support
- Each user only sees their own Android TV devices

## Code Locations

### Backend (app.py)
- Lines 217-220: `connected_android_tvs` dict and lock declaration
- Lines 2039-2116: Enhanced `/api/screen_heartbeat` with Android TV tracking
- Lines 5536-5607: `/api/android_tv_status` endpoint
- Lines 11158-11253: Socket.IO handlers and HTTP endpoints for remote control

### Frontend (templates/pi_manager.html)
- Lines 900-935: Android TV Devices HTML section
- Lines 1728-1828: `refreshAndroidTvStatus()` JavaScript function
- Lines 1831-1883: Android TV action functions (refresh, view, remove)
- Lines 1900-1906: Auto-refresh timer integration

## Testing Checklist
- [ ] Start Android TV emulator: `.\start_android_tv_emulator.ps1`
- [ ] Pair device with 4-digit code via WebPlayer
- [ ] Verify device appears in Pi Manager "Android TV Devices" section
- [ ] Check online status badge is green
- [ ] Verify store/screen assignment shows correctly
- [ ] Test "Refresh Screen" button sends command
- [ ] Wait 120+ seconds without heartbeat, verify shows offline
- [ ] Test "Remove" button removes device from list
- [ ] Refresh page, verify device list persists (from heartbeats)

## Future Enhancements
- [ ] Persistent storage for device history (currently in-memory only)
- [ ] Device details modal with full information
- [ ] More remote commands (restart app, change screen, clear cache)
- [ ] Device health metrics (playback errors, last content played)
- [ ] Push notifications for device offline events
- [ ] Batch operations (refresh all devices in store)
- [ ] Device grouping by store or location

## Integration Notes
- **Works with existing WebPlayer system**: Devices using 4-digit pairing codes are tracked
- **No changes required to Android TV app**: Existing heartbeat mechanism works out of the box
- **Socket.IO optional**: Commands work via HTTP if Socket.IO not available
- **Backwards compatible**: Existing Pi Manager functionality unchanged
