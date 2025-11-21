# Phone Verification Setup Guide

## Overview
Phone verification has been implemented using **Vonage SMS API** (formerly Nexmo). Users can add their phone number and verify it via SMS code.

## Features Implemented

### 1. **Database Schema**
Added columns to `users` table:
- `phone_number` TEXT - User's phone in international format (+61403666669)
- `phone_verified` INTEGER - 0 = not verified, 1 = verified
- `phone_verification_code` TEXT - Temporary 6-digit code
- `phone_code_sent_at` INTEGER - Unix timestamp of when code was sent

### 2. **Backend API Routes**

#### `/api/account/phone` (POST)
- **Purpose**: Save/update user's phone number
- **Validation**: 
  - Must start with `+` (international format)
  - Checks for duplicate phone numbers
- **Response**: Marks phone as unverified after update

#### `/api/account/phone/send-code` (POST)
- **Purpose**: Send 6-digit verification code via SMS
- **Features**:
  - Rate limiting: 1 code per 60 seconds
  - Code expires in 10 minutes
  - Uses Vonage SMS API
- **Message Format**: "Your EverydayAdvertise verification code is: 123456\n\nThis code will expire in 10 minutes."

#### `/api/account/phone/verify` (POST)
- **Purpose**: Verify the SMS code
- **Validation**:
  - Code must be exactly 6 digits
  - Code must match stored code
  - Code must not be expired (< 10 minutes old)
- **Success**: Marks phone_verified = 1, clears verification code

### 3. **Frontend UI (account.html)**

#### Phone Number Display
- Shows current phone number
- Badge indicators:
  - ✓ Verified (green) - Phone is verified
  - ⚠ Not verified (yellow) - Phone exists but not verified
  - Not set (gray) - No phone added

#### Phone Edit Form
- International phone input with country flags
- Placeholder: "+61403666669"
- Helper text: "Must include country code"
- Save/Cancel buttons

#### Phone Verification Form (Yellow Warning Box)
- Only shown when phone exists but not verified
- Features:
  - "Send Verification Code" button
  - 6-digit code input (large, centered, letter-spaced)
  - "Verify Code" button
  - 60-second countdown before resend allowed
  - Real-time error/success messages

## Vonage Configuration

### API Credentials (from your screenshots)
```
VONAGE_API_KEY=cd8f971d
VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m
VONAGE_FROM_NUMBER=+13165308999
```

### Setup on Server

1. **Add to `.env` file on server:**
```bash
cd /var/www/pizza-hut-tv
nano .env
```

Add these lines:
```bash
# Vonage SMS Configuration
VONAGE_API_KEY=cd8f971d
VONAGE_API_SECRET=az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m
VONAGE_FROM_NUMBER=+13165308999
```

2. **Restart service:**
```bash
sudo systemctl restart pizza-hut-tv
```

3. **Verify it's working:**
```bash
sudo journalctl -u pizza-hut-tv -n 20 --no-pager | grep -i vonage
```

You should see: `INFO: Vonage SMS enabled for phone verification`

## User Flow

### Adding Phone Number
1. User goes to Account page
2. Clicks "Add Phone Number" button
3. Enters phone with country code (e.g., +61403666669)
4. Clicks "Save Phone"
5. Yellow verification box appears

### Verifying Phone
1. User clicks "📤 Send Verification Code"
2. SMS sent to their phone via Vonage
3. User enters 6-digit code
4. Clicks "✓ Verify Code"
5. Success: Phone marked as verified ✓
6. Badge changes from yellow to green

## Testing

### Test Locally (if Vonage credentials are set)
```powershell
$env:VONAGE_API_KEY="cd8f971d"
$env:VONAGE_API_SECRET="az2Stt9sdkNpPjCssXMvdxkzR7ZxL99UoDK5FqEqHXMBy1m"
$env:VONAGE_FROM_NUMBER="+13165308999"
python app.py
```

### Test on Production
1. Login to your account
2. Go to Account page
3. Add your phone number
4. Click "Send Verification Code"
5. Check your phone for SMS
6. Enter code and verify

## Vonage Dashboard

Your Vonage account: https://dashboard.nexmo.com/

**Features available:**
- SMS & MMS sending
- Voice calls (not implemented yet)
- Phone number: (+1) 3165308999 (linked to application)
- Webhooks configured:
  - Inbound: https://everydayadvertise.com/webhooks/vonage/inbound
  - Status: https://everydayadvertise.com/webhooks/vonage/inbound

## Cost & Limits

### Vonage Pricing
- SMS: ~$0.005 - $0.02 per message (varies by country)
- To Australia: ~$0.06 per SMS
- To USA: ~$0.0075 per SMS

### Rate Limiting Implemented
- 1 code per 60 seconds per user
- Code expires in 10 minutes
- Prevents spam/abuse

## Troubleshooting

### "SMS service not configured"
**Solution**: Vonage credentials not set in .env
```bash
# Check if credentials exist
grep VONAGE /var/www/pizza-hut-tv/.env

# If missing, add them and restart
sudo systemctl restart pizza-hut-tv
```

### "Failed to send SMS"
**Possible causes:**
1. Invalid phone number format
2. Vonage API error (check dashboard)
3. Insufficient Vonage balance
4. Phone number not supported by Vonage

**Check logs:**
```bash
sudo journalctl -u pizza-hut-tv -f | grep -i sms
```

### "Please wait X seconds before requesting a new code"
**This is normal**: Rate limiting prevents abuse. Wait the specified time.

### "Verification code expired"
**This is normal**: Codes expire after 10 minutes. Request a new code.

### "Invalid verification code"
**Possible causes:**
1. User entered wrong code
2. Code expired
3. User requested multiple codes (only latest is valid)

## Security Features

✅ **Rate limiting** - 1 code per minute per user  
✅ **Code expiration** - 10 minutes  
✅ **One-time use** - Code cleared after successful verification  
✅ **Unique phone numbers** - No duplicate phones across users  
✅ **International format validation** - Must start with +  

## Next Steps (Optional Enhancements)

1. **2FA (Two-Factor Authentication)**
   - Require phone verification for login
   - Send codes on suspicious login attempts

2. **Phone Number Recovery**
   - Allow password reset via SMS
   - Alternative to email verification

3. **SMS Notifications**
   - Subscription reminders
   - Payment confirmations
   - Screen status alerts

4. **Voice Verification**
   - Call user with code (for accessibility)
   - Vonage supports voice calls

5. **WhatsApp/Viber Integration**
   - Vonage supports WhatsApp Business API
   - More reliable in some regions

## Files Modified

- `app.py` - Added phone verification routes and Vonage client
- `templates/account.html` - Added verification UI
- `requirements.txt` - Added `vonage>=3.0,<4`
- `.env.example` - Added Vonage configuration example
- `setup_vonage_server.sh` - Server setup script

## Support

If you encounter issues:
1. Check server logs: `sudo journalctl -u pizza-hut-tv -f`
2. Check Vonage dashboard: https://dashboard.nexmo.com/
3. Test SMS delivery manually in Vonage dashboard
4. Verify .env credentials are correct
