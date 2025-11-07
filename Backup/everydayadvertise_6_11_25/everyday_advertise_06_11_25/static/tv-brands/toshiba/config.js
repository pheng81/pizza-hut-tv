/**
 * Toshiba TV Configuration
 */

window.TVConfig = {
  brand: 'toshiba',
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
    reducedMotion: true,
    lazyLoad: true
  },
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Return',
      navigationKeys: ['Up', 'Down', 'Left', 'Right']
    },
    fontSize: 'medium',
    margin: '6%'
  },
  network: {
    retryAttempts: 6,
    timeout: 35000,
    keepAlive: true
  }
};

console.log('🟤 Toshiba TV configuration loaded');
