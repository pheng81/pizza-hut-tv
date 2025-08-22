#!/bin/bash
# Script to verify repository privacy settings

echo "=== Repository Privacy Verification ==="
echo ""

echo "1. Testing repository accessibility..."
echo "   Attempting to access repository without authentication..."

# Test if repository is accessible without authentication
curl -s -o /dev/null -w "%{http_code}" https://github.com/pheng81/pizza-hut-tv > /tmp/repo_status.txt
STATUS=$(cat /tmp/repo_status.txt)

if [ "$STATUS" = "404" ]; then
    echo "   ✅ Repository appears to be PRIVATE (404 error when accessing without auth)"
elif [ "$STATUS" = "200" ]; then
    echo "   ⚠️  Repository appears to be PUBLIC (accessible without authentication)"
    echo "   📋 To make it private, follow these steps:"
    echo "      - Go to https://github.com/pheng81/pizza-hut-tv/settings"
    echo "      - Scroll to 'Danger Zone'"
    echo "      - Click 'Change repository visibility'"
    echo "      - Select 'Make private'"
else
    echo "   ❓ Unexpected status code: $STATUS"
fi

echo ""
echo "2. Manual verification steps:"
echo "   - Open an incognito/private browser window"
echo "   - Go to: https://github.com/pheng81/pizza-hut-tv"
echo "   - You should see '404 - Not Found' if repository is private"
echo "   - If you can see the repository content, it's still public"

echo ""
echo "3. For detailed setup instructions, see:"
echo "   - PRIVACY_SETUP.md (comprehensive guide)"
echo "   - push_to_github.md (updated GitHub setup)"

echo ""
echo "=== End Verification ==="

rm -f /tmp/repo_status.txt