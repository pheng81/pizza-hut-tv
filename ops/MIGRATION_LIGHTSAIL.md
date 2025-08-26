# Lightsail Upgrade / Migration Guide

This guide walks you through moving the Pizza TV app to a bigger Lightsail instance with minimal downtime.

## Prereqs
- Current server reachable via SSH.
- Domain proxied through Cloudflare Tunnel to 127.0.0.1:5002 on the instance.
- Repo is in `/home/ubuntu/pizza-hut-tv` on server.

## Steps

1) Snapshot the current instance
- In Lightsail console: Instances > Select current > Snapshots > Create snapshot.
- Wait until snapshot completes.

2) Create a new larger instance from snapshot
- Create new instance from the snapshot.
- Choose stronger plan (2GB or 4GB RAM recommended).
- Add a static IP and attach it to the new instance.

3) Attach networking and security
- Open ports: 22 (SSH). App is internal (127.0.0.1:5002), only the tunnel should access it.
- Update DNS only when ready to cut over if you’re not using a tunnel. For Cloudflare Tunnel, no DNS change needed.

4) Bring code onto the new instance
- SSH into new instance; install git, clone repo:
  - sudo apt-get update && sudo apt-get install -y git
  - git clone <your-repo> /home/ubuntu/pizza-hut-tv
  - cd /home/ubuntu/pizza-hut-tv
- Or rsync from old instance if you have uploaded media to copy:
  - rsync -avz -e ssh ubuntu@OLD_IP:/home/ubuntu/pizza-hut-tv/static/uploads/ static/uploads/

5) Bootstrap the app
- sudo bash ops/bootstrap_ubuntu.sh
- Verify service:
  - systemctl status pizzatv
  - curl -I http://127.0.0.1:5002/

6) Restore Cloudflare Tunnel
- Option A: Copy existing tunnel config from old instance `/etc/cloudflared` and enable service.
- Option B: Create a new tunnel via `cloudflared tunnel` and route your domain to http://127.0.0.1:5002.

7) Cutover
- If using the same tunnel, once the new server answers 200 at `/`, point the tunnel to the new instance.
- If using DNS directly, switch the A record to the new static IP (TTL low).

8) Post-cutover tuning
- Increase Gunicorn workers to match RAM/CPU:
  - 2GB: 3 workers
  - 4GB: 4–5 workers
- Edit `/etc/systemd/system/pizzatv.service`, change `-w` and restart:
  - sudo systemctl daemon-reload
  - sudo systemctl restart pizzatv

## Verify
- Dashboard loads quickly.
- Video plays via `/media/...` with `Accept-Ranges: bytes` header.
- `/vpreview` and `/vthumb` return 200 for local videos.
- JSON endpoints return 304 on conditional GET (ETag).

## Rollback
- If issues arise, point the tunnel back to the old instance or revert DNS.

## Notes
- Keep 2G swap as a safety net, even on larger instances.
- Monitor Cloudflare Tunnel logs for unexpected EOFs; large files should route via `/media` to utilize Range streaming.

## Troubleshooting quick refs
- Gunicorn status: `systemctl status pizzatv`
- Logs (last 200 lines): `journalctl -u pizzatv -n 200 --no-pager`
- Tunnel logs: `journalctl -u cloudflared -n 200 --no-pager`
