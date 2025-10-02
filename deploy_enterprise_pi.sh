#!/usr/bin/env bash
set -euo pipefail

# Enterprise deployment helper.
# Usage:
#   ./deploy_enterprise_pi.sh <pi_host> <store_code> <pair_code> [screens]
# Example:
#   ./deploy_enterprise_pi.sh raspberrypi.local 1000 4682 1,2

PI_HOST=${1:-}
STORE=${2:-}
PAIR=${3:-}
SCREENS=${4:-1}

if [ -z "$PI_HOST" ] || [ -z "$STORE" ] || [ -z "$PAIR" ]; then
  echo "Usage: $0 <pi_host> <store_code> <pair_code> [screens]" >&2
  exit 1
fi

IFS=',' read -r -a SCR_ARR <<< "$SCREENS"

echo "==> Syncing project files to Pi"
rsync -av --delete --exclude '.git' ./ "${PI_HOST}:/home/everydayadvertise/pizza-hut-tv/"

echo "==> Creating systemd units"
for S in "${SCR_ARR[@]}"; do
  TEMPLATE="systemd/phtv-screen${S}.service.template"
  if [ ! -f "$TEMPLATE" ]; then
    echo "Skipping screen ${S} (no template)"; continue; fi
  SERVICE_CONTENT=$(sed -e "s/{{STORE_CODE}}/${STORE}/g" -e "s/{{PAIR_CODE}}/${PAIR}/g" "$TEMPLATE")
  echo "Installing unit for screen ${S}";
  ssh "$PI_HOST" "cat > /tmp/phtv-screen${S}.service" <<< "$SERVICE_CONTENT"
  ssh "$PI_HOST" "sudo mv /tmp/phtv-screen${S}.service /etc/systemd/system/phtv-screen${S}.service && sudo systemctl daemon-reload && sudo systemctl enable phtv-screen${S}.service"
done

echo "==> Starting services"
for S in "${SCR_ARR[@]}"; do
  ssh "$PI_HOST" "sudo systemctl restart phtv-screen${S}.service"
done

echo "==> Status (journal tail for each)"
for S in "${SCR_ARR[@]}"; do
  echo "------ screen ${S} ------"
  ssh "$PI_HOST" "journalctl -u phtv-screen${S}.service -n 25 --no-pager || true"
done

echo "Deployment complete."
