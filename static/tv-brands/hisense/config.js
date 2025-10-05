/**
 * Hisense/Vidaa TV Configuration
 */

window.TVConfig = {
  brand: 'hisense',
  video: {
    preferredCodec: 'h264',
    maxBitrate: 16000000,
    bufferSize: 22,
    preload: 'auto',
    hardwareAcceleration: true
  },
  performance: {
    enableGPU: true,
    useWebGL: true,
    reducedMotion: false,
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
    fontSize: 'large',
    margin: '4%'
  },
  network: {
    retryAttempts: 5,
    timeout: 28000,
    keepAlive: true
  }
};

console.log('🟢 Hisense/Vidaa configuration loaded');
