# Pizza Hut TV - Deployment & Database Management Guide

## ✅ What We Fixed Today (Oct 2, 2025)

### 1. **Pi Client Pairing Code Issue**
- **Problem:** Pi client couldn't connect using TV pairing code
- **Root Cause:** We accidentally overwrote the production database with local test data when deploying
- **Solution:** 
  - Added user account back to database: `toengpheng@gmail.com` with code `3204`
  - Fixed deployment script to NEVER upload database files

### 2. **Webplayer Orientation/Rotation**
- **Problem:** Webplayer had letterboxing (black bars) unlike Pi client
- **Solution:** Updated `player.html` to match Pi client behavior:
  - Changed scale calculation from `Math.min()` to `Math.max()` (fills screen)
  - Updated CSS: `width: 100%; height: 100%; object-fit: cover`
  - Added `transform-origin: center center`

### 3. **Deploy Script Fixed**
- **Location:** `deploy_to_server.ps1`
- **Change:** Removed `database.db` and `users.sqlite` from deployment files
- **Why:** Database files contain production user accounts and must NOT be overwritten

---

## 🚨 CRITICAL: Database Management Rules

### **NEVER Deploy Database Files**
```powershell
# ❌ BAD - Don't include these in deployment:
'database.db'
'users.sqlite'

# ✅ GOOD - Only deploy code files:
'app.py'
'requirements.txt'
'templates/**'
```

### **Why This Matters**
1. **User Accounts:** Database contains all user accounts with TV pairing codes
2. **Dynamic Data:** Users create accounts via dashboard registration
3. **Store Configurations:** While stores are in JSON files, user-to-store mappings are in the database
4. **Overwriting = Data Loss:** Deploying local database will wipe out production users

---

## 📂 File Structure

### **Server Locations**
- **Working Directory:** `/home/ubuntu/pizza-hut-tv/`
- **Service:** Running via gunicorn on port `5002`
- **Database:** `/home/ubuntu/pizza-hut-tv/database.db`
- **Store Configs:** `/home/ubuntu/pizza-hut-tv/store_config__*.json`

### **Database Files**
- `database.db` - Main database (users, accounts, pairing codes)
- Store configurations in separate JSON files per user

### **Key Code Files**
- `app.py` - Flask backend (uses `database.db` by default)
- `custom_player.py` - Raspberry Pi client
- `templates/webplayer/player.html` - Web-based player
- `deploy_to_server.ps1` - Deployment script

---

## 🔑 TV Pairing Code System

### **How It Works**
1. Each user gets a unique 4-digit code (e.g., `3204`)
2. Code is stored in `users` table: `link_code` column
3. Pi client sends code to `/api/stores_by_code/{code}`
4. Server returns user's stores and screens

### **When Codes Are Generated**
- ✅ First time user registers
- ✅ User clicks "Regenerate" button
- ❌ Should NEVER auto-generate on page refresh

### **Function: `_ensure_user_link_code()`**
```python
def _ensure_user_link_code(username: str) -> str:
    # 1. Check if user already has a code
    # 2. If yes, return existing code
    # 3. If no, generate new unique 4-digit code and save
```

---

## 🚀 Deployment Checklist

### **Before Deploying**
- [ ] Test changes locally
- [ ] Verify no database files in deployment script
- [ ] Check that app.py uses `database.db` (not `users.sqlite`)

### **Deploy Command**
```powershell
.\deploy_to_server.ps1 -Server '54.252.90.27' -KeyPath 'C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem'
```

### **After Deploying**
- [ ] Service restarts automatically
- [ ] Test dashboard access: `https://api.everydayadvertise.com/dashboard`
- [ ] Verify TV pairing code doesn't change on refresh
- [ ] Test Pi client can connect with existing code

---

## 🔧 Server Management

### **Check Service Status**
```bash
sudo systemctl status pizza-hut-tv
```

### **Restart Service**
```bash
sudo systemctl restart pizza-hut-tv
```

### **View Logs**
```bash
sudo journalctl -u pizza-hut-tv -n 50 --no-pager
```

### **Check Database Users**
```bash
cd /home/ubuntu/pizza-hut-tv
/home/ubuntu/pizza-hut-tv/.venv/bin/python3 -c "import sqlite3; conn = sqlite3.connect('database.db'); rows = conn.execute('SELECT username, link_code FROM users').fetchall(); print('\n'.join([f'{r[0]} | {r[1]}' for r in rows]))"
```

---

## 📱 Pi Client Usage

### **Setup Steps**
1. Run `custom_player.py` on Raspberry Pi
2. Enter TV pairing code (from dashboard)
3. Select store from list
4. Select screen (Screen 1, 2, 3, Promo 1-4, etc.)
5. Content starts playing

### **Debug Logging**
The Pi client now includes enhanced debug output:
```
🔍 Fetching playlist:
   Store: 1135
   Screen: 1135_screen1
   Full Screen ID: 1135_screen1
   URL: https://everydayadvertise.com/playlist/1135/1135_screen1
   Response Status: 200
   ✅ Loaded 5 items
```

---

## 🌐 Webplayer

### **Access URL**
`https://api.everydayadvertise.com/webplayer/`

### **Orientation Behavior**
- Dashboard toggle: Vertical ↔ Horizontal
- Webplayer auto-rotates and scales to fill screen
- No letterboxing (matches Pi client)

---

## 👤 Current Users

### **Production Users**
- `toengpheng@gmail.com` - Code: `3204` (YOUR ACCOUNT)
  - Store 1135: canley vale
  - Store 1000: My First Store
  
- `kayson5@gmail.com` - Code: `7844` (Test account)

---

## 🐛 Troubleshooting

### **Issue: Pi shows "Failed to load screens"**
- Check TV pairing code exists in database
- Verify server is running: `curl https://api.everydayadvertise.com/api/stores_by_code/{CODE}`
- Check server logs for errors

### **Issue: TV code changes on dashboard refresh**
- This was the bug we fixed today
- If it happens again, check `_ensure_user_link_code()` function
- Verify database query is finding the user

### **Issue: Webplayer has black bars**
- Check orientation settings in dashboard
- Verify `player.html` has `object-fit: cover` and `Math.max()` scaling
- Clear browser cache and refresh

---

## 📝 Notes

- **Server:** AWS Lightsail (54.252.90.27)
- **Domain:** api.everydayadvertise.com (via Cloudflare Tunnel)
- **Port:** 5002 (internal), 443 (external HTTPS)
- **Python:** 3.12
- **Framework:** Flask + Gunicorn

---

## ✅ System Status (Oct 2, 2025)

- [x] Pi client working with TV code 3204
- [x] Webplayer orientation matches Pi behavior
- [x] Dashboard TV code no longer auto-regenerates
- [x] Deployment script protects production database
- [x] Store configurations intact (1135, 1000)
- [x] All screens working (Screen 1-3, Promo 1-4)
- [x] Scheduling rules working (weekly, one-off, enabled switch)
- [x] Fade transitions implemented (0.5s)

**Everything is working correctly! 🎉**
