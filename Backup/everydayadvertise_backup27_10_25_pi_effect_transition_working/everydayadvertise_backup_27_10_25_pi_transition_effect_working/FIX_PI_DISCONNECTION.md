# Fix Pi WebSocket Disconnection Issue

## Problem
Pi device `raspberrypi-ce39` connects successfully but disconnects after ~2 minutes and doesn't reconnect.

## Investigation Results

### Server Logs Show:
```
12:31:43 ✅ Pi registered via WebSocket: raspberrypi-ce39 (203.158.51.30)
12:31:43 - 12:33:13: Receiving regular heartbeats (every 30s)
12:36:23 ❌ Pi disconnected (was connected for 115s)
```

### Current Status:
- Pi is currently OFFLINE
- Last connected: ~4 minutes ago
- Pi was sending heartbeats properly before disconnect
- No reconnection attempts detected

## Possible Root Causes:

### 1. **Network/Internet Issue** (Most Likely)
- Pi's internet connection unstable
- Router restarted
- ISP connection dropped
- Firewall blocking WebSocket after initial connection

### 2. **Service Restart Broke Connection**
- When we restarted `pizza-hut-tv.service`, all WebSocket connections were dropped
- Pi client should auto-reconnect but might not be configured for it

### 3. **Pi Client Not Running**
- Software crashed after disconnect
- No auto-restart mechanism configured
- Process died without respawn

### 4. **WebSocket Timeout Issue**
- Server or Pi timeout configuration mismatch
- Keep-alive not working properly
- Firewall killing idle connections

## Diagnostic Steps

### Step 1: Check if Pi is Running
SSH into the Pi (if accessible):
```bash
# Check if Pi client process is running
ps aux | grep -i "pi_client\|pizza.*hut\|webplayer"

# Check Pi client logs
journalctl -u phtv-client -n 100 --no-pager
# or
tail -f /var/log/phtv-client.log
```

### Step 2: Check Pi Network Connectivity
From Pi:
```bash
# Can Pi reach the server?
ping -c 3 api.everydayadvertise.com

# Can Pi connect to WebSocket port?
curl -I https://api.everydayadvertise.com

# Check Pi's public IP
curl -s https://api.ipify.org
```

### Step 3: Check Server WebSocket Configuration
```bash
# Check if socketio is running
sudo netstat -tulpn | grep gunicorn

# Check server logs for WebSocket issues
sudo journalctl -u pizza-hut-tv.service --since "10 minutes ago" | grep -i "websocket\|disconnect"
```

### Step 4: Test WebSocket Connection
From your computer:
```bash
# Use websocat tool or browser console
# Browser: https://api.everydayadvertise.com/dashboard
# Press F12, Console:
const socket = io('https://api.everydayadvertise.com');
socket.on('connect', () => console.log('Connected:', socket.id));
socket.emit('register_pi', {pi_id: 'raspberrypi-ce39', version: 'test'});
```

## Solutions

### Solution 1: Restart Pi Client (Quick Fix)
SSH into the Pi and restart the client:
```bash
sudo systemctl restart phtv-client
# or
sudo reboot
```

### Solution 2: Add Auto-Reconnect to Pi Client
The Pi client should have reconnection logic. Check if `complete_pi_client.py` has:
```python
socketio = SocketIO(
    reconnection=True,
    reconnection_attempts=0,  # Infinite attempts
    reconnection_delay=1000,  # 1 second
    reconnection_delay_max=10000,  # Max 10 seconds
    timeout=20000  # 20 second connection timeout
)
```

### Solution 3: Add Watchdog to Keep Pi Client Alive
Create systemd service with restart on failure:
```ini
[Unit]
Description=Pizza Hut TV Client
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pizza-hut-tv
ExecStart=/usr/bin/python3 /home/pi/pizza-hut-tv/complete_pi_client.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Solution 4: Network Stability Check
Check router/network:
- Static IP for Pi instead of DHCP
- Port forwarding if needed (though WebSocket is outbound)
- Disable router firewall for WebSocket connections
- Use wired Ethernet instead of WiFi if possible

### Solution 5: Server-Side Keep-Alive
In `app.py`, ensure SocketIO has proper timeouts:
```python
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,  # Wait 60s for pong
    ping_interval=25,  # Send ping every 25s
    logger=True,
    engineio_logger=True
)
```

## Immediate Action Required

**User needs to do ONE of these:**

### Option A: Check Pi Status
1. Go to the physical Pi device (raspberrypi-ce39)
2. Check if it's powered on and has network connection
3. Open terminal and run: `sudo systemctl status phtv-client`
4. If not running: `sudo systemctl restart phtv-client`

### Option B: Reboot Pi Remotely (if you have SSH access)
```bash
ssh pi@raspberrypi-ce39.local
sudo reboot
```

### Option C: Physical Reboot
Simply unplug and replug the Pi power supply

## After Reconnection

Monitor the connection:
1. Open Remote Pi Manager in dashboard
2. Enter: `raspberrypi-ce39`
3. Should show "Online" within 30 seconds of Pi booting
4. If it shows online but disconnects again -> network issue
5. If it never shows online -> client configuration issue

## Prevention

1. **Add connection monitoring** - alert if Pi offline > 5 minutes
2. **Add auto-reconnect** with exponential backoff
3. **Add systemd watchdog** for automatic restart
4. **Use wired connection** instead of WiFi if possible
5. **Add logging** to Pi client to debug disconnections
