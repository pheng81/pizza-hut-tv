#!/bin/bash
# Complete Pi deployment and test script

set -e

echo "=== STOPPING OLD SERVICE ==="
sudo systemctl stop pizza-hut-tv-working.service || true
sudo pkill -f webplayer_style_pi_client.py || true
sudo pkill vlc || true

echo "=== INSTALLING FIXED SERVICE ==="
sudo cp /home/everydayadvertise/Desktop/pizza-hut-tv-fixed.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pizza-hut-tv-fixed.service

echo "=== ENSURING LOG FILES ==="
sudo touch /var/log/pizza-hut-tv.log /var/log/pizza-hut-tv.err.log
sudo chown everydayadvertise:everydayadvertise /var/log/pizza-hut-tv.log /var/log/pizza-hut-tv.err.log

echo "=== TESTING PYTHON-VLC ==="
python3 -c "import vlc; print('python-vlc OK')" || {
    echo "Installing python-vlc..."
    sudo apt-get update
    sudo apt-get install -y python3-pip vlc libvlc5
    pip3 install --upgrade python-vlc requests
}

echo "=== STARTING FIXED SERVICE ==="
sudo systemctl start pizza-hut-tv-fixed.service
sleep 3
sudo systemctl status --no-pager pizza-hut-tv-fixed.service

echo "=== RECENT LOGS ==="
journalctl -u pizza-hut-tv-fixed.service -n 20 --no-pager

echo "=== TESTING SCREEN 2 DETECTION ==="
echo "Manual test: python3 ~/Desktop/webplayer_style_pi_client.py"
echo "Select: Android TV Code 4682, Store 1000, Screen 2"
echo "Watch logs for: 'Using slice_url (screen 2, slice_aware=True)'"