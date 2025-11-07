# TV Browser Compatibility Reference

## Comprehensive Guide to Smart TV Browsers and Compatibility

This document provides detailed information about browser engines, capabilities, and compatibility requirements for major Smart TV brands.

---

## 🔵 **SAMSUNG TIZEN**

### Browser Engine
- **Engine**: Chromium-based (from Tizen 3.0+)
- **Versions**:
  - Tizen 2.3/2.4 (2015-2016): WebKit-based
  - Tizen 3.0+ (2017-present): Chromium 38-94 (varies by year)
  - Tizen 6.0/6.5 (2020-2022): Chromium 69-85
  - Tizen 7.0+ (2023-present): Chromium 94+

### Supported Features
✅ H.264 video codec (hardware accelerated)
✅ AAC audio codec
✅ WebGL 1.0/2.0
✅ Flexbox
✅ CSS Grid
✅ ES6 JavaScript
✅ Fetch API
✅ Promises
✅ LocalStorage/SessionStorage
✅ Web Sockets

❌ H.265/HEVC (limited, newer models only)
❌ VP9 (limited support)
❌ Service Workers
❌ PWA features

### Known Issues
- Older models (2015-2016) have limited ES6 support
- CSS Grid not supported on Tizen 2.x
- WebGL performance varies significantly by model year
- Memory constraints on lower-end models

### Recommended Settings
- Max video bitrate: 15-20 Mbps
- Prefer H.264 codec
- Use hardware acceleration
- Avoid complex CSS animations on older models
- Safe area: 5% margin

---

## 🟣 **LG webOS**

### Browser Engine
- **Engine**: Chromium-based (from webOS 3.0+)
- **Versions**:
  - webOS 1.x/2.x (2014-2015): WebKit-based
  - webOS 3.0-4.x (2016-2019): Chromium 38-53
  - webOS 5.0-6.0 (2020-2021): Chromium 68-79
  - webOS 22/23 (2022-2024): Chromium 87-94

### Supported Features
✅ H.264 video codec (hardware accelerated)
✅ H.265/HEVC (most models 2017+)
✅ AAC, MP3 audio
✅ WebGL 1.0/2.0
✅ Flexbox
✅ CSS Grid (webOS 3.5+)
✅ ES6 JavaScript
✅ Fetch API
✅ Promises
✅ LocalStorage

❌ VP9 (very limited)
❌ Service Workers
❌ Full PWA support

### Known Issues
- Magic Remote pointer requires special handling
- Cursor/pointer events work differently than standard mouse
- WebGL performance issues on webOS 3.x and earlier
- Memory management more aggressive than Samsung

### Recommended Settings
- Max video bitrate: 15-18 Mbps
- H.264 or H.265 codec
- Support pointer events for Magic Remote
- Use hardware acceleration
- Safe area: 4% margin

---

## 🔴 **SONY BRAVIA (Android TV)**

### Browser Engine
- **Engine**: Chromium-based (Android WebView)
- **Versions**:
  - Opera-based (pre-2015 models)
  - Android TV 5.x-7.x (2015-2018): Chromium 44-66
  - Android TV 8.x-9.x (2018-2020): Chromium 69-80
  - Android TV 10-12 (2020-2023): Chromium 83-108
  - Google TV (2021+): Chromium 90+

### Supported Features
✅ H.264 video codec
✅ H.265/HEVC (2016+ models)
✅ VP9 (2016+ models)
✅ AAC, MP3, Opus audio
✅ WebGL 1.0/2.0
✅ Flexbox
✅ CSS Grid (Android 8+)
✅ Full ES6+ support
✅ Fetch API
✅ Service Workers (Android 10+)
✅ PWA support (newer models)

❌ AV1 codec (very limited)

### Known Issues
- Older models (pre-2018) can be **significantly slower**
- Opera-based models have severe limitations
- Memory constraints on older Android TV versions
- Network performance can be inconsistent
- Some models have overheating issues affecting performance

### Recommended Settings
- Max video bitrate: 12-16 Mbps (conservative)
- H.264 codec (safest)
- Disable WebGL on older models
- Reduce animations
- Safe area: 6% margin (Sony needs more)
- Longer timeout values (35-40 seconds)

---

## 🟠 **PANASONIC VIERA**

### Browser Engine
- **Engine**: Firefox OS-based (older) / Chromium (newer)
- **Versions**:
  - My Home Screen 1.0-3.0 (2015-2019): Firefox OS (Gecko)
  - My Home Screen 4.0+ (2019-2021): Chromium 68-76
  - My Home Screen 5.0/6.0 (2022+): Chromium 83+

### Supported Features
✅ H.264 video codec
✅ H.265/HEVC (2017+ models)
✅ AAC, MP3 audio
✅ Flexbox (Chromium models)
✅ CSS Grid (Chromium models)
✅ ES6 (Chromium models)

❌ WebGL (limited/unreliable on Firefox OS models)
❌ VP9 (limited)
❌ Advanced CSS features on older models

### Known Issues
- **Firefox OS models have VERY different compatibility**
- Performance varies widely between model years
- Network stack can be slow
- CSS rendering issues on older models

### Recommended Settings
- Max video bitrate: 12-15 Mbps
- H.264 codec only
- Avoid WebGL unless confirmed support
- Simple CSS animations
- Safe area: 5% margin

---

## 🔵 **PHILIPS (Saphi / Android TV)**

### Browser Engine
- **Engine**: Dual platform
- **Saphi OS** (budget models): Chromium 53-68
- **Android TV** (premium models): Same as Sony above

### Supported Features (Saphi)
✅ H.264 video codec
✅ AAC audio
✅ Basic Flexbox
✅ Basic ES5/ES6

❌ CSS Grid (limited)
❌ WebGL (unreliable)
❌ H.265 (model dependent)
❌ Advanced CSS features

### Known Issues
- Saphi platform is **significantly limited**
- Performance comparable to 2015-era browsers
- Memory constraints
- Network performance issues

### Recommended Settings (Saphi)
- Max video bitrate: 10-14 Mbps
- H.264 codec only
- Avoid WebGL
- Conservative JavaScript
- Safe area: 5% margin

---

## 🟢 **HISENSE VIDAA**

### Browser Engine
- **Engine**: Chromium-based (custom)
- **Versions**:
  - VIDAA 2.x/3.x (2016-2019): Chromium 49-63
  - VIDAA 4.x (2020-2021): Chromium 72-80
  - VIDAA U5/U6 (2022+): Chromium 87+

### Supported Features
✅ H.264 video codec
✅ H.265/HEVC (most models)
✅ AAC audio
✅ WebGL 1.0
✅ Flexbox
✅ CSS Grid (U4+)
✅ ES6 JavaScript

❌ VP9 (limited)
❌ WebGL 2.0 (unreliable)

### Known Issues
- Performance inconsistent across models
- Network stack can have delays
- Memory management aggressive

### Recommended Settings
- Max video bitrate: 14-16 Mbps
- H.264 or H.265 codec
- WebGL with fallback
- Safe area: 4% margin

---

## ⚫ **TCL (Roku TV / Android TV / Google TV)**

### Browser Engine
- **Depends on platform**:
  - **Roku OS**: Proprietary (BrightScript, limited web)
  - **Android TV**: Chromium 69-108
  - **Google TV**: Chromium 90-108

### Supported Features (Android TV / Google TV)
✅ H.264, H.265/HEVC
✅ VP9
✅ AAC, MP3, Opus
✅ WebGL 1.0/2.0
✅ Flexbox, CSS Grid
✅ Full ES6+
✅ Modern web standards

### Roku OS Limitations
❌ **No web browser** (BrightScript only for apps)
❌ Must use Roku SDK for channel development
❌ Cannot run standard web apps

### Recommended Settings (Android TV / Google TV)
- Max video bitrate: 15-17 Mbps
- H.264 or H.265 codec
- Full web features available
- Safe area: 4% margin

---

## � **AMAZON FIRE TV**

### Browser Engine
- **Engine**: Fire OS (Android-based) with Chromium WebView
- **Browser**: Amazon Silk Browser (Chromium-based)
- **Versions**:
  - Fire OS 5 (2014-2017): Android 5.1 Lollipop (API 22)
  - Fire OS 6 (2017-2019): Android 7.1 Nougat (API 25)  
  - Fire OS 7 (2019-2023): Android 9 Pie (API 28)
  - Fire OS 8 (2023-present): Android 10-11 (API 29-30)
  - Vega OS (2025+): New Linux-based OS

### Supported Features
✅ H.264 video codec (all models)
✅ H.265/HEVC (Fire TV Stick 4K, Cube, 2015+ models)
✅ VP9 (Fire TV Stick 4K, Cube, 2018+ models)
✅ AV1 (Fire TV Stick 4K Max 2021+)
✅ AAC, MP3, Opus audio
✅ WebGL 1.0/2.0 (Fire OS 6+)
✅ Flexbox
✅ CSS Grid (Fire OS 7+)
✅ ES6+ JavaScript (Fire OS 6+)
✅ Fetch API
✅ Promises
✅ LocalStorage
✅ Dolby Vision (Fire TV Stick 4K, Cube)
✅ Dolby Atmos (Fire TV Stick 4K, Cube)

❌ Some Google services (replaced with Amazon services)

### Known Issues
- Fire OS 5 devices (2014-2017) have limited ES6 support
- Older Fire TV Stick models (pre-2018) have performance constraints
- Amazon Silk browser has quirks compared to Chrome
- Some Fire TV Edition TVs have slower hardware

### Recommended Settings
- Max video bitrate: 15-18 Mbps
- H.264 primary, H.265 for 4K models
- Use hardware acceleration
- Alexa voice integration available
- Safe area: 4% margin

### Device Lineup
**Streaming Devices:**
- Fire TV Stick HD ($30-40)
- Fire TV Stick (standard) ($40-50)
- Fire TV Stick 4K ($50-60)
- Fire TV Stick 4K Max ($55-70) - Most powerful stick
- Fire TV Cube ($140) - Hands-free Alexa

**Fire TV Edition TVs:**
- Insignia, Toshiba, JVC, Grundig, Hisense, TCL branded TVs with Fire OS built-in
- Available in HD, FHD, and 4K resolutions

---

## 🇦🇺 **KOGAN TV**

### Browser Engine
- **Engine**: Varies by OEM manufacturer
- **Most common**: Android TV (Chromium-based)
- **Versions**: Depends on model year and OEM
  - Older models (pre-2018): Various Linux-based systems
  - Modern models (2018+): Android TV 9-11

### Supported Features (Conservative Estimate)
✅ H.264 video codec (all models)
✅ AAC, MP3 audio
✅ Basic Flexbox
✅ Basic ES5/ES6 JavaScript

⚠️ H.265/HEVC (premium models only)
⚠️ WebGL (newer models only)
⚠️ CSS Grid (Android TV models only)
⚠️ VP9 (very limited)
⚠️ 4K support (model dependent)

❌ HDR (budget models)
❌ Dolby Vision (most models)
❌ Advanced codecs

### Known Issues
- **Extreme variation** between models (OEM manufactured)
- Kogan TVs made by TCL, Hisense, and other OEMs
- Budget hardware = performance constraints
- Older models have very limited browser capabilities
- Some models may not support modern web standards

### Recommended Settings
- Max video bitrate: 12-15 Mbps (conservative)
- H.264 codec only (safest)
- Avoid WebGL and advanced CSS
- Disable GPU acceleration on older models
- Safe area: 5% margin
- Longer timeout values (35+ seconds)

### Market Information
- **Region**: Primarily Australia and New Zealand
- **Brand**: Kogan.com (Australian e-commerce company)
- **Manufacturing**: OEM manufactured (not in-house)
- **Positioning**: Value/budget brand
- **Quality**: Varies significantly by model and year

### Device Recognition
Detection can be challenging due to OEM manufacturing:
- User agent may show OEM brand (TCL, Hisense, etc.)
- May include "Kogan" in UA string
- Often detected as Android TV generically

---

## �🟤 **TOSHIBA**

### Browser Engine
- **Engine**: Varies widely by model
- **Older models** (pre-2018): Opera TV
- **Newer models** (2018+): Android TV (Chromium)
- **Budget models**: Firefox OS or custom

### Supported Features (varies greatly)
- Android TV models: Same as Sony
- Opera TV models: **Very limited** (Presto engine)
- Firefox OS models: Gecko engine limitations

### Known Issues
- **Extreme variation** between models
- Opera TV models are obsolete
- Poor documentation
- Inconsistent performance

### Recommended Settings
- Max video bitrate: 12-14 Mbps
- H.264 codec only (safest)
- Conservative feature use
- Safe area: 6% margin
- Long timeouts

---

## 🔘 **GENERIC / UNKNOWN TVs**

### Fallback Strategy
When TV brand cannot be detected or for less common brands:

### Conservative Settings
- **Video**: H.264 only, max 10-12 Mbps
- **Audio**: AAC or MP3
- **JavaScript**: ES5 baseline, basic ES6
- **CSS**: Flexbox only (no Grid)
- **Features**: No WebGL, no advanced APIs
- **Safe area**: 8% margin (maximum)
- **Timeouts**: 40+ seconds
- **Network**: Aggressive retry logic

### Detection Fallbacks
1. Feature detection over browser detection
2. Progressive enhancement approach
3. Graceful degradation for all features
4. Extensive error handling
5. Fallback video/image formats

---

## 📊 COMPATIBILITY MATRIX

| Feature | Samsung Tizen | LG webOS | Sony Android | Amazon Fire TV | Panasonic | Philips | Hisense | TCL Android | Kogan | Generic |
|---------|--------------|----------|--------------|----------------|-----------|---------|---------|-------------|-------|---------|
| H.264 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| H.265 | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | ❌ |
| VP9 | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ⚠️ | ✅ | ❌ | ❌ |
| AV1 | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| WebGL | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ⚠️ | ✅ | ⚠️ | ❌ |
| CSS Grid | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ⚠️ | ✅ | ⚠️ | ❌ |
| Flexbox | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ES6 | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | ⚠️ |
| Fetch API | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ✅ | ✅ | ⚠️ | ❌ |

Legend: ✅ Full Support | ⚠️ Partial/Model Dependent | ❌ Not Supported

---

## 🎯 BEST PRACTICES

### Video Delivery
1. **Always provide H.264 as fallback**
2. Use adaptive bitrate streaming when possible
3. Implement buffer monitoring
4. Have multiple quality levels
5. Detect bandwidth and adjust automatically

### CSS Strategy
1. Use Flexbox as baseline
2. Feature-detect CSS Grid
3. Avoid complex animations
4. Use hardware acceleration wisely
5. Test safe areas on real devices

### JavaScript Approach
1. Transpile to ES5 baseline
2. Polyfill carefully (bundle size!)
3. Feature detection, not browser detection
4. Extensive error handling
5. Performance budgets

### Network Handling
1. Implement aggressive retry logic
2. Use longer timeouts (30-40s)
3. Cache aggressively
4. Offline capability when possible
5. Monitor connection quality

### Testing Priority
1. Samsung Tizen (largest market share)
2. LG webOS (second largest)
3. Android TV/Google TV (growing)
4. Others as resources allow

---

## 📚 RESOURCES

- Samsung Tizen: https://developer.samsung.com/smarttv
- LG webOS: https://webostv.developer.lge.com/
- Android TV: https://developer.android.com/tv
- Can I Use: https://caniuse.com/
- TV Browser Testing: BrowserStack Real Devices

---

Last Updated: October 2025
