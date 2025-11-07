#!/bin/bash
# Update config to pair code 8329
cat > ~/.pizza_hut_tv_config.json << 'EOF'
{
  "pair_code": "8329",
  "store_id": "1787",
  "screen_id": "1787_promo1",
  "pi_id": "raspberrypi-ce39"
}
EOF

echo "=== Updated config ==="
cat ~/.pizza_hut_tv_config.json

# Test playlist fetch
curl -s -H "X-User-Code: 8329" "https://everydayadvertise.com/playlist/1787/1787_promo1?user_code=8329" -k > /tmp/playlist_test.json
echo ""
echo "=== Playlist Response ==="
cat /tmp/playlist_test.json | python3 -c "import sys, json; d=json.load(sys.stdin); print('Success:', d.get('success')); print('Rotation:', d.get('rotation')); print('Orientation:', d.get('orientation')); print('Playlist items:', len(d.get('playlist',[])))"
