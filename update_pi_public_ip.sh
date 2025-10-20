#!/bin/bash
# Update Pi to register public IP instead of local IP

echo "🔄 Updating Pi registration to use public IP..."

# Backup original complete_pi_client.py
cp /home/everydayadvertise/Desktop/complete_pi_client.py /home/everydayadvertise/Desktop/complete_pi_client.py.backup

# Update the registration to use public IP
cat > /tmp/update_pi_ip.py << 'EOF'
import sys

# Read the file
with open('/home/everydayadvertise/Desktop/complete_pi_client.py', 'r') as f:
    content = f.read()

# Replace local IP detection with public IP detection
old_code = '''        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        pi_ip = s.getsockname()[0]
        s.close()'''

new_code = '''        # Get public IP for remote access
        try:
            import requests
            public_ip = requests.get('https://api.ipify.org', timeout=5).text
            pi_ip = f"{public_ip}:8080"  # Include port since we're using port forwarding
            print(f"📡 Detected public IP: {pi_ip}")
        except Exception as e:
            print(f"⚠️ Could not detect public IP: {e}")
            # Fallback to local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            pi_ip = s.getsockname()[0]
            s.close()'''

# Replace the code
content = content.replace(old_code, new_code)

# Write back
with open('/home/everydayadvertise/Desktop/complete_pi_client.py', 'w') as f:
    f.write(content)

print("✅ Updated complete_pi_client.py to use public IP")
EOF

python3 /tmp/update_pi_ip.py

echo "✅ Pi updated! Restarting Pi client..."
sudo systemctl restart pizza-hut-tv-client

echo "🎉 Done! Pi will now register with public IP: 203.158.51.30:8080"
