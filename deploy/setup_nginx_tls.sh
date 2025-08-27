#!/usr/bin/env bash
set -euo pipefail

# This script installs and configures NGINX on Ubuntu to terminate TLS
# using a Cloudflare Origin Certificate and proxy to Gunicorn on 127.0.0.1:5002.

DOMAIN=${DOMAIN:-api.everydayadvertise.com}
CRT_SRC=${CRT_SRC:-/home/ubuntu/pizza-hut-tv/deploy/ssl/origin.crt}
KEY_SRC=${KEY_SRC:-/home/ubuntu/pizza-hut-tv/deploy/ssl/origin.key}
NGINX_CONF_SRC=${NGINX_CONF_SRC:-/home/ubuntu/pizza-hut-tv/deploy/nginx-everydayadvertise.conf}

echo "Installing nginx..."
sudo apt-get update -y
sudo apt-get install -y nginx

echo "Placing cert and key at /etc/ssl/cloudflare ..."
sudo mkdir -p /etc/ssl/cloudflare
sudo cp "$CRT_SRC" /etc/ssl/cloudflare/origin.crt
sudo cp "$KEY_SRC" /etc/ssl/cloudflare/origin.key
sudo chown root:root /etc/ssl/cloudflare/origin.crt /etc/ssl/cloudflare/origin.key
sudo chmod 644 /etc/ssl/cloudflare/origin.crt
sudo chmod 600 /etc/ssl/cloudflare/origin.key

echo "Installing nginx site config..."
sudo cp "$NGINX_CONF_SRC" /etc/nginx/sites-available/everydayadvertise.conf

if [ ! -e /etc/nginx/sites-enabled/everydayadvertise.conf ]; then
  sudo ln -s /etc/nginx/sites-available/everydayadvertise.conf /etc/nginx/sites-enabled/everydayadvertise.conf
fi

echo "Testing nginx configuration..."
sudo nginx -t

echo "Reloading nginx..."
sudo systemctl enable nginx
sudo systemctl reload nginx || sudo systemctl restart nginx

echo "Done. Verify with: curl -I https://$DOMAIN/healthz"
