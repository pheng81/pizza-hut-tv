/**
 * Sony Bravia TV Configuration
 * Optimized for Sony Bravia Smart TVs
 * 
 * IMPORTANT: Sony uses different platforms:
 * - Pre-2015 models: Opera TV browser (very limited, Presto engine)
 * - 2015+ models: Android TV (Chromium-based, full modern support)
 * - 2021+ models: Google TV (newer Android TV with Chromium 90+)
 * 
 * This config is conservative to support older Opera models.
 */

window.TVConfig = {
  brand: 'sony',
  
  // Video settings - Conservative for Opera models
  video: {
    preferredCodec: 'h264', // CRITICAL: Opera models require H.264
    fallbackCodecs: ['h264'], // No H.265 on Opera models
    maxBitrate: 14000000, // 14 Mbps - Very conservative for Opera
    bufferSize: 30, // Larger buffer for slower models
    preload: 'auto',
    hardwareAcceleration: true
  },
  
  // Performance optimizations
  performance: {
    enableGPU: false, // Opera models have GPU issues
    useWebGL: false, // Opera doesn't support WebGL reliably
    reducedMotion: true, // Critical for older models
    lazyLoad: true,
    operaBrowserMode: true // Flag for Opera TV compatibility
  },
  
  // UI adjustments for Sony remote
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Return',
      navigationKeys: ['Up', 'Down', 'Left', 'Right']
    },
    fontSize: 'large', // Easier to read
    margin: '6%' // Sony needs more safe area
  },
  
  // Network settings
  network: {
    retryAttempts: 6, // More retries for slower models
    timeout: 40000, // 40 seconds for Opera browsers
    keepAlive: true
  },
  
  // Sony-specific information
  notes: {
    operaModels: 'Pre-2015 models use Opera TV browser (very limited)',
    androidTV: '2015+ models use Android TV (Chromium-based)',
    googleTV: '2021+ models use Google TV (modern Chromium)',
    recommendation: 'Use feature detection to differentiate between platforms'
  }
};
