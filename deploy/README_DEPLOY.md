# Production deploy (Ubuntu + Cloudflare Tunnel)

Follow these steps once per VM. Replace values only if your paths differ.

## 1) Clone the repo to the VM via SSH deploy key

- On the VM, generate a key and add it as a Deploy key in GitHub (Allow write not required):
  
  ssh-keygen -t ed25519 -f ~/.ssh/github -N ""
  
  cat ~/.ssh/github.pub
  
  # Copy the printed public key to GitHub > repo > Settings > Deploy keys > Add deploy key

- Make GitHub use this key:
  
  echo "Host github.com`n  HostName github.com`n  IdentityFile ~/.ssh/github`n  User git" >> ~/.ssh/config
  
- Clone:
  
  git clone git@github.com:pheng81/pizza-hut-tv.git

## 2) Python venv and dependencies

cd ~/pizza-hut-tv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
pip install gunicorn

Quick smoke test:

MEDIA_BASE_URL=https://api.everydayadvertise.com \
  .venv/bin/gunicorn -c deploy/gunicorn.conf.py app:app --pid /tmp/gunicorn-test.pid \
  --access-logfile - --error-logfile - --daemon

curl -I http://127.0.0.1:5002/
# If 200 OK, stop the test:
kill "$(cat /tmp/gunicorn-test.pid)"

## 3) Install systemd service

sudo cp deploy/everydayadvertise.service /etc/systemd/system/everydayadvertise.service
sudo systemctl daemon-reload
sudo systemctl enable --now everydayadvertise

Check logs:

sudo journalctl -u everydayadvertise -f

## 4) Cloudflare Tunnel (already configured)

Your tunnel maps api.everydayadvertise.com -> http://127.0.0.1:5002.
If you changed ports/path, update /etc/cloudflared/config.yml accordingly, then:

sudo systemctl restart cloudflared

Validate public endpoint:

curl -I https://api.everydayadvertise.com/

## Notes
- The app binds to 127.0.0.1:5002; do not expose port 5002 publicly.
- MEDIA_BASE_URL must be https://api.everydayadvertise.com so clients get absolute URLs.
- For updates: `cd ~/pizza-hut-tv && git pull && source .venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart everydayadvertise`.
