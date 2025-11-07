# Android TV Emulator Setup Guide

## Option 1: Android Studio (Full Featured)

### Prerequisites
1. Download Android Studio: https://developer.android.com/studio
2. Install Android Studio (requires ~10GB disk space)

### Setup Steps
```powershell
# 1. Open Android Studio
# 2. Go to: Tools → Device Manager (or AVD Manager)
# 3. Click "Create Virtual Device"
# 4. Select "TV" category
# 5. Choose "Android TV (1080p)" - recommended profile
# 6. Select system image (API 33+ recommended)
# 7. Click "Finish"
# 8. Click "Play" button to start emulator
```

### Quick Test in Emulator
1. Open Chrome browser in Android TV
2. Navigate to: `https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1`
3. Watch debug overlay for memory usage and rotation updates
4. Monitor logcat for crash indicators

---

## Option 2: Chrome DevTools (Quick Test)

Test Android WebView behavior without full emulator:

### PowerShell Command
```powershell
# Open Chrome with Android WebView user agent
Start-Process chrome.exe -ArgumentList `
  "--user-agent=`"Mozilla/5.0 (Linux; Android 10; Android TV Build/QTT1.200111.002) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Safari/537.36`"", `
  "--window-size=1920,1080", `
  "https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1"
```

**Limitations**: 
- Doesn't test actual Android WebView crashes
- Can't test GPU context issues
- Good for UI/rotation testing only

---

## Option 3: Genymotion (Lighter Alternative)

Faster than Android Studio emulator:

1. Download: https://www.genymotion.com/download/
2. Install Genymotion
3. Create Android TV device (select TV template)
4. Start device
5. Install Chrome or use built-in browser
6. Navigate to test URL

---

## Option 4: Physical Android TV Device (Best)

If you have access to real Android TV hardware:

### TCL/Sony/Hisense Android TV
1. Open Google Chrome or built-in browser
2. Navigate to: `https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1`
3. Monitor with ADB logcat

### ADB Logcat Monitoring (Real Device)
```powershell
# Enable ADB debugging on TV:
# Settings → Device Preferences → About → Build (click 7x)
# Settings → Device Preferences → Developer options → USB debugging (enable)

# Connect via network
adb connect [TV_IP_ADDRESS]:5555

# Monitor logs
adb logcat | Select-String -Pattern "pizzahut|chromium|Context lost|calloc|Renderer process"
```

---

## Quick Chrome Test (Available Now)

I can launch Chrome with Android TV simulation:

```powershell
# Test rotation and UI (not full crash testing)
Start-Process chrome.exe -ArgumentList `
  "--user-agent=`"Mozilla/5.0 (Linux; Android 10; Android TV) AppleWebKit/537.36`"", `
  "--window-size=1920,1080", `
  "--disable-gpu-vsync", `
  "https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1"
```

---

## What to Look For During Testing

### Success Indicators ✅
- Debug overlay shows: `MEMORY: <80MB`
- Messages: `VIDEO: Loaded [1 active]`
- Messages: `CLEANUP: Cleared video from layer`
- Rotation responds within 1-3 seconds
- No frame skips or stuttering

### Failure Indicators ❌
- Memory usage >100MB and climbing
- Multiple active videos: `VIDEO: Loaded [2 active]`
- Browser/app crashes
- Console errors: `Context lost`, `calloc failed`

---

## Recommended Testing Path

1. **Quick Test** → Chrome with Android user agent (5 minutes)
2. **Full Test** → Android Studio emulator (if crashes persist)
3. **Real Test** → Physical Android TV device (final validation)

---

## Need Help?

Choose one option and I can provide specific commands to:
- Launch Chrome with Android simulation
- Generate Android Studio AVD config
- Set up ADB monitoring scripts
- Create automated test scenarios
