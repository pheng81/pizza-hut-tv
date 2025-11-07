# 🔧 Android TV Rotation Troubleshooting Guide

## Current Status
✅ **Crash fixes applied** - App should no longer crash  
🔄 **Rotation debugging enhanced** - Multiple fallback methods added  
🐛 **Debug mode available** - Enhanced debugging with visual indicators  

## 🎯 How to Test Rotation

### 1. **Open Debug Mode**
```
http://your-server/tv_view.html?debug=1
```

### 2. **Look for Debug Elements**
When debug mode is active, you should see:
- 🔄 **Rotation controls** in top-right corner (buttons: 0°, 90°, 180°, 270°)
- 📊 **Blue rotation indicator** in center showing current angle
- 💬 **Debug messages** in bottom-left corner with timestamps

### 3. **Automatic Rotation Test**
The app automatically tests rotation on startup:
- Waits 500ms after init
- Tests basic `applyOrientation()` 
- Tests 90° rotation after 2 seconds
- Resets to 0° after 3 more seconds
- Watch debug messages for results

### 4. **Manual Testing**
Click the rotation buttons in top-right:
- **0°** = Normal orientation
- **90°** = Portrait mode  
- **180°** = Upside down
- **270°** = Landscape flipped
- **Auto Test** = Cycles through all rotations
- **Reset** = Back to server settings

## 🔍 Debug Messages to Watch For

### ✅ **Success Messages**
```
ROTATION: Applying transform: rotate(90deg) scale(1.77778)
ROTATION: Style transform: rotate(90deg) scale(1.77778)  
ROTATION: Computed transform: matrix(...)
ROTATION: Transform successfully applied
```

### ⚠️ **Warning Messages**
```
ROTATION: WARNING - Transform not applied!
ROTATION: Applied to body as fallback
```
*This means CSS transforms on #stage failed, trying fallback*

### ❌ **Error Messages** 
```
ROTATION: applyOrientation failed: [error details]
ROTATION: Transform application failed: [error details]
ROTATION: stage element not found
```
*These indicate serious problems*

## 🐛 Common Issues & Solutions

### **Issue 1: No Rotation Controls Visible**
**Problem:** Debug mode not working  
**Solution:** 
1. Make sure URL includes `?debug=1`
2. Check browser console for JavaScript errors
3. Try clearing browser cache

### **Issue 2: Rotation Controls Visible but No Movement**
**Problem:** CSS transforms not supported or blocked  
**Symptoms:** Debug shows "Transform not applied" warnings  
**Solutions:**
1. **Try different Android TV WebView settings:**
   ```
   Settings > Apps > WebView > Enable Hardware Acceleration
   Settings > Developer Options > Enable GPU Rendering  
   ```

2. **Test alternative transform methods:**
   - The app tries multiple CSS prefixes (-webkit-, -moz-, -ms-)
   - Falls back to applying transform to `<body>` element
   - Forces hardware acceleration with `backface-visibility`

### **Issue 3: Partial Rotation (Only Indicator Rotates)**
**Problem:** Only the blue indicator rotates, main content doesn't  
**Root Cause:** Android WebView doesn't support transforms on fixed positioned elements  
**Solution:** This is a known Android WebView limitation on some devices

### **Issue 4: App Still Crashes**
**Problem:** JavaScript errors causing crashes  
**Check Debug Messages For:**
```
ERROR: [error message]
PROMISE ERROR: [promise rejection]
applyOrientation failed: [details]
initialization failed: [details]  
```
**Solution:** Report the exact error message for specific fix

## 📊 Advanced Debugging

### **Check WebView Capabilities**
Add this to URL: `?debug=1&test=webview`
```javascript
// Test CSS transform support
console.log('Transform support:', 'transform' in document.body.style);
console.log('WebKit transform:', 'webkitTransform' in document.body.style);
console.log('Hardware acceleration:', 'backfaceVisibility' in document.body.style);
```

### **Test Different Approaches**
If standard rotation fails, we can try:

1. **Matrix transforms** instead of rotate()
2. **Viewport meta changes** 
3. **Canvas-based rotation** (more complex)
4. **Server-side image/video rotation** (fallback)

## 🎯 Expected Behavior

### **Working Rotation:**
1. Click 90° button
2. Debug shows: "Applying transform: rotate(90deg) scale(1.77778)"  
3. Content rotates 90° clockwise
4. Blue indicator shows "90°"
5. Scale factor fills screen properly (no black bars)

### **Working Auto-Rotation:**  
1. Content detects portrait video on landscape screen
2. Automatically rotates to maximize screen usage
3. Debug shows orientation logic

## 🚀 Next Steps

1. **Test on your Android TV device:**
   ```
   http://YOUR_IP/rotation_debug.html
   ```

2. **Try the main app with debug:**
   ```  
   http://YOUR_IP/tv_view.html?debug=1
   ```

3. **Report back what you see:**
   - Do rotation controls appear?
   - Does the blue indicator rotate when you click buttons?
   - Does the actual content rotate?
   - What debug messages appear?

4. **If rotation still doesn't work:**
   - We'll implement alternative rotation methods
   - Possibly server-side video pre-rotation
   - Or layout-based orientation changes

## 💡 Alternative Solutions Ready

If CSS transforms don't work on your Android TV, I have backup plans:

1. **Flexbox-based rotation simulation**
2. **Viewport manipulation** 
3. **Media query responsive design**
4. **Server-side media transformation**

The key is identifying exactly where the failure occurs so we can pick the right alternative approach.

---

**🎯 Goal:** Get the blue rotation indicator working first. If that works, the main content rotation should work too. If the indicator doesn't rotate, we know it's a fundamental CSS transform issue and need alternative approaches.