# Amazon Fire TV & Universal TV Browser Compatibility Fix

## Problem
Webplayer not displaying videos or images on Amazon Fire TV and potentially other smart TV browsers.

## Root Causes Identified

### 1. **Insufficient Browser Compatibility**
- Not using `<source>` elements for better codec detection
- Missing TV-specific video attributes
- Inadequate error logging for debugging

### 2. **Amazon Fire TV Specifics**
- Uses Amazon Silk browser (Chromium-based)
- Fire OS (Android-based) requires specific video attributes
- Need explicit MIME types for codec detection

### 3. **Lack of Diagnostic Information**
- No visible error messages for users
- Insufficient console logging for debugging
- No device capability detection display

## Solutions Implemented

### 1. Enhanced Video Loading (`player.html`)

#### **Better Codec Detection**
- **ALWAYS use `<source>` elements** instead of just setting `video.src`
- Explicitly set MIME types: `video/mp4; codecs="avc1.42E01E"`
- Helps Fire TV, Samsung, LG, and other smart TVs identify the correct codec

```javascript
// Before: Just setting video.src
v.src = url;

// After: Using source element with MIME type
var srcEl = document.createElement('source');
srcEl.src = url;
srcEl.type = 'video/mp4; codecs="avc1.42E01E"';
v.appendChild(srcEl);
v.src = url; // Also set as fallback
v.load();
```

#### **Amazon Fire TV Specific Attributes**
Added Fire TV / Silk browser specific attributes:
- `preload="auto"` - Fire TV can handle aggressive preloading
- `type="video/mp4"` - Explicit format hint
- `data-webos-player="true"` - LG webOS compatibility
- `data-tizen-player="true"` - Samsung Tizen compatibility

#### **CrossOrigin Handling**
Wrapped crossOrigin setting in try-catch to prevent failures on TVs that don't support it:
```javascript
try{ 
    v.crossOrigin = 'anonymous'; 
}catch(e){ 
    console.log('📹 [COMPAT] crossOrigin not supported, continuing anyway'); 
}
```

### 2. Comprehensive Error Logging

#### **Video Errors**
Enhanced error logging with:
- Error codes (1=ABORTED, 2=NETWORK, 3=DECODE, 4=SRC_NOT_SUPPORTED)
- Ready state (0-4 values with descriptions)
- Network state (0-3 values with descriptions)
- TV brand, model, and browser engine
- Codec support information

#### **Image Errors**
Added detailed image preload logging:
- Load start/success/error events
- Natural dimensions on error
- CrossOrigin compatibility handling

### 3. Error Recovery & User Feedback

#### **Consecutive Error Tracking**
- Tracks multiple failed media loads
- After 3 consecutive errors, shows diagnostic screen
- Automatically resets counter when media loads successfully

#### **Diagnostic Display**
Shows detailed information when errors occur:
- Device brand, model, browser engine
- Video codec support (H.264, H.265, VP9)
- Screen and store IDs
- Instructions to open browser console

Example diagnostic message:
```
⚠️ Media Loading Error

Unable to load media files.
This may be a compatibility issue.

📺 Device Info:
Brand: AMAZON
Model: Fire TV Stick 4K
Browser: silk

🎬 Video Support:
H.264: ✅ Yes
H.265: ✅ Yes
VP9: ✅ Yes

Screen: screen1
Store: store123

💡 Open browser console (F12) for detailed logs
```

### 4. Amazon Fire TV Configuration

The system already has Amazon Fire TV configuration in:
`static/tv-brands/amazon/config.js`

Key settings:
- **Hardware acceleration**: Enabled (Fire TV has good GPU)
- **Preferred codec**: H.264 (universal support)
- **Buffer size**: 30 seconds
- **Preload**: `auto` (aggressive)
- **Max bitrate**: 18 Mbps
- **Remote control**: Full support for Fire TV remote

## How to Test

### Testing on Amazon Fire TV

1. **Open the Silk Browser on Fire TV**
   - Press Home button
   - Go to "Internet" or "Silk Browser"
   - Navigate to your webplayer URL

2. **Check Console Logs**
   - Press Menu button on Fire TV remote
   - Look for developer options (may need to enable)
   - Or use remote debugging via ADB

3. **Look for These Log Messages**
   - `📹 [PRELOAD] Starting video preload for:` - Video loading started
   - `📹 [COMPAT] Using <source> element` - Codec detection active
   - `🔥 Amazon Fire TV configuration loaded` - TV detected
   - `✅ [IMAGE] Image loaded successfully` - Image working
   - `❌ [VIDEO ERROR]` - Video error with details

### Testing on Other TV Browsers

The fixes are universal and will help:
- **Samsung Tizen** - Source element + attributes
- **LG webOS** - Source element + attributes  
- **Sony Android TV** - Enhanced compatibility
- **Generic Smart TVs** - Better error handling

### Debug Mode

Add `?debug=1` to URL to enable debug mode:
```
https://your-domain.com/webplayer/play?store_id=XXX&screen_id=YYY&debug=1
```

Debug mode shows:
- Detailed diagnostic screen on errors
- All console logging
- Device capability information

## Expected Behavior

### On Success
- Videos and images load normally
- Console shows: `✅ [IMAGE] Image loaded successfully`
- Console shows: `✅ Video ready, readyState: 4`
- Error counter stays at 0

### On Failure (with new enhancements)
- Console shows detailed error information
- After 3 failures, diagnostic screen appears
- Shows device info and codec support
- Easier to identify the root cause

## Common Issues & Solutions

### Issue: "Video error code 4 (SRC_NOT_SUPPORTED)"
**Cause**: TV doesn't support the video codec
**Solution**: 
- Check video format (should be H.264 MP4)
- Verify video is properly encoded
- Check if file is accessible from TV's network

### Issue: "Image timeout after 6s"
**Cause**: Network connectivity or CORS issues
**Solution**:
- Check if images are accessible from TV's network
- Verify CDN is not blocking TV user agents
- Check if CORS headers are correct

### Issue: "crossOrigin not supported"
**Cause**: Some older TVs don't support crossOrigin
**Solution**: ✅ Already handled - wrapped in try-catch

### Issue: Multiple consecutive errors
**Cause**: Systematic compatibility or network issue
**Solution**: 
- Diagnostic screen will show after 3 errors
- Check console for specific error codes
- Verify media files are in compatible format

## Files Modified

1. **`templates/webplayer/player.html`**
   - Enhanced video preloading with source elements
   - Added comprehensive error logging
   - Implemented consecutive error tracking
   - Added diagnostic display screen
   - Improved image preloading with logging

2. **`static/tv-brands/amazon/config.js`**
   - Already optimized for Fire TV (no changes needed)

3. **`static/tv-brands/tv-detector.js`**
   - Already detects Amazon Fire TV properly

## Monitoring

The system now sends error events to the server when media fails:
```javascript
sendClientEvent('media_load_error', item, `Consecutive errors: ${consecutiveErrors}, Last: ${e.message}`)
```

You can monitor these in the server logs or add to dashboard analytics.

## Next Steps

1. **Test on Amazon Fire TV** to confirm fixes work
2. **Check browser console** for detailed diagnostic logs
3. **Verify video formats** are H.264 MP4 (most compatible)
4. **Monitor error events** from webplayer clients
5. **Report specific error codes** if issues persist

## Questions to Answer

When testing, please provide:
1. **TV Brand & Model**: e.g., "Amazon Fire TV Stick 4K"
2. **Console Error Messages**: Look for `❌ [VIDEO ERROR]` or `❌ [LOAD ERROR]`
3. **Error Code**: Will be shown in console (1, 2, 3, or 4)
4. **Diagnostic Screen**: Take photo if shown after 3 errors
5. **What shows**: Black screen, loading forever, error message, etc?

This information will help identify the specific issue if problems persist.
