# 🚀 Quick Start - Pi Setup Guide

## Problem Solved ✅

**Before:** You needed to manually assign a "Pi ID" to each Raspberry Pi
**Now:** The Pi automatically uses its hostname (e.g., `raspberrypi`) or MAC address!

---

## Two Ways to Set Up a Pi

### Option 1: Simple Setup Script (Recommended) ⭐

**On the Raspberry Pi:**
```bash
cd ~/pizza-hut-tv
python3 setup_pi_client.py
```

**It will:**
1. ✅ Auto-detect Pi's hostname (e.g., `raspberrypi`)
2. ✅ Show you the Pi's MAC address, IP, serial number
3. ✅ Ask for your pairing code (`3835`)
4. ✅ Ask for store ID and screen ID
5. ✅ Check if you already configured it remotely from dashboard
6. ✅ Set up and start the service automatically

**Interactive Example:**
```
╔═══════════════════════════════════════════════════════╗
║   🍕 Pizza Hut TV - Pi Client Setup 🍕               ║
╚═══════════════════════════════════════════════════════╝

🔍 Detected Pi Information:
   Hostname:      raspberrypi
   MAC Address:   b8:27:eb:12:34:56
   IP Address:    192.168.1.100
   Serial:        00000000a1b2c3d4

Pi Identifier [raspberrypi]: ⏎ (just press Enter)
Server URL [https://everydayadvertise.com]: ⏎
Your Pairing Code (4 digits): 3835
Store ID: 1234
Screen ID [1]: ⏎

✅ Proceed with this configuration? (y/N): y
```

Done! Service starts automatically! 🎉

---

### Option 2: Quick Command Line

If you already know your settings:

```bash
python3 setup_pi_client.py --pair-code 3835 --store-id 1234 --screen-id 1 --start
```

**The Pi will:**
- Use its hostname as identifier
- Check dashboard for remote config
- Set up and start immediately

---

## Remote Configuration from Dashboard

### Step 1: In Dashboard Menu

1. Click hamburger menu (☰)
2. Click "**Remote Pi Manager**" 🖥️ (if you don't see it, hard refresh: Ctrl+F5)
3. Fill in:
   - **Pi Identifier:** `raspberrypi` (the Pi's hostname)
   - **Pairing Code:** `3835` (auto-filled from your account)
   - **Store:** Select from dropdown
   - **Screen:** Select 1-5
4. Click "**Configure Pi**"

### Step 2: On the Pi

```bash
python3 setup_pi_client.py
```

When it asks for pairing code and store/screen, just enter them, and it will automatically fetch the remote config if available!

---

## How Pi Identity Works

The system now uses **what the Pi already has**:

| Identity Type | Example | When to Use |
|--------------|---------|-------------|
| **Hostname** | `raspberrypi` | Default, easiest |
| **Custom Name** | `store-1234-screen-1` | For organization |
| **MAC Address** | `b8:27:eb:12:34:56` | Hardware-based unique ID |

**To change hostname on Pi:**
```bash
sudo raspi-config
# System Options → Hostname → Enter new name
```

---

## What Changed

### Old Way ❌
```
1. Think of a Pi ID manually
2. Enter it in dashboard
3. SSH to Pi and enter same ID
4. Hope you didn't make typo
```

### New Way ✅
```
1. Pi automatically uses its hostname
2. Dashboard asks for hostname (e.g., "raspberrypi")
3. Pi setup script auto-detects and uses hostname
4. Everything matches automatically!
```

---

## Files You Need on Each Pi

Just copy these 4 files to `~/pizza-hut-tv/`:

1. `complete_pi_client.py` - Main client
2. `seamless_video_player.py` - Video player
3. `transition_engine.py` - Effects engine
4. `setup_pi_client.py` - **NEW** - Easy setup script

**Copy command from your PC:**
```powershell
scp complete_pi_client.py seamless_video_player.py transition_engine.py setup_pi_client.py everydayadvertise@raspberrypi:~/pizza-hut-tv/
```

---

## Troubleshooting

### "I don't see Remote Pi Manager button"

**Solution:** Hard refresh your browser
- **Windows:** Ctrl + F5
- **Mac:** Cmd + Shift + R
- **Or:** Clear browser cache

### "What's my Pi's hostname?"

**On the Pi, run:**
```bash
hostname
```

Most Raspberry Pis default to `raspberrypi`

### "I want to change the hostname"

**Option 1: Using raspi-config**
```bash
sudo raspi-config
# System Options → Hostname → Enter new name
sudo reboot
```

**Option 2: Manually**
```bash
sudo hostnamectl set-hostname my-new-name
sudo reboot
```

### "Can I use the same setup for multiple Pis?"

**Yes!** Just make sure each Pi has a unique hostname:
- `raspberrypi-1`, `raspberrypi-2`, `raspberrypi-3`
- Or: `store-1-screen-1`, `store-1-screen-2`

---

## Quick Reference

### Check Pi Identity
```bash
hostname                    # Show hostname
ifconfig | grep ether       # Show MAC address
cat /proc/cpuinfo | grep Serial  # Show CPU serial
```

### Service Commands
```bash
sudo systemctl status pizza-hut-tv      # Check status
sudo systemctl restart pizza-hut-tv     # Restart
journalctl -u pizza-hut-tv -f           # View logs
sudo systemctl enable pizza-hut-tv      # Enable auto-start
```

### Re-configure Pi
```bash
cd ~/pizza-hut-tv
python3 setup_pi_client.py
```

---

## Summary

✅ **No more manual Pi IDs!**
✅ **Pi auto-detects its identity**
✅ **Dashboard pre-fills your pairing code**
✅ **Remote config from dashboard (optional)**
✅ **One command setup on Pi**

**On Pi:**
```bash
python3 setup_pi_client.py
```

That's it! 🎉
