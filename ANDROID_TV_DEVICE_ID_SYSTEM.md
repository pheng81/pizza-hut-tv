# Android TV Device Identification System

## How Android TV Devices Are Tracked

### Device ID Generation

**WebPlayer/Android TV now generates a persistent unique device ID:**

```javascript
// Stored in browser localStorage
deviceId = 'tv_' + random(9 chars) + '_' + timestamp
// Example: tv_a3f8k2m7x_1762614000000
```

**Persistence:**
- Stored in `localStorage.getItem('phtv_device_id')`
- Survives browser refresh/restart
- Only resets if user clears browser data or reinstalls app

### Comparison with Raspberry Pi

| Feature | Raspberry Pi | Android TV (WebPlayer) |
|---------|--------------|------------------------|
| **Device ID** | `raspberrypi-ce39` (hostname) | `tv_a3f8k2m7x_1762614000000` (generated) |
| **Persistence** | Hardware-based (MAC/hostname) | localStorage (browser storage) |
| **Uniqueness** | Per physical device | Per browser/app installation |
| **Changes when** | Never (unless hostname changed) | When browser data cleared or app reinstalled |
| **Format** | `raspberrypi-XXXX` | `tv_XXXXXXX_timestamp` |

### Heartbeat System

**Every 30 seconds, device sends:**
```
GET /api/screen_heartbeat?store_id=1111&screen_id=1111_screen1&device_id=tv_a3f8k2m7x_1762614000000
```

**Server tracks:**
```python
connected_android_tvs = {
    'tv_a3f8k2m7x_1762614000000': {
        'store_id': '1111',
        'screen_id': '1111_screen1',
        'last_seen': 1762614123,
        'ip': '203.158.51.30',
        'user_key': 'test9@gmail.com'
    }
}
```

### Device Lifecycle

1. **First Visit**: Device generates new ID → stores in localStorage → sends in heartbeat
2. **Subsequent Visits**: Device reads existing ID from localStorage → continues using same ID
3. **Browser Data Cleared**: ID lost → generates new ID → appears as "new device" in dashboard
4. **Multiple Tabs**: Same browser = same device ID (shared localStorage)
5. **Multiple Browsers**: Different browser = different device ID (separate localStorage)

## Testing Android TV Tracking

### Test 1: Basic Device Tracking

1. **Open WebPlayer:**
   ```
   http://everydayadvertise.com/webplayer
   ```

2. **Pair with 4-digit code:**
   - Enter code: `8329` (test9@gmail.com)
   - Select store: `1111 - test store`
   - Select screen: `1111_screen1`

3. **Check Pi Manager:**
   ```
   http://everydayadvertise.com/pi_manager
   ```
   - Look in "📱 Android TV Devices" section
   - Device should appear with:
     - ID: `tv_XXXXXXX_timestamp`
     - Status: 🟢 online
     - Store: test store
     - Screen: 1111_screen1
     - IP: Your IP address
     - Last Seen: Just now

4. **Check browser console:**
   ```javascript
   localStorage.getItem('phtv_device_id')
   // Should show: tv_XXXXXXX_timestamp
   ```

### Test 2: Device Persistence

1. **Refresh the WebPlayer page**
2. **Check console again:**
   ```javascript
   localStorage.getItem('phtv_device_id')
   // Should show SAME ID as before
   ```
3. **Check Pi Manager** - device should maintain same ID

### Test 3: Multiple Devices

1. **Open WebPlayer in different browser** (Chrome vs Firefox)
2. **Pair both devices to same screen**
3. **Check Pi Manager:**
   - Should show 2 devices with different IDs
   - Both assigned to same screen
   - Both showing online

### Test 4: Offline Detection

1. **Close WebPlayer tab**
2. **Wait 2 minutes** (120 second timeout)
3. **Refresh Pi Manager:**
   - Device status should change to 🔴 offline
   - Last Seen should show time of last heartbeat

### Test 5: Remote Commands

1. **With WebPlayer open and online**
2. **In Pi Manager, click "Refresh Screen" button**
3. **Expected:**
   - Alert shows "✅ Command sent"
   - Note: WebPlayer doesn't have Socket.IO yet, so command won't execute
   - But server logs the command attempt

## Checking Server Logs

**SSH to server:**
```bash
ssh -i ~/.ssh/everydayadvertise.pem ubuntu@54.252.90.27
```

**View Android TV heartbeats:**
```bash
sudo journalctl -u pizza-hut-tv.service -f | grep "Android TV"
```

**Expected output:**
```
[Android TV] Heartbeat from device tv_a3f8k2m7x_1762614000000: 1111/1111_screen1 @ 203.158.51.30
```

## Device ID Limitations

### ⚠️ Potential Issues

1. **Browser Data Clearing**
   - User clears cookies/storage → device ID lost → new ID generated
   - Solution: User education (don't clear data) or store ID on server side

2. **Multiple Tabs**
   - Same browser, multiple tabs → same device ID
   - Dashboard shows only 1 device (not a problem, just awareness)

3. **Private/Incognito Mode**
   - localStorage not persisted between sessions
   - Each incognito session = new device ID

4. **Android TV App vs WebPlayer**
   - Native Android TV app: Should use `Settings.Secure.ANDROID_ID` (hardware-based)
   - WebPlayer: Uses localStorage (browser-based)

## Future Improvements

### For Native Android TV App

**Use Android's secure device ID:**
```java
import android.provider.Settings;

String deviceId = Settings.Secure.getString(
    context.getContentResolver(),
    Settings.Secure.ANDROID_ID
);
// Example: 9774d56d682e549c
```

**Benefits:**
- Truly unique per device (like Pi hostname)
- Survives app reinstall
- Never changes (unless factory reset)

### For WebPlayer

**Option 1: Server-side registration**
- First heartbeat → server generates & returns device ID
- Store in localStorage for future use
- Server maintains registry of all devices

**Option 2: Fingerprinting**
- Combine: screen resolution + user agent + timezone + WebGL renderer
- More persistent than random ID
- Privacy concerns to consider

## Summary

✅ **Working Now:**
- WebPlayer generates unique device ID on first visit
- Stores in localStorage for persistence
- Sends in every heartbeat (30s interval)
- Pi Manager shows all Android TV devices
- Online/offline detection (120s timeout)

🟡 **Limitations:**
- ID resets if browser data cleared
- Not as permanent as Pi hostname
- Multiple tabs share same ID

🔵 **Recommended:**
- For native Android TV app: Use `ANDROID_ID`
- For WebPlayer: Current system is good enough
- Educate users: Don't clear browser data
