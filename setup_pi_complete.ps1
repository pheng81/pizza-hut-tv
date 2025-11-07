#!/usr/bin/env pwsh
# Complete Pi Setup - All in one script

$PI_IP = "192.168.1.113"
$PI_USER = "everydayadvertise0002"

Write-Host "🍕 Setting up Pizza Hut TV on Pi..." -ForegroundColor Green

# Create simple client script
$clientCode = @'
#!/usr/bin/env python3
import sys, time, socket, socketio
VERSION = "v1.0"
SERVER = "https://everydayadvertise.com"
PI_ID = socket.gethostname()
print(f"Pi: {PI_ID} connecting to {SERVER}")
sio = socketio.Client()
@sio.event
def connect():
    print("Connected!")
    sio.emit("pi_register", {"pi_id": PI_ID})
@sio.event  
def disconnect():
    print("Disconnected")
try:
    sio.connect(SERVER)
    while True: time.sleep(1)
except KeyboardInterrupt:
    sio.disconnect()
'@

# Save to temp file
$clientCode | Out-File -FilePath ".\temp_client.py" -Encoding UTF8

Write-Host "📤 Copying client to Pi..." -ForegroundColor Cyan
scp .\temp_client.py ${PI_USER}@${PI_IP}:~/pizzahut-client/complete_pi_client.py

Write-Host "🔧 Setting up service..." -ForegroundColor Cyan
ssh ${PI_USER}@${PI_IP} @"
chmod +x ~/pizzahut-client/complete_pi_client.py && \
sudo tee /etc/systemd/system/pizzahut-client.service > /dev/null <<'EOF'
[Unit]
Description=Pizza Hut TV Client
After=network.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=/home/${PI_USER}/pizzahut-client
ExecStart=/usr/bin/python3 /home/${PI_USER}/pizzahut-client/complete_pi_client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && \
sudo systemctl enable pizzahut-client.service && \
sudo systemctl start pizzahut-client.service && \
sudo systemctl status pizzahut-client.service --no-pager
"@

Remove-Item .\temp_client.py

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host "Pi should now appear in Pi Manager at:" -ForegroundColor Yellow
Write-Host "  https://everydayadvertise.com/pi-manager" -ForegroundColor Cyan
