# 📱 Remote Pi Manager - User Instructions

## Step-by-Step Configuration Flow

### 🎯 Access the Dashboard
1. Open: **https://everydayadvertise.com/dashboard**
2. Click the **"Remote Pi Manager"** button (top right corner with 💻 icon)

---

### 📝 Configuration Steps

#### **Step 1: Enter Pi Identifier**
- **Field**: "Pi Identifier"
- **Value**: `raspberrypi-ce39` (or your Pi's unique ID)
- **Format**: Can be hostname (raspberrypi), MAC address, or custom ID
- **Click**: Green **"Connected"** button

**Expected Result**: 
- ✅ Green banner shows: **"Pi Online - raspberrypi-ce39"**
- Shows: Version: v2.1.0-websocket | Last seen: Just now
- **Next field appears**: "Your Pairing Code"

---

#### **Step 2: Enter Pairing Code**
- **Field**: "Your Pairing Code"
- **Value**: `3835` (your 4-digit pairing code)
- **Format**: Exactly 4 digits
- **Action**: Type the code (field auto-validates)

**Expected Result**: 
- As you type the 4th digit, the **Store dropdown appears below**
- Store selection field becomes visible

---

#### **Step 3: Select Store**
- **Field**: "Store ID" (dropdown menu)
- **Options**: 
  - 1000 - My First Store
  - (Other stores if configured)
- **Action**: Click dropdown and select your store

**Expected Result**: 
- Store selected (e.g., "1000 - My First Store")
- **Screen dropdown appears below**

---

#### **Step 4: Select Screen**
- **Field**: "Screen ID" (dropdown menu)
- **Options**:
  - **Screen 1 (Main Display)** - `1000_screen1`
  - **Screen 2 (Secondary)** - `1000_screen2`
  - **Screen 3** - `1000_screen3`
  - **Screen 4** - `1000_screen4`
  - **Promo 1 (Portrait)** - `1000_promo1`
  - **Promo 2 (Portrait)** - `1000_promo2`
  - **Promo 3 (Portrait)** - `1000_promo3`
- **Action**: Select which screen content this Pi should display

**Expected Result**: 
- Screen selected (e.g., "Screen 1 (Main Display)")
- All fields now filled

---

#### **Step 5: Auto-start Option**
- **Checkbox**: "Auto-start on boot"
- **Default**: ✓ Checked (recommended)
- **Purpose**: Pi will automatically start playing content when it boots up

---

#### **Step 6: Configure Pi**
- **Button**: Blue **"Configure Pi"** button
- **Action**: Click to send configuration via WebSocket

**Expected Result**: 
- ✅ Green banner: **"Configuration successful!"**
- Shows: Pi ID, Store, Screen, Pair Code
- Modal closes automatically after 3 seconds
- **Pi starts playing** the selected screen content immediately!

---

## 🎬 Complete Example

```
1. Pi ID: raspberrypi-ce39          [Connected ✓]
2. Pair Code: 3835                   [Shows Store dropdown ✓]
3. Store: 1000 - My First Store      [Shows Screen dropdown ✓]
4. Screen: Screen 1 (Main Display)   [Ready to configure ✓]
5. Auto-start: ✓ Checked             [Enabled ✓]
6. Click: "Configure Pi"             [Configuration sent! ✓]
```

**Result**: Pi immediately starts displaying content from Store 1000, Screen 1!

---

## 🔧 How It Works (Behind the Scenes)

### WebSocket Relay Architecture
```
Dashboard → HTTPS → Server → WebSocket → Pi
(Browser)           (AWS)                (Raspberry)
```

1. **Dashboard** sends configuration to server API
2. **Server** checks if Pi is connected via WebSocket
3. **Server** emits `configure` event to Pi's WebSocket connection
4. **Pi** receives configuration **instantly** (no polling!)
5. **Pi** applies configuration (pair code, store, screen)
6. **Pi** starts playing content from specified screen
7. **Pi** sends `config_applied` confirmation back to server
8. **Dashboard** shows success message

### Key Benefits
- ✅ **No Port Forwarding** - Works on any network
- ✅ **Instant Delivery** - Real-time WebSocket communication
- ✅ **Global Access** - Configure from anywhere in the world
- ✅ **Secure** - SSL/TLS encrypted, no exposed ports
- ✅ **Reliable** - Auto-reconnection if connection drops

---

## 🎯 Screen Types Explained

### Horizontal Screens (Landscape)
- **screen1**: Main display (primary content)
- **screen2**: Secondary display
- **screen3**: Third display
- **screen4**: Fourth display

**Use Case**: Large landscape TVs, digital menu boards

### Vertical Screens (Portrait)
- **promo1**: Portrait promotional content
- **promo2**: Portrait promotional content
- **promo3**: Portrait promotional content

**Use Case**: Vertical displays, door signage, promotional stands

---

## 📊 Configuration Data Sent

When you click "Configure Pi", this JSON is sent via WebSocket:

```json
{
  "pi_id": "raspberrypi-ce39",
  "pair_code": "3835",
  "store_id": "1000",
  "screen_id": "1000_screen1",
  "auto_start": true
}
```

The Pi receives this and:
1. Validates the pair code
2. Fetches playlist for store_id + screen_id
3. Starts media player with the playlist
4. Saves configuration for auto-start on reboot

---

## 🐛 Troubleshooting

### "Pi Offline" Error
**Problem**: Dashboard shows "❌ Pi Offline - raspberrypi-ce39 is not responding"

**Solutions**:
1. **Check Pi is running**:
   ```bash
   ssh everydayadvertise@192.168.1.131
   sudo systemctl status pizza-hut-tv
   ```

2. **Check Pi is connected to WebSocket**:
   ```powershell
   Invoke-RestMethod -Uri "https://everydayadvertise.com/api/connected-pis"
   ```
   Should show: `"count": 1` with your Pi ID

3. **Restart Pi service**:
   ```bash
   sudo systemctl restart pizza-hut-tv
   ```

4. **Wait 30 seconds** for Pi to reconnect

---

### Store/Screen Dropdown Not Appearing
**Problem**: After entering pair code, store dropdown doesn't appear

**Solutions**:
1. **Hard refresh browser**: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
2. **Clear browser cache**: Settings → Clear browsing data
3. **Check pair code format**: Must be exactly 4 digits (e.g., 3835)
4. **Open browser console**: F12 → Console tab → Look for errors

---

### Configuration Not Applied
**Problem**: Configuration sent but Pi doesn't start playing

**Solutions**:
1. **Check Pi logs**:
   ```bash
   sudo journalctl -u pizza-hut-tv -n 50
   ```
   Look for: "Configuration received via WebSocket"

2. **Verify pair code matches**: 
   - Dashboard pair code must match Pi's display

3. **Check playlist exists**:
   ```bash
   curl "https://everydayadvertise.com/playlist?pair_code=3835&screen_id=1000_screen1"
   ```

4. **Restart Pi client**:
   ```bash
   sudo systemctl restart pizza-hut-tv
   ```

---

## 📞 Quick Reference

### API Endpoints
- **List Connected Pis**: `GET /api/connected-pis`
- **Check Pi Status**: `GET /api/pi-status-ws/{pi_id}`
- **Configure Pi**: `POST /api/configure-pi-ws`

### Test Commands
```powershell
# Check connected Pis
Invoke-RestMethod -Uri "https://everydayadvertise.com/api/connected-pis"

# Check specific Pi
Invoke-RestMethod -Uri "https://everydayadvertise.com/api/pi-status-ws/raspberrypi-ce39"

# Send test configuration
$config = @{
    pi_id = "raspberrypi-ce39"
    pair_code = "3835"
    store_id = "1000"
    screen_id = "1000_screen1"
    auto_start = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://everydayadvertise.com/api/configure-pi-ws" `
    -Method POST -Body $config -ContentType "application/json"
```

### Pi Service Commands
```bash
# Check status
sudo systemctl status pizza-hut-tv

# Restart service
sudo systemctl restart pizza-hut-tv

# View logs
sudo journalctl -u pizza-hut-tv -f

# Check WebSocket connection
sudo journalctl -u pizza-hut-tv | grep -i "websocket\|registered\|configure"
```

---

## ✅ Success Checklist

Before clicking "Configure Pi", ensure:
- [ ] Pi ID entered correctly
- [ ] Green "Connected" button shows "Pi Online"
- [ ] Pair code is exactly 4 digits
- [ ] Store dropdown appeared and store selected
- [ ] Screen dropdown appeared and screen selected
- [ ] Auto-start checkbox is checked (if desired)
- [ ] Blue "Configure Pi" button is enabled

After clicking "Configure Pi":
- [ ] Green success message appears
- [ ] Message shows all configuration details
- [ ] Modal closes after 3 seconds
- [ ] Pi starts playing content (check physical display)

---

## 🎉 You're Done!

Your Raspberry Pi is now configured and playing content via the WebSocket relay system. No port forwarding, no manual IP configuration, works from anywhere in the world!

**Need to reconfigure?** Just open Remote Pi Manager again and follow the same steps.

---

**System Status**: 🟢 OPERATIONAL  
**Support**: Check browser console (F12) for detailed logs  
**Documentation**: See WEBSOCKET_DEPLOYMENT_COMPLETE.md for technical details
