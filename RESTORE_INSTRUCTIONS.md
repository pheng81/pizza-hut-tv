# Master Backup Restore Instructions

## Backup Files Created: November 7, 2025

### Master Backup Files

**On Server (everydayadvertise.com):**
- `/var/www/pizza-hut-tv/database.db.MASTER_BACKUP` (24 KB)
- `/var/www/pizza-hut-tv/store_config__test9_at_gmail.com.json.MASTER_BACKUP` (269 KB)

**Local Copies:**
- `database_MASTER_BACKUP.db` (24 KB)
- `store_config_MASTER_BACKUP.json` (269 KB)

### What's Included

**Database (database.db):**
- User: test9@gmail.com
- Password: test9
- Link Code: 8329
- Email verified: Yes

**Store Configuration (store_config__test9_at_gmail.com.json):**
- All stores and screens
- All playlists and schedules
- Screen configurations
- Pi device mappings

### How to Restore

#### On Production Server:

```bash
# SSH into server
ssh -i "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-southeast-2.pem" ubuntu@54.252.90.27

# Stop the service
sudo systemctl stop everydayadvertise
sudo fuser -k 5002/tcp

# Restore database
cd /var/www/pizza-hut-tv
cp database.db.MASTER_BACKUP database.db
cp store_config__test9_at_gmail.com.json.MASTER_BACKUP store_config__test9_at_gmail.com.json

# Set permissions
sudo chown ubuntu:ubuntu database.db
sudo chown ubuntu:ubuntu store_config__test9_at_gmail.com.json

# Restart service
sudo systemctl start everydayadvertise
```

#### From Local Backup:

```powershell
# Upload from local machine
scp -i "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-southeast-2.pem" "database_MASTER_BACKUP.db" ubuntu@54.252.90.27:/tmp/database.db
scp -i "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-southeast-2.pem" "store_config_MASTER_BACKUP.json" ubuntu@54.252.90.27:/tmp/store_config.json

# SSH and restore
ssh -i "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-southeast-2.pem" ubuntu@54.252.90.27 "sudo systemctl stop everydayadvertise && sudo fuser -k 5002/tcp && sudo cp /tmp/database.db /var/www/pizza-hut-tv/database.db && sudo cp /tmp/store_config.json /var/www/pizza-hut-tv/store_config__test9_at_gmail.com.json && sudo chown ubuntu:ubuntu /var/www/pizza-hut-tv/database.db /var/www/pizza-hut-tv/store_config__test9_at_gmail.com.json && sudo systemctl start everydayadvertise"
```

### Login Credentials

- **URL:** https://everydayadvertise.com/login
- **Username:** test9@gmail.com
- **Password:** test9
- **Link Code:** 8329

### Important Notes

1. Always stop the service before restoring
2. Always kill processes on port 5002
3. Always set proper file ownership after restore
4. Verify the service started successfully after restore
5. Keep these backup files safe - they contain all your store data

### Backup Location on GitHub

These master backups are also stored locally and should be committed to the repository for safekeeping.
