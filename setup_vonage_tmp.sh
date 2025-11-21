#!/bin/bash
echo "Setting up Vonage SMS credentials..."

cd /var/www/pizza-hut-tv

cp .env .env.backup-$(date +%s) 2>/dev/null || true

if ! grep -q "VONAGE_API_KEY" .env 2>/dev/null; then
    echo "" >> .env
    echo "# Vonage SMS Configuration" >> .env
    echo "VONAGE_API_KEY=cd8f971d" >> .env
    echo "VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m" >> .env
    echo "VONAGE_FROM_NUMBER=+13165308999" >> .env
    echo "Vonage credentials added to .env"
else
    echo "Vonage credentials already exist in .env"
fi

echo ""
echo "Installing Vonage SDK..."
source venv/bin/activate
pip install 'vonage>=3.0,<4'

echo ""
echo "Restarting service..."
sudo systemctl restart pizza-hut-tv
sleep 2

echo ""
echo "Setup complete!"
echo ""
echo "Checking service status:"
sudo systemctl status pizza-hut-tv --no-pager -l | head -15

echo ""
echo "Checking for Vonage initialization:"
sudo journalctl -u pizza-hut-tv -n 50 --no-pager | grep -i vonage