/**
 * TCL TV Configuration (Usually Android TV)
 */

window.TVConfig = {
  brand: 'tcl',
  video: {
    preferredCodec: 'h264',
    maxBitrate: 17000000,
    bufferSize: 25,
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
      backKey: 'Back',
      navigationKeys: ['Up', 'Down', 'Left', 'Right']
    },
    fontSize: 'large',
    margin: '4%'
  },
  network: {
    retryAttempts: 4,
    timeout: 25000,
    keepAlive: true
  }
};

console.log('⚫ TCL Android TV configuration loaded');
