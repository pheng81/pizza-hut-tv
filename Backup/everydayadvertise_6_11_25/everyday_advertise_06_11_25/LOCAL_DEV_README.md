# 🍕 Pizza Hut TV - Local Development vs Production

## 📁 Project Structure

```
Pizza Hut TV/
├── app.py                    # 🚀 PRODUCTION SERVER (AWS deployment)
├── app_local_dev.py         # 🔧 LOCAL DEVELOPMENT SERVER (testing only)
├── templates/               # Production templates
├── templates_local/         # Local dev templates (simplified)
├── database.db             # Production database
└── database_from_server.db # Production database copy (for local testing)
```

---

## 🔧 Local Development Server

### Purpose
- **Test features locally** without affecting production
- **HTTP-compatible** cookies (no HTTPS required)
- **Simplified authentication** for easy testing
- **Completely isolated** from production code

### Files
- **Server:** `app_local_dev.py`
- **Templates:** `templates_local/` folder
- **Database:** `database_from_server.db` (production copy)

### Start Local Dev Server
```powershell
python app_local_dev.py
```

### Access
- **URL:** http://127.0.0.1:5002
- **Login:** `kayson5@gmail.com` / `test123`

### Features
- ✅ HTTP cookies (no SSL certificate needed)
- ✅ Session persistence working
- ✅ Simplified login/dashboard
- ✅ Uses production database (read-only copy)
- ✅ Debug mode enabled
- ✅ Auto-reload on code changes

---

## 🚀 Production Server

### Purpose
- **Live deployment** on AWS (everydayadvertise.com)
- **HTTPS-only** with secure cookies
- **Full feature set** with all dashboards
- **Production-ready** configuration

### Files
- **Server:** `app.py` (9500+ lines)
- **Templates:** `templates/` folder
- **Database:** `database.db` (live production data)

### Deploy to Production
```powershell
# Use existing deployment scripts
.\deploy_to_server.ps1
```

### Access
- **URL:** https://everydayadvertise.com
- **Login:** Production credentials

### Features
- ✅ HTTPS with SSL certificates
- ✅ Secure cookies (HTTPS-only)
- ✅ OAuth integration
- ✅ Full dashboard features
- ✅ Production database
- ✅ Cloudflare CDN

---

## 🔄 Workflow

### 1. Local Development
```powershell
# Start local dev server
python app_local_dev.py

# Access at http://127.0.0.1:5002
# Login: kayson5@gmail.com / test123
# Test your features
```

### 2. Test Pi Connectivity
```powershell
# Pi is at 192.168.1.131:8080
# Local server can reach it (same network)
# Test Remote Pi Manager with Pi ID: raspberrypi-ce39
```

### 3. Deploy to Production
```powershell
# When local testing complete
# Deploy production app.py (unchanged)
.\deploy_to_server.ps1
```

---

## 🔑 Key Differences

| Feature | Local Development | Production |
|---------|------------------|-----------|
| **Protocol** | HTTP | HTTPS |
| **Cookies** | HTTP-compatible | HTTPS-only |
| **Port** | 5002 | 443 (HTTPS) |
| **Database** | `database_from_server.db` | `database.db` |
| **Templates** | `templates_local/` | `templates/` |
| **Debug Mode** | ON | OFF |
| **Session Domain** | None (any) | `.everydayadvertise.com` |
| **Auto-reload** | Yes | No |

---

## ⚙️ Configuration

### Local Dev (`app_local_dev.py`)
```python
SESSION_COOKIE_SECURE = False   # HTTP allowed
SESSION_COOKIE_SAMESITE = 'Lax'  # Lax for local
SESSION_COOKIE_DOMAIN = None     # Any domain
PREFERRED_URL_SCHEME = 'http'    # HTTP
```

### Production (`app.py`)
```python
SESSION_COOKIE_SECURE = True          # HTTPS required
SESSION_COOKIE_SAMESITE = 'None'      # Cross-site allowed
SESSION_COOKIE_DOMAIN = '.everydayadvertise.com'
PREFERRED_URL_SCHEME = 'https'        # HTTPS
```

---

## 🎯 Benefits of This Approach

1. **No Production Risk** - Local changes don't affect live site
2. **Easy Testing** - Simple HTTP setup for local development
3. **Quick Iteration** - Auto-reload on code changes
4. **Realistic Data** - Use production database copy
5. **Clean Separation** - Clear distinction between dev/prod

---

## 🚨 Important Notes

### ⚠️ DO NOT Deploy Local Dev Server to Production
- `app_local_dev.py` is **ONLY for local testing**
- Uses insecure HTTP settings
- Missing production features
- Always deploy `app.py` to production

### ⚠️ Database Safety
- Local dev uses `database_from_server.db` (copy)
- Changes won't affect production database
- Periodically refresh copy from production

### ⚠️ Credentials
- Test credentials: `kayson5@gmail.com` / `test123`
- Created specifically for local testing
- Change password before production use

---

## 📝 Quick Reference

### Start Local Dev
```powershell
python app_local_dev.py
```

### Access Local Dev
```
http://127.0.0.1:5002
kayson5@gmail.com / test123
```

### Deploy Production
```powershell
.\deploy_to_server.ps1
```

### Test Pi Connection
```
Pi ID: raspberrypi-ce39
Pi IP: 192.168.1.131:8080
```

---

## ✅ Checklist

### Before Testing Locally
- [ ] Run `python app_local_dev.py`
- [ ] Clear browser cookies
- [ ] Access http://127.0.0.1:5002
- [ ] Login with test credentials

### Before Production Deployment
- [ ] Test all features locally
- [ ] Verify Pi connectivity
- [ ] Check production `app.py` unchanged
- [ ] Run `.\deploy_to_server.ps1`
- [ ] Verify production site works

---

Made with ❤️ for easier development and safer production deployments!
