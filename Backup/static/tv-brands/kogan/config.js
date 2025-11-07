/**
 * Kogan TV Configuration
 * Optimized for Kogan brand TVs (Australian brand)
 * 
 * IMPORTANT: Kogan TVs are manufactured by various OEMs
 * - Most modern Kogan TVs use Android TV (Chromium-based)
 * - Budget models may use simpler Linux-based systems
 * - Kogan branded TVs are sold primarily in Australia/New Zealand
 * 
 * Since Kogan uses OEM manufacturers, TV capabilities vary by model
 * This config uses conservative settings to support all Kogan models
 */

window.TVConfig = {
  brand: 'kogan',
  
  // Video settings - Conservative for varied hardware
  video: {
    preferredCodec: 'h264', // H.264 for maximum compatibility
    fallbackCodecs: ['h264'], // Stick to H.264 for older models
    maxBitrate: 15000000, // 15 Mbps - Conservative for budget models
    bufferSize: 25,
    preload: 'auto',
    hardwareAcceleration: true
  },
  
  // Performance optimizations - Conservative settings
  performance: {
    enableGPU: true, // Most Kogan TVs have basic GPU
    useWebGL: false, // Disable for older/budget models
    reducedMotion: true, // Better for lower-end hardware
    lazyLoad: true,
    androidTVMode: true // Most modern Kogans use Android TV
  },
  
  // UI adjustments for Kogan remote
  ui: {
    focusStyle: 'highlight',
    remoteControl: {
      enabled: true,
      enterKey: 'Enter',
      backKey: 'Back',
      navigationKeys: ['Up', 'Down', 'Left', 'Right'],
      // Kogan remotes vary by model
      homeButton: true,
      menuButton: true
    },
    fontSize: 'medium',
    margin: '5%' // Standard safe area
  },
  
  // Network settings - Standard
  network: {
    retryAttempts: 5,
    timeout: 35000, // Slightly longer for budget hardware
    keepAlive: true
  },
  
  // Kogan TV information
  kogan: {
    region: 'Australia/New Zealand',
    oemManufactured: true, // Kogan uses various OEM manufacturers
    androidTVCommon: true, // Most modern models use Android TV
    budgetFriendly: true, // Kogan is value brand
    variedCapabilities: true // Hardware varies significantly by model
  },
  
  // Device capabilities - Conservative assumptions
  capabilities: {
    h264: true, // All Kogan TVs support H.264
    h265: false, // Not all models support H.265
    vp9: false, // Limited support
    hdr10: false, // Only premium Kogan models
    '4K': false // Not all models are 4K
  },
  
  // Kogan TV notes
  notes: {
    manufacturer: 'Kogan TVs manufactured by various OEMs (TCL, Hisense, etc.)',
    platform: 'Most modern Kogan TVs use Android TV operating system',
    budget: 'Value-oriented brand with varying hardware capabilities',
    browser: 'Android TV models use Chromium-based browser',
    recommendation: 'Use conservative settings due to varied hardware across models',
    region: 'Primarily sold in Australian and New Zealand markets'
  }
};

console.log('🇦🇺 Kogan TV configuration loaded');
