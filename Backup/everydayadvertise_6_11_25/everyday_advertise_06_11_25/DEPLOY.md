# Deployment / Sync to Raspberry Pi

This project includes a helper PowerShell script to push updated client files to the Raspberry Pi and optionally run a diagnostic.

## Prerequisites
- SSH key or password access to the Pi (default host: everydayadvertise@raspberrypi.local)
- Project directory exists on Pi at /home/everydayadvertise/pizza-hut-tv
- Python3 + pip installed on Pi

## Script: deploy_to_pi.ps1
Parameters:
- -Host <user@host>  (default everydayadvertise@raspberrypi.local)
- -Dest <remote path> (default /home/everydayadvertise/pizza-hut-tv)
- -PlayUrl <full webplayer play URL> (optional, for diagnostic)
- -Test (run a remote --print-only diagnostic after upload)
- -SkipRequirements (skip pip install)

## Examples

1. Basic deploy:
```
./deploy_to_pi.ps1
```

2. Deploy and run diagnostic with a dynamic link:
```
./deploy_to_pi.ps1 -PlayUrl "https://everydayadvertise.com/webplayer/play?store_id=1000&screen_id=1000_screen2&code=4682" -Test
```

3. Deploy faster (skip reinstalling requirements):
```
./deploy_to_pi.ps1 -SkipRequirements
```

## After Deploy
Launch kiosk on Pi (SSH):
```
ssh everydayadvertise@raspberrypi.local "cd /home/everydayadvertise/pizza-hut-tv; DISPLAY=:0 python3 slice_kiosk.py --play-url 'https://everydayadvertise.com/webplayer/play?store_id=1000&screen_id=1000_screen2&code=4682' --kiosk --perf --force-f11"
```

Add --demo-fallback to open a sample video tab if the playlist is empty.

## Troubleshooting
- If playlist seems empty, test directly:
```
curl -v "https://everydayadvertise.com/playlist/1000/1000_screen2"
```
(Add ?user_code=4682 if server expects it.)
- If Chromium fails to start: ensure `chromium-browser` installed and DISPLAY=:0 is valid.
- For GPU acceleration validate Pi config (e.g. `libva-info` on device; may still fall back to software decode).
