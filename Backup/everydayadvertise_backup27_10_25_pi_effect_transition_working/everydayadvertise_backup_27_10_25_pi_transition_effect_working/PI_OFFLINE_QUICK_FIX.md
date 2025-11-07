# Pi Shows "Offline" - Quick Fix Guide

## What You're Seeing
When you enter `raspberrypi-ce39` in Remote Pi Manager, it shows:
```
❌ Pi Offline - raspberrypi-ce39 is not responding
```

## What This Means
The **server cannot reach the Pi device**. The Pi is either:
- Not powered on
- Not connected to the internet
- Pi client software not running
- Network issue preventing connection

## ✅ QUICK FIXES (Try in order)

### Fix 1: Restart the Pi (EASIEST - 90% success rate)
**Physical restart:**
1. Go to the Pi device (raspberrypi-ce39)
2. Unplug the power cable
3. Wait 10 seconds
4. Plug power back in
5. Wait 60 seconds for boot + connection
6. Try "Connect" again in Remote Pi Manager

**SSH restart (if you have network access):**
```bash
ssh pi@raspberrypi-ce39.local
sudo reboot
```

---

### Fix 2: Check Pi Client is Running
SSH into the Pi and check status:
```bash
ssh pi@raspberrypi-ce39.local

# Check if client is running
sudo systemctl status phtv-client

# If not running, start it:
sudo systemctl start phtv-client

# Check logs for errors:
sudo journalctl -u phtv-client -n 50 --no-pager
```

---

### Fix 3: Verify Network Connection
On the Pi:
```bash
# Check internet connectivity
ping -c 3 google.com

# Check if Pi can reach server
ping -c 3 api.everydayadvertise.com

# Check Pi's IP address
hostname -I
```

---

### Fix 4: Manually Connect Pi
If all else fails, try connecting manually on the Pi:
```bash
cd ~/pizza-hut-tv
python3 complete_pi_client.py
```

Watch the output for connection errors.

---

## 🔍 UNDERSTANDING THE ISSUE

### Server Logs Show:
```
12:31:43 ✅ Pi registered via WebSocket: raspberrypi-ce39
12:33:13    Sending heartbeats every 30s (working normally)
12:36:23 ❌ Pi disconnected (after 115 seconds)
[No reconnection since then]
```

### What Happened:
1. Pi **WAS** connecting successfully
2. Pi worked for ~2 minutes
3. Connection dropped (likely network or power issue)
4. Pi has NOT reconnected since

### Why It's Not Auto-Reconnecting:
The Pi client **DOES have auto-reconnect** configured, but:
- If the process crashed → needs manual restart
- If network is down → can't reconnect until network restored
- If Pi powered off → needs power restoration

---

## ⚙️ TECHNICAL DETAILS

### How the Connection Works:
```
[Pi Device] --WebSocket--> [Server: api.everydayadvertise.com]
     ↓                              ↓
Runs complete_pi_client.py    Tracks connected_pis dict
Sends heartbeat every 30s     Shows "online" in dashboard
```

### What "Offline" Means:
The Pi is NOT in the server's `connected_pis` dictionary. This means:
- No active WebSocket connection
- Server hasn't received heartbeat in >30 seconds
- Pi either disconnected or never connected

### Pi Client Features (Already Configured):
- ✅ Auto-reconnect: YES (reconnection=True)
- ✅ Infinite retries: YES (reconnection_attempts=0)
- ✅ Retry delay: 5-30 seconds
- ✅ Heartbeat: Every 30 seconds
- ✅ Connection loop: Retries every 5-10 seconds if fails

---

## 📊 CURRENT STATUS

**Last Known Connection:**
- Time: October 10, 2025 at 12:31:43 UTC
- Duration: 115 seconds (disconnected at 12:36:23)
- IP: 203.158.51.30
- Version: v2.1.0-websocket

**Current Status:** OFFLINE (not connected for ~4+ minutes)

---

## 🎯 NEXT STEPS FOR YOU

### Immediate Action:
1. **Go to the physical Pi device** (raspberrypi-ce39)
2. **Check if it's powered on** - Look for LED lights
3. **Restart it** - Unplug/replug power
4. **Wait 60 seconds** - Give it time to boot and connect
5. **Test connection** in Remote Pi Manager

### If Still Offline After Restart:
1. Connect monitor/keyboard to Pi
2. Check console for errors
3. Run: `sudo systemctl status phtv-client`
4. Check WiFi/Ethernet connection
5. Review logs: `sudo journalctl -u phtv-client -n 100`

### If Pi Client Not Installed:
You may need to deploy the Pi client software:
```bash
# From your computer, deploy to Pi:
./deploy_complete_pi_client.sh

# Or manually on the Pi:
cd ~/pizza-hut-tv
python3 complete_pi_client.py
```

---

## 💡 PREVENTION

To avoid this in the future:

1. **Use wired Ethernet** instead of WiFi (more stable)
2. **Set static IP** for the Pi in router
3. **Add systemd watchdog** to auto-restart on crash
4. **Add monitoring** to alert if Pi offline > 5 minutes
5. **Keep Pi plugged into UPS** to prevent power loss

---

## 📞 TROUBLESHOOTING CHECKLIST

- [ ] Pi has power (LED lights are on)
- [ ] Pi connected to network (WiFi or Ethernet)
- [ ] Can ping Pi from your computer: `ping raspberrypi-ce39.local`
- [ ] Pi client service running: `sudo systemctl status phtv-client`
- [ ] Pi can reach internet: `ping google.com` (from Pi)
- [ ] Pi can reach server: `ping api.everydayadvertise.com` (from Pi)
- [ ] No firewall blocking ports 80/443
- [ ] Correct pairing code configured (6364 for mom.toeng@gmail.com)

---

## ✅ UPDATED DASHBOARD

The Remote Pi Manager now shows detailed troubleshooting steps when Pi is offline:
- Step-by-step instructions
- Common causes and solutions
- SSH commands to diagnose issues
- Helpful notes about connection timing

**This makes it easier to understand WHY the Pi is offline and HOW to fix it.**

---

Need more help? Check:
- `FIX_PI_DISCONNECTION.md` - Full technical guide
- `COMPLETE_PI_CLIENT_README.md` - Pi client documentation
- Server logs: `sudo journalctl -u pizza-hut-tv.service`
