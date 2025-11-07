/**
 * Samsung Tizen TV Configuration
 * Optimized for Samsung Smart TVs (Tizen OS)
 */

window.TVConfig = {
  brand: 'samsung',
  
  // Video settings optimized for Samsung
  video: {
    preferredCodec: 'h264',
    maxBitrate: 20000000, // 20 Mbps
    bufferSize: 30, // seconds
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
  
  // UI adjustments for Samsung remote
  ui: {
    focusStyle: 'highlight', // Samsung uses highlight style
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Return',
      navigationKeys: ['Up', 'Down', 'Left', 'Right']
    },
    fontSize: 'large', // Tizen TVs are usually 4K
    margin: '5%' // Safe area for Samsung TVs
  },
  
  // Network settings
  network: {
    retryAttempts: 5,
    timeout: 30000,
    keepAlive: true
  },
  
  // Samsung-specific APIs
  samsungAPIs: {
    useTizenAPI: true,
    useAvplay: true // Samsung's advanced video player
  }
};

console.log('🔵 Samsung Tizen configuration loaded');
