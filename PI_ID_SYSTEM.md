# 📟 Pi ID System - Auto-Generated Identification

## Overview

Every Raspberry Pi now gets a **unique, auto-generated ID** that:
- ✅ **Displays on screen** as a watermark (bottom-right corner)
- ✅ **Persists across reboots** (saved in `~/.pizza_hut_tv_id`)
- ✅ **Identifies the device** for remote management
- ✅ **Admin-friendly** - Just look at the screen to see the Pi ID!

---

## How Pi ID Works

### Auto-Generation Formula
```
Pi ID = hostname-XXXX

Examples:
- raspberrypi-a1b2
- store-main-c3d4
- kitchen-screen-e5f6
```

**Where XXXX comes from:** Last 4 characters of the Pi's MAC address (hardware-based, unique)

### On-Screen Display

```
┌────────────────────────────────────────┐
│                                        │
│        Video/Image Playing Here        │
│                                        │
│                                        │
│                                        │
│                    ┌─────────────────┐ │
│                    │ Pi ID: pi-a1b2  │ │ ← Bottom right watermark
│                    └─────────────────┘ │
└────────────────────────────────────────┘
```

- **Semi-transparent** background (doesn't block content)
- **Always visible** during playback
- **Small and unobtrusive** but easy to read

---

## Setup Workflow

### Step 1: First Boot

When you run `setup_pi_client.py` for the first time:

```bash
python3 setup_pi_client.py
```

**Output:**
```
╔═══════════════════════════════════════════════════════╗
║   🍕 Pizza Hut TV - Pi Client Setup 🍕               ║
╚═══════════════════════════════════════════════════════╝

🔍 Detected Pi Information:
   Hostname:      raspberrypi
   MAC Address:   b8:27:eb:12:34:56
   IP Address:    192.168.1.100
   Serial:        00000000a1b2c3d4

   📟 Generated Pi ID: raspberrypi-3456
   (This ID will be displayed on screen)

Pi Identifier [raspberrypi-3456]: ⏎ (just press Enter)
```

The ID is:
1. ✅ **Auto-generated** from hostname + MAC
2. ✅ **Saved** to `~/.pizza_hut_tv_id`
3. ✅ **Shown during setup**
4. ✅ **Displayed on screen** during playback

---

### Step 2: Remote Management from Dashboard

Admin can now configure the Pi remotely:

1. **Look at the Pi's screen** → See "Pi ID: raspberrypi-3456"
2. **Open Dashboard → Remote Pi Manager**
3. **Enter the Pi ID:** `raspberrypi-3456`
4. **Select Store & Screen**
5. **Click Configure**

The Pi will fetch its configuration automatically!

---

## Benefits

### ✅ No Manual ID Assignment
**Before:** Admin had to manually think of Pi IDs and track them
**Now:** Pi generates its own unique ID automatically

### ✅ Visual Identification
**Before:** Had to SSH into Pi or check config files to find ID
**Now:** Just look at the screen bottom-right corner!

### ✅ Hardware-Based Uniqueness
**Before:** Risk of duplicate IDs if admin made mistake
**Now:** MAC address ensures every Pi has unique ID

### ✅ Persistent Across Reinstalls
**Before:** Lost ID if OS was reinstalled
**Now:** ID saved in file, survives reboots and updates

---

## Pi ID File Location

**File:** `~/.pizza_hut_tv_id`

**Example content:**
```
raspberrypi-3456
```

### Commands

**View your Pi ID:**
```bash
cat ~/.pizza_hut_tv_id
```

**Manually set a Pi ID:**
```bash
echo "my-custom-pi-id" > ~/.pizza_hut_tv_id
```

**Delete and regenerate:**
```bash
rm ~/.pizza_hut_tv_id
python3 complete_pi_client.py  # Will generate new ID
```

---

## Remote Management Workflow

### Scenario: Configure 10 New Pis

**Traditional way (tedious):**
1. SSH into each Pi
2. Manually configure with store/screen
3. Keep spreadsheet of which Pi is which
4. Hope you didn't mess up

**New way (easy):**
1. Install all Pis and start them
2. Walk around and **write down Pi IDs from screens**:
   - Pi 1: `raspberrypi-a1b2` 
   - Pi 2: `raspberrypi-c3d4`
   - Pi 3: `raspberrypi-e5f6`
3. Go to dashboard, configure each by entering its ID
4. Done! ✅

---

## Customizing Pi IDs

### Change Hostname (Easy Method)

If you want friendlier Pi IDs like `store-1-screen-1-a1b2`:

```bash
sudo raspi-config
# System Options → Hostname → Enter: store-1-screen-1
sudo reboot
```

**Result:**
- Old ID: `raspberrypi-a1b2`
- New ID: `store-1-screen-1-a1b2`

### Manual Override

Want a completely custom ID?

```bash
echo "my-custom-id" > ~/.pizza_hut_tv_id
sudo systemctl restart pizza-hut-tv
```

The custom ID will appear on screen immediately!

---

## Dashboard Integration

### In Remote Pi Manager

When configuring a Pi:

```
╔══════════════════════════════════════════╗
║     🖥️ Remote Pi Manager                ║
╠══════════════════════════════════════════╣
║                                          ║
║  Pi Identifier: [raspberrypi-3456    ]  ║
║  (Look at the Pi's screen for this ID)  ║
║                                          ║
║  Pairing Code:  [3835               ]  ║
║  Store:         [▼ 1234 - Main Store ]  ║
║  Screen:        [▼ Screen 1          ]  ║
║                                          ║
║              [Configure Pi]              ║
╚══════════════════════════════════════════╝
```

### API Endpoint

**Get Pi configuration:**
```
GET /api/get_pi_config/raspberrypi-3456
Headers: X-User-Code: 3835

Response:
{
  "success": true,
  "config": {
    "pi_id": "raspberrypi-3456",
    "store_id": "1234",
    "screen_id": "1",
    "pair_code": "3835"
  }
}
```

---

## Troubleshooting

### Can't See Pi ID on Screen

**Check:**
1. Is the Pi in "playing" mode? (Not still in setup)
2. Hard refresh if using webplayer
3. Check logs: `journalctl -u pizza-hut-tv | grep "Pi ID"`

**Expected log:**
```
📟 Pi ID loaded: raspberrypi-3456
```

### Pi ID File Missing

**Recreate:**
```bash
python3 -c "
import socket, uuid, os
hostname = socket.gethostname()
mac = ':'.join(['{:02x}'.format((uuid.getnode() >> e) & 0xff) for e in range(0,2*6,2)][::-1])
pi_id = f'{hostname}-{mac.replace(\":\", \"\")[-4:]}'
with open(os.path.expanduser('~/.pizza_hut_tv_id'), 'w') as f:
    f.write(pi_id)
print(f'Generated Pi ID: {pi_id}')
"
```

### Want to Change Pi ID

**Option 1:** Change hostname
```bash
sudo raspi-config  # Change hostname
sudo reboot
rm ~/.pizza_hut_tv_id  # Remove old ID file
# New ID will be generated on next start
```

**Option 2:** Manual override
```bash
echo "new-pi-id" > ~/.pizza_hut_tv_id
sudo systemctl restart pizza-hut-tv
```

---

## Technical Details

### Pi ID Generation Code

```python
def _get_or_create_pi_id(self) -> str:
    """Generate or load persistent Pi ID."""
    id_file = os.path.expanduser('~/.pizza_hut_tv_id')
    
    # Try loading existing
    if os.path.exists(id_file):
        with open(id_file, 'r') as f:
            return f.read().strip()
    
    # Generate new
    hostname = socket.gethostname()
    mac = get_mac_address()
    mac_suffix = mac.replace(':', '')[-4:]
    pi_id = f"{hostname}-{mac_suffix}"
    
    # Save to file
    with open(id_file, 'w') as f:
        f.write(pi_id)
    
    return pi_id
```

### On-Screen Display Code

```python
def draw_overlay_info(self):
    """Draw Pi ID watermark."""
    # Create Pi ID text
    pi_id_text = f"Pi ID: {self.pi_id}"
    pi_id_surface = self.font_small.render(pi_id_text, True, (255, 255, 255))
    pi_id_surface.set_alpha(180)  # Semi-transparent
    
    # Position bottom-right
    pi_id_rect = pi_id_surface.get_rect()
    pi_id_rect.bottomright = (self.width - 10, self.height - 10)
    
    # Semi-transparent background
    bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
    bg_surface.fill((0, 0, 0, 128))
    
    # Draw
    self.screen.blit(bg_surface, bg_rect)
    self.screen.blit(pi_id_surface, pi_id_rect)
```

---

## Example Deployment

### 5 Pis in Same Store

**Physical setup:**
1. Connect all 5 Pis
2. Install software: `bash install_new_pi.sh`
3. Run setup on each
4. Write down IDs from screens:

| Location | Pi ID | Assignment |
|----------|-------|------------|
| Kitchen Display | `kitchen-pi-a1b2` | Store 1234, Screen 1 |
| Dining Area Left | `dining-left-c3d4` | Store 1234, Screen 2 |
| Dining Area Right | `dining-right-e5f6` | Store 1234, Screen 3 |
| Drive-thru Menu | `drivethru-g7h8` | Store 1234, Screen 4 |
| Counter Display | `counter-i9j0` | Store 1234, Screen 5 |

**Dashboard config:**
- All use same pair code (3835)
- All use same store (1234)
- Different screens (1-5)
- Configure in 2 minutes!

---

## Summary

✅ **Auto-generated** - No manual ID assignment needed
✅ **Visible on screen** - Easy identification
✅ **Persistent** - Survives reboots and updates  
✅ **Unique** - Hardware MAC-based uniqueness
✅ **Remote management** - Configure from dashboard by Pi ID
✅ **Admin-friendly** - Just look at the screen!

**The admin workflow:**
1. Look at Pi screen → See Pi ID
2. Dashboard → Enter Pi ID → Configure
3. Done! 🎉
