# 🚀 Multi-Screen Loading Optimization Guide

## 📊 Current Setup Analysis

### Your Configuration:
- **CDN**: Cloudflare R2 at `https://cdn.everydayadvertise.com/`
- **Server**: AWS Lightsail (54.252.90.27)
- **Workers**: 3 Gunicorn workers
- **Memory**: 1.9GB (508MB used, plenty available)
- **Disk**: 44GB used of 58GB (77% - OK)
- **Load**: Very low (0.44, 0.34, 0.18)

### Problem Identified:
When 4 screens load videos simultaneously, they compete for:
1. **CDN bandwidth** - All pulling from Cloudflare at same time
2. **Network bandwidth** - Shared internet connection
3. **Browser resources** - Each screen trying to buffer full videos

## ✅ Solutions to Implement

### 1. **Cloudflare CDN Optimization** (MOST IMPORTANT)

Your CDN might not be optimized. Check these settings in Cloudflare dashboard:

#### A. Enable Argo Smart Routing
- Go to Cloudflare Dashboard → Traffic → Argo
- Enable "Argo Smart Routing" (~$5/month)
- This optimizes routing and speeds up delivery 30%+

#### B. Enable Stream Delivery Optimization
- Go to R2 bucket settings
- Enable "Stream Delivery" if available
- This optimizes video streaming specifically

#### C. Cache Settings
```
Cloudflare Dashboard → Caching → Configuration
- Caching Level: Standard
- Browser Cache TTL: 4 hours (or longer)
- Always Online: ON
- Development Mode: OFF
```

#### D. Video-Specific Rules
Create a Page Rule for `cdn.everydayadvertise.com/*`:
```
Cache Level: Cache Everything
Edge Cache TTL: 1 month
Browser Cache TTL: 4 hours
```

### 2. **Enable Video Range Requests** (CRITICAL)

Videos should support HTTP Range requests so browsers can stream chunks instead of downloading the entire file.

Check if enabled:
```bash
# Test from any computer
curl -I -H "Range: bytes=0-1000" https://cdn.everydayadvertise.com/your-video.mp4
```

Look for: `Accept-Ranges: bytes` in response

If NOT enabled, you need to:
1. Enable in Cloudflare R2 bucket settings
2. OR add to nginx configuration (if proxying)

### 3. **Player Code Optimization** (ALREADY IMPLEMENTED)

I've already optimized the player code with:

✅ **Staggered Loading**
- Screen 1: Loads immediately
- Screen 2: Waits 300ms
- Screen 3: Waits 600ms  
- Screen 4: Waits 900ms
- This spreads bandwidth usage over 900ms instead of hitting all at once

✅ **Smart Preloading**
- Changed from `preload="auto"` (download entire video)
- To `preload="metadata"` (download only headers)
- Then upgrade to `auto` after 2 seconds of playback
- Videos start faster, buffer during playback

✅ **Lower Ready State Requirements**
- Start playback with minimal buffering (HAVE_CURRENT_DATA)
- Don't wait for entire video to download
- Progressive loading while playing

### 4. **Network-Level Fixes**

#### A. Check Internet Speed
From a screen's browser, go to: https://fast.com
- Need at least **25 Mbps** for 4 screens playing HD videos
- 50+ Mbps recommended for smooth operation

#### B. Local Network Optimization
- Use wired Ethernet instead of WiFi for TVs if possible
- Put all 4 screens on same network switch
- Check for other devices using bandwidth (downloads, streaming)

#### C. Router QoS (Quality of Service)
- Access your router settings
- Enable QoS
- Prioritize traffic to your TV screens' IP addresses

### 5. **Video File Optimization**

Your video files themselves might be too large. Optimize them:

#### Recommended Video Settings:
```
Resolution: 1920x1080 (1080p) - not 4K
Bitrate: 3-5 Mbps (not 10+ Mbps)
Codec: H.264 (most compatible)
Format: MP4
FPS: 24-30 fps (not 60fps)
```

#### Tool to Optimize Videos:
```bash
# Using FFmpeg (install if needed)
ffmpeg -i input.mp4 -c:v libx264 -b:v 4M -maxrate 5M -bufsize 8M -c:a aac -b:a 128k output.mp4
```

This reduces file size by 50-70% without visible quality loss.

### 6. **CDN Geographic Location**

Check where your Cloudflare R2 bucket is located:
- Should be in **same region** as your screens
- If screens are in Asia-Pacific, bucket should be in Asia
- If in Americas, bucket should be in Americas

To change:
1. Create new R2 bucket in correct region
2. Copy files to new bucket
3. Update MEDIA_BASE_URL in .env

## 🔧 Quick Diagnostic Tests

### Test 1: Check CDN Speed
From a screen browser, open DevTools (F12) → Network tab:
1. Reload page
2. Find a video file
3. Check "Time" column
4. **Good**: <2 seconds to start
5. **Bad**: >5 seconds to start

### Test 2: Check Bandwidth Usage
While 4 screens playing:
```bash
# On your router/firewall
# Check current bandwidth: Should be 15-30 Mbps for 4 HD videos
```

### Test 3: Check CDN Cache Hit Rate
In Cloudflare Dashboard → Analytics → Traffic:
- **Cache Hit Rate** should be >90%
- If <70%, your cache rules need fixing

## 📈 Performance Targets

| Metric | Target | Current Issue |
|--------|--------|---------------|
| Video Start Time | <2s | >5s (slow) |
| Buffering Events | 0-1 per video | Multiple (loading) |
| Sync Accuracy | <100ms | Variable |
| CDN Cache Hit | >90% | Unknown |
| Bandwidth per Screen | 3-5 Mbps | Unknown |

## 🎯 Immediate Actions (Do These Now)

### Priority 1: Check CDN Settings
1. Login to Cloudflare Dashboard
2. Go to your R2 bucket
3. Verify these are enabled:
   - Public access to bucket
   - CORS enabled
   - Range requests enabled
   - Cache headers set correctly

### Priority 2: Test One Video
1. Copy a video URL from one of your screens
2. Open in browser: `https://cdn.everydayadvertise.com/path/to/video.mp4`
3. Does it play immediately? Or buffer/slow?
4. Check DevTools → Network → Size/Time

### Priority 3: Optimize Video Files
1. Take your largest video file
2. Run through FFmpeg optimization
3. Upload optimized version
4. Test if loading is faster

### Priority 4: Enable Page Rules
In Cloudflare, create page rule:
```
URL: cdn.everydayadvertise.com/*
Settings:
  - Cache Level: Cache Everything
  - Edge Cache TTL: 1 month
  - Browser Cache TTL: 4 hours
```

## 🚨 Common Issues & Fixes

### Issue: Videos buffer constantly
**Fix**: Reduce video bitrate to 3-4 Mbps

### Issue: First video loads fast, others slow
**Fix**: CDN cache warming - load each video once manually

### Issue: Videos work fine individually, slow together
**Fix**: Internet speed too slow - upgrade or reduce video quality

### Issue: Random screens fail to load
**Fix**: CDN CORS issue - verify CORS headers in R2 bucket

## 📞 Need Help Troubleshooting?

### Get This Information:
1. **Internet Speed**: Run https://fast.com from one screen
2. **Video File Size**: How big are your video files? (MB)
3. **CDN Response**: Open browser DevTools, reload page, check Network tab
4. **Console Errors**: Any red errors in browser console? (F12)

### Share These Screenshots:
1. Network tab showing video load times
2. Console log from one screen
3. Cloudflare Analytics → Traffic page
4. Router bandwidth usage graph

---

## ✅ Summary

**Root Cause**: 4 screens loading large videos simultaneously from CDN
**Quick Fixes**:
1. ✅ Staggered loading (already deployed in player code)
2. ⚠️ Optimize videos (reduce bitrate to 3-5 Mbps)
3. ⚠️ Check Cloudflare cache settings
4. ⚠️ Verify internet speed is adequate (25+ Mbps)

**Expected After Fixes**:
- Videos start playing within 1-2 seconds
- Minimal buffering during playback
- All 4 screens play smoothly together
- Sync stays tight (<100ms drift)

---

**Status**: 🔍 DIAGNOSTICS NEEDED - Please check Cloudflare settings and video file sizes!
