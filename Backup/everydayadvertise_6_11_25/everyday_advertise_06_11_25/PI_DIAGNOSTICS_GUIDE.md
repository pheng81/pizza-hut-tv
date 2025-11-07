# 🔧 Pi Connection Diagnostic Guide

## Current Situation

✅ **OAuth Fix Applied** - New users will now be created automatically on login  
❌ **Pi Offline** - raspberrypi-ce39 is not connected to the server

## Server Status
- ✅ Server running (restarted at 13:05:50 UTC)
- ✅ WebSocket service operational
- ❌ No connection attempts from raspberrypi-ce39 in last 5 minutes

---

## 🚨 IMMEDIATE ACTION REQUIRED

The Pi device **raspberrypi-ce39** needs to be checked physically. It's either:
1. **Not running** - Pi client software stopped or crashed
2. **No network** - Lost internet connection
3. **Configuration issue** - Missing or wrong server URL

---

## Step-by-Step Troubleshooting

### Option 1: SSH into Pi (If you have network access)

```bash
# Connect to Pi
ssh pi@raspberrypi-ce39.local
# or if you know the IP:
ssh pi@192.168.1.XXX

# Check if Pi client is running
ps aux | grep -i "python.*complete_pi\|python.*pizza"

# Check system logs
sudo journalctl -u phtv-client -n 50 --no-pager

# Check if Pi can reach server
ping -c 3 api.everydayadvertise.com
curl -I https://api.everydayadvertise.com

# Check Pi's public IP
curl -s https://api.ipify.org

# Restart the Pi client
sudo systemctl restart phtv-client
# or
sudo reboot

# Watch logs in real-time
sudo journalctl -u phtv-client -f
```

### Option 2: Physical Access to Pi

**If you can see the Pi's screen:**

1. **Look for the Pi ID overlay** - Should show "Pi ID: raspberrypi-ce39" in corner
   - If you see it: Pi client is running ✅
   - If black screen: Pi client crashed or not running ❌

2. **Check for error messages** on screen

3. **Reboot the Pi:**
   - Unplug power cable
   - Wait 10 seconds
   - Plug back in
   - Wait 60 seconds for boot + connection

4. **Watch for these signs after reboot:**
   - Pi ID appears on screen (within 30 seconds)
   - "Connecting to server..." message
   - Pi ID disappears and video starts playing (if configured)

### Option 3: Check from Another Computer on Same Network

```bash
# Find Pi on network
nmap -sn 192.168.1.0/24 | grep -i raspberry

# Try to reach Pi's config server (port 8080)
curl http://raspberrypi-ce39.local:8080
# or
curl http://192.168.1.XXX:8080
```

---

## Common Issues & Solutions

### Issue 1: Pi Client Not Running

**Symptoms:**
- No Pi ID overlay visible
- Black screen
- No logs in journalctl

**Solutions:**
```bash
# Start the client manually
sudo systemctl start phtv-client

# Enable auto-start on boot
sudo systemctl enable phtv-client

# Check service status
sudo systemctl status phtv-client
```

### Issue 2: Network Connectivity Lost

**Symptoms:**
- Pi client running but can't reach server
- "Connection failed" errors in logs

**Solutions:**
1. Check WiFi connection:
```bash
iwconfig
# Should show connected network

# Restart networking
sudo systemctl restart NetworkManager
```

2. Check router/firewall:
- Is Pi getting IP address?
- Can Pi access internet?
- Any firewall blocking port 443?

3. Use wired Ethernet instead of WiFi (more reliable)

### Issue 3: Server URL Misconfigured

**Symptoms:**
- Pi tries to connect but to wrong URL
- Connection refused errors

**Check configuration:**
```bash
cat ~/.pizza_hut_tv_config.json
# Should show:
# - pair_code: "6364" (for mom.toeng@gmail.com)
# - store_id: "1000"
# - screen_id: (your screen)
```

**Check Pi client code:**
```bash
grep -n "server_url\|SERVER_URL" /home/pi/pizza-hut-tv/complete_pi_client.py
# Should be: https://api.everydayadvertise.com
```

### Issue 4: Wrong Pairing Code

**Current Valid Codes:**
- `6364` - mom.toeng@gmail.com ✅ (newly added)
- `8624` - toengpheng@gmail.com ✅

**To check Pi's current code:**
```bash
cat ~/.pizza_hut_tv_config.json | grep pair_code
```

**To reconfigure remotely (if Pi connects):**
1. Go to Remote Pi Manager
2. Enter `raspberrypi-ce39`
3. Click "Check Status" - will show online within 30s of Pi connecting
4. Configure with code `6364` for mom.toeng's account

---

## Expected Behavior When Working

### Normal Startup Sequence:
```
1. Pi boots up (30-60 seconds)
2. Pi client starts automatically
3. Pi ID "raspberrypi-ce39" appears on screen
4. Pi connects to WebSocket server (5-10 seconds)
5. Server logs: "✅ Pi registered via WebSocket: raspberrypi-ce39"
6. Pi starts sending heartbeats every 30 seconds
7. Remote Pi Manager shows "Online" status
8. If configured: Pi ID disappears, video playback starts
```

### What You Should See in Logs:
```
🔄 Connecting to WebSocket server: https://api.everydayadvertise.com
🌐 WebSocket connected to https://api.everydayadvertise.com
✅ Registered with server via WebSocket: {...}
💓 Heartbeat acknowledged by server (every 30s)
```

---

## Testing Checklist

After reboot/restart, verify:

- [ ] Pi powers on (LED lights up)
- [ ] Pi gets network connection (check router DHCP)
- [ ] Pi client process is running (`ps aux | grep python`)
- [ ] Pi ID visible on screen (within 30 seconds)
- [ ] Server shows connection in logs (check journalctl)
- [ ] Remote Pi Manager shows "Online" (within 60 seconds)
- [ ] Can send configuration from dashboard
- [ ] Video playback starts after configuration

---

## Quick Reference

### Server Details:
- **URL:** https://api.everydayadvertise.com
- **IP:** 54.252.90.27
- **Service:** pizza-hut-tv.service
- **Status:** ✅ Running (as of 13:05:50 UTC)

### Pi Details:
- **Pi ID:** raspberrypi-ce39
- **Last Seen:** Oct 10, 12:36:23 UTC (4+ minutes ago)
- **Last IP:** 203.158.51.30
- **Version:** v2.1.0-websocket
- **Status:** ❌ Offline - needs restart

### Your Account:
- **Email:** mom.toeng@gmail.com
- **Pair Code:** 6364 ✅
- **Store:** 1000
- **Screens:** 5 screens configured

---

## Next Steps

**IMMEDIATE (Do this now):**
1. Go to the physical Pi device (raspberrypi-ce39)
2. Check if it's powered on and has network
3. Reboot it (unplug/replug power)
4. Wait 60 seconds
5. Check Remote Pi Manager - should show "Online"

**AFTER Pi Connects:**
1. Test OAuth fix by logging out and back in
2. Configure Pi with your pairing code (6364)
3. Verify video playback works
4. Monitor connection stability (should stay online)

**IF Pi Still Won't Connect:**
1. SSH into Pi (if possible)
2. Check logs: `sudo journalctl -u phtv-client -n 100`
3. Restart service: `sudo systemctl restart phtv-client`
4. Share error messages for further debugging

---

## Success Indicators

You'll know everything is working when:
- ✅ OAuth creates users automatically (no more manual SQL)
- ✅ Pi shows "Online" in Remote Pi Manager
- ✅ Can configure Pi remotely from dashboard
- ✅ Videos play on Pi screen
- ✅ Connection stays stable (no disconnects)

---

**Need Help?** Share:
1. Output of `sudo systemctl status phtv-client`
2. Output of `sudo journalctl -u phtv-client -n 50`
3. Photo of Pi screen (if visible)
4. Router/network status
