# How to Purge CloudFlare Cache

## Step-by-Step Instructions:

1. **Go to CloudFlare Dashboard**
   - Visit: https://dash.cloudflare.com/
   - Log in with your account

2. **Select Your Domain**
   - Click on `everydayadvertise.com`

3. **Go to Caching Section**
   - Left sidebar → Click **Caching** → **Configuration**

4. **Purge the Cache**
   - Click **Purge Everything** button
   - Or click **Custom Purge** and enter:
     ```
     https://everydayadvertise.com/static/promotion.mp4
     ```

5. **Wait 30 seconds** then refresh your browser

---

## Option 2: Use a Completely New Filename

Since CloudFlare caches by URL, using a NEW filename bypasses the cache entirely.

**Current issue:** `promotion.mp4` is cached
**Solution:** Use `home_video_sync_02.mp4` (different name = no cache)

---

## Option 3: Development Mode (Temporary)

1. In CloudFlare dashboard
2. Go to **Caching** → **Configuration**
3. Toggle **Development Mode** to ON
4. This disables caching for 3 hours
5. Test your changes
6. Turn it back OFF when done

---

## Which Option Do You Want?

**Option 1**: I'll wait for you to purge CloudFlare cache
**Option 2**: I'll rename the video file to bypass cache completely
**Option 3**: You enable Development Mode in CloudFlare

Let me know which one you prefer!
