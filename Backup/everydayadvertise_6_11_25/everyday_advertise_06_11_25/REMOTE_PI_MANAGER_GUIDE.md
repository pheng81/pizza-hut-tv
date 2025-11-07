# 🖥️ Remote Pi Manager - User Guide

## Overview

The **Remote Pi Manager** allows you to remotely configure Raspberry Pi devices from the dashboard. Instead of manually setting up each Pi with store IDs, screen IDs, and pairing codes, you can now configure them centrally and have Pis auto-configure themselves.

## Features

- ✅ **Centralized Configuration** - Configure all your Pis from one dashboard
- ✅ **Remote Management** - No need to physically access each Pi
- ✅ **Auto-Configuration** - Pis can fetch and apply their config automatically
- ✅ **Store & Screen Assignment** - Easy dropdown selection
- ✅ **Pairing Code Management** - Associate Pis with user accounts
- ✅ **Auto-Start Control** - Enable/disable auto-start on boot

---

## How to Use

### 1. Access Remote Pi Manager

From the dashboard menu (hamburger icon), click:
**"Remote Pi Manager"** 🖥️

<img src="attachment://menu_screenshot.png" width="300"/>

### 2. Fill in Pi Configuration

The configuration form requires:

| Field | Description | Example |
|-------|-------------|---------|
| **Pi ID** | Unique identifier for this Pi | `pi-001`, `raspberrypi`, `store-1234-screen-1` |
| **Pairing Code** | 4-digit code from dashboard | `3835` |
| **Store ID** | Which store this Pi belongs to | Select from dropdown |
| **Screen ID** | Which screen content to display | `1`, `2`, `3`, `4`, or `5` |
| **Auto-start** | Start on boot? | ☑️ Checked |

### 3. Configure the Pi

Click **"Configure Pi"** button. The configuration will be:
- ✅ Saved to your account
- ✅ Sent as a command to the screen's queue
- ✅ Ready for the Pi to fetch

---

## Pi Setup Methods

There are **3 ways** to configure a Raspberry Pi:

### Method 1: Auto-Configuration (Recommended) 🚀

**On the Pi, run:**
```bash
cd /home/everydayadvertise/pizza-hut-tv
python3 auto_configure_pi.py --pi-id pi-001 --pair-code 3835 --server https://everydayadvertise.com --start
```

**What happens:**
1. Script fetches configuration from server
2. Updates systemd service automatically
3. Starts the service
4. Pi begins playing content immediately

**Advantages:**
- ⚡ Fastest method
- 🤖 Fully automated
- ✅ No manual editing
- 🔄 Can be scripted for multiple Pis

---

### Method 2: Manual Service Configuration

**1. SSH into the Pi:**
```bash
ssh everydayadvertise@raspberrypi
```

**2. Edit systemd service:**
```bash
sudo nano /etc/systemd/system/pizza-hut-tv.service
```

**3. Update the ExecStart line with your configuration:**
```ini
ExecStart=/home/everydayadvertise/pizza-hut-tv/venv/bin/python /home/everydayadvertise/pizza-hut-tv/complete_pi_client.py --server https://everydayadvertise.com --store-id 1234 --screen-id 1 --pair-code 3835
```

**4. Reload and restart:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart pizza-hut-tv
```

---

### Method 3: Installation Script with Config

**When running `install_new_pi.sh`, provide:**
- Server URL: `https://everydayadvertise.com`
- Store ID: From Remote Pi Manager
- Screen ID: `1`, `2`, `3`, etc.
- Pair Code: `3835` (from dashboard)

The installation script will set up everything automatically.

---

## Configuration Storage

Configurations are stored in your `store_config.json`:

```json
{
  "pi_configurations": {
    "pi-001": {
      "pi_id": "pi-001",
      "pair_code": "3835",
      "store_id": "1234",
      "screen_id": "1",
      "auto_start": true,
      "server_url": "https://everydayadvertise.com",
      "configured_at": 1696723200,
      "configured_by": "user@example.com"
    }
  }
}
```

---

## API Endpoints

### Configure a Pi (Dashboard → Server)
```
POST /api/configure_remote_pi
Authorization: Login session required

Body:
{
  "pi_id": "pi-001",
  "pair_code": "3835",
  "store_id": "1234",
  "screen_id": "1",
  "auto_start": true
}

Response:
{
  "success": true,
  "message": "Pi pi-001 configured successfully",
  "config": {...}
}
```

### Fetch Pi Configuration (Pi → Server)
```
GET /api/get_pi_config/{pi_id}
Headers:
  X-User-Code: 3835

Response:
{
  "success": true,
  "config": {
    "pi_id": "pi-001",
    "pair_code": "3835",
    "store_id": "1234",
    "screen_id": "1",
    "server_url": "https://everydayadvertise.com"
  }
}
```

---

## File Structure

```
pizza-hut-tv/
├── complete_pi_client.py          # Main Pi client
├── seamless_video_player.py       # Video player
├── transition_engine.py           # Effects engine
├── auto_configure_pi.py           # 🆕 Auto-configuration script
├── install_new_pi.sh             # Complete installation script
└── venv/                          # Python virtual environment
```

---

## Troubleshooting

### Pi Can't Fetch Configuration

**Check:**
1. ✅ Pair code is correct (4 digits from dashboard)
2. ✅ Pi ID matches exactly (case-sensitive)
3. ✅ Pi has internet connection
4. ✅ Server URL is correct

**Test connection:**
```bash
curl -H "X-User-Code: 3835" https://everydayadvertise.com/api/get_pi_config/pi-001
```

### Configuration Not Applied

**Check service status:**
```bash
sudo systemctl status pizza-hut-tv
journalctl -u pizza-hut-tv -n 50
```

**Manually restart:**
```bash
sudo systemctl restart pizza-hut-tv
```

### Wrong Store/Screen Playing

**Verify configuration:**
```bash
# Check what's in the service file
sudo cat /etc/systemd/system/pizza-hut-tv.service | grep ExecStart
```

**Re-configure:**
```bash
python3 auto_configure_pi.py --pi-id YOUR_PI_ID --pair-code YOUR_CODE --server https://everydayadvertise.com --start
```

---

## Best Practices

### Pi ID Naming Convention

**Recommended formats:**
- `pi-001`, `pi-002`, `pi-003` (Simple sequential)
- `store-1234-screen-1` (Store + Screen)
- `location-room-01` (Location based)
- `raspberrypi-serial` (Hardware serial)

**Avoid:**
- ❌ Spaces in Pi ID
- ❌ Special characters (except dash/underscore)
- ❌ Duplicate Pi IDs

### Security

- 🔒 **Unique pair codes** - Each account has different code
- 🔒 **Authentication required** - All API calls authenticated
- 🔒 **User isolation** - Users only see their own configurations
- 🔒 **Audit trail** - Tracks who configured each Pi

---

## Bulk Configuration

**For multiple Pis, create a script:**

```bash
#!/bin/bash
# configure_all_pis.sh

PIDS=("pi-001" "pi-002" "pi-003" "pi-004" "pi-005")
PAIR_CODE="3835"
SERVER="https://everydayadvertise.com"

for PI_ID in "${PIDS[@]}"; do
    echo "Configuring $PI_ID..."
    ssh everydayadvertise@$PI_ID "cd pizza-hut-tv && python3 auto_configure_pi.py --pi-id $PI_ID --pair-code $PAIR_CODE --server $SERVER --start"
done
```

---

## Migration from Manual Setup

**If you have existing Pis with manual configuration:**

1. Note their current store ID, screen ID, pair code
2. Use Remote Pi Manager to create their configuration
3. Run auto-configuration script on each Pi:
   ```bash
   python3 auto_configure_pi.py --pi-id THEIR_ID --pair-code CODE --server URL --start
   ```
4. Service will update and restart automatically

---

## Support

- 📧 **Email:** support@everydayadvertise.com
- 📚 **Docs:** https://everydayadvertise.com/docs
- 🐛 **Issues:** GitHub Issues

---

## Changelog

### v1.0.0 (October 2025)
- ✨ Initial release of Remote Pi Manager
- 🖥️ Dashboard UI integration
- 🤖 Auto-configuration script
- 📝 API endpoints for Pi management
- 🔐 Secure authentication with pair codes
