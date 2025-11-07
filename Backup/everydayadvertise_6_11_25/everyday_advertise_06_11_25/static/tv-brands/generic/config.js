/**
 * Generic TV Configuration
 * Fallback configuration for unknown TV brands
 */

window.TVConfig = {
  brand: 'generic',
  
  // Conservative video settings
  video: {
    preferredCodec: 'h264',
    maxBitrate: 12000000, // 12 Mbps - safe for most TVs
    bufferSize: 15,
    preload: 'metadata',
    hardwareAcceleration: false // Play safe
  },
  
  // Conservative performance settings
  performance: {
    enableGPU: false,
    useWebGL: false,
    reducedMotion: true,
    lazyLoad: true
  },
  
  // Generic UI settings
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Backspace',
      navigationKeys: ['Up', 'Down', 'Left', 'Right', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']
    },
    fontSize: 'large',
    margin: '8%' // Extra safe area
  },
  
  // Network settings
  network: {
    retryAttempts: 8,
    timeout: 40000,
    keepAlive: true
  }
};

console.log('⚪ Generic TV configuration loaded');
