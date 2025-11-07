#!/bin/bash
# Disable complete_pi_client from auto-starting at boot
# Keep QR code mobile sync setup instead

echo "🛑 Stopping complete_pi_client service..."
systemctl --user stop complete_pi_client.service

echo "❌ Disabling complete_pi_client from auto-start..."
systemctl --user disable complete_pi_client.service

echo "📋 Current status:"
systemctl --user status complete_pi_client.service --no-pager

echo ""
echo "✅ Done! complete_pi_client will NOT auto-start on reboot"
echo "🔄 To use QR code setup, the mobile sync will handle starting the player"
