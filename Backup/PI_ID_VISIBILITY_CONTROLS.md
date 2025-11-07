# 📟 Pi ID Visibility Controls

## Summary

The Pi ID watermark can now be **hidden, shown, or auto-hidden** to keep customer-facing displays clean while still allowing easy identification when needed.

---

## 🎮 Controls

### Keyboard Shortcut
**Press `I` key** to toggle Pi ID visibility on/off

- **Press once** → Hide Pi ID
- **Press again** → Show Pi ID
- Works anytime during playback
- No need to restart

### Command-Line Options

#### Start with Pi ID Hidden
```bash
python3 complete_pi_client.py --hide-pi-id
```
- Pi ID won't show on startup
- Press `I` anytime to reveal it temporarily

#### Custom Auto-Hide Timer
```bash
python3 complete_pi_client.py --pi-id-auto-hide 60
```
- Shows Pi ID for 60 seconds after startup
- Then automatically hides
- Press `I` to show again for another 60 seconds

#### Disable Auto-Hide (Always Show)
```bash
python3 complete_pi_client.py --pi-id-auto-hide 0
```
- Pi ID stays visible permanently
- Still can toggle with `I` key

#### Combined Example
```bash
python3 complete_pi_client.py --hide-pi-id --pi-id-auto-hide 120
```
- Starts hidden
- When shown (press `I`), auto-hides after 120 seconds

---

## 🔄 Default Behavior

**Out of the box:**
- ✅ Pi ID **shows** when client starts
- ✅ Auto-hides after **5 minutes** (300 seconds)
- ✅ Press `I` to show again
- ✅ Includes hint: `[Press 'I' to hide]`

---

## 💡 Use Cases

### Scenario 1: Customer-Facing Display
**Requirement:** Pi ID should never be visible to customers

**Solution:**
```bash
python3 complete_pi_client.py --hide-pi-id
```

**Or update systemd service:**
```ini
ExecStart=/path/to/venv/bin/python /path/to/complete_pi_client.py --server https://everydayadvertise.com --store-id 1234 --screen-id 1 --hide-pi-id
```

**When needed:** Admin can press `I` key to temporarily show Pi ID, then press `I` again to hide.

---

### Scenario 2: During Setup/Testing
**Requirement:** Need to see Pi ID while configuring, then hide it

**Solution:** Default behavior works perfectly!
- Shows Pi ID for first 5 minutes
- Auto-hides after setup complete
- Can show again anytime with `I` key

---

### Scenario 3: Internal/Staff Display
**Requirement:** Always show Pi ID for easy identification

**Solution:**
```bash
python3 complete_pi_client.py --pi-id-auto-hide 0
```

**Or update systemd service:**
```ini
ExecStart=... --pi-id-auto-hide 0
```

---

### Scenario 4: Quick Setup Window
**Requirement:** Show Pi ID for 30 seconds during boot, then hide

**Solution:**
```bash
python3 complete_pi_client.py --pi-id-auto-hide 30
```

Admin has 30 seconds to see and note down the Pi ID.

---

## 🔧 Systemd Service Configuration

### Example 1: Hidden by Default
```ini
[Service]
ExecStart=/home/everydayadvertise/pizza-hut-tv/venv/bin/python \
          /home/everydayadvertise/pizza-hut-tv/complete_pi_client.py \
          --server https://everydayadvertise.com \
          --store-id 1234 \
          --screen-id 1 \
          --pair-code 3835 \
          --hide-pi-id
```

### Example 2: 60-Second Auto-Hide
```ini
[Service]
ExecStart=/home/everydayadvertise/pizza-hut-tv/venv/bin/python \
          /home/everydayadvertise/pizza-hut-tv/complete_pi_client.py \
          --server https://everydayadvertise.com \
          --store-id 1234 \
          --screen-id 1 \
          --pair-code 3835 \
          --pi-id-auto-hide 60
```

### Example 3: Always Visible
```ini
[Service]
ExecStart=/home/everydayadvertise/pizza-hut-tv/venv/bin/python \
          /home/everydayadvertise/pizza-hut-tv/complete_pi_client.py \
          --server https://everydayadvertise.com \
          --store-id 1234 \
          --screen-id 1 \
          --pair-code 3835 \
          --pi-id-auto-hide 0
```

---

## 📊 Visibility States

| State | Description | How to Achieve |
|-------|-------------|----------------|
| **Visible** | Pi ID shown on screen | Default, or press `I` |
| **Hidden** | Pi ID not displayed | Press `I` or `--hide-pi-id` |
| **Auto-Hide** | Shows then hides after timer | `--pi-id-auto-hide N` |
| **Always Visible** | Never auto-hides | `--pi-id-auto-hide 0` |

---

## 🎨 What It Looks Like

### When Visible
```
┌────────────────────────────────────────┐
│                                        │
│        Video Playing Here              │
│                                        │
│                                        │
│              ┌──────────────────────┐  │
│              │ Pi ID: pi-a1b2       │  │ ← Bottom right
│              │ [Press 'I' to hide]  │  │
│              └──────────────────────┘  │
└────────────────────────────────────────┘
```

### When Hidden
```
┌────────────────────────────────────────┐
│                                        │
│        Video Playing Here              │
│                                        │
│                                        │
│                                        │ ← Nothing shown
│                                        │
│                                        │
└────────────────────────────────────────┘
```

---

## 🔍 How to Check Pi ID When Hidden

**Method 1: Press `I` key**
- Temporarily reveals Pi ID
- Press `I` again to hide

**Method 2: Check log file**
```bash
journalctl -u pizza-hut-tv | grep "Pi ID"
```

**Output:**
```
📟 Pi ID loaded: raspberrypi-a1b2
```

**Method 3: Check Pi ID file**
```bash
cat ~/.pizza_hut_tv_id
```

**Output:**
```
raspberrypi-a1b2
```

---

## 🚀 Quick Commands Reference

```bash
# Show current Pi ID (from file)
cat ~/.pizza_hut_tv_id

# Start with Pi ID hidden
python3 complete_pi_client.py --hide-pi-id

# Auto-hide after 2 minutes
python3 complete_pi_client.py --pi-id-auto-hide 120

# Never auto-hide
python3 complete_pi_client.py --pi-id-auto-hide 0

# Start hidden + auto-hide when shown
python3 complete_pi_client.py --hide-pi-id --pi-id-auto-hide 60

# Check service status and see Pi ID setting
sudo systemctl status pizza-hut-tv
journalctl -u pizza-hut-tv -n 20 | grep "Pi ID"
```

---

## 📝 Summary

| Feature | How To |
|---------|--------|
| **Toggle visibility** | Press `I` key |
| **Start hidden** | `--hide-pi-id` |
| **Auto-hide timer** | `--pi-id-auto-hide N` (seconds) |
| **Always show** | `--pi-id-auto-hide 0` |
| **Check Pi ID** | `cat ~/.pizza_hut_tv_id` |
| **View in logs** | `journalctl -u pizza-hut-tv \| grep "Pi ID"` |

**Default:** Shows for 5 minutes, then auto-hides. Press `I` anytime to toggle! ✨
