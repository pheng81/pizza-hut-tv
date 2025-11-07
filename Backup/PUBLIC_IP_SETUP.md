# 🌐 Public IP Auto-Registration Setup

## What Changed

The Pi client now **automatically registers its PUBLIC IP** instead of local IP when it starts.

### Before:
```
Pi boots → Gets local IP (192.168.1.131) → Registers with server
Dashboard tries to connect → Can't reach 192.168.1.131 from internet ❌
```

### After:
```
Pi boots → Gets public IP (203.158.51.30) → Registers with server
Dashboard connects → Reaches public IP via port forwarding ✅
```

---

## 📋 Setup Steps

### Step 1: Router Port Forwarding (Required)

You need to forward **port 8080** from the internet to your Pi.

1. **Login to your router** (usually http://192.168.1.1)
2. **Find "Port Forwarding"** section:
   - Might be called: "NAT", "Virtual Server", "Applications", or "Port Mapping"
3. **Create new rule:**
   - **Service Name**: Pizza Hut TV Pi
   - **External Port**: 8080
   - **Internal IP**: 192.168.1.131 (your Pi's local IP)
   - **Internal Port**: 8080
   - **Protocol**: TCP
   - **Enable**: Yes/On

### Step 2: Deploy Updated Pi Client

The updated `complete_pi_client.py` now includes:
- ✅ `get_public_ip()` - detects public IP using ipify.org
- ✅ Auto-registration with public IP on boot
- ✅ HTTP server on port 8080 for status checks

**Deploy to Pi:**
```bash
scp complete_pi_client.py pi@192.168.1.131:~/
ssh pi@192.168.1.131 "sudo systemctl restart pizza-hut-tv"
```

### Step 3: Test Registration

1. **Reboot Pi** or restart the service
2. **Check server mapping file:**
   ```bash
   ssh ubuntu@54.252.90.27 "cat /var/www/pizza-hut-tv/pi_id_ip_map.json"
   ```
   Should show:
   ```json
   {
     "raspberrypi-ce39": "203.158.51.30"
   }
   ```

3. **Test from dashboard:**
   - Go to https://everydayadvertise.com/dashboard
   - Click "Remote Pi Manager"
   - Enter Pi ID: `raspberrypi-ce39`
   - Click "Connect"
   - Should show: ✅ Pi Online

---

## 🔍 How It Works

### 1. Pi Auto-Registration
When Pi boots, it calls `/api/register_pi`:
```python
public_ip = get_public_ip()  # Gets 203.158.51.30
requests.post(
    "https://everydayadvertise.com/api/register_pi",
    json={"pi_id": "raspberrypi-ce39", "pi_ip": "203.158.51.30"}
)
```

### 2. Server Saves Mapping
```json
{
  "raspberrypi-ce39": "203.158.51.30"
}
```

### 3. Dashboard Connects
```javascript
// User enters Pi ID: raspberrypi-ce39
fetch('/api/pi-status/raspberrypi-ce39')

// Server resolves: 203.158.51.30
// Server checks: http://203.158.51.30:8080/status
// Server returns: { status: 'online', pi_id: 'raspberrypi-ce39' }
```

### 4. Dashboard Configures
```javascript
// User fills form: pair_code, store_id, screen_id
fetch('/api/configure-pi', {
  method: 'POST',
  body: JSON.stringify({
    pi_id: 'raspberrypi-ce39',
    // pi_ip: auto-resolved to 203.158.51.30
    pair_code: '1234',
    store_id: '1000',
    screen_id: '1000_screen1'
  })
})

// Server sends config to: http://203.158.51.30:8080/configure
```

---

## ✅ Verification Checklist

- [ ] Router port forwarding enabled (8080 → 192.168.1.131:8080)
- [ ] Updated Pi client deployed
- [ ] Pi restarted
- [ ] Pi registered public IP (check pi_id_ip_map.json)
- [ ] Dashboard shows "Pi Online" when connecting
- [ ] Configuration works from dashboard

---

## 🔧 Troubleshooting

### "Pi Offline" Error
1. Check port forwarding is enabled
2. Check Pi is running: `ssh pi@192.168.1.131 "systemctl status pizza-hut-tv"`
3. Test Pi locally: `curl http://192.168.1.131:8080/status`
4. Test from internet: `curl http://203.158.51.30:8080/status` (from different network)

### "Could not resolve IP" Error
1. Check Pi registration: `cat /var/www/pizza-hut-tv/pi_id_ip_map.json`
2. Check Pi logs: `ssh pi@192.168.1.131 "journalctl -u pizza-hut-tv -n 50"`
3. Manually trigger registration: restart Pi client

### Port Forwarding Issues
- Make sure Pi has static local IP (192.168.1.131)
- Check router firewall isn't blocking port 8080
- Some ISPs block certain ports - try port 8088 or 8888 instead
- Test with: `telnet 203.158.51.30 8080` (from different network)

---

## 🌟 Benefits

✅ **Automatic** - Pi self-registers on boot
✅ **Dynamic** - Works even if public IP changes (DDNS compatible)
✅ **Scalable** - Add unlimited Pis, each with unique ID
✅ **No Manual Config** - Dashboard auto-resolves IPs
✅ **Works Anywhere** - Configure Pi from anywhere with internet
