# Disable VNC on Pi 2 (raspberrypi-3ef9 at 192.168.1.113)
# This stops the XGetImage() errors

Write-Host "Disabling VNC on Pi 2 (192.168.1.113)..." -ForegroundColor Yellow

# Create disable flag file
ssh everydayadvertise0002@192.168.1.113 "touch ~/.disable_phtv_vnc && echo 'VNC_DISABLED' > ~/.disable_phtv_vnc"

# Kill current Pi client
ssh everydayadvertise0002@192.168.1.113 "pkill -f complete_pi_client.py"

# Wait a moment
Start-Sleep -Seconds 2

# Restart Pi client (it will respect the disable flag)
ssh everydayadvertise0002@192.168.1.113 "nohup python3 /home/everydayadvertise0002/complete_pi_client.py --server https://everydayadvertise.com > /tmp/pi_client.log 2>&1 &"

Write-Host "VNC disabled on Pi 2. Remote Pi Viewer will no longer show errors." -ForegroundColor Green
Write-Host "Main video playback functionality is unaffected." -ForegroundColor Cyan
