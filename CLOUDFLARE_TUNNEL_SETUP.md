# Cloudflare Tunnel for Flask (Windows)

Use this to serve your local Flask app on a real domain without changing server code.

## Prereqs
- A Cloudflare account and a domain added to Cloudflare (e.g. example.com)
- Your Flask app running on 0.0.0.0:5002 (already configured)

## Steps (PowerShell)

1) Install cloudflared

```powershell
Invoke-WebRequest -Uri https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile $env:ProgramFiles\cloudflared\cloudflared.exe
$env:Path += ";$env:ProgramFiles\cloudflared"
```

2) Authenticate to Cloudflare

```powershell
cloudflared tunnel login
```
A browser opens; pick your account and domain.

3) Create a named tunnel

```powershell
$TUNNEL_NAME = "phtv-tunnel"
cloudflared tunnel create $TUNNEL_NAME
```
This prints a Tunnel UUID. Keep it handy.

4) Configure routing (DNS)

Choose a subdomain (e.g. tv.everydayadvertise.com) and route it to the tunnel:

```powershell
$SUBDOMAIN = "tv"           # change as needed
$DOMAIN = "everydayadvertise.com"     # your domain on Cloudflare
cloudflared tunnel route dns $TUNNEL_NAME "$SUBDOMAIN.$DOMAIN"
```

5) Create a config file

```powershell
$ConfigDir = "$env:ProgramFiles\cloudflared"
$ConfigPath = Join-Path $ConfigDir "config.yml"
@"
tunnel: $TUNNEL_NAME
credentials-file: $ConfigDir\$TUNNEL_NAME.json

ingress:
  - hostname: $SUBDOMAIN.$DOMAIN
    service: http://localhost:5002
  - service: http_status:404
"@ | Out-File -Encoding utf8 $ConfigPath
```

6) Run the tunnel as a service

```powershell
cloudflared service install
Start-Service cloudflared
# To restart later: Restart-Service cloudflared
```

7) Test
- Open https://tv.everydayadvertise.com/
- Dashboard should load unchanged.

## Android app base URL
Set the build-time base URL without code edits:

```powershell
# Example release build pointing to your domain
cd "android_tv_app"
./gradlew assembleRelease -PPHTV_BASE_URL="https://tv.everydayadvertise.com/"
```
This sets BuildConfig.PHTV_BASE_URL; install the generated APK on your TV device.

## Notes
- Keep the Flask server running on the same PC. Cloudflared securely forwards from Cloudflare edge to your localhost.
- To stop: Stop-Service cloudflared
- To update config: edit %ProgramFiles%\cloudflared\config.yml, then Restart-Service cloudflared
