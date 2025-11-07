/**
 * Amazon Fire TV Configuration
 * Optimized for Amazon Fire TV devices (Stick, Cube, Fire TV Edition TVs)
 * 
 * IMPORTANT: Amazon Fire TV uses Fire OS (Android-based)
 * - Fire OS 5 (2014-2017): Android 5.1 Lollipop (API 22)
 * - Fire OS 6 (2017-2019): Android 7.1 Nougat (API 25)
 * - Fire OS 7 (2019-2023): Android 9 Pie (API 28)
 * - Fire OS 8 (2023+): Android 10-11 (API 29-30)
 * - Vega OS (2025): New Linux-based OS
 * 
 * Fire TV uses Chromium-based browser (WebView)
 * Amazon Silk Browser on Fire TV devices
 */

window.TVConfig = {
  brand: 'amazon',
  
  // Video settings - Fire TV has excellent codec support
  video: {
    preferredCodec: 'h264', // H.264 universal support
    fallbackCodecs: ['h264', 'h265', 'vp9'], // Fire TV Stick 4K supports VP9 and H.265
    maxBitrate: 18000000, // 18 Mbps - Fire TV handles high bitrates well
    bufferSize: 30,
    preload: 'auto',
    hardwareAcceleration: true // Fire TV has excellent hardware acceleration
  },
  
  // Performance optimizations
  performance: {
    enableGPU: true, // Fire TV has good GPU acceleration
    useWebGL: true, // WebGL works well on Fire OS 6+
    reducedMotion: false, // Fire TV handles animations well
    lazyLoad: true,
    fireOSMode: true // Flag for Fire OS specific optimizations
  },
  
  // UI adjustments for Fire TV remote
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Back',
      navigationKeys: ['Up', 'Down', 'Left', 'Right'],
      voiceButton: true, // Fire TV has Alexa voice button
      menuButton: true, // Fire TV remote has menu button
      homeButton: true,
      playPauseButton: true,
      rewindButton: true,
      fastForwardButton: true
    },
    fontSize: 'large', // Better for 10-foot interface
    margin: '4%', // Fire TV safe area
    alexaVoiceReady: true // Fire TV supports Alexa voice commands
  },
  
  // Network settings
  network: {
    retryAttempts: 5,
    timeout: 32000, // Fire TV has good network performance
    keepAlive: true
  },
  
  // Fire TV specific features
  fireTV: {
    silkBrowser: true, // Amazon Silk browser
    chromiumBased: true, // Fire OS uses Chromium WebView
    alexaIntegration: true, // Can integrate with Alexa
    primeVideo: true, // Prime Video optimized
    appstoreAvailable: true // Amazon Appstore available
  },
  
  // Fire TV device capabilities
  capabilities: {
    h264: true, // All Fire TV devices
    h265: true, // Fire TV Stick 4K, Cube, newer models
    vp9: true, // Fire TV Stick 4K, Cube
    av1: true, // Fire TV Stick 4K Max (2021+)
    dolbyVision: true, // Fire TV Stick 4K, Cube
    hdr10: true, // Most Fire TV devices
    dolbyAtmos: true, // Fire TV Stick 4K, Cube
    '4K': true // Fire TV Stick 4K, Cube, Fire TV 4K
  },
  
  // Amazon Fire TV information
  notes: {
    fireOS5: 'Older Fire TV (2014-2017) - Android 5.1, limited features',
    fireOS6: 'Fire TV Stick/Cube (2017-2019) - Android 7.1, good support',
    fireOS7: 'Current Fire TV (2019-2023) - Android 9, excellent support',
    fireOS8: 'Latest Fire TV (2023+) - Android 10-11, best performance',
    vegaOS: '2025 Fire TV Stick 4K Select - New Linux-based OS',
    browser: 'Amazon Silk browser (Chromium-based)',
    recommendation: 'Fire TV has excellent web standards support, similar to Android TV'
  }
};

console.log('🔥 Amazon Fire TV configuration loaded');
