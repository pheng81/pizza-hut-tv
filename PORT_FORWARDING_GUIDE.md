# Port Forwarding for Remote Pi Access

This allows the AWS server to reach your local Pi.

## Router Configuration:

1. **Log into your router** (usually http://192.168.1.1)

2. **Create Port Forward Rule**:
   - External Port: 8080 (or any available port like 18080)
   - Internal IP: 192.168.1.131 (your Pi)
   - Internal Port: 8080
   - Protocol: TCP
   - Name: "PizzaHut-Pi"

3. **Update Pi Registration**:
   Instead of registering local IP (192.168.1.131), register your public IP with port.

## Get Your Public IP:
```powershell
# Find your public IP
curl https://api.ipify.org
```

Example: If your public IP is `203.10.20.30`, then:
- Register Pi as: `203.10.20.30:8080` (or `:18080` if you used different external port)

## Security Considerations:
⚠️ **WARNING**: This exposes your Pi to the internet!
- Use firewall rules to restrict access
- Consider VPN solution instead (Option 3)
- Monitor access logs regularly

## Update Pi Registration:
Modify `complete_pi_client.py` line 36-50 to register public IP instead of local:

```python
def register_pi_with_server(pi_id, server_url):
    """Register Pi identifier and IP with the server automatically."""
    try:
        # Get public IP instead of local IP
        public_ip = requests.get('https://api.ipify.org', timeout=5).text
        pi_ip = f"{public_ip}:8080"  # Include port if forwarded
        
        url = f"{server_url}/api/register_pi"
        payload = {"pi_id": pi_id, "pi_ip": pi_ip}
        
        logger.info(f"📡 Registering Pi with server: {pi_id} -> {pi_ip}")
        resp = requests.post(url, json=payload, timeout=5)
        # ... rest of code
```
