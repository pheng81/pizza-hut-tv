# 🔄 Pi Auto-Registration System

## Overview
The Pi now automatically registers its IP address with the server when it boots up. No more manual IP configuration needed!

## How It Works

### 1. **On Pi Startup**
When `complete_pi_client.py` starts:
- Detects its Pi Identifier (e.g., `raspberrypi-ce39`)
- Gets its current local IP address
- Sends both to the server via `/api/register_pi`
- Server updates `pi_id_ip_map.json` automatically

### 2. **On Dashboard**
When you use Remote Pi Manager:
- Enter only the Pi Identifier (e.g., `raspberrypi-ce39`)
- Click "Connect"
- Server looks up the Pi's IP from `pi_id_ip_map.json`
- Server checks if Pi is online at that IP
- If online, you can configure it remotely

### 3. **Dynamic IP Updates**
- Every time the Pi restarts, it re-registers its current IP
- If the Pi moves to a new network (e.g., home → shop), the IP is automatically updated
- No manual intervention needed

## Architecture

```
┌─────────────────┐
│   Raspberry Pi  │
│  (at Shop WiFi) │
└────────┬────────┘
         │ 1. On boot, register:
         │    POST /api/register_pi
         │    { pi_id: "raspberrypi-ce39",
         │      pi_ip: "192.168.50.100" }
         ↓
┌─────────────────┐
│  Server (Cloud) │
│  everydayadver  │
│    tise.com     │
└────────┬────────┘
         │ 2. Updates pi_id_ip_map.json:
         │    { "raspberrypi-ce39": "192.168.50.100" }
         ↓
┌─────────────────┐
│   Dashboard     │
│   (Browser)     │
└─────────────────┘
         │ 3. User enters Pi ID only
         │    GET /api/pi-status/raspberrypi-ce39
         ↓
    Server resolves IP automatically
    and checks Pi status
```

## API Endpoints

### Register Pi (Pi → Server)
```http
POST /api/register_pi
Content-Type: application/json

{
  "pi_id": "raspberrypi-ce39",
  "pi_ip": "192.168.50.100"
}

Response:
{
  "success": true,
  "message": "Registered raspberrypi-ce39 with IP 192.168.50.100"
}
```

### Check Pi Status (Dashboard → Server)
```http
GET /api/pi-status/raspberrypi-ce39

Response (if online):
{
  "pi_id": "raspberrypi-ce39",
  "status": "online",
  "version": "v2.1.0",
  "last_seen": "2025-10-08T10:05:00Z"
}

Response (if offline):
{
  "pi_id": "raspberrypi-ce39",
  "status": "offline",
  "message": "Pi not responding"
}
```

## Code Changes

### Backend (`app.py`)
- Added `/api/register_pi` endpoint
- Updated `/api/pi-status/<pi_id>` to auto-resolve IP from `pi_id_ip_map.json`

### Pi Client (`complete_pi_client.py`)
- Added `get_local_ip()` helper function
- Added `register_pi_with_server()` function
- Calls registration on startup (in background thread)

### Dashboard (`dashboard.html`)
- Removed client-side IP resolution
- Sends only Pi Identifier to server
- Server handles all IP lookup

## Deployment Workflow

### Setup New Pi in Shop

1. **Before Going to Shop:**
   - Flash SD card with Pi client software
   - No configuration needed

2. **At Shop:**
   - Connect Pi to shop WiFi
   - Pi auto-boots and runs `complete_pi_client.py`
   - Pi registers itself with server automatically

3. **From Dashboard:**
   - Open Remote Pi Manager
   - Enter Pi ID shown on screen (e.g., `raspberrypi-ce39`)
   - Click "Connect"
   - If online, configure store and screen
   - Done!

## Troubleshooting

### Pi Shows "Offline" in Dashboard

**Check:**
1. Pi is powered on and connected to WiFi
2. Pi client is running (`sudo systemctl status pizza-hut-tv`)
3. Pi can reach the server (check internet connectivity)
4. Server has the Pi's IP in `pi_id_ip_map.json`

**Test from Pi:**
```bash
# Check if Pi registered successfully
curl -X POST https://everydayadvertise.com/api/register_pi \
  -H "Content-Type: application/json" \
  -d '{"pi_id":"raspberrypi-ce39","pi_ip":"192.168.50.100"}'
```

**Test from Server:**
```bash
# Check if Pi is in mapping file
cat /var/www/pizza-hut-tv/pi_id_ip_map.json

# Try to reach Pi from server
curl http://192.168.50.100:8080/status
```

### Network Considerations

**Same Network Required:**
- For direct connection, server and Pi must be on the same network
- OR use port forwarding / VPN for remote access
- For cloud server, consider using a VPN mesh (e.g., Tailscale, ZeroTier)

**Alternative: Registration-Only Mode**
- Pi registers its public IP
- Use port forwarding on router (8080 → Pi)
- Server can reach Pi from anywhere

## Benefits

✅ **Zero Manual Configuration**  
No need to find and enter Pi IP addresses

✅ **Dynamic IP Support**  
Works even if DHCP assigns different IPs

✅ **Scalable for 100+ Locations**  
Each Pi auto-registers on boot

✅ **Move Pi Between Networks**  
IP updates automatically when network changes

✅ **Simple Dashboard UX**  
Only need to enter Pi Identifier

## Future Enhancements

- **Heartbeat Monitoring:** Pi sends periodic heartbeats to show it's alive
- **Database Storage:** Store Pi registry in database instead of JSON file
- **Public IP Support:** Register public IP for cloud-to-edge management
- **Security:** Add authentication token for registration endpoint
- **Dashboard Features:** Show Pi list, last seen times, network info

---

**Status:** ✅ Deployed and Active  
**Version:** 1.0  
**Last Updated:** 2025-10-08
