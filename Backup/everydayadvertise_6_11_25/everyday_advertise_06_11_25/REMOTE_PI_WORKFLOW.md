# 🎯 Remote Pi Manager - Simple Workflow

## The Complete Process (2 Steps)

### Step 1: Configure from Dashboard 💻

1. **Open Dashboard Menu**
   - Click hamburger menu (☰) in top right
   - Click "**Remote Pi Manager**" 🖥️
   
   > ⚠️ **Don't see the button?** Press **Ctrl+F5** (Windows) or **Cmd+Shift+R** (Mac) to hard refresh

2. **Fill in the Form:**

   | Field | What to Enter | Example |
   |-------|---------------|---------|
   | **Pi Identifier** | The Pi's hostname or name you choose | `raspberrypi` or `store-1-screen-1` |
   | **Pairing Code** | Your 4-digit code (already filled) | `3835` |
   | **Store ID** | Select from dropdown | `1234 - Main Store` |
   | **Screen ID** | Which screen (1-5) | `1` |
   | **Auto-start** | Keep checked ✓ | ✓ |

3. **Click "Configure Pi"**
   - ✅ Configuration saved!
   - The system now knows: "When a Pi with ID 'raspberrypi' connects with pairing code 3835, it should play Store 1234, Screen 1"

---

### Step 2: Setup the Pi 🖥️

**SSH into your Raspberry Pi:**
```bash
ssh everydayadvertise@raspberrypi
cd ~/pizza-hut-tv
```

**Run the setup script:**
```bash
python3 setup_pi_client.py
```

**Answer the prompts:**
```
Pi Identifier [raspberrypi]: raspberrypi  ← MUST match what you entered in dashboard!
Server URL [https://everydayadvertise.com]: ⏎ (just press Enter)
Your Pairing Code (4 digits): 3835
Store ID: 1234
Screen ID [1]: 1
```

**The script will:**
- ✅ Check dashboard for remote configuration
- ✅ Use remote settings if found (Store 1234, Screen 1)
- ✅ Set up systemd service
- ✅ Start playing content immediately

---

## Key Point: Pi Identifier MUST Match! 🔑

**Dashboard:** Enter `raspberrypi`  
**On Pi Setup:** Enter `raspberrypi`  
**They MUST be identical!**

---

## Quick Setup (If You Already Know Settings)

**On the Pi:**
```bash
python3 setup_pi_client.py --pair-code 3835 --store-id 1234 --screen-id 1
```

The Pi will automatically use its hostname (`raspberrypi`) and check the dashboard for configuration.

---

## What if I Can't See "Remote Pi Manager" Button?

The button was just added! Your browser cached the old dashboard.

**Fix it:**

### Windows:
1. Press **Ctrl + F5** (hard refresh)
2. Or: Press **Ctrl + Shift + Delete** → Clear cache → Refresh

### Mac:
1. Press **Cmd + Shift + R** (hard refresh)
2. Or: **Cmd + Option + E** → Clear cache → Refresh

### Alternative:
Open dashboard in **Incognito/Private** window - the button will be there!

---

## Naming Your Pis

Choose clear, consistent names:

### ✅ Good Names:
- `raspberrypi` (default, simple)
- `store-1234-screen-1` (organized by location)
- `location-main-screen-1` (descriptive)
- `pi-001`, `pi-002`, `pi-003` (sequential)

### ❌ Avoid:
- Names with spaces: `store 1` ❌
- Special characters: `store#1` ❌
- Too generic: `pi` ❌
- Duplicates: Two Pis both named `raspberrypi` ❌

---

## Changing a Pi's Hostname

**If you want to rename a Pi from `raspberrypi` to something else:**

```bash
sudo raspi-config
# Navigate to: System Options → Hostname
# Enter new name (e.g., store-1-screen-1)
# Reboot: sudo reboot
```

**Then:**
1. Update dashboard configuration with new name
2. Re-run `setup_pi_client.py` on the Pi

---

## How Remote Configuration Works

```
┌─────────────────┐
│   Dashboard     │  ← You configure: Pi "raspberrypi" → Store 1234, Screen 1
└────────┬────────┘
         │
         │ Configuration saved to server
         │
         ▼
┌─────────────────┐
│     Server      │  ← Stores: "raspberrypi" = {store: 1234, screen: 1, pair_code: 3835}
└────────┬────────┘
         │
         │ Pi requests config
         │
         ▼
┌─────────────────┐
│  Raspberry Pi   │  ← Fetches config using Pi ID "raspberrypi" + pair code 3835
└─────────────────┘     Starts playing Store 1234, Screen 1 automatically
```

---

## Without Remote Configuration (Manual)

If you **skip the dashboard step**, just run on the Pi:

```bash
python3 setup_pi_client.py --pair-code 3835 --store-id 1234 --screen-id 1
```

It will work fine - just won't fetch anything from dashboard.

---

## Multiple Pis Example

**Dashboard Configuration:**

| Pi Identifier | Store | Screen |
|--------------|-------|--------|
| `pi-store-1-screen-1` | 1234 | 1 |
| `pi-store-1-screen-2` | 1234 | 2 |
| `pi-store-2-screen-1` | 5678 | 1 |

**On Each Pi:**

```bash
# Pi #1
python3 setup_pi_client.py
# Enter: pi-store-1-screen-1

# Pi #2
python3 setup_pi_client.py
# Enter: pi-store-1-screen-2

# Pi #3
python3 setup_pi_client.py
# Enter: pi-store-2-screen-1
```

Each Pi fetches its specific configuration automatically! 🎉

---

## Troubleshooting

### "Button not visible"
→ Hard refresh: **Ctrl+F5** or clear browser cache

### "Configuration not found"
→ Make sure Pi ID in dashboard **exactly matches** what you enter on Pi

### "Wrong store/screen playing"
→ Check: `sudo cat /etc/systemd/system/pizza-hut-tv.service | grep ExecStart`

### "Want to reconfigure"
→ Just run `python3 setup_pi_client.py` again!

---

## Summary

1. **Dashboard:** Enter Pi identifier + Store + Screen → Save
2. **On Pi:** Run setup script → Enter same identifier → Auto-configured! ✅

That's it! 🚀
