# Everyday Advertise - Google Play Store Release Guide

## ✅ BUILD COMPLETE - Ready for Upload!

---

## 📦 Release Files

### Location: `C:\Users\toeng\Pizza Hut TV\`

1. **everydayadvertise-release.aab** (3.5 MB)
   - **Use this for Google Play Store upload** (Required for new apps)
   - Android App Bundle format
   - **Updated with API 35 and ProGuard enabled**
   
2. **everydayadvertise-release.apk** (8.4 MB)
   - For direct installation on devices
   - For testing before store submission

---

## 🔐 Keystore Information

**⚠️ KEEP THIS INFORMATION SECURE - YOU NEED IT FOR ALL FUTURE UPDATES!**

- **Keystore File:** `android_tv_app/everydayadvertise.keystore`
- **Keystore Password:** `EverydayAdvertise2025!`
- **Key Alias:** `everydayadvertise`
- **Key Password:** `EverydayAdvertise2025!`

**Backup the keystore file now!** Without it, you cannot update your app on Google Play.

---

## 📱 App Information

- **Package Name:** `com.pizzahut.tv`
- **Version Code:** 1
- **Version Name:** 1.0
- **Minimum SDK:** Android 5.0 (API 21)
- **Target SDK:** Android 15 (API 35)
- **App Type:** Android TV / Leanback
- **Code Optimization:** ProGuard/R8 enabled (reduces size, includes mapping file)

---

## 🚀 Google Play Console Upload Steps

### 1. Create Google Play Console Account
- Visit: https://play.google.com/console
- Pay $25 one-time registration fee
- Accept developer agreements

### 2. Create New App
1. Click **"Create App"**
2. Fill in basic details:
   - **App name:** Everyday Advertise
   - **Default language:** English
   - **App type:** App
   - **Category:** Business
   - **Free or Paid:** Free

### 3. Set Up Store Listing

#### Required Information:
- **App name:** Everyday Advertise
- **Short description (80 chars):**
  ```
  Digital signage for restaurants - manage screens remotely with ease
  ```
  
- **Full description (4000 chars):**
  ```
  Everyday Advertise is a powerful digital signage solution designed specifically for restaurant chains and retail businesses. Transform your Android TV devices into dynamic digital displays that showcase your promotions, menus, and brand content.

  KEY FEATURES:
  • Remote screen management from web dashboard
  • Multi-screen support (horizontal & vertical displays)
  • Automatic content rotation and scheduling
  • Real-time updates across all locations
  • Time-based content scheduling
  • Transition effects and animations
  • Built for reliability and 24/7 operation
  
  PERFECT FOR:
  • Restaurant chains (Pizza Hut, quick service restaurants)
  • Retail stores
  • Corporate offices
  • Reception areas
  • Waiting rooms
  
  EASY SETUP:
  1. Install the app on your Android TV device
  2. Scan QR code or enter store ID
  3. Your screens are instantly connected
  4. Manage content from anywhere via web dashboard
  
  RELIABLE & SECURE:
  • Built-in auto-recovery and monitoring
  • Secure device authentication
  • Automatic content caching for offline playback
  • No recurring subscription fees
  
  Transform your digital displays with Everyday Advertise today!
  ```

#### Required Graphics:

**📱 App Icon (512x512 px)**
- Create a professional icon with your brand
- PNG format, no transparency

**🎨 Feature Graphic (1024x500 px)**
- Showcasing the app's main features
- Will appear at the top of your store listing

**📺 TV Banner (1280x720 px)**
- Required for Android TV apps
- Shows in the TV home screen

**📸 Screenshots (at least 2)**
- **For Android TV:** 1920x1080 pixels
- Show the app in action
- Capture setup screen, display screen, content management

### 4. Content Rating
Complete the questionnaire:
- Target age: Everyone
- Content type: Business/Informational
- No violence, explicit content, gambling, etc.

### 5. Target Audience
- Select age groups: All ages
- Not directed at children under 13

### 6. Privacy Policy
**Required!** You need a privacy policy URL. Host a simple page like:

```
https://everydayadvertise.com/privacy-policy
```

Content should cover:
- What data you collect (device ID, store information)
- How you use it (for display management)
- Data security measures
- Contact information

### 7. Upload Release

1. Go to **"Release" → "Production"**
2. Click **"Create new release"**
3. Upload **everydayadvertise-release.aab**
4. Add release notes:
   ```
   Initial release of Everyday Advertise digital signage app
   
   Features:
   - Multi-screen support for Android TV devices
   - Remote content management
   - Automatic scheduling and rotation
   - Real-time updates
   - Transition effects
   ```
5. Click **"Review release"**
6. Click **"Start rollout to Production"**

### 8. Review & Publish

- Google will review your app (usually 1-3 days)
- You'll receive an email when approved
- App will be live on Google Play Store!

---

## 🎨 Assets You Need to Create

Use tools like Canva, Photoshop, or Figma:

### Priority 1 (Required):
- [ ] App icon (512x512)
- [ ] Feature graphic (1024x500)
- [ ] TV banner (1280x720)
- [ ] 2+ screenshots (1920x1080)
- [ ] Privacy policy page

### Priority 2 (Recommended):
- [ ] Promotional video (30 seconds)
- [ ] TV screenshots showing actual content
- [ ] Dashboard/management screenshots

---

## 🔄 Future Updates

### To Release Updates:

1. Update version in `build.gradle`:
   ```gradle
   versionCode 2  // Increment by 1
   versionName "1.1"  // Update version
   ```

2. Build new release:
   ```powershell
   cd android_tv_app
   .\gradlew.bat bundleRelease
   ```

3. Upload new AAB to Google Play Console
4. Same keystore will be used automatically ✅

---

## 📝 Checklist Before Submission

- [ ] Test APK on real Android TV device
- [ ] Verify QR code setup works
- [ ] Test content playback (images & videos)
- [ ] Test multi-screen support
- [ ] Verify remote updates work
- [ ] Check all transition effects
- [ ] Test schedule functionality
- [ ] Create all required graphics (icon, banner, screenshots)
- [ ] Write privacy policy
- [ ] Backup keystore file securely
- [ ] Screenshot the keystore passwords
- [ ] Test APK installation from file

---

## 🆘 Support & Resources

- **Google Play Console:** https://play.google.com/console
- **Android Developer Guide:** https://developer.android.com/distribute
- **App Bundle Guide:** https://developer.android.com/guide/app-bundle

---

## 💾 Important Files to Backup

1. **android_tv_app/everydayadvertise.keystore** ⚠️ CRITICAL
2. This guide (GOOGLE_PLAY_RELEASE_GUIDE.md)
3. Keystore passwords (store securely)

**Without the keystore, you CANNOT update your app on Google Play!**

---

*Generated: November 10, 2025*
*App ready for Google Play Store submission*
