# TV Brand-Specific Configuration System

## Overview
This folder structure contains brand-specific configurations and optimizations for different TV manufacturers. Each brand has its own isolated configuration to prevent cross-contamination of settings.

## Folder Structure
```
static/tv-brands/
├── tv-detector.js          # Main detection script
├── samsung/
│   ├── config.js          # Samsung-specific settings
│   └── style.css          # Samsung-specific styles
├── lg/
│   ├── config.js          # LG webOS settings
│   └── style.css          # LG-specific styles
├── sony/
│   ├── config.js          # Sony Bravia settings
│   └── style.css          # Sony-specific styles
├── panasonic/
│   ├── config.js          # Panasonic Viera settings
│   └── style.css          # (optional styles)
├── philips/
│   ├── config.js          # Philips settings
│   └── style.css          # (optional styles)
├── toshiba/
│   ├── config.js          # Toshiba settings
│   └── style.css          # (optional styles)
├── hisense/
│   ├── config.js          # Hisense/Vidaa settings
│   └── style.css          # (optional styles)
├── tcl/
│   ├── config.js          # TCL settings
│   └── style.css          # (optional styles)
└── generic/
    ├── config.js          # Fallback configuration
    └── style.css          # Fallback styles
```

## How It Works

### 1. **Automatic Detection**
- The `tv-detector.js` script automatically detects the TV brand from the user agent
- It identifies the browser engine (Tizen, webOS, Opera, etc.)
- It detects TV capabilities (codecs, WebGL, resolution, etc.)

### 2. **Brand-Specific Loading**
- Once detected, it loads the appropriate `config.js` and `style.css` for that brand
- If no specific configuration exists, it falls back to `generic/`

### 3. **Configuration Options**
Each brand's `config.js` can customize:
- **Video Settings**: Preferred codec, bitrate, buffer size
- **Performance**: GPU acceleration, WebGL usage, animations
- **UI Settings**: Focus styles, remote control mappings, font sizes, safe areas
- **Network Settings**: Retry attempts, timeouts, keep-alive

### 4. **Style Overrides**
Each brand's `style.css` can customize:
- Focus/highlight styles (different colors per brand)
- Safe area margins (varies by TV manufacturer)
- Button sizes and spacing
- Video rendering optimization
- Animation timing

## Usage in Web Player

Add this to your web player HTML `<head>`:

```html
<!-- TV Brand Detection -->
<script src="{{ url_for('static', filename='tv-brands/tv-detector.js') }}"></script>
```

Then in your JavaScript:

```javascript
// Access detected TV info
const tvInfo = window.tvDetector.getBrandInfo();
console.log('TV Brand:', tvInfo.brand);
console.log('Capabilities:', tvInfo.capabilities);

// Access TV-specific configuration
if (window.TVConfig) {
  // Use TV-specific settings
  const videoBitrate = window.TVConfig.video.maxBitrate;
  const bufferSize = window.TVConfig.video.bufferSize;
}
```

## Supported TV Brands

### ✅ Fully Configured
- **Samsung** (Tizen OS) - Blue focus, high performance
- **LG** (webOS) - Red focus, pointer support
- **Sony** (Bravia) - Conservative settings for older models

### ⚙️ Basic Configuration
- **Panasonic** (Viera)
- **Philips** (Saphi/Android)
- **Toshiba**
- **Hisense** (Vidaa)
- **TCL** (Android TV)

### 🔄 Fallback
- **Generic** - Used for unknown brands (conservative settings)

## Adding a New TV Brand

1. Create folder: `static/tv-brands/[brand-name]/`
2. Add `config.js` with TVConfig object
3. (Optional) Add `style.css` for visual customizations
4. Update `tv-detector.js` to detect the brand's user agent

Example:
```javascript
// In config.js
window.TVConfig = {
  brand: 'yourbrand',
  video: { ... },
  performance: { ... },
  ui: { ... },
  network: { ... }
};
```

## Testing

To test detection, open browser console on the TV and check:
```javascript
window.tvDetector.getBrandInfo()
```

This will show:
- Detected brand
- Browser engine
- Model information
- Full capabilities list

## Benefits

✅ **Isolation**: Changes to Samsung config won't affect LG TVs
✅ **Optimization**: Each brand gets optimal settings for its hardware
✅ **Maintainability**: Easy to update individual brand settings
✅ **Scalability**: Simple to add new TV brands
✅ **Fallback**: Unknown TVs get safe, conservative settings
✅ **Performance**: Only loads what's needed for detected TV

## Notes

- Samsung TVs benefit most from GPU acceleration
- LG webOS has unique Magic Remote (pointer support)
- Sony Bravia older models need conservative settings
- Generic fallback ensures compatibility with all TVs
- Safe areas vary significantly between manufacturers
