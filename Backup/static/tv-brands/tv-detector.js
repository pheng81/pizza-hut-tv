/**
 * TV Brand Detection and Configuration System
 * Detects TV brand and loads brand-specific optimizations
 */

class TVBrandDetector {
  constructor() {
    this.brand = 'generic';
    this.model = 'unknown';
    this.browserEngine = 'unknown';
    this.capabilities = {};
    this.detect();
    // Apply brand/engine classes early
    this.applyBrandClasses();
  }

  detect() {
    const ua = navigator.userAgent.toLowerCase();
    const vendor = navigator.vendor ? navigator.vendor.toLowerCase() : '';
    
    // Detect TV Brand
    if (ua.includes('samsung') || ua.includes('tizen')) {
      this.brand = 'samsung';
      this.browserEngine = 'tizen';
      this.detectSamsungModel(ua);
    } else if (ua.includes('lg') || ua.includes('webos') || ua.includes('netcast')) {
      this.brand = 'lg';
      this.browserEngine = 'webos';
      this.detectLGModel(ua);
    } else if (ua.includes('sony') || ua.includes('bravia')) {
      this.brand = 'sony';
      this.browserEngine = 'opera';
      this.detectSonyModel(ua);
    } else if (ua.includes('aft') || ua.includes('fire') || ua.includes('amazon')) {
      // Amazon Fire TV detection (AFT = Amazon Fire TV device codes)
      this.brand = 'amazon';
      this.browserEngine = 'fireos';
      this.detectFireTVModel(ua);
    } else if (ua.includes('kogan')) {
      this.brand = 'kogan';
      this.browserEngine = 'android'; // Most Kogan TVs use Android TV
      this.model = 'Kogan TV';
    } else if (ua.includes('philips')) {
      this.brand = 'philips';
      this.browserEngine = 'saphi';
    } else if (ua.includes('panasonic') || ua.includes('viera')) {
      this.brand = 'panasonic';
      this.browserEngine = 'firefox';
    } else if (ua.includes('toshiba')) {
      this.brand = 'toshiba';
      this.browserEngine = 'opera';
    } else if (ua.includes('hisense') || ua.includes('vidaa')) {
      this.brand = 'hisense';
      this.browserEngine = 'vidaa';
    } else if (ua.includes('tcl')) {
      this.brand = 'tcl';
      this.browserEngine = 'android';
    } else if (ua.includes('sharp') || ua.includes('aquos')) {
      this.brand = 'sharp';
      this.browserEngine = 'opera';
    } else if (ua.includes('vizio')) {
      this.brand = 'vizio';
      this.browserEngine = 'smartcast';
    }
    
    // Detect capabilities
    this.detectCapabilities();
    
    console.log(`🖥️ TV Brand Detected: ${this.brand.toUpperCase()}`);
    console.log(`🔧 Browser Engine: ${this.browserEngine}`);
    console.log(`📱 Model: ${this.model}`);
    console.log(`✨ Capabilities:`, this.capabilities);
  }

  applyBrandClasses(){
    try{
      const root = document.documentElement;
      const b = `tv-brand-${this.brand}`;
      const e = `tv-engine-${this.browserEngine}`;
      if(!root.classList.contains(b)) root.classList.add(b);
      if(!root.classList.contains(e)) root.classList.add(e);
    }catch(e){}
  }

  detectSamsungModel(ua) {
    if (ua.includes('smart-tv')) {
      const match = ua.match(/smart-tv\/([\d.]+)/);
      if (match) this.model = 'Tizen ' + match[1];
    }
  }

  detectLGModel(ua) {
    if (ua.includes('webos')) {
      const match = ua.match(/webos\/([\d.]+)/);
      if (match) this.model = 'webOS ' + match[1];
    }
  }

  detectSonyModel(ua) {
    if (ua.includes('bravia')) {
      this.model = 'Bravia';
    }
  }

  detectFireTVModel(ua) {
    // Amazon Fire TV device detection
    if (ua.includes('aftmm')) {
      this.model = 'Fire TV Stick 4K';
    } else if (ua.includes('aftka')) {
      this.model = 'Fire TV Stick 4K Max';
    } else if (ua.includes('aftr')) {
      this.model = 'Fire TV Cube';
    } else if (ua.includes('afts') || ua.includes('aftss')) {
      this.model = 'Fire TV Stick';
    } else if (ua.includes('aft')) {
      this.model = 'Fire TV';
    } else {
      this.model = 'Fire TV Device';
    }
    
    // Detect Fire OS version
    if (ua.includes('fireos/8')) {
      this.model += ' (Fire OS 8)';
    } else if (ua.includes('fireos/7')) {
      this.model += ' (Fire OS 7)';
    } else if (ua.includes('fireos/6')) {
      this.model += ' (Fire OS 6)';
    }
  }

  detectCapabilities() {
    this.capabilities = {
      // Video codecs
      h264: this.supportsVideoCodec('video/mp4; codecs="avc1.42E01E"'),
      h265: this.supportsVideoCodec('video/mp4; codecs="hev1.1.6.L93.B0"'),
      vp8: this.supportsVideoCodec('video/webm; codecs="vp8"'),
      vp9: this.supportsVideoCodec('video/webm; codecs="vp9"'),
      
      // Audio codecs
      aac: this.supportsAudioCodec('audio/mp4; codecs="mp4a.40.2"'),
      mp3: this.supportsAudioCodec('audio/mpeg'),
      opus: this.supportsAudioCodec('audio/ogg; codecs="opus"'),
      
      // Features
      webgl: this.supportsWebGL(),
      websocket: 'WebSocket' in window,
      localStorage: this.supportsLocalStorage(),
      flexbox: this.supportsFlexbox(),
      grid: this.supportsGrid(),
      fetch: 'fetch' in window,
      promises: 'Promise' in window,
      
      // Media features
      mse: 'MediaSource' in window,
      eme: 'requestMediaKeySystemAccess' in navigator,
      pip: 'pictureInPictureEnabled' in document,
      
      // Resolution
      maxWidth: screen.width,
      maxHeight: screen.height,
      pixelRatio: window.devicePixelRatio || 1
    };
  }

  supportsVideoCodec(type) {
    const video = document.createElement('video');
    return video.canPlayType(type) !== '';
  }

  supportsAudioCodec(type) {
    const audio = document.createElement('audio');
    return audio.canPlayType(type) !== '';
  }

  supportsWebGL() {
    try {
      const canvas = document.createElement('canvas');
      return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
    } catch (e) {
      return false;
    }
  }

  supportsLocalStorage() {
    try {
      localStorage.setItem('test', 'test');
      localStorage.removeItem('test');
      return true;
    } catch (e) {
      return false;
    }
  }

  supportsFlexbox() {
    const div = document.createElement('div');
    div.style.display = 'flex';
    return div.style.display === 'flex';
  }

  supportsGrid() {
    const div = document.createElement('div');
    div.style.display = 'grid';
    return div.style.display === 'grid';
  }

  getConfigPath() {
    return `/static/tv-brands/${this.brand}/config.js`;
  }

  getStylePath() {
    return `/static/tv-brands/${this.brand}/style.css`;
  }

  async loadBrandConfig() {
    const path = this.getConfigPath();
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) {
        console.log(`ℹ️ No brand config at ${path}, will use fallback`);
        return false;
      }
      await new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = path;
        script.onload = () => resolve(true);
        script.onerror = () => resolve(false);
        document.head.appendChild(script);
      });
      console.log(`✅ Loaded ${this.brand} configuration`);
      return true;
    } catch (e) {
      console.log(`ℹ️ No specific configuration for ${this.brand}`);
      return false;
    }
  }

  async loadBrandStyles() {
    const path = this.getStylePath();
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) return false;
      await new Promise((resolve)=>{
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = path;
        link.onload = () => resolve(true);
        link.onerror = () => resolve(false);
        document.head.appendChild(link);
      });
      console.log(`✅ Loaded ${this.brand} styles`);
      return true;
    } catch (e) {
      console.log(`ℹ️ No specific styles for ${this.brand}`);
      return false;
    }
  }

  getBrandInfo() {
    return {
      brand: this.brand,
      model: this.model,
      browserEngine: this.browserEngine,
      capabilities: this.capabilities
    };
  }
}

// Create global instance
window.tvDetector = new TVBrandDetector();

// Expose readiness promise to coordinate with player
window.tvBrandReady = new Promise((resolve) => {
  window.addEventListener('DOMContentLoaded', async () => {
    const cfgLoaded = await window.tvDetector.loadBrandConfig();
    await window.tvDetector.loadBrandStyles();

    // Fallback TVConfig if brand config didn't define it
    if (typeof window.TVConfig === 'undefined') {
      // Minimal safe defaults; brand-specific generic config will still be fetched if present elsewhere
      window.TVConfig = {
        brand: window.tvDetector.brand || 'generic',
        video: { preferredCodec: 'h264', maxBitrate: 12000000, bufferSize: 15, preload: 'metadata', hardwareAcceleration: false },
        performance: { enableGPU: false, useWebGL: false, reducedMotion: true, lazyLoad: true },
        ui: { fontSize: 'large', margin: '6%', remoteControl: { enabled: true } },
        network: { retryAttempts: 6, timeout: 35000, keepAlive: true }
      };
      console.log('ℹ️ Using inline generic TVConfig fallback');
    }

    // Apply UI hints from config
    try{
      const root = document.documentElement;
      if (window.TVConfig && window.TVConfig.performance && window.TVConfig.performance.reducedMotion) {
        root.classList.add('reduced-motion');
      }
      // Safe area CSS var for brand-specific margins (used optionally by player)
      const margin = (window.TVConfig && window.TVConfig.ui && window.TVConfig.ui.margin) ? window.TVConfig.ui.margin : '0';
      root.style.setProperty('--tv-safe-margin', margin);
    }catch(e){}

    resolve(true);
  }, { once: true });
});
