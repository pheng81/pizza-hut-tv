# Task: deploy the 3.1.1 billing fix to production

**Status:** code is on GitHub, **not yet deployed**. This is the outstanding half.

**For:** whoever works from the Windows clone — it holds the Lightsail key
(`%USERPROFILE%\.ssh\LightsailDefaultKey-ap-southeast-2.pem`), which the Mac
does not, so the deploy cannot run from there.

| | |
| --- | --- |
| Branch | `agent/native-google-signin-ios` |
| Commit | `4aa32a56c09` "Let an App Store customer actually buy the subscription" |
| Server file changed | `app.py` only |
| Production | `54.252.90.27`, `/var/www/everydayadvertise_tv` |
| iOS build | 1.2.0 (68), built and uploaded separately from the Mac |

## Why this exists

App Review rejected **1.0 (65)** under guideline 3.1.1 (submission
`f9bff407-e98e-49f2-80e3-b84842555ca3`, reviewed 1 Sep 2026): the app reached
paid content bought outside it, with no In-App Purchase offered for that
content.

The reviewer signed in with Apple, so the account had a `privaterelay.appleid.com`
address and **no phone number**. Subscribing required a verified phone, so
Subscribe Now told them to verify a number they could not receive. No other
route to a purchase existed. The account page also read **"Billing Provider:
Website / Stripe"** above the website's `$1.99 per screen / month` rate — an
external price, advertised in the app, for a purchase the app cannot make.

## What changed in `app.py`

1. **`_client_platform()` / `_client_forbids_external_purchase()`** — new. Read
   a new `X-Client-Platform` header (`ios` / `android` / `web`) that the Flutter
   client now sends on every request. Absent means the website.
   `has_request_context()` guards it so background jobs and the test suite still
   work.

2. **`_subscription_eligibility(user_id, provider=None)`** — gained the
   `provider` argument. Apple and Google purchases skip the phone-number checks;
   Stripe keeps them. The phone requirement is a chargeback-risk measure that
   only applies where we take the money. **This is the fix for the actual
   rejection.**

3. **`/api/subscription/summary`** — passes the caller's platform as the
   provider, so `can_subscribe` answers about the purchase that client would
   actually make. Also blanks `mobile_plan_upgrade_url` for iOS.

4. **`_store_plan_ceiling_message()`** — an iOS-only wording that names support
   instead of walking the user through "then subscribe on the website". Android
   and web keep the existing three-step message verbatim.

5. **`/api/account/overview`** — when nothing is subscribed, reports the
   provider that *would* take the payment (`apple` on iOS, `google` on Android)
   instead of hardcoding `stripe`, and adds `prospective_store_product_id` so
   the app can quote StoreKit's price. An account genuinely billed by Stripe
   still reports `stripe` — that multiplatform case is allowed, and honest.

6. **`/check_screen_limit` and `/add_screen`** — withhold `upgrade_url` from iOS
   callers.

Nothing else on the server changed. No template, `.env`, schema or dependency
changes.

## Deploy

```powershell
git fetch origin
git merge origin/agent/native-google-signin-ios   # or check the branch out
.\deploy_automated.ps1
```

`deploy_automated.ps1` ships `app.py`, `config.py` and `.env.production`, which
covers this change. It runs `test_app.py` first and aborts on failure.

## Verify before the deploy

The suites are in git now (HANDOFF.md still says they are Windows-only — that
is out of date). All pass on the Mac:

```
python test_ceiling_message.py       # iOS wording carries no website CTA
python test_eligibility_action.py    # Stripe still requires a phone
python test_account_overview_api.py
python test_subscribe_page.py
```

`test_ceiling_message.py` and `test_price_source.py` end in a `FileNotFoundError`
on a hardcoded `c:\Users\toeng\Pizza Hut TV\app.py` path. That is pre-existing
and unrelated — read the PASS/FAIL lines above it, not the exit code.

## Verify after the deploy

The point of the change is that the answer now depends on the caller. Use a
session for an account with a **verified email and no phone number** — that is
the reviewer's shape.

```bash
# iOS: must be true, with no blocking action
curl -s https://everydayadvertise.com/api/subscription/summary \
  -H 'X-Mobile-Auth: <token>' -H 'X-Client-Platform: ios' \
  | python -m json.tool | grep -E 'can_subscribe|subscribe_blocked|upgrade_url'
# expect: "can_subscribe": true, blocked_reason "", upgrade_url ""

# Web: must still be false, action add_phone (the Stripe gate is intact)
curl -s https://everydayadvertise.com/api/subscription/summary \
  -H 'X-Mobile-Auth: <token>' \
  | python -m json.tool | grep -E 'can_subscribe|subscribe_blocked'
# expect: "can_subscribe": false, "subscribe_blocked_action": "add_phone"

# iOS, unsubscribed account: names Apple, not Stripe
curl -s https://everydayadvertise.com/api/account/overview \
  -H 'X-Mobile-Auth: <token>' -H 'X-Client-Platform: ios' \
  | python -m json.tool | grep -E 'billing_provider|prospective_store_product_id'
# expect: "billing_provider": "apple", "prospective_store_product_id": "Screen_1"
```

If the iOS and web answers are identical, the header is not reaching Flask —
check for a proxy stripping unknown headers in the nginx config before
suspecting the code.

## Also confirm on the box

**`APPLE_IAP_SHARED_SECRET` must be set in the server's `.env`.** Without it
`_apple_iap_enabled()` returns false and receipts are refused *after* Apple has
charged the customer, which is worse than the bug being fixed. Note the known
trap recorded in HANDOFF.md: the deploy writes `.env`, and `.env.production`
was historically uploaded to a filename nothing read — so check the live file,
not the local one.

```bash
ssh -i <key> ubuntu@54.252.90.27 \
  "grep -c APPLE_IAP_SHARED_SECRET /var/www/everydayadvertise_tv/.env"
```

## Still open, not fixed here

- **The IAP products must be "Ready to Submit" and attached to the build** in
  App Store Connect: `Screen_1`, `Screens_3`, `Screens_5`, `Screens_10`. If
  `queryProductDetails` returns empty there is no purchasable IAP at all and the
  rejection reads exactly the same. Not verifiable from either clone — check the
  console.
- **A demo account for App Review** with a verified email. It no longer needs a
  phone number, which is the point of this change.
- Cosmetic: the account page shows `Upcoming Billing: Sep 15, 2026` next to
  `No Subscription` and `$0.00`. Not a compliance problem, left alone.
