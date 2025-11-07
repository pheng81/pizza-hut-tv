# 🔴 URGENT: Pi Not Connecting - Fix Instructions

## Problem
- ✅ Pi is online (192.168.1.131 responding)
- ❌ Dashboard can't see Pi
- 🔍 **Root Cause**: Dashboard was deployed to **WRONG SERVER**

## What Happened
1. You deployed dashboard to AWS Lightsail (54.252.90.27) ✅
2. BUT your Pi connects to everydayadvertise.com (DigitalOcean) ❌
3. They are **TWO DIFFERENT SERVERS** - Pi and dashboard are on different servers!

## The Fix
Deploy dashboard to the **CORRECT SERVER**: everydayadvertise.com (DigitalOcean)

### Method 1: DigitalOcean Console (RECOMMENDED)
Since SSH is timing out, use the web console:

1. Go to: https://cloud.digitalocean.com/droplets
2. Click your droplet (everydayadvertise.com server)
3. Click "Console" button (top right)
4. Log in as: `everydayadvertise`
5. Run these commands:
   ```bash
   cd /home/everydayadvertise/pizza-hut-tv
   git pull origin main
   sudo systemctl restart pizza-hut-tv
   ```

### Method 2: Fix SSH Connection (If you prefer)
The SSH timeout might be due to firewall. Try:
```powershell
# Try different SSH port or check firewall
ssh -v everydayadvertise@everydayadvertise.com
```

## After Deployment
1. Refresh dashboard: https://everydayadvertise.com
2. Go to Remote Pi Manager
3. Enter Pi ID: `raspberrypi-ce39`
4. Status should change from "❌ Offline" to "✅ Connected"
5. Enter pairing code: 6640
6. Select store and screen

## Technical Details
**Server Architecture:**
- **Production Server**: everydayadvertise.com (DigitalOcean behind Cloudflare)
  - Domain: everydayadvertise.com
  - IPs: 172.67.166.34, 104.21.11.136 (Cloudflare)
  - Pi connects HERE ✅
  - Dashboard SHOULD be deployed HERE ✅

- **Dev/Test Server**: 54.252.90.27 (AWS Lightsail)
  - IP: 54.252.90.27
  - Dashboard was deployed here by mistake ❌
  - Pi NOT configured to connect here ❌

**Pi Configuration:**
```python
# In complete_pi_client.py line 407
def __init__(self, server_url: str = "https://everydayadvertise.com"):
```
Pi is hardcoded to connect to everydayadvertise.com domain.

## Why This Happened
You ran: `.\deploy_to_server.ps1 -Server '54.252.90.27'`
This deployed to the AWS Lightsail server instead of your production DigitalOcean server.

## Quick Test After Fix
```powershell
# Check if deployment worked
curl https://everydayadvertise.com/api/health
```

## Need Help?
If DigitalOcean console doesn't work, alternative:
1. Contact DigitalOcean support to enable SSH
2. Or use their recovery console
3. Or temporarily update Pi to connect to 54.252.90.27 (not recommended)
