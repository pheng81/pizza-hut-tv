#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a fresh Ubuntu server for pizza-hut-tv
# - Installs Python, pip, venv, ffmpeg, git
# - Sets up 2G swap (idempotent)
# - Creates venv, installs requirements
# - Installs and enables systemd service (pizzatv)

APP_DIR="/home/ubuntu/pizza-hut-tv"
PYBIN="${APP_DIR}/.venv/bin/python"

if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

# Packages
$SUDO apt-get update -y
$SUDO apt-get install -y python3 python3-venv python3-pip git ffmpeg curl

# Swap (2G)
if ! grep -q '^/swapfile' /etc/fstab 2>/dev/null; then
  $SUDO fallocate -l 2G /swapfile || $SUDO dd if=/dev/zero of=/swapfile bs=1M count=2048
  $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile
  $SUDO swapon /swapfile
  echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
  echo 'vm.swappiness=60' | $SUDO tee /etc/sysctl.d/99-swap.conf >/dev/null
  $SUDO sysctl -p /etc/sysctl.d/99-swap.conf || true
fi

# App setup
cd "$APP_DIR"
python3 -m venv .venv
"$PYBIN" -m pip install -U pip wheel
if [[ -f requirements.txt ]]; then
  "$PYBIN" -m pip install -r requirements.txt
fi

# Ensure folders
mkdir -p static/uploads static/thumbs static/vthumbs static/vpreviews

# Systemd service
$SUDO cp "$APP_DIR/ops/pizzatv.service" /etc/systemd/system/pizzatv.service
$SUDO systemctl daemon-reload
$SUDO systemctl enable pizzatv
$SUDO systemctl restart pizzatv

# Show status
sleep 1
$SUDO systemctl --no-pager status pizzatv | sed -n '1,20p'

# Optional: Cloudflare Tunnel (manual/auth required)
cat << 'EOF'
---
Cloudflare Tunnel not auto-configured.
- If migrating, copy /etc/cloudflared from old server and enable the service:
  sudo systemctl enable --now cloudflared
- Or re-create the tunnel and point to http://127.0.0.1:5002
---
EOF

# Quick local checks
curl -sI http://127.0.0.1:5002/ | head -n 1 || true
mp4=$(ls static/uploads/*.mp4 2>/dev/null | head -n 1 || true)
if [[ -n "${mp4}" ]]; then
  bn=$(basename "$mp4")
  echo "HEAD /media/${bn}"
  curl -sI "http://127.0.0.1:5002/media/${bn}" | sed -n '1,15p' || true
fi

echo 'Bootstrap complete.'
