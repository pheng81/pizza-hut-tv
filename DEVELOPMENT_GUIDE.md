# Expert-Level Development Setup

## Quick Start

### Local Development
```powershell
# Set environment
$env:FLASK_ENV="development"

# Run the app
python app.py
```

### Local Backend For Mobile Testing
```powershell
# Local backend for iOS simulator / mobile app testing
$env:FLASK_ENV="development"
$env:FLASK_DEBUG="1"
$env:SESSION_COOKIE_SECURE="False"
$env:SESSION_COOKIE_SAMESITE="Lax"
$env:PORT="5002"

python app.py
```

Local mobile/backend notes:
- Local backend target: `http://127.0.0.1:5002`
- `everyday_mobile` defaults to remote production API: `https://everydayadvertise.com`
- For simulator testing, change the mobile app base URL to the local backend before testing server-side auth fixes
- iOS simulator should use `127.0.0.1`, not Android emulator host aliases

### Deploy to Production
```powershell
# Automated deployment with tests
.\deploy_automated.ps1

# Dry run (test without deploying)
.\deploy_automated.ps1 -DryRun

# Skip tests (faster)
.\deploy_automated.ps1 -SkipTests
```

## Configuration Files

### .env.development (Local)
- Database: `database.db` (local)
- Port: 5100 in env file, but `app.py` currently defaults to `PORT` or `5002`
- Debug: Enabled

### .env.production (Server)
- Database: `/var/www/pizza-hut-tv/database.db`
- Port: 5002
- Debug: Disabled

## Database Migrations

### Run migrations
```powershell
python db_migrate.py
```

### Show migration status
```python
from db_migrate import DatabaseMigration
migrator = DatabaseMigration('database.db')
migrator.show_status()
```

## Testing

### Run all tests
```powershell
python test_app.py
```

### Run specific test
```python
from test_app import test_imports
test_imports()
```

## Deployment Pipeline

The automated deployment (`deploy_automated.ps1`) does:

1. ✅ **Pre-checks** - Verify files exist, check syntax
2. 🧪 **Tests** - Run test suite (unless -SkipTests)
3. 💾 **Backup** - Create timestamped backup on server
4. 📤 **Deploy** - Upload app.py, config.py, .env.production
5. 🔄 **Restart** - Restart service gracefully
6. 🏥 **Health Check** - Verify service is running
7. ↩️ **Rollback** - Auto-rollback if health check fails

## Environment Variables

All configuration is in `.env.*` files:

- `FLASK_ENV` - development or production
- `FLASK_DEBUG` - Enable debug mode
- `DATABASE_PATH` - Path to SQLite database
- `SERVER_HOST` - Bind address (0.0.0.0 or 127.0.0.1)
- `SERVER_PORT` - Port number
- `LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR
- `BASE_URL` - Full URL for the app

## Mobile Auth Notes

### Apple Sign-In
- The iOS app already includes Apple Sign-In entitlement in `everyday_mobile/ios/Runner/Runner.entitlements`
- The mobile login screen now shows Apple sign-in on iOS/macOS even if backend provider config does not explicitly return `apple: true`
- Backend Apple native login requires:
  - `APPLE_CLIENT_ID`
  - `APPLE_CLIENT_SECRET`
- Native Apple login validates token audience against `APPLE_CLIENT_ID`
- Repeat Apple sign-ins may not return email from Apple; backend now stores and matches `apple_sub` so returning users can still log in
- First Apple sign-in still requires email so the account can be created

#### Apple Developer Values

| Value | Setting |
| --- | --- |
| Team ID | `U6SKM3QX29` |
| Key ID | `S8BN744L7P` |
| Web Service ID / Client ID | `com.everydayadvertise.web` |
| iOS Bundle ID | `com.everydayadvertise.everydayMobile` |

The Team ID is set as `DEVELOPMENT_TEAM` in `everyday_mobile/ios/Runner.xcodeproj/project.pbxproj`
for the Debug, Release and Profile configurations.

Apple website configuration in the developer portal:

- Domains: `everydayadvertise.com`, `api.everydayadvertise.com`
- Return URLs: `https://everydayadvertise.com/auth/apple/callback`, `https://api.everydayadvertise.com/auth/apple/callback`

The return URLs match the `/auth/apple/callback` route in `app.py`.

#### Generating APPLE_CLIENT_SECRET

`APPLE_CLIENT_SECRET` is an ES256 JWT signed with the `.p8` private key
(`AuthKey_S8BN744L7P.p8`). Apple caps its lifetime at 6 months, so it has to be
regenerated before it expires.

**Never commit the `.p8` file or the generated JWT.** Keep the key outside the repo
(for example `C:\Secrets\AuthKey_S8BN744L7P.p8` on Windows) - `*.p8` is gitignored as
a backstop. Write the generation script outside the repo too:

```bash
pip install PyJWT cryptography
```

```python
import time
import jwt
from cryptography.hazmat.primitives import serialization

team_id = "U6SKM3QX29"
key_id = "S8BN744L7P"
client_id = "com.everydayadvertise.web"
key_path = r"C:\Secrets\AuthKey_S8BN744L7P.p8"

with open(key_path, "rb") as file:
    private_key = serialization.load_pem_private_key(file.read(), password=None)

now = int(time.time())

token = jwt.encode(
    {
        "iss": team_id,
        "iat": now,
        "exp": now + 15552000,
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    },
    private_key,
    algorithm="ES256",
    headers={"kid": key_id},
)

print(token)
```

Copy the printed JWT into `APPLE_CLIENT_SECRET`. The production server already has
these credentials configured.

### Google Sign-In
- Native Google Sign-In is wired up for Web, Android, and iOS — all three call the same
  backend endpoint, `/api/auth/google/native`, which verifies the `id_token` against
  Google's `tokeninfo` endpoint and checks the `aud` claim against the allowed client IDs.
- Web uses Google Identity Services (the `accounts.google.com/gsi/client` button embedded
  in `templates/login.html` and `templates/signup.html`), not the old server-side redirect
  flow. `/auth/google` (Authlib redirect) still exists as a `<noscript>`/fallback link.
- Android and iOS use the `google_sign_in` Flutter package; the native ID token is posted
  to the same `/api/auth/google/native` endpoint.
- Backend env vars (all live in the `google-oauth.conf` systemd drop-in):
  - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Web OAuth client (used by both the GIS
    button and the legacy Authlib redirect flow)
  - `GOOGLE_ANDROID_CLIENT_ID` — Android OAuth client (no secret; Android clients are public)
  - `GOOGLE_IOS_CLIENT_ID` — iOS OAuth client

#### Google Cloud OAuth clients

All client IDs live under the `everydayadvertise` GCP project (project number
`929679124405`), Google Auth Platform → Clients:

| Client | Type | Package / Bundle ID |
| --- | --- | --- |
| Everyday Mobile iOS | iOS | `com.everydayadvertise.everydayMobile` |
| Everyday Mobile Android Debug | Android | `com.everydayadvertise.everyday_mobile` |
| everydayadvertise | Web application | n/a |

The Android client needs a **SHA-1 certificate fingerprint** matching whatever keystore
signed the APK/AAB actually running on the device. Two fingerprints are registered on
that one client (via **Advanced settings** on the client's edit page):

- The **debug keystore** SHA-1 (for local `flutter run` builds during development)
- The **Play App Signing key certificate** SHA-1 (for anything installed from Play,
  including internal testing) — found in Play Console under **Protected with Play →
  Play Store protection → Manage Play app signing → App signing key → Classical key →
  SHA-1 certificate fingerprint**. This is *not* the same as the "Upload key certificate"
  SHA-1 shown further down that same page — Play re-signs the app with its own key before
  distributing it, so the upload key's fingerprint never appears on a real user's device.

If you rotate/add a signing key, add its SHA-1 as an extra fingerprint on the same
Android client rather than creating a new client — Google matches on package name + SHA-1
pairs, and a client can hold more than one fingerprint.

### Remote vs Local Server
- Remote production server is the normal app target: `https://everydayadvertise.com`
- Local backend is best for testing auth and backend fixes without touching production
- Pushing to GitHub does not automatically update the live backend unless deployment is run separately

## Local Python Setup

This repo's local backend dependencies may require native build tools on macOS.

### One-time setup
```powershell
brew install openssl@3 pkg-config rust
```

### Install Python requirements with OpenSSL path
```powershell
$env:OPENSSL_DIR = "$(brew --prefix openssl@3)"
$env:PKG_CONFIG_PATH = "$env:OPENSSL_DIR\lib\pkgconfig"
python3 -m pip install -r requirements.txt
```

Notes:
- If `cryptography` fails to build, check `OPENSSL_DIR` and `PKG_CONFIG_PATH`
- If Flask is missing, rerun `python3 -m pip install -r requirements.txt`
- `app.py` must compile cleanly before local backend boot will work

## Best Practices

✅ **Never commit .env files to git**  
✅ **Always test locally before deploying**  
✅ **Use automated deployment script**  
✅ **Check server logs after deployment**  
✅ **Keep backups of working versions**  

## Troubleshooting

### Config not loading?
```python
from config import config
print(config.FLASK_ENV)
print(config.DATABASE_PATH)
```

### Migration failed?
- Check database permissions
- Verify SQL syntax in migration
- Check migration status: `python db_migrate.py`

### Deployment failed?
- Run with `-DryRun` to test
- Check server logs: `ssh ubuntu@54.252.90.27 "sudo journalctl -u everydayadvertise -n 50"`
- Manually rollback: Find backup in `/var/www/pizza-hut-tv/app.py.backup_*`

### Mobile app still hits production?
- `everyday_mobile/lib/services/api_client.dart` defaults to `https://everydayadvertise.com`
- Change the app base URL in the mobile app before testing local server changes

### Apple login still fails?
- Verify `APPLE_CLIENT_ID` matches the `aud` claim in the Apple identity token
- Verify `APPLE_CLIENT_SECRET` exists on the backend
- Verify backend deployment has the latest Apple fix, not just the mobile UI change

## File Structure

```
Pizza Hut TV/
├── .env.development          # Local config
├── .env.production           # Server config (DO NOT COMMIT)
├── config.py                 # Config loader
├── app.py                    # Main application
├── db_migrate.py             # Database migrations
├── test_app.py               # Test suite
├── deploy_automated.ps1      # Automated deployment
├── deploy_to_server.ps1      # Manual deployment
├── deploy_pi_client.ps1      # Pi deployment
├── requirements.txt          # Python dependencies
├── database.db               # Local database
├── templates/                # Production templates
└── templates_local/          # Local dev templates
```

## Expert Score: 10/10 🎯

You now have:
- ✅ Environment-specific configuration
- ✅ Automated testing
- ✅ Database migrations
- ✅ Deployment pipeline with rollback
- ✅ Health checks
- ✅ Proper .gitignore
- ✅ Professional structure

**Welcome to expert-level development!** 🚀
