#!/bin/bash
# Quick Vonage setup script - run on server

cd /var/www/everydayadvertise_tv

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
sudo systemctl restart everydayadvertise_tv

echo "Service restarted - checking status..."
sleep 2
sudo systemctl status everydayadvertise_tv --no-pager -l | head -20

echo ""
echo "Checking for Vonage initialization:"
sudo journalctl -u everydayadvertise_tv -n 30 --no-pager | grep -i vonage
