#!/usr/bin/env bash
set -euo pipefail

# Simple Chromium kiosk launcher for EA TV webplayer slices.
# Usage:
#   STORE_ID=1000 SCREEN_ID=1000_screen2 CODE=4682 ./pi_webplayer_kiosk.sh
# or provide via command line flags:
#   ./pi_webplayer_kiosk.sh --store 1000 --screen 1000_screen2 --code 4682
#
# This script prefers environment variables; flags override.

STORE_ID="${STORE_ID:-}"
SCREEN_ID="${SCREEN_ID:-}"
CODE="${CODE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --store) STORE_ID="$2"; shift 2;;
    --screen) SCREEN_ID="$2"; shift 2;;
    --code) CODE="$2"; shift 2;;
    *) echo "Unknown argument: $1"; exit 1;;
  esac
done

if [[ -z "$STORE_ID" || -z "$SCREEN_ID" || -z "$CODE" ]]; then
  echo "ERROR: Must provide STORE_ID, SCREEN_ID and CODE (env vars or flags)." >&2
  exit 1
fi

URL="https://everydayadvertise.com/webplayer/play?store_id=${STORE_ID}&screen_id=${SCREEN_ID}&code=${CODE}"
echo "Launching EA TV Webplayer kiosk for: $URL" >&2

# Prevent screen blanking (non-persistent; for persistent edit /boot/config.txt or LXDE autostart)
if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

# Hide mouse cursor if unclutter available
if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 1 &
fi

# Pick chromium command name
CHROMIUM_BIN=""
for c in chromium-browser chromium chrome google-chrome; do
  if command -v "$c" >/dev/null 2>&1; then
    CHROMIUM_BIN="$c"; break
  fi
done

if [[ -z "$CHROMIUM_BIN" ]]; then
  echo "ERROR: Chromium/Chrome not installed on this system" >&2
  exit 2
fi

exec "$CHROMIUM_BIN" \
  --noerrdialogs \
  --disable-infobars \
  --kiosk \
  --autoplay-policy=no-user-gesture-required \
  --disable-features=Translate,EnableEphemeralFlashPermission \
  --incognito \
  --app="$URL"
