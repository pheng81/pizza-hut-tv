# 🔧 Remote Pi Manager - Dashboard Integration Fix

## Issues Fixed

### Problem 1: Hardcoded Pi IP in Dashboard Modal
**File**: `templates/dashboard.html`
**Line**: ~1962
**Issue**: The `configureRemotePi()` function was hardcoding Pi IP as `192.168.1.100` instead of using the dynamic IP mapping system.

**Before**:
```javascript
let piIp = '';
if (piId === 'raspberrypi-ce39') { piIp = '192.168.1.100'; }
```

**After**:
```javascript
// First, get Pi IP from status endpoint
const statusResponse = await fetch('/api/pi-status/' + encodeURIComponent(piId));
const statusData = await statusResponse.json();

if (!statusResponse.ok || statusData.status !== 'online') {
    // Show error if Pi is offline
}
// Pi IP is resolved on backend from pi_id_ip_map.json
```

**Result**: ✅ Dashboard now uses auto IP resolution system

---

### Problem 2: Backend API Required Pi IP Parameter
**File**: `app.py` 
**Line**: ~9402
**Issue**: The `/api/configure-pi` endpoint required `pi_ip` parameter but dashboard wasn't sending it after status check.

**Before**:
```python
if not all([pi_id, pair_code, store_id, screen_id, pi_ip]):
    return jsonify({'success': False, 'message': 'Missing required fields'}), 400
```

**After**:
```python
# Validate required fields (except pi_ip which can be auto-resolved)
if not all([pi_id, pair_code, store_id, screen_id]):
    return jsonify({'success': False, 'message': 'Missing required fields'}), 400

# If no IP provided, resolve from mapping file
if not pi_ip:
    import json
    try:
        with open('pi_id_ip_map.json', 'r') as f:
            pi_map = json.load(f)
        pi_ip = pi_map.get(pi_id)
        if pi_ip:
            logging.info(f'Resolved Pi IP from mapping: {pi_id} -> {pi_ip}')
    except Exception as e:
        logging.error(f'Error loading pi_id_ip_map.json: {e}')
        return jsonify({'success': False, 'message': 'Could not resolve Pi IP'}), 400
```

**Result**: ✅ Backend now auto-resolves Pi IP from mapping file

---

### Problem 3: Local Dev Server Inconsistency
**File**: `app_local_dev.py`
**Line**: ~250
**Issue**: Same hardcoded IP requirement as production.

**Fix**: Applied same auto-resolution logic to local dev server.

**Result**: ✅ Both production and local dev servers now use auto IP resolution

---

## How It Works Now

### Complete Flow:

1. **User Opens Dashboard**
   - Clicks "Remote Pi Manager" button
   - Modal opens with Pi ID input field

2. **User Enters Pi ID and Clicks "Connect"**
   - Frontend calls: `GET /api/pi-status/raspberrypi-ce39`
   - Backend reads `pi_id_ip_map.json`
   - Backend resolves: `raspberrypi-ce39` → `192.168.1.131`
   - Backend contacts Pi: `http://192.168.1.131:8080/status`
   - Returns online/offline status

3. **If Pi is Online - Configuration Steps Appear**
   - User fills in:
     - Pair Code (4 digits)
     - Store ID (dropdown)
     - Screen ID (dropdown)
   - User clicks "Configure Pi"

4. **Configuration is Sent**
   - Frontend calls: `POST /api/configure-pi` with:
     ```json
     {
       "pi_id": "raspberrypi-ce39",
       "pair_code": "1234",
       "store_id": "1000",
       "screen_id": "tv1"
     }
     ```
   - **No `pi_ip` needed!** Backend auto-resolves from mapping
   - Backend reads `pi_id_ip_map.json` again
   - Backend resolves IP and sends config to Pi
   - Pi applies configuration and starts playback

5. **Success!**
   - Dashboard shows success message
   - Pi begins playing content for specified store/screen

---

## Files Modified

| File | Changes | Status |
|------|---------|--------|
| `templates/dashboard.html` | Remove hardcoded IP, add status check before config | ✅ Fixed |
| `app.py` | Add auto IP resolution to `/api/configure-pi` | ✅ Fixed |
| `app_local_dev.py` | Add auto IP resolution to `/api/configure-pi` | ✅ Fixed |

---

## Testing Checklist

### Local Testing (app_local_dev.py):
- [x] Dashboard loads correctly
- [x] Remote Pi Manager modal opens
- [x] "Connect" button checks Pi status
- [x] Pi shows online with correct status
- [x] Configuration form appears when Pi online
- [x] "Configure Pi" sends config without needing Pi IP
- [x] Pi receives and applies configuration

### Production Testing (app.py):
- [ ] Deploy updated files to AWS
- [ ] Dashboard loads correctly
- [ ] Remote Pi Manager modal opens
- [ ] "Connect" button checks Pi status via Tailscale
- [ ] Pi shows online with correct status
- [ ] Configuration form appears when Pi online
- [ ] "Configure Pi" sends config without needing Pi IP
- [ ] Pi receives and applies configuration

---

## What's Different from Before

### Before:
- ❌ Dashboard hardcoded Pi IP as `192.168.1.100`
- ❌ Backend required Pi IP in request
- ❌ Only worked for one specific Pi
- ❌ Needed code changes to add new Pis

### After:
- ✅ Dashboard uses auto IP resolution
- ✅ Backend reads from `pi_id_ip_map.json`
- ✅ Works for any Pi ID in mapping file
- ✅ Adding new Pis only requires updating JSON file

---

## Benefits

1. **Scalable**: Add new Pis by updating `pi_id_ip_map.json` only
2. **Maintainable**: No code changes needed for new stores
3. **Flexible**: Works with local IPs (dev) or Tailscale IPs (production)
4. **Consistent**: Same behavior in local dev and production
5. **User-Friendly**: Users only need to know Pi ID, not IP address

---

## Next Steps

### For Local Testing:
1. ✅ Already working! Test at http://127.0.0.1:5002/dashboard
2. ✅ Pi at 192.168.1.131 is responding
3. ✅ Can configure Pi from dashboard modal

### For Production:
1. Deploy updated files to AWS: `.\deploy_to_server.ps1`
2. Install Tailscale on AWS and Pi (see `REMOTE_PI_MANAGER_QUICK_START.md`)
3. Update `pi_id_ip_map.json` with Tailscale IPs
4. Test at https://everydayadvertise.com/dashboard

---

## Configuration File Format

**`pi_id_ip_map.json`** - Maps Pi IDs to IP addresses:

### Local Development:
```json
{
  "raspberrypi-ce39": "192.168.1.131",
  "raspberrypi-a1b2": "192.168.1.132",
  "raspberrypi-c3d4": "192.168.1.133"
}
```

### Production (with Tailscale):
```json
{
  "raspberrypi-ce39": "100.64.0.2",
  "raspberrypi-a1b2": "100.64.0.3",
  "raspberrypi-c3d4": "100.64.0.4"
}
```

**Note**: Pi IDs are automatically generated by the Pi client on first boot and stored in `~/.pizza_hut_tv_id`

---

## Troubleshooting

### "Could not resolve Pi IP"
- Check `pi_id_ip_map.json` exists in server directory
- Verify Pi ID spelling is correct
- Ensure JSON file is valid

### "Pi offline or not found"
- Verify Pi is powered on and connected to network
- Check Pi service is running: `sudo systemctl status pizza-hut-tv`
- Test connectivity: `curl http://[PI_IP]:8080/status`

### "Missing required fields"
- Ensure all fields are filled in dashboard form
- Check browser console for JavaScript errors
- Verify JSON payload in network tab

---

## Summary

✅ **Fixed**: Dashboard Remote Pi Manager now uses auto IP resolution
✅ **Fixed**: Backend `/api/configure-pi` endpoint auto-resolves Pi IPs
✅ **Fixed**: Local dev server matches production behavior
✅ **Ready**: Dashboard integration fully functional
✅ **Scalable**: Easy to add new Pis by updating mapping file

**Status**: 🟢 **PRODUCTION READY** (pending Tailscale deployment)

---

*Last Updated: October 9, 2025*
*Remote Pi Manager Dashboard Integration v2.0*
