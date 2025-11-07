/**
 * LG webOS TV Configuration
 * Optimized for LG Smart TVs (webOS)
 */

window.TVConfig = {
  brand: 'lg',
  
  // Video settings optimized for LG
  video: {
    preferredCodec: 'h264',
    maxBitrate: 18000000, // 18 Mbps
    bufferSize: 25,
    preload: 'auto',
    hardwareAcceleration: true
  },
  
  // Performance optimizations
  performance: {
    enableGPU: true,
    useWebGL: true,
    reducedMotion: false,
    lazyLoad: true
  },
  
  // UI adjustments for LG Magic Remote
  ui: {
    focusStyle: 'pointer', // LG uses pointer/cursor
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Back',
      navigationKeys: ['Up', 'Down', 'Left', 'Right'],
      pointerSupport: true // LG Magic Remote has pointer
    },
    fontSize: 'large',
    margin: '4%'
  },
  
  // Network settings
  network: {
    retryAttempts: 5,
    timeout: 30000,
    keepAlive: true
  },
  
  // LG-specific APIs
  lgAPIs: {
    useWebOSAPI: true,
    useLunaService: true
  }
};

console.log('🟣 LG webOS configuration loaded');
