#!/bin/bash
# OAuth Setup Script for EverydayAdvertise
# Run this on the server to enable Google and Microsoft login

echo "🔐 OAuth Setup for EverydayAdvertise"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "⚠️  Please don't run as root. Run as ubuntu user."
   exit 1
fi

# Create environment file if it doesn't exist
ENV_FILE="/var/www/pizza-hut-tv/.env"
if [ ! -f "$ENV_FILE" ]; then
    sudo touch "$ENV_FILE"
    sudo chown ubuntu:ubuntu "$ENV_FILE"
    sudo chmod 600 "$ENV_FILE"
    echo "✅ Created $ENV_FILE"
fi

echo ""
echo "To enable OAuth login, you need to set up credentials:"
echo ""
echo "📝 For Google OAuth:"
echo "   1. Go to: https://console.cloud.google.com/apis/credentials"
echo "   2. Create OAuth 2.0 Client ID"
echo "   3. Add authorized redirect URI: https://everydayadvertise.com/auth/google/callback"
echo ""
echo "📝 For Microsoft OAuth:"
echo "   1. Go to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
echo "   2. Register new application"
echo "   3. Add redirect URI: https://everydayadvertise.com/auth/microsoft/callback"
echo ""

read -p "Do you have Google OAuth credentials? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter Google Client ID: " GOOGLE_CLIENT_ID
    read -p "Enter Google Client Secret: " GOOGLE_CLIENT_SECRET
    
    # Add to .env file
    echo "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID" | sudo tee -a "$ENV_FILE" > /dev/null
    echo "GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET" | sudo tee -a "$ENV_FILE" > /dev/null
    echo "✅ Google OAuth configured"
fi

echo ""
read -p "Do you have Microsoft OAuth credentials? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter Microsoft Client ID: " MICROSOFT_CLIENT_ID
    read -p "Enter Microsoft Client Secret: " MICROSOFT_CLIENT_SECRET
    
    # Add to .env file
    echo "MICROSOFT_CLIENT_ID=$MICROSOFT_CLIENT_ID" | sudo tee -a "$ENV_FILE" > /dev/null
    echo "MICROSOFT_CLIENT_SECRET=$MICROSOFT_CLIENT_SECRET" | sudo tee -a "$ENV_FILE" > /dev/null
    echo "✅ Microsoft OAuth configured"
fi

echo ""
echo "🔄 Restarting application..."
sudo systemctl restart pizza-hut-tv

echo ""
echo "✅ Done! OAuth credentials have been configured."
echo "   The Google/Microsoft login buttons should now appear on the login page."
