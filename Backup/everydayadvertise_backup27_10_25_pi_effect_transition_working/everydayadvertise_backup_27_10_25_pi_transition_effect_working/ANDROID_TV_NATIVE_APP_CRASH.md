# Android TV App Crash - Setup Activity WebView Issue

## Critical Discovery

### What Happened
The Android TV emulator crashed **before** reaching the TV display screen. The crash occurred in **SetupActivity** (the initial QR code screen), not in the TV viewing mode.

### Crash Timeline
```
19:24:06.715 - SetupActivity: Connecting Socket.IO
19:24:07.149 - SetupActivity: Socket connect error (websocket error)
19:24:09.083 - SetupActivity: QR code bitmap set successfully
19:24:16.220 - chromium: Renderer process (3558) crash detected (code -1)
19:24:19.118 - ActivityTaskManager: Force removing ActivityRecord (app died)
```

## Root Cause

**SetupActivity.kt** (lines 105-120) loads a **WebView** for the intro overlay:
```kotlin
val wv = android.webkit.WebView(this).apply {
    settings.javaScriptEnabled = false
    settings.domStorageEnabled = true
    setBackgroundColor(android.graphics.Color.TRANSPARENT)
}
// ...
wv.loadUrl("file:///android_asset/ea-logo-intro.html")
```

This WebView is **crashing the renderer process** before the user even gets to the TV display.

### Why It's Crashing
1. **Android TV emulator has limited WebView resources**
2. **Intro overlay WebView** allocates memory even for simple HTML
3. **No memory management** in SetupActivity intro code
4. **WebView initialization timing** conflicts with video loading

## Impact Analysis

### What This Means
- ✅ Your **tv_view.html crash fixes are GOOD** (not tested yet)
- ❌ The **native app crashes BEFORE** reaching TV display
- ❌ **SetupActivity intro WebView** needs fixes too
- ⚠️ Cannot test tv_view.html until SetupActivity is fixed

### Two Separate Issues
1. **SetupActivity WebView** (crashing now) → needs fix
2. **TvDisplayActivity WebView** (loads tv_view.html) → already fixed

## Solution Options

### Option 1: Disable Setup Intro (Quick Fix)
Comment out the intro overlay in SetupActivity to skip WebView loading entirely.

### Option 2: Add Memory Management to Setup
Apply same crash prevention to SetupActivity intro:
- Remove intro WebView entirely
- Use static ImageView only
- No video/WebView until TV display

### Option 3: Test TV Display Directly
Skip setup and launch TvDisplayActivity directly with hardcoded store/screen IDs.

## Recommended Action

**DISABLE THE INTRO OVERLAY** to reach TV display:

```kotlin
// In SetupActivity.kt onCreate(), comment out:
// maybeShowIntroOverlay()
```

Then rebuild and test the actual TV view WebView which has your crash fixes.

## Testing Steps After Fix

1. **Rebuild app** without intro overlay
2. **Reinstall** to emulator
3. **Navigate** to TV display screen (enter store 1931, select promo1)
4. **Monitor logcat** for the REAL crash test:
   - Memory usage
   - Video loading queue
   - GPU context stability
   - Renderer process health

## Files to Modify

**android_tv_app/app/src/main/java/com/pizzahut/tv/SetupActivity.kt**
Line ~42: Comment out `maybeShowIntroOverlay()` call

Or better: Remove the entire WebView fallback section (lines 105-120).

---

## Status

- ❌ **Current**: Native app crashes in SetupActivity intro
- ⏳ **Pending**: Test tv_view.html crash fixes in TvDisplayActivity
- ✅ **Ready**: tv_view.html with comprehensive crash prevention deployed
