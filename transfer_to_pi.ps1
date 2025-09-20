# Transfer Pizza Hut TV clients to local Raspberry Pi
# Usage: .\transfer_to_pi.ps1

Write-Host "🍕 Transferring Pizza Hut TV clients to Raspberry Pi..."

# Create remote directory
ssh everydayadvertise@raspberrypi "mkdir -p ~/pizza-hut-tv-pi"

# Transfer GUI client
scp "pizza_hut_tv_gui_client.py" everydayadvertise@raspberrypi:~/pizza-hut-tv-pi/

# Transfer CLI client  
scp "pizza_hut_tv_client_enhanced.py" everydayadvertise@raspberrypi:~/pizza-hut-tv-pi/pizza_hut_tv_client.py

# Transfer installer (updated version)
scp "pizza-hut-tv-enhanced-installer.sh" everydayadvertise@raspberrypi:~/pizza-hut-tv-pi/

# Transfer Python environment fix
scp "fix-python-environment.sh" everydayadvertise@raspberrypi:~/pizza-hut-tv-pi/

# Make scripts executable
ssh everydayadvertise@raspberrypi "chmod +x ~/pizza-hut-tv-pi/*.sh ~/pizza-hut-tv-pi/*.py"

Write-Host "✅ Transfer complete!"
Write-Host ""
Write-Host "Next steps on your Pi:"
Write-Host "  ssh everydayadvertise@raspberrypi"
Write-Host "  cd ~/pizza-hut-tv-pi"
Write-Host "  ./fix-python-environment.sh  # If needed"
Write-Host "  python3 pizza_hut_tv_gui_client.py"