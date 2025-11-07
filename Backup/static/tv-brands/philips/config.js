/**
 * Philips TV Configuration
 */

window.TVConfig = {
  brand: 'philips',
  video: {
    preferredCodec: 'h264',
    maxBitrate: 14000000,
    bufferSize: 18,
    preload: 'metadata',
    hardwareAcceleration: true
  },
  performance: {
    enableGPU: true,
    useWebGL: false,
    reducedMotion: false,
    lazyLoad: true
  },
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Back',
      navigationKeys: ['Up', 'Down', 'Left', 'Right']
    },
    fontSize: 'medium',
    margin: '5%'
  },
  network: {
    retryAttempts: 5,
    timeout: 30000,
    keepAlive: true
  }
};

console.log('🔵 Philips TV configuration loaded');
