#!/bin/bash
# Test if rotation endpoint actually works

echo "Testing /update_rotation endpoint..."

# Try to update rotation to 90 degrees
curl -s -X POST https://everydayadvertise.com/update_rotation \
  -H "Content-Type: application/json" \
  -H "Cookie: session=test" \
  -d '{"store_id":"1787","screen_id":"1787_promo1","rotation":90}' \
  -k | python3 -c "import sys,json; d=json.load(sys.stdin); print('Response:', d)"

echo ""
echo "Waiting 2 seconds..."
sleep 2

echo "Checking if rotation was saved in config file..."
curl -s -H "X-User-Code: 8329" "https://everydayadvertise.com/playlist/1787/1787_promo1?user_code=8329" -k | python3 -c "import sys,json; d=json.load(sys.stdin); print('Rotation from playlist:', d.get('rotation'))"
