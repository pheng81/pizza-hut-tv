#!/usr/bin/env bash
set -euo pipefail

# Inputs via env with defaults
REPO_PATH=${REPO_PATH:-/home/ubuntu/pizza-hut-tv}
PRESERVE=${PRESERVE:-False}
SERVICES=${SERVICES:-"everydayadvertise tv-api"}

echo "[update] Repo: $REPO_PATH | Preserve: $PRESERVE | Services: $SERVICES"

if [ ! -d "$REPO_PATH" ]; then
  echo "[update] Repo path missing: $REPO_PATH; creating parent and cloning..."
  mkdir -p "$(dirname "$REPO_PATH")"
  git clone https://github.com/pheng81/pizza-hut-tv.git "$REPO_PATH"
fi

if [ ! -d "$REPO_PATH/.git" ]; then
  echo "[update] .git missing in $REPO_PATH; recloning fresh..."
  rm -rf "$REPO_PATH"
  git clone https://github.com/pheng81/pizza-hut-tv.git "$REPO_PATH"
fi

cd "$REPO_PATH"

if [ "$PRESERVE" = "True" ]; then
  if [ -f store_config.json ]; then cp store_config.json /tmp/store_config.json.local.bak; fi
  if git ls-files --error-unmatch store_config.json >/dev/null 2>&1; then
    git update-index --no-skip-worktree store_config.json || true
  fi
  rm -f store_config.json || true
fi

echo "[update] Pulling latest..."
git pull --ff-only || { git fetch origin main && git checkout -f main && git reset --hard origin/main; }

if [ "$PRESERVE" = "True" ]; then
  if [ -f /tmp/store_config.json.local.bak ]; then cp /tmp/store_config.json.local.bak store_config.json; fi
  if git ls-files --error-unmatch store_config.json >/dev/null 2>&1; then
    git update-index --skip-worktree store_config.json || true
  fi
fi

echo "[update] Ensuring venv and requirements..."
if [ ! -x "$REPO_PATH/.venv/bin/python" ]; then
  python3 -m venv "$REPO_PATH/.venv"
fi
"$REPO_PATH/.venv/bin/python" -m ensurepip --upgrade || true
"$REPO_PATH/.venv/bin/python" -m pip install --upgrade pip wheel
"$REPO_PATH/.venv/bin/python" -m pip install -r requirements.txt

echo "[update] Restarting service..."
for svc in $SERVICES; do
  if systemctl list-unit-files | grep -q "^${svc}\.service"; then
    sudo systemctl restart "$svc"
    sudo systemctl status "$svc" --no-pager -l || true
    exit 0
  fi
done

echo "[update] WARNING: No known service found to restart: $SERVICES" >&2
exit 2
