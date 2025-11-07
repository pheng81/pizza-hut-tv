# 🔄 Remote Client Restart Feature

## Overview
You can now remotely restart the `complete_pi_client.py` software directly from the dashboard without SSH access!

## How to Use

### 1. Open Remote Pi Manager
- Go to: https://everydayadvertise.com/dashboard
- Click **"Remote Pi Manager"** in the sidebar

### 2. Connect to Pi
- Enter Pi ID: `raspberrypi-ce39`
- Click **"Connected"** button
- Wait for green **"✅ Pi Online"** status

### 3. Restart Client Software
- Click the **"🔄 Restart Client"** button (blue button)
- Confirm the action in the popup dialog
- Watch the status messages:
  - "🔄 Restarting client software..."
  - "✅ Client is restarting..."
  - "🔄 Reconnecting..."

### 4. Wait for Reconnection
- The Pi screen will briefly go blank (5-10 seconds)
- Client software automatically restarts
- Pi reconnects to server
- Live stream resumes automatically

## Button Locations

When Pi is connected, you'll see these buttons:

| Button | Color | Function |
|--------|-------|----------|
| **⏹️ Close Screen** | Orange | Close the display screen on Pi |
| **🔄 Restart Client** | Blue | Restart complete_pi_client software |
| **🔄 Restart Pi** | Red | Reboot the entire Raspberry Pi |

## Technical Details

### What Happens When You Click "Restart Client"?

1. **Dashboard** → Sends WebSocket event `restart_client` to server
2. **Server** → Forwards command to specific Pi via WebSocket
3. **Pi Client** → Receives command and:
   - Sends acknowledgment: `client_restarting`
   - Closes pygame display
   - Attempts `systemctl --user restart complete_pi_client`
   - Fallback: Re-executes Python script with `os.execv()`
4. **Dashboard** → Shows status updates
5. **Pi** → Reconnects after restart (5-10 seconds)

### WebSocket Events

```javascript
// Dashboard sends:
socket.emit('restart_client', { pi_id: 'raspberrypi-ce39' });

// Pi responds:
socket.emit('client_restarting', { 
    pi_id: 'raspberrypi-ce39',
    status: 'restarting',
    message: 'Client is restarting...'
});
```

### Error Handling

If restart fails, you'll see error messages:
- ❌ "Pi not connected" - Pi is offline
- ❌ "Not connected to server" - WebSocket disconnected
- ❌ "Error: [specific error]" - Technical issue

### Fallback Methods

If the button doesn't work:

#### Method 1: SSH Manual Restart
```bash
ssh everydayadvertise@192.168.1.131
pkill -f complete_pi_client.py
python3 /home/everydayadvertise/complete_pi_client.py &
```

#### Method 2: Create systemd Service (Recommended)
```bash
# Create service file
cat > ~/.config/systemd/user/complete_pi_client.service << 'EOF'
[Unit]
Description=Pizza Hut TV Complete Pi Client
After=graphical.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/everydayadvertise/complete_pi_client.py
Restart=always
RestartSec=10
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
EOF

# Enable and start
systemctl --user daemon-reload
systemctl --user enable complete_pi_client
systemctl --user start complete_pi_client

# Now you can restart with:
systemctl --user restart complete_pi_client
```

## Use Cases

### When to Use "Restart Client" vs "Restart Pi"

| Scenario | Use "Restart Client" | Use "Restart Pi" |
|----------|---------------------|------------------|
| Client software frozen | ✅ Yes | ❌ No (too extreme) |
| Display not updating | ✅ Yes | ❌ No |
| After code changes | ✅ Yes | ❌ No |
| Network issues | ❌ No | ✅ Yes |
| System updates | ❌ No | ✅ Yes |
| Hardware problems | ❌ No | ✅ Yes |

### Best Practices

1. **Try Restart Client First** - Less disruptive, faster recovery
2. **Monitor Live Stream** - Watch for screen reconnection
3. **Wait 10 Seconds** - Give client time to restart before trying again
4. **Full Reboot Last Resort** - Use "Restart Pi" only if client restart fails

## Troubleshooting

### Client Doesn't Restart
1. Check Pi is online (green status)
2. Check WebSocket connection (see browser console)
3. Try "Restart Pi" as fallback
4. Use SSH manual restart

### Screen Stays Black
1. Wait 15 seconds (client may still be loading)
2. Check Pi logs: `ssh everydayadvertise@192.168.1.131 "journalctl --user -u complete_pi_client -n 50"`
3. Manually restart via SSH

### Button Not Visible
1. Make sure Pi is connected (green status)
2. Hard refresh dashboard: Ctrl+Shift+R
3. Check Pi version has restart handler (deployed: 2025-10-12)

## Security

- ✅ Restart command only sent to authenticated Pis
- ✅ WebSocket connection required (no REST API exposure)
- ✅ Confirmation dialog prevents accidental restarts
- ✅ Status updates show what's happening

## Benefits

- ⚡ **Fast Recovery** - 5-10 seconds vs minutes for full reboot
- 🎯 **Targeted** - Restarts only client software, not entire system
- 🔒 **Safe** - No filesystem changes, just process restart
- 📱 **Convenient** - No SSH needed, works from dashboard
- 🔄 **Automatic** - Client reconnects automatically after restart

## Future Enhancements

Potential improvements:
- [ ] Scheduled restarts (daily at 3 AM)
- [ ] Auto-restart on crash detection
- [ ] Restart with config reload
- [ ] Batch restart multiple Pis
- [ ] Restart logs/history

---

**Last Updated:** 2025-10-12  
**Feature Status:** ✅ Deployed and Active
