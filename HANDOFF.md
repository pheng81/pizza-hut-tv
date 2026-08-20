# Handoff - state as at 2026-08-20

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
| iPhone (TestFlight) | **build 1.1.0 (64)** |

`deploy_automated.ps1` ships **only** `app.py`, `config.py` and
`.env.production`. It does **not** ship `templates/` and it does **not** build
the app. Template changes need a separate upload plus a service restart (Jinja
caches compiled templates). A Dart change reaches the phone only via a new
TestFlight build.

## Apple and the website: how it actually works

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

## The two pricing models are genuinely different

This causes the most confusion, and it is not a bug:

| | Apple / Google | Website |
| --- | --- | --- |
| Model | one flat **tier** | **per screen** |
| Price set in | App Store Connect / Play Console | admin Subscription settings |
| Currency | the customer's own, localized | whatever the Stripe price uses |
| Known to the server? | **no** | yes |

The server cannot know what a store charged, so it must not try. For a store
account `/api/account/overview` sends neither `price_display` nor
`monthly_cost`, only `store_plan_label` and `mobile_plan_product_id`; the app
looks the real price up from StoreKit, the same way the paywall does. Never
"helpfully" restore a computed figure there.

## Fixed this round

- Renewals, cancels and expiry now update the record on their own. Previously
  the website only learned anything when the app was opened, so a subscriber
  was locked out at their first renewal.
- Adding a screen no longer opens a Stripe subscription for an account a store
  already bills. That was charging the same screens twice.
- Subscribe and account pages (web) say who is billing: no Stripe pitch or
  per-screen price to a store subscriber, and no "cancel all and remove all
  screens" button, which for a store account deleted the screens without
  stopping the store billing.
- The app's account page reads the store's own price instead of applying the
  website's per-screen model. It previously showed "$1.99 per screen / month"
  and "$3.98" on an Apple `Screens_3` plan that Apple had charged A$7.99 for,
  and fell back to `screenCount * 5` when the server sent nothing.
- Prices come only from admin Subscription settings. No `$5` literals remain in
  `app.py`, the templates, or `account_page.dart`.
- Saving admin billing settings repoints Stripe at a price matching the
  per-screen number (Stripe prices are immutable, so it reuses or creates one).
  Typing a specific price ID by hand still overrides.
- `/screens/<store_id>` returned **404 "store not found"** for a store that
  exists but has no screens yet, because it keyed off the `screens` map rather
  than the store list. That broke every brand-new store and any store whose
  screens had been deleted. This was the "server problem" seen in the app.
- The paywall's eligibility block is no longer a dead end. It said "Please
  verify your phone number before subscribing" and left the customer to find
  the screen themselves. `/api/subscription/summary` now also returns
  `subscribe_blocked_action` - a stable code (`verify_email`, `add_phone`,
  `verify_phone`, `login`) - and the app shows a button that opens the account
  page with the phone editor already open. Match on the code, never the
  message text.
- `deploy_automated.ps1` here-strings had CRLF endings, so `&&` chaining did
  nothing and a failed step still reported DEPLOYMENT SUCCESSFUL.

## Resolved since the last handoff

- **Admin price and Stripe now agree.** Admin `1.99` / "$1.99 per screen /
  month" points at `price_1U5zfzH80pD9X0Fy8Camw3DJ` = **USD 1.99/month**,
  verified matching. Note this moved web billing from **AUD to USD**; the old
  AUD 5.00 price (`price_1STZqBH80pD9X0Fy3WVGJIV7`, product
  `prod_TQQh4AcbGLeeVM`) is no longer in use.
- **The 10 duplicate Stripe subscriptions are all cancelled.** Verified against
  Stripe: every remaining one reads `canceled`. Nothing will be charged on
  Aug 29 or 30. Their local `screen_subscriptions` rows still carry the dead
  `stripe_subscription_id` values - harmless, but stale if anyone audits.

## Outstanding

1. **Ship a TestFlight build, and bump the build number first.**
   `everyday_mobile/pubspec.yaml` reads `1.1.0+62` but TestFlight is already on
   **64**, so an upload from the repo as-is is rejected by Apple as a duplicate
   build number. Set it to **1.1.0+65** or higher before building.

   Two fixes deployed on the server depend on a build newer than the Dart
   commits of 2026-08-20 (`321f154bf1`, `835e224a0c`):
   - the account page reading the real StoreKit price - without it the price
     and monthly-cost fields render blank, because the server deliberately no
     longer sends them for store accounts;
   - the button on the paywall's eligibility block.

   Whether build 64 already contains them depends on when it was cut - check
   before assuming a rebuild is unnecessary.
2. **Promotion pricing is not covered.** `superadmin_update_billing_promotion`
   has its own price and price ID and was not given the same reconciliation as
   the main settings, so it can still show one price and charge another.
3. **`_active_store_subscription()` ignores `current_period_end`.** It treats a
   row as blocking while `status` reads active, even if the period has passed,
   while `_user_has_active_subscription()` honours the date. A stale row means
   locked out of the dashboard *and* blocked from subscribing on the web. Less
   likely now notifications set `expired` properly, but a missed notification
   still traps someone.
4. **Two hardcoded `$5` fallbacks remain in the Flutter app**
   (`subscribe_page.dart`, `stores_tab.dart`). Both are `price_display`
   fallbacks. `account_page.dart` is done.
5. **Product display names still read e.g. "EverydayAdvertie Screen
   Subcription"** in App Store Connect. Customers see these on Apple's purchase
   sheet.
6. **No demo account for App Review.** The app is login-gated, so review fails
   without one in App Review Information.
7. **Google Play** is deliberately parked. `screens_monthly` has no tier
   allowance, so those subscribers are uncapped on screens. Play's real-time
   developer notifications are not implemented - Play state has the same
   staleness problem Apple had before this round.

## Tests

`test_*.py` is in `.gitignore`, so the suites written this round live **only on
the Windows clone** and are not in git (this includes the pre-existing
`test_app.py` that `deploy_automated.ps1` runs). **178 checks** across nine
files:

| File | Checks | Covers |
| --- | --- | --- |
| `test_apple_notifications.py` | 39 | JWS signature and certificate chain pinning |
| `test_apple_notification_apply.py` | 26 | notification to database outcomes |
| `test_subscribe_page.py` | 23 | subscribe page in every billing state |
| `test_account_screens.py` | 17 | account page store vs Stripe rendering |
| `test_admin_price_sync.py` | 23 | Stripe price reconciliation (fake Stripe) |
| `test_account_overview_api.py` | 18 | mobile overview payload |
| `test_price_source.py` | 11 | pricing derives only from admin |
| `test_screens_endpoint.py` | 10 | `/screens/<store_id>` empty-store fix |
| `test_eligibility_action.py` | 11 | subscribe eligibility codes |

Ask before relying on them from another machine - they need copying across
manually, or `.gitignore` line 75 (`test_*.py`) relaxing.
