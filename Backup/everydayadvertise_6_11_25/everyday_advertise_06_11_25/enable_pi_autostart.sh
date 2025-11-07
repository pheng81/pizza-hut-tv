#!/bin/bash
# Enable complete_pi_client to auto-start at boot

echo "✅ Enabling complete_pi_client service..."
systemctl --user enable complete_pi_client.service

echo "🚀 Starting complete_pi_client service..."
systemctl --user start complete_pi_client.service

echo "📋 Current status:"
systemctl --user status complete_pi_client.service --no-pager

echo ""
echo "✅ Done! complete_pi_client will auto-start on reboot"
