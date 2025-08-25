#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/pheng81/pizza-hut-tv.git"
APP_DIR="${APP_DIR:-/home/ubuntu/pizza-hut-tv}"
SERVICE_NAME="${SERVICE_NAME:-everydayadvertise}"

echo "[+] Installing OS dependencies..."
sudo apt-get update -y
sudo apt-get install -y git python3-venv ffmpeg

echo "[+] Cloning repo to $APP_DIR ..."
mkdir -p "$(dirname "$APP_DIR")"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  echo "Repo already exists at $APP_DIR"
fi

cd "$APP_DIR"
echo "[+] Creating venv and installing Python packages..."
python3 -m venv .venv
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install -r requirements.txt
"$APP_DIR/.venv/bin/pip" install gunicorn

echo "[+] Installing systemd service ($SERVICE_NAME)..."
sudo cp deploy/everydayadvertise.service "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager -l || true

echo "[+] Done. Validate locally: curl -I http://127.0.0.1:5002/"