# Production deploy (Ubuntu + Cloudflare Tunnel)

Two ways to deploy updates:
- One-time bootstrap + one-command updates via Windows PowerShell script.
- Manual steps on the server (if you prefer).

## Option A — One-command deploy from Windows

1) First-time on a new VM (installs deps, clones repo, sets up service):

  In PowerShell from the repo root:

  powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1 -Server <SERVER_IP_OR_DOMAIN> -Bootstrap

  This will:
  - Install git, python3-venv, ffmpeg
  - Clone to /home/ubuntu/pizza-hut-tv
  - Create .venv and install requirements
  - Install systemd service everydayadvertise.service and start it

2) Subsequent updates (pull + restart):

  powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1 -Server <SERVER_IP_OR_DOMAIN>

  Optional parameters: -RepoPath '/opt/pizza-hut-tv' -ServiceNames 'tv-api' -KeyPath 'C:\path\to\key.pem'

## Option B — Manual steps on the server

1) Clone the repo (HTTPS or SSH) and create venv:

  cd ~
  sudo apt-get update -y
  sudo apt-get install -y git python3-venv ffmpeg
  git clone https://github.com/pheng81/pizza-hut-tv.git
  cd pizza-hut-tv
  python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip wheel
  pip install -r requirements.txt
  pip install gunicorn

2) Install systemd service and start:

  sudo cp deploy/everydayadvertise.service /etc/systemd/system/everydayadvertise.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now everydayadvertise
  sudo systemctl status everydayadvertise --no-pager -l

3) Cloudflare Tunnel (already configured):

  Your tunnel maps api.everydayadvertise.com -> http://127.0.0.1:5002.
  If you changed ports/path, update /etc/cloudflared/config.yml accordingly, then:

  sudo systemctl restart cloudflared
  curl -I https://api.everydayadvertise.com/

## Notes
- Service name: repo includes everydayadvertise.service (preferred). If you used tv-api.service before, you can keep it, but pick one to avoid confusion.
- App binds to 127.0.0.1:5002; don’t expose 5002 publicly.
- Set MEDIA_BASE_URL=https://api.everydayadvertise.com for absolute media URLs.
- For updates by hand:
  cd ~/pizza-hut-tv && git pull && . .venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart everydayadvertise
