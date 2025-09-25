# Manual Pi Client Update Instructions

## To update the EA TV Pi client with enhanced synchronization:

### Option 1: Direct SSH Transfer
1. Open a new PowerShell terminal
2. Run: `scp phtv_pi_client.py everydayadvertise@raspberrypi:/home/everydayadvertise/`
3. Enter password: `pheng168`
4. If successful, restart EA TV by clicking the desktop icon

### Option 2: Manual Copy via SSH
1. SSH into the Pi: `ssh everydayadvertise@raspberrypi`
2. Password: `pheng168`
3. Navigate to: `cd /home/everydayadvertise`
4. Edit the file: `nano phtv_pi_client.py`
5. Copy the enhanced sync methods from the local file

### Option 3: Use WinSCP or similar GUI tool
1. Connect to `raspberrypi` with user `everydayadvertise` and password `pheng168`
2. Navigate to `/home/everydayadvertise/`
3. Upload the `phtv_pi_client.py` file

### Verification
After updating, the EA TV desktop icon should run with:
- ✅ Enhanced synchronization matching webplayer
- ✅ Global server-coordinated timing
- ✅ Professional sync transitions
- ✅ Identical behavior to browser-based players

### Test Synchronization
1. Click EA TV icon on Pi desktop
2. Open webplayer on browser: `http://54.252.90.27:8082/webplayer`
3. Both should sync perfectly with screens 1, 2, and 3

The enhanced Pi client now includes:
- `fetch_sync_time()` - Gets server timestamps
- `calculate_sync_moment()` - Calculates sync timing
- `schedule_sync_transition()` - Schedules transitions
- `execute_sync_transition()` - Executes sync changes
- Enhanced main loop with enterprise-grade timing