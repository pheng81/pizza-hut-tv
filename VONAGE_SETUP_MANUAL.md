# Manual Vonage Setup Instructions

## Step 1: SSH to Server
```bash
ssh ubuntu@54.252.90.27
```

## Step 2: Add Vonage Credentials
```bash
cd /var/www/pizza-hut-tv
nano .env
```

Add these lines at the end:
```
# Vonage SMS Configuration
VONAGE_API_KEY=cd8f971d
VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m
VONAGE_FROM_NUMBER=+13165308999
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

## Step 3: Install Vonage SDK
```bash
source venv/bin/activate
pip install 'vonage>=3.0,<4'
```

## Step 4: Restart Service
```bash
sudo systemctl restart pizza-hut-tv
```

## Step 5: Verify It's Working
```bash
sudo journalctl -u pizza-hut-tv -n 20 --no-pager | grep -i vonage
```

You should see: `INFO: Vonage SMS enabled for phone verification`

## Step 6: Test It
1. Go to https://everydayadvertise.com/account
2. Click "Add Phone Number"
3. Enter your phone number with country code (e.g., +61403666669)
4. Click "Send Verification Code"
5. Check your phone for SMS
6. Enter the 6-digit code
7. Click "Verify Code"

✅ Done! Phone verification is now active.
