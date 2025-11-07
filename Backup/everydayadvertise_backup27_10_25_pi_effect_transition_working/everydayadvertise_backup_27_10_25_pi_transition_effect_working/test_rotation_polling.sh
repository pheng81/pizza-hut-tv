#!/bin/bash
echo "Monitoring rotation changes - Click rotate button in dashboard NOW!"
for i in {1..10}; do
    echo ""
    echo "=== Poll $i at $(date +%H:%M:%S) ==="
    curl -s -H "X-User-Code: 8329" "https://everydayadvertise.com/playlist/1787/1787_promo1?user_code=8329" -k | python3 -c "import sys, json; d=json.load(sys.stdin); print('Rotation:', d.get('rotation'), 'degrees')"
    sleep 3
done
