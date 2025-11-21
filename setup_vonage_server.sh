#!/bin/bash
# Quick Vonage setup script - run on server

cd /var/www/pizza-hut-tv

# Backup existing .env
cp .env .env.backup-vonage

# Add Vonage credentials
cat >> .env << 'EOF'

# Vonage SMS Configuration
VONAGE_API_KEY=cd8f971d
VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m
VONAGE_FROM_NUMBER=+13165308999
EOF

echo "Vonage credentials added to .env"

# Restart service
sudo systemctl restart pizza-hut-tv

echo "Service restarted - checking status..."
sleep 2
sudo systemctl status pizza-hut-tv --no-pager -l | head -20

echo ""
echo "Checking for Vonage initialization:"
sudo journalctl -u pizza-hut-tv -n 30 --no-pager | grep -i vonage
