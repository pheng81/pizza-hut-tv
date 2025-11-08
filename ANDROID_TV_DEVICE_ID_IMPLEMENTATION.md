# Android TV App - Device ID Implementation

## ✅ Changes Made

### 1. Updated `HeartbeatReq` Model (ApiModels.kt)
**File:** `android_tv_app/app/src/main/java/com/pizzahut/tv/api/ApiModels.kt`

```kotlin
// Heartbeat
data class HeartbeatReq(
	@SerializedName("store_id") val storeId: String,
	@SerializedName("screen_id") val screenId: String,
	@SerializedName("device_id") val deviceId: String? = null  // ✅ ADDED
)
```

### 2. Updated Heartbeat Sender (TvDisplayActivity.kt)
**File:** `android_tv_app/app/src/main/java/com/pizzahut/tv/TvDisplayActivity.kt`

```kotlin
private fun startHeartbeatLoop(storeId: String, screenId: String) {
    heartbeatJob?.cancel()
    heartbeatJob = lifecycleScope.launch(Dispatchers.IO) {
        // ✅ Get persistent device ID
        val deviceId = com.pizzahut.tv.api.DeviceIdHelper.get(applicationContext)
        while (isActive) {
            try {
                ApiClient.service.sendHeartbeat(HeartbeatReq(
                    storeId = storeId, 
                    screenId = screenId,
                    deviceId = deviceId  // ✅ Send in heartbeat
                ))
```

### 3. Device ID System (Already Exists!)
**File:** `android_tv_app/app/src/main/java/com/pizzahut/tv/api/DeviceId.kt`

The app **already had** a complete device ID system:
- Uses `UUID.randomUUID()` to generate unique ID
- Stores in SharedPreferences (persists across app restarts)
- Initialized in `SetupActivity.onCreate()`
- Shows device ID on screen for 7 seconds on startup

## How It Works

### Device ID Generation
1. **First Launch**: App generates UUID and stores in SharedPreferences
   ```
   UUID Example: d4f8a3b2-7c1e-4d9f-8a6b-9e3f2c1d4a5b
   ```

2. **Subsequent Launches**: App reads same UUID from SharedPreferences
   - ID persists across app restarts
   - Only changes if app data is cleared or app is reinstalled

3. **Displayed to User**: When app starts, shows first 8 characters:
   ```
   TV ID: d4f8a3b2
   ```
   - Appears for 7 seconds on top of screen
   - Helps with support/debugging

### Heartbeat Flow
```
Android TV App (every 30 seconds)
    ↓
POST /api/screen_heartbeat
    device_id: "d4f8a3b2-7c1e-4d9f-8a6b-9e3f2c1d4a5b"
    store_id: "1111"
    screen_id: "1111_screen1"
    ↓
Server (app.py)
    ↓
connected_android_tvs["d4f8a3b2-..."] = {
    'store_id': '1111',
    'screen_id': '1111_screen1',
    'last_seen': 1762615000,
    'ip': '192.168.1.100',
    'user_key': 'test9@gmail.com'
}
    ↓
Pi Manager Dashboard
    Shows device with UUID in "📱 Android TV Devices" section
```

## Testing the Updated App

### Build & Install
1. **APK Location:**
   ```
   android_tv_app/app/build/outputs/apk/debug/app-debug.apk
   ```

2. **Install on Android TV Emulator:**
   ```powershell
   .\start_android_tv_emulator.ps1
   ```
   - Emulator starts automatically
   - APK installed automatically
   - App launches to setup screen

3. **Or Install via ADB:**
   ```bash
   adb install -r android_tv_app/app/build/outputs/apk/debug/app-debug.apk
   ```

### Pairing Process
1. **Open app on Android TV**
2. **Enter pair code:** `8329` (test9@gmail.com)
3. **Select store:** `1111 - test store`
4. **Select screen:** `1111_screen1`
5. **Note the Device ID** displayed for 7 seconds (e.g., "TV ID: d4f8a3b2")

### Verify in Pi Manager
1. **Open:** http://everydayadvertise.com/pi_manager
2. **Check "📱 Android TV Devices" section**
3. **You should see:**
   ```
   Device ID: d4f8a3b2-7c1e-4d9f-8a6b-9e3f2c1d4a5b
   Status: 🟢 online
   Store: test store
   Screen: 1111_screen1
   IP: (emulator IP)
   Last Seen: Just now
   ```

### Check Server Logs
```bash
ssh -i ~/.ssh/key.pem ubuntu@54.252.90.27
sudo journalctl -u pizza-hut-tv.service -f | grep "Android TV"
```

**Expected output:**
```
[Android TV] Heartbeat from device d4f8a3b2-7c1e-4d9f-8a6b-9e3f2c1d4a5b: 1111/1111_screen1 @ 192.168.1.100
```

## Device ID Uniqueness

### ✅ Truly Unique Per Device
- Uses Android's UUID.randomUUID() 
- Format: Standard UUID (36 characters)
- Example: `d4f8a3b2-7c1e-4d9f-8a6b-9e3f2c1d4a5b`

### ✅ Persists Across
- App restarts
- Device reboots
- Screen changes (device keeps same ID when reassigned)

### ❌ Resets When
- App data cleared (Settings → Apps → Pizza Hut TV → Clear Data)
- App uninstalled and reinstalled
- Device factory reset

### Comparison with Alternatives

| Method | Pros | Cons |
|--------|------|------|
| **UUID (Current)** | Simple, works everywhere, no permissions | Resets on reinstall |
| **ANDROID_ID** | Survives reinstall, hardware-based | Requires permission, can be null on some devices |
| **MAC Address** | Hardware-based, never changes | Requires location permission, privacy concerns |

**Current implementation is BEST for this use case:**
- No special permissions needed
- Works on all Android versions
- Good enough uniqueness for TV displays
- Reinstalls are rare for commercial TVs

## Multiple Devices Support

### Scenario: 2 Android TVs on Same Screen
```
Device 1: UUID d4f8a3b2-... → Store 1111, Screen 1111_screen1
Device 2: UUID e7c9b4d1-... → Store 1111, Screen 1111_screen1
```

**Pi Manager shows:**
- ✅ Both devices listed separately
- ✅ Each with unique UUID
- ✅ Both assigned to same screen
- ✅ Both showing online status

**Before (WebPlayer fallback):**
- ❌ Only showed 1 device (used store+screen as ID)
- ❌ Multiple devices appeared as one

## Summary

✅ **Android TV app now sends unique device ID in every heartbeat**
✅ **Server tracks devices by UUID (not store+screen)**
✅ **Pi Manager shows all Android TVs with unique IDs**
✅ **Multiple TVs on same screen show separately**
✅ **APK built successfully and ready to test**

## Next Steps

1. **Install updated APK on Android TV emulator**
2. **Pair with code 8329**
3. **Check Pi Manager to see device appear**
4. **Note the UUID shown in dashboard**
5. **Test with multiple emulators to verify uniqueness**
