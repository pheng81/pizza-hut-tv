/**
 * Panasonic Viera TV Configuration
 * 
 * IMPORTANT: Panasonic uses different platforms:
 * - My Home Screen 1.0-3.0 (2015-2019): Firefox OS (Gecko engine)
 * - My Home Screen 4.0+ (2019+): Chromium-based
 * 
 * This config is conservative to support Firefox OS models.
 */

window.TVConfig = {
  brand: 'panasonic',
  video: {
    preferredCodec: 'h264', // Firefox OS requires H.264
    fallbackCodecs: ['h264'], // No H.265 on Firefox OS
    maxBitrate: 13000000, // 13 Mbps - Conservative for Firefox OS
    bufferSize: 25,
    preload: 'auto',
    hardwareAcceleration: true
  },
  performance: {
    enableGPU: false, // Firefox OS has GPU issues
    useWebGL: false, // Unreliable on Firefox OS models
    reducedMotion: true, // Better for older Firefox OS
    lazyLoad: true,
    firefoxOSMode: true // Flag for Firefox OS compatibility
  },
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Back', // Firefox OS uses different key
      navigationKeys: ['Up', 'Down', 'Left', 'Right']
    },
    fontSize: 'medium',
    margin: '5%'
  },
  network: {
    retryAttempts: 5,
    timeout: 38000, // Longer for Firefox OS
    keepAlive: true
  },
  
  // Panasonic-specific information
  notes: {
    firefoxOS: 'My Home Screen 1.0-3.0 use Firefox OS (Gecko)',
    chromium: 'My Home Screen 4.0+ use Chromium',
    recommendation: 'Test CSS carefully on Firefox OS models'
  }
};

console.log('🟠 Panasonic Viera configuration loaded');
