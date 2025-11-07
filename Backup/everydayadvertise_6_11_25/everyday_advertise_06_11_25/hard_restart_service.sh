#!/bin/bash
# Hard restart Pizza Hut TV service - force reload all workers

echo "🔄 Hard restart of Pizza Hut TV service..."

# Stop the service completely
echo "1. Stopping service..."
sudo systemctl stop pizza-hut-tv

# Kill any lingering Gunicorn processes
echo "2. Killing lingering Gunicorn processes..."
sudo pkill -9 -f "gunicorn.*pizza-hut-tv" || true

# Wait for processes to die
echo "3. Waiting for processes to terminate..."
sleep 2

# Start the service fresh
echo "4. Starting service..."
sudo systemctl start pizza-hut-tv

# Wait for startup
echo "5. Waiting for service to start..."
sleep 3

# Check status
echo "6. Checking service status..."
sudo systemctl status pizza-hut-tv --no-pager

echo "✅ Hard restart complete!"
echo ""
echo "Testing endpoint..."
curl -X POST http://localhost:5002/api/register_pi \
  -H "Content-Type: application/json" \
  -d '{"pi_id":"test-local","pi_ip":"127.0.0.1"}' \
  2>/dev/null || echo "Endpoint test failed"
