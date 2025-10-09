# 🚀 Remote Pi Manager - Production Deployment Guide

## ✅ Current Status

### Local Development (WORKING ✅)
- **Server**: `app_local_dev.py` running on `192.168.1.115:5002`
- **Pi**: `raspberrypi-ce39` running on `192.168.1.131:8080`
- **Network**: Same local network → Direct communication ✅
- **Functionality**: Fully tested and working ✅

### Production Challenge
- **Server**: AWS EC2 at `54.252.90.27` (everydayadvertise.com)
- **Pi**: Local network at `192.168.1.131` (behind NAT/router)
- **Problem**: AWS server cannot directly reach local Pi IP addresses
- **Reason**: Network isolation - Pi is on a private local network, AWS is on the internet

## 🌐 The Network Architecture Problem

```
┌─────────────────────────────────────────────────────────────┐
│                       INTERNET                               │
│                                                               │
│   ┌──────────────────────────────┐                          │
│   │  AWS Production Server       │                          │
│   │  54.252.90.27                │                          │
│   │  everydayadvertise.com       │                          │
│   │                               │                          │
│   │  ❌ Cannot reach 192.168.x.x │                          │
│   └──────────────────────────────┘                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                          ▼
                     ❌ BLOCKED
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   LOCAL NETWORK                              │
│                   192.168.1.0/24                             │
│                                                               │
│   ┌──────────────────────────────┐                          │
│   │  Raspberry Pi                │                          │
│   │  192.168.1.131:8080         │                          │
│   │  raspberrypi-ce39            │                          │
│   └──────────────────────────────┘                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Why this happens:**
1. Raspberry Pi is on a **private local network** (192.168.x.x)
2. Your router uses **NAT (Network Address Translation)**
3. AWS server sees only your **public router IP**, not individual device IPs
4. Pi's HTTP server (port 8080) is **not accessible from the internet**

## 🎯 Three Production Solutions

### **Solution 1: Tailscale VPN (RECOMMENDED ⭐)**

**Best for:** Production deployments, multiple stores, enterprise use

**How it works:**
- Creates a **secure private network** between AWS server and all Raspberry Pis
- Each device gets a permanent IP address (e.g., `100.64.x.x`)
- Works through firewalls and NAT automatically
- Free for up to 100 devices

**Benefits:**
- ✅ Secure (encrypted)
- ✅ Works from anywhere
- ✅ No router configuration needed
- ✅ Scales to many stores
- ✅ Zero-trust networking

**Setup Steps:**

#### 1. Install Tailscale on AWS Server
```bash
# SSH to AWS server
ssh ubuntu@everydayadvertise.com

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Get Tailscale IP
tailscale ip -4
# Example output: 100.64.0.1
```

#### 2. Install Tailscale on Raspberry Pi
```bash
# SSH to Pi
ssh everydayadvertise@raspberrypi.local

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Get Tailscale IP
tailscale ip -4
# Example output: 100.64.0.2
```

#### 3. Update Pi ID Mapping
On AWS server, update `pi_id_ip_map.json`:
```json
{
  "raspberrypi-ce39": "100.64.0.2"
}
```

#### 4. Copy Remote Pi Manager Template to Production
```powershell
# Copy template to production templates folder
Copy-Item "templates_local\remote_pi_manager.html" "templates\remote_pi_manager.html"
```

#### 5. Add Route to Production app.py
Add this route (around line 9520 in app.py):
```python
@app.route('/remote-pi-manager')
@login_required
def remote_pi_manager():
    """Remote Pi Manager page"""
    return render_template('remote_pi_manager.html')
```

#### 6. Deploy to Production
```powershell
.\deploy_to_server.ps1
```

#### 7. Test
```bash
# Check Pi status from production
curl https://everydayadvertise.com/api/pi-status/raspberrypi-ce39
```

**Production URL:**
- Access at: https://everydayadvertise.com/remote-pi-manager

---

### **Solution 2: Reverse SSH Tunnel**

**Best for:** Single store, temporary testing, budget-conscious

**How it works:**
- Pi creates an **SSH tunnel** to AWS server
- Pi's port 8080 becomes accessible via localhost on AWS
- Requires SSH access and port forwarding

**Setup Steps:**

#### 1. On AWS Server - Create SSH User
```bash
ssh ubuntu@everydayadvertise.com
sudo adduser pitunnel --disabled-password
sudo mkdir /home/pitunnel/.ssh
sudo touch /home/pitunnel/.ssh/authorized_keys
sudo chown -R pitunnel:pitunnel /home/pitunnel/.ssh
sudo chmod 700 /home/pitunnel/.ssh
sudo chmod 600 /home/pitunnel/.ssh/authorized_keys
```

#### 2. On Raspberry Pi - Generate SSH Key
```bash
ssh everydayadvertise@raspberrypi.local
ssh-keygen -t ed25519 -f ~/.ssh/aws_tunnel -N ""
cat ~/.ssh/aws_tunnel.pub
# Copy this public key
```

#### 3. On AWS Server - Add Pi's Public Key
```bash
sudo nano /home/pitunnel/.ssh/authorized_keys
# Paste Pi's public key, save
```

#### 4. On Raspberry Pi - Create Tunnel Service
```bash
sudo nano /etc/systemd/system/ssh-tunnel.service
```

Add:
```ini
[Unit]
Description=SSH Tunnel to AWS
After=network.target

[Service]
User=everydayadvertise
ExecStart=/usr/bin/ssh -N -R 9080:localhost:8080 -i /home/everydayadvertise/.ssh/aws_tunnel pitunnel@everydayadvertise.com -o ServerAliveInterval=60 -o ExitOnForwardFailure=yes
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable ssh-tunnel
sudo systemctl start ssh-tunnel
```

#### 5. Update Production Code
In `app.py`, modify `/api/configure-pi` endpoint:
```python
# Around line 9410, change:
pi_url = f'http://{pi_ip}:8080/configure'

# To:
pi_url = f'http://localhost:9080/configure'  # Use tunnel port
```

**Pros:**
- ✅ Free (no third-party service)
- ✅ Direct access to Pi

**Cons:**
- ❌ Complex setup per Pi
- ❌ Single point of failure
- ❌ Requires SSH access
- ❌ Doesn't scale well

---

### **Solution 3: WebSocket/Long Polling (Architecture Change)**

**Best for:** Enterprise deployments with many stores

**How it works:**
- **Reverse communication pattern**: Pi connects TO server (not server TO Pi)
- Pi maintains **persistent WebSocket connection** to AWS
- Server queues configuration commands
- Pi polls or receives commands via WebSocket

**Architecture:**
```
┌─────────────────────┐
│  AWS Server         │
│  (Command Queue)    │
└──────────┬──────────┘
           │
           │ ← Pi initiates connection
           │
┌──────────▼──────────┐
│  Raspberry Pi       │
│  (Pulls commands)   │
└─────────────────────┘
```

**Implementation Overview:**

#### 1. Add Redis/Database Queue
```python
# In app.py
import redis
r = redis.Redis(host='localhost', port=6379, db=0)

@app.route('/api/queue-pi-config', methods=['POST'])
def queue_pi_config():
    data = request.get_json()
    pi_id = data['pi_id']
    config = {
        'pair_code': data['pair_code'],
        'store_id': data['store_id'],
        'screen_id': data['screen_id']
    }
    r.setex(f'pi_config:{pi_id}', 300, json.dumps(config))  # Expire in 5 min
    return jsonify({'success': True, 'queued': True})

@app.route('/api/pull-config/<pi_id>')
def pull_config(pi_id):
    """Pi polls this endpoint for new config"""
    config = r.get(f'pi_config:{pi_id}')
    if config:
        r.delete(f'pi_config:{pi_id}')  # Clear after retrieval
        return jsonify({'success': True, 'config': json.loads(config)})
    return jsonify({'success': False, 'message': 'No pending config'})
```

#### 2. Update Pi Client
```python
# In complete_pi_client.py
def poll_for_config():
    """Poll server every 10 seconds for new configuration"""
    while True:
        try:
            resp = requests.get(
                f'{SERVER_URL}/api/pull-config/{PI_ID}',
                timeout=5
            )
            data = resp.json()
            if data.get('success') and 'config' in data:
                config = data['config']
                logging.info(f'📥 New config received: {config}')
                apply_config(config)
        except Exception as e:
            logging.error(f'Config poll error: {e}')
        time.sleep(10)

# Start polling thread
threading.Thread(target=poll_for_config, daemon=True).start()
```

**Pros:**
- ✅ Works through any firewall
- ✅ Scales to unlimited Pis
- ✅ No VPN or tunnels needed
- ✅ Enterprise-grade architecture

**Cons:**
- ❌ Requires Redis or database
- ❌ More complex implementation
- ❌ Not real-time (polling delay)

---

## 📋 Comparison Table

| Feature | Tailscale VPN | SSH Tunnel | WebSocket/Polling |
|---------|---------------|------------|-------------------|
| **Setup Complexity** | ⭐ Easy | ⭐⭐⭐ Complex | ⭐⭐ Moderate |
| **Scalability** | ⭐⭐⭐ Excellent | ⭐ Poor | ⭐⭐⭐ Excellent |
| **Security** | ⭐⭐⭐ Encrypted | ⭐⭐ Good | ⭐⭐⭐ Encrypted |
| **Cost** | Free (< 100 devices) | Free | Free (DIY) |
| **Maintenance** | ⭐⭐⭐ Low | ⭐ High | ⭐⭐ Moderate |
| **Real-time** | ⭐⭐⭐ Yes | ⭐⭐⭐ Yes | ⭐⭐ Polling delay |
| **Works Anywhere** | ⭐⭐⭐ Yes | ⭐⭐ Limited | ⭐⭐⭐ Yes |

## 🎯 Recommended Solution

### For Your Use Case: **Tailscale VPN** ⭐

**Why:**
1. You already have the perfect architecture (Remote Pi Manager works locally)
2. Minimal code changes needed
3. Secure and production-ready
4. Easy to scale to multiple stores
5. Free for your use case
6. Works identically to local testing

**Time to Production:**
- Setup: 15 minutes
- Testing: 10 minutes
- Total: **25 minutes** to fully functional production Remote Pi Manager

---

## 🚀 Quick Start (Tailscale - RECOMMENDED)

### Step 1: Install Tailscale (5 min)
```bash
# On AWS server
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# On Raspberry Pi
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### Step 2: Get Tailscale IPs (1 min)
```bash
# On both machines
tailscale ip -4
```

### Step 3: Update Mapping (1 min)
```json
{
  "raspberrypi-ce39": "100.64.0.2"  # Use Pi's Tailscale IP
}
```

### Step 4: Copy Template (1 min)
```powershell
Copy-Item "templates_local\remote_pi_manager.html" "templates\remote_pi_manager.html"
```

### Step 5: Add Route to app.py (2 min)
```python
@app.route('/remote-pi-manager')
@login_required
def remote_pi_manager():
    return render_template('remote_pi_manager.html')
```

### Step 6: Deploy (5 min)
```powershell
.\deploy_to_server.ps1
```

### Step 7: Test (2 min)
Visit: https://everydayadvertise.com/remote-pi-manager

---

## 🔍 Verification Checklist

After deployment, verify:

- [ ] Tailscale installed on AWS server
- [ ] Tailscale installed on all Raspberry Pis
- [ ] Pi ID mapping updated with Tailscale IPs
- [ ] Remote Pi Manager template copied to production
- [ ] Route added to production app.py
- [ ] Production deployed successfully
- [ ] Can access https://everydayadvertise.com/remote-pi-manager
- [ ] Pi status shows "online"
- [ ] Configuration sends successfully
- [ ] Pi receives and applies configuration

---

## 📝 Code Changes Summary

### Files to Modify:

1. **pi_id_ip_map.json** - Update with Tailscale IPs
2. **templates/remote_pi_manager.html** - Copy from templates_local/
3. **app.py** - Add `/remote-pi-manager` route

### Files Already Ready:
- ✅ `/api/configure-pi` endpoint (exists in app.py line 9381)
- ✅ `/api/register_pi` endpoint (exists in app.py line 9433)
- ✅ `/api/pi-status/<pi_id>` endpoint (exists in app.py line 9465)
- ✅ `complete_pi_client.py` (already deployed and working)

---

## 🎓 Understanding the Architecture

### Current Local Setup (Working):
```
Your Computer (192.168.1.115:5002)
        ↓ HTTP Request
Raspberry Pi (192.168.1.131:8080)
```

### Production with Tailscale:
```
AWS Server (100.64.0.1)
        ↓ HTTP Request over Tailscale VPN
Raspberry Pi (100.64.0.2)
```

**Key Point:** With Tailscale, your production setup becomes **identical** to local testing, just with different IP addresses!

---

## 🐛 Troubleshooting

### "Pi shows offline in production"
1. Check Tailscale status: `sudo tailscale status`
2. Verify Pi ID mapping has correct Tailscale IP
3. Test connectivity: `curl http://100.64.0.2:8080/status`

### "Configuration not reaching Pi"
1. Check Pi service: `sudo systemctl status pizza-hut-tv`
2. View Pi logs: `journalctl -u pizza-hut-tv -f`
3. Test direct config: `curl -X POST http://100.64.0.2:8080/configure -H "Content-Type: application/json" -d '{"pi_id":"raspberrypi-ce39","pair_code":"1234","store_id":"1000","screen_id":"tv1"}'`

### "Tailscale connection lost"
1. Restart Tailscale: `sudo systemctl restart tailscaled`
2. Re-authenticate: `sudo tailscale up`
3. Check firewall: `sudo ufw status`

---

## 🌟 Next Steps

1. **Choose your solution** (Tailscale recommended)
2. **Follow the Quick Start guide** above
3. **Test in production** with one Pi
4. **Scale to multiple stores** as needed
5. **Document your deployment** for future reference

---

## 💡 Pro Tips

- **Keep local dev environment**: Always test changes locally first
- **Monitor Tailscale logs**: `sudo journalctl -u tailscaled -f`
- **Backup pi_id_ip_map.json**: Version control this file
- **Use environment variables**: Store Tailscale network ID in .env
- **Set up alerts**: Monitor Pi connectivity and status

---

## 📞 Support

If you encounter issues:
1. Check logs on both server and Pi
2. Verify network connectivity
3. Test API endpoints individually
4. Review this guide's troubleshooting section

Your Remote Pi Manager is already **production-ready** - you just need to solve the network connectivity challenge! 🚀
