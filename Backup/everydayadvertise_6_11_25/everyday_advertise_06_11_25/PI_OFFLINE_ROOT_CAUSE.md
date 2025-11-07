# 🔴 ROOT CAUSE FOUND: Pi Shows Offline in Dashboard

## Problem Summary
Dashboard shows "❌ Pi Offline - raspberrypi-ce39 is not responding" even though:
- ✅ Pi is running (`systemctl status` shows active)
- ✅ Pi WebSocket connected (`journalctl` shows heartbeat every 30s)
- ✅ Pi logs show successful connection to `everydayadvertise.com`

## Root Cause
**The production server does NOT have the WebSocket handlers deployed!**

### Evidence
1. **API Test Result**:
   ```powershell
   Invoke-RestMethod -Uri "https://everydayadvertise.com/api/pi-status-ws/raspberrypi-ce39"
   ```
   **Response**:
   ```json
   {
       "connection_type": "none",
       "message": "Pi not connected to WebSocket server",
       "pi_id": "raspberrypi-ce39",
       "status": "offline"
   }
   ```

2. **What this means**:
   - The Pi IS sending heartbeats (confirmed in Pi logs)
   - The server API endpoint `/api/pi-status-ws/<pi_id>` exists and responds
   - BUT `connected_pis` dictionary is empty (server not tracking connections)
   - **Conclusion**: Server WebSocket handlers are NOT running or NOT deployed

## Deployment History
1. ✅ **Pi Client**: Deployed successfully to `192.168.1.131`
   - Version: v2.1.0-websocket
   - WebSocket working, sending heartbeats
   
2. ❌ **Dashboard Code**: Pushed to GitHub (commit df4ca5f)
   - Fixed dynamic screen fetch from API
   - Code exists locally
   
3. ❌ **Server**: Last deployment went to WRONG server
   - `deploy_to_server.ps1` deployed to `54.252.90.27` (AWS Lightsail) ❌
   - Should have deployed to `everydayadvertise.com` (DigitalOcean) ✅
   - Production server code is **OUTDATED** - missing WebSocket handlers

## Solution Required
**Deploy complete `app.py` with WebSocket handlers to production server**

### Critical Code Sections That Need Deployment
From `app.py`:
- Line 188: `connected_pis = {}`  (global dictionary)
- Line 9590-9645: `@socketio.on('register_pi')` handler
- Line 9646-9656: `@socketio.on('pi_heartbeat')` handler  
- Line 9686-9712: `@app.route('/api/pi-status-ws/<pi_id>')` API endpoint

### Deployment Methods
**Option 1: Via DigitalOcean Console** (RECOMMENDED)
1. Login to DigitalOcean: https://cloud.digitalocean.com/
2. Open Console for droplet running everydayadvertise.com
3. Commands:
   ```bash
   cd /home/everydayadvertise/pizza-hut-tv  # or wherever app is hosted
   git pull origin main
   sudo systemctl restart pizza-hut-tv
   ```

**Option 2: Via SSH** (if accessible)
```bash
ssh user@142.93.249.238  # DigitalOcean IP (if known)
cd /path/to/pizza-hut-tv
git pull origin main
sudo systemctl restart pizza-hut-tv
```

**Option 3: Manual File Upload** (last resort)
- Upload `app.py` via SCP/SFTP
- Restart service

## Expected Result After Deployment
1. Server starts tracking WebSocket connections in `connected_pis{}`
2. When Pi sends `register_pi`, server adds it to dictionary
3. When Pi sends `pi_heartbeat`, server updates `last_heartbeat` timestamp
4. API `/api/pi-status-ws/raspberrypi-ce39` returns:
   ```json
   {
       "pi_id": "raspberrypi-ce39",
       "status": "online",
       "connection_type": "websocket",
       "connected_since": 1728573600,
       "ip_address": "...",
       "version": "v2.1.0-websocket",
       "last_heartbeat": 1728573900
   }
   ```
5. Dashboard shows "✅ Pi Online - raspberrypi-ce39"

## Why This Wasn't Caught Earlier
1. **Pi deployment successful** - Everything works Pi-side
2. **Code committed to GitHub** - Latest code exists in repo
3. **Wrong server deployed** - `deploy_to_server.ps1` went to AWS instead of DigitalOcean
4. **SSH timeout** - Can't easily check production server status
5. **Assumption**: Thought it was browser cache, but server never received the code

## Next Steps
1. ⚠️ **URGENT**: Deploy `app.py` to production server (everydayadvertise.com)
2. Verify deployment by checking API again:
   ```powershell
   Invoke-RestMethod -Uri "https://everydayadvertise.com/api/pi-status-ws/raspberrypi-ce39"
   ```
3. Hard refresh dashboard (Ctrl+Shift+R)
4. Test Remote Pi Manager - should show "✅ Pi Online"
5. Configure Pi via dashboard - should work end-to-end
