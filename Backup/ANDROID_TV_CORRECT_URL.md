# ✅ CORRECT ANDROID TV URL FORMAT

## 🚨 The Issue
You're getting "Not Found" because the URL format is incorrect.

## ❌ WRONG URL:
```
https://everydayadvertise.com/tv_view.html?debug=1&store_id=1931&screen_id=1931_promo1
```

## ✅ CORRECT URL:
```
https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1
```

## 📋 URL Format Explanation:
```
https://everydayadvertise.com/tv_view/<STORE_ID>/<SCREEN_ID>?debug=1
                                      └─────────┘ └──────────┘ └───────┘
                                      Required    Required     Optional
```

## 🎯 Your Specific URLs:

### Screen: 1931_promo1
```
https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1
```

### Screen: 1931_screen1
```
https://everydayadvertise.com/tv_view/1931/1931_screen1?debug=1
```

### Screen: 1931_screen2
```
https://everydayadvertise.com/tv_view/1931/1931_screen2?debug=1
```

### Screen: 1931_screen3
```
https://everydayadvertise.com/tv_view/1931/1931_screen3?debug=1
```

### Screen: 1931_screen4
```
https://everydayadvertise.com/tv_view/1931/1931_screen4?debug=1
```

## 🔍 Debug Mode:
- **With Debug**: Add `?debug=1` to see rotation messages and test controls
- **Without Debug**: Remove `?debug=1` for production use

## 📱 Testing Steps:

1. **Open Android TV browser**
2. **Navigate to**:
   ```
   https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1
   ```
3. **You should see**:
   - Content playing fullscreen
   - Debug overlay in bottom-left (if `?debug=1`)
   - Rotation test controls in top-right (if `?debug=1`)

4. **Open Dashboard** (on another device):
   ```
   https://everydayadvertise.com/dashboard
   ```

5. **Click rotation button** for the screen

6. **Expected Result**:
   - Android TV rotates within 1-3 seconds
   - Debug overlay shows: `POLL: Rotation changed from 0° to 90°`
   - Debug overlay shows: `ROTATION: 90° rotation applied`

## 🚀 Quick Test Links:

### Test Rotation on Promo1:
1. Android TV: https://everydayadvertise.com/tv_view/1931/1931_promo1?debug=1
2. Dashboard: https://everydayadvertise.com/dashboard
3. Click rotation icon next to "1931_promo1"
4. Watch Android TV rotate instantly

---

**Status**: 🟢 Ready to test with correct URL format
