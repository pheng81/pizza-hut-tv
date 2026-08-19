# Handoff - state as at 2026-08-19

Written from the Windows clone. Everything below is on GitHub `main`
(`github.com/phengtoeng/everydayadvertise`) **and deployed to production**,
unless a line says otherwise.

Billing detail lives in `MOBILE_BILLING_SETUP.md`; this file is the short
version plus what is still outstanding.

## Where things run

| Place | State |
| --- | --- |
| GitHub `main` | source of truth |
| Windows clone | deploys from here |
| Production `54.252.90.27` | in sync with `main` |
| iPhone (TestFlight) | **build 1.1.0 (57) - five builds behind `1.1.0+62`** |

`deploy_automated.ps1` ships **only** `app.py`, `config.py` and
`.env.production`. It does **not** ship `templates/` and it does **not** build
the app. A Dart change reaches the phone only via a new TestFlight build.

## Apple <-> website: how it actually works

There is no direct link between Apple and the website. Both the app and the
website read **one row** in `subscriptions`, keyed by user:

```
iPhone --receipt--> server --verifies with Apple--> subscriptions row
                                                     ^            ^
                                              app reads it   website reads it
```

`billing_provider` (`apple`/`google`/`stripe`) and `billing_product_id` on that
row decide what every page shows and what the server allows.

**App Store Server Notifications V2 are live and working.** Registered in App
Store Connect and confirmed receiving: an `EXPIRED` notification landed one
minute after a subscription lapsed and correctly wrote `expired` to both
`subscriptions` and `mobile_store_purchases`. Endpoint:
`POST /api/billing/apple/notifications`. Trust comes from walking the JWS
certificate chain back to Apple Root CA - G3, pinned in `app.py`. No shared
secret involved.

Notification outcomes log at **warning**, not info - the server runs at WARNING
level, so an info-level log is invisible. Do not "tidy" that back to info.

## Fixed this round

- Renewals/cancels/expiry now update the record on their own. Previously the
  website only learned anything when the app was opened, so a subscriber was
  locked out at their first renewal.
- Adding a screen no longer opens a Stripe subscription for an account a store
  already bills. That was charging the same screens twice.
- Subscribe and account pages say who is billing: no Stripe pitch or per-screen
  price to a store subscriber, and no "cancel all and remove all screens"
  button, which for a store account deleted the screens without stopping the
  store billing.
- Prices come only from admin Subscription settings. No `$5` literals remain in
  `app.py` or the templates.
- Saving admin billing settings now repoints Stripe at a price matching the
  per-screen number (Stripe prices are immutable, so it reuses or creates one).
  Typing a specific price ID by hand still overrides.
- `/screens/<store_id>` returned **404 "store not found"** for a store that
  exists but has no screens yet, because it keyed off the `screens` map rather
  than the store list. That broke every brand-new store and any store whose
  screens had been deleted. This was the "server problem" seen in the app.
- `deploy_automated.ps1` here-strings had CRLF endings, so `&&` chaining did
  nothing and a failed step still reported DEPLOYMENT SUCCESSFUL.

## Outstanding

1. **10 duplicate live Stripe subscriptions** on `toengpheng@gmail.com`
   (user 44), A$5/month each, first charge **2026-08-29**. Created before the
   double-billing fix. No card on file so nothing has been collected. Cancel
   them in the Stripe Dashboard - the fix stops new ones but does not remove
   these.
2. **Admin price vs Stripe price disagree.** Admin says `1.0` / "$1 per screen
   / month"; the Stripe price ID it points at charges **AUD 5.00**. Pressing
   Save on the admin billing page now reconciles this. A second product
   `prod_V6C45WJEEZV8bC` ("$1.99 Per Screen", `price_1U5zfzH80pD9X0Fy8Camw3DJ`,
   **USD 1.99**) also exists and matches the Apple `Screen_1` tier price.
   Decide which is intended - it is a business call, not a code fix.
3. **Ship a TestFlight build.** The phone is five builds behind and is missing
   every master-store fix plus the debug API logging.
4. **Promotion pricing is not covered.** `superadmin_update_billing_promotion`
   has its own price and price ID and was not given the same reconciliation, so
   it can still show one price and charge another.
5. **`_active_store_subscription()` ignores `current_period_end`.** It treats a
   row as blocking while `status` reads active, even if the period has passed,
   while `_user_has_active_subscription()` honours the date. A stale row means
   locked out of the dashboard *and* blocked from subscribing on the web. Less
   likely now notifications set `expired` properly, but a missed notification
   still traps someone.
6. **Four hardcoded `$5` strings remain in the Flutter app**
   (`account_page.dart` x2, `subscribe_page.dart`, `stores_tab.dart`). The
   first also describes per-screen Stripe billing, which is wrong on a store
   account.
7. **Google Play** is deliberately parked. `screens_monthly` has no tier
   allowance, so those subscribers are uncapped on screens. Play's real-time
   developer notifications are not implemented - Play state has the same
   staleness problem Apple had before this round.

## Tests

`test_*.py` is in `.gitignore`, so the suites written this round live **only on
the Windows clone** and are not in git (this includes the pre-existing
`test_app.py` that `deploy_automated.ps1` runs). 149 checks covering Apple JWS
verification and notification handling, the subscribe/account page states,
admin-driven pricing, the Stripe price reconciliation, and the
`/screens/<store_id>` fix. Ask before relying on them from another machine.
