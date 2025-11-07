#!/bin/bash
# Deploy updated Pi client with public IP auto-registration

PI_IP="192.168.1.131"
PI_USER="pi"

echo "🚀 Deploying updated Pi client..."
echo "===================================="

# Copy updated client
echo "📤 Uploading complete_pi_client.py..."
scp complete_pi_client.py ${PI_USER}@${PI_IP}:~/

# Restart service
echo "🔄 Restarting Pi service..."
ssh ${PI_USER}@${PI_IP} "sudo systemctl restart pizza-hut-tv"

# Wait for service to start
sleep 3

# Check status
echo "✅ Checking service status..."
ssh ${PI_USER}@${PI_IP} "sudo systemctl status pizza-hut-tv --no-pager | head -20"

echo ""
echo "===================================="
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Set up port forwarding on your router (port 8080 → 192.168.1.131:8080)"
echo "2. Check Pi registered its public IP:"
echo "   ssh ubuntu@54.252.90.27 'cat /var/www/pizza-hut-tv/pi_id_ip_map.json'"
echo "3. Test from dashboard: https://everydayadvertise.com/dashboard"
echo ""
