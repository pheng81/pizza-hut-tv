# Handoff - state as at 2026-08-23

> Blockchain recovery is tracked separately in
> [`PoASy3-recovery-work/BLOCKCHAIN_RECOVERY_TASK.md`](PoASy3-recovery-work/BLOCKCHAIN_RECOVERY_TASK.md).
> Read that file before changing or redeploying validator, Tower, finality,
> snapshot, sync, or RPC-node code. It records the August 2026 chain freeze,
> cumulative hardening, node inventory, completed rollout/deployed hashes, and
> the completed EVM canonical-history correction, build provenance, rolling
> deployment and post-rollout monitoring evidence.

Written from the Windows clone. Everything below is on GitHub `main`
(`github.com/WcahtDenvion/everydayadvertise`) **and deployed to production**,
unless a line says otherwise.

Billing detail lives in `MOBILE_BILLING_SETUP.md`; this file is the short
version plus what is still outstanding.

## Where things run

| Place | State |
| --- | --- |
| GitHub `main` | source of truth |
| Windows clone | deploys from here |
| Production `54.252.90.27` | in sync with `main` |
| iPhone (TestFlight) | build **1.1.0 (64)** |
| Google Play | version code **53** (name 1.11), released Jun 25 |
| Repo (`pubspec.yaml`) | **1.2.0+65** - clears both |

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

## Remote control: why "Scan Wi-Fi" found nothing

Two independent faults, both fixed, neither yet on a device.

**1. The scan could never work on iPhone.** `multicast_dns` opens a raw socket
and calls `joinMulticast(224.0.0.251)`. iOS blocks raw multicast without the
`com.apple.developer.networking.multicast` entitlement, which Apple grants only
on request. `NSBonjourServices` does **not** unlock this - it only applies to
Apple's native Bonjour APIs - so `Info.plist` looked perfectly correct while the
scan returned nothing at all, not even the Chromecast and AirPlay devices that
are usually everywhere.

Discovery now uses **`bonsoir`**, which wraps `NSNetServiceBrowser` on iOS and
`NsdManager` on Android. It honours the declared `NSBonjourServices` and needs
no entitlement. `multicast_dns` has been removed. Every service type must still
be listed in `Info.plist`: iOS refuses to browse a type that is not.

SSDP still uses a raw socket and so remains **dead on iOS**, working on Android
only. Requesting the multicast entitlement would revive it - worth starting,
since approval is slow, but nothing depends on it.

**2. Our own TVs advertised nothing.** The Android TV app had no `NsdManager`
registration, so an EverydayAdvertise screen was invisible even to a working
scan. It now advertises `_everydayadvertise._tcp` (`TvNsdAdvertiser.kt`, started
from `TvDisplayActivity`) carrying `device_id`, `store_id`, `screen_id` and
`pair_code` as TXT records, and the phone reads those to match a discovered TV
to a registered screen. Matching previously compared the server's stored IP with
the discovered one, which almost never agreed: the server records the device's
**public** address (live rows are public IPv6, days stale) while discovery
returns its LAN address.

### Controlling third-party TVs is not implemented

Worth being blunt, because the UI implies otherwise. Only "Android / Google TV"
is `ready: true`, and that is our own bridge - phone to server to the TV app
over socket.io. Samsung, LG, Sony, TCL, Hisense, Vizio, Panasonic and Philips
are all `ready: false, 'Setup required'` placeholders with no protocol behind
them. Discovery finding a Samsung will not let you control it.

Rough order of effort if this gets built:

| Brand | Protocol | Pairing |
| --- | --- | --- |
| Roku / TCL | ECP, plain HTTP port 8060 | none - easiest by far |
| Sony Bravia | REST | pre-shared key typed into the TV |
| Samsung | WebSocket 8001/8002 | on-screen accept, store token |
| LG webOS | SSAP WebSocket 3000/3001 | on-screen accept, client key |
| Vizio | HTTPS 7345 | PIN |
| Android TV (other) | androidtvremote2 | TLS certificate pairing |

Note that **powering a TV on over Wi-Fi generally cannot work** - most sets drop
their network interface when off. That needs Wake-on-LAN or HDMI-CEC, and is why
`powerReady` is false on the bridge profile.

### Verified so far

Android APK builds with `bonsoir`; `flutter analyze` clean; the TV app's Kotlin
compiles. **Not** verified: the iOS build (cannot be done from the Windows
clone - `bonsoir_darwin` needs iOS 13.0 and the app targets 14.0, so it should
be fine) and real discovery against actual hardware. Both need a device.

## Stripe webhooks, and the env file that was never read

Stripe emailed about deliveries failing to `https://yoyiyu.com` - a five-year-old
endpoint from an unrelated project, the only one the account had. **There was no
endpoint for everydayadvertise.com at all**, so Stripe renewals, cancellations
and payment failures had never reached the server. New checkouts still worked
because `/billing/success` syncs on return; everything after that went stale, the
same fault Apple had.

That endpoint has been repointed at `https://everydayadvertise.com/stripe/webhook`
with the four events `stripe_webhook()` handles. Note it keeps its 2021 creation
date and delivery history, so its failure graph shows old `yoyiyu.com` failures.

Fixing it exposed something worse. **The app reads `.env`, not `.env.production`** -
`load_dotenv()` takes no argument, so it loads `.env` from the working directory.
`deploy_automated.ps1` only ever uploaded `.env.production`, which nothing reads.
Every config change deployed that way was silently discarded while the app kept
using a `.env` last touched in May, and nothing errored. That is why
`STRIPE_WEBHOOK_SECRET` was still `whsec_PLACEHOLDER_UPDATE_AFTER_WEBHOOK_SETUP`
and every signed delivery came back 400.

The deploy now writes `.env`. Before changing it, the two files were compared:
the server's `.env` held four keys the local file did not - `SECRET_KEY`,
`GOOGLE_MAPS_API_KEY`, `GOOGLE_SERVER_API_KEY`, `VONAGE_FROM_NUMBER` - so a
straight overwrite would have destroyed them. Losing `SECRET_KEY` alone
invalidates every signed session. Those four were copied into the local
`.env.production` first, and the deploy now takes a timestamped `.env.backup_*`
before each overwrite.

**`.env.production` on the Windows clone is now the source of truth for server
config.** Anything added on the server must be copied back into it, or the next
deploy erases it.

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

0. **Two artifacts now need building, not one.** Nothing from the remote-control
   work has reached a device, and the two halves only work together - the TV has
   to advertise before the phone can find it:
   - **Android TV app** (`android_tv_app`) - installs on the TVs, adds the
     `_everydayadvertise._tcp` announcement.
   - **iOS app** (`everyday_mobile`) - adds the Bonjour-based scan plus the
     billing and account-page fixes below.

1. **Ship the builds.** `pubspec.yaml` is now **1.2.0+65**, which is high
   enough for both stores. One number feeds both: `1.2.0` becomes the version
   name (Android `versionName`, iOS `CFBundleShortVersionString`) and `65` the
   build number (`versionCode` / `CFBundleVersion`). It has to clear the
   **highest already uploaded anywhere** - TestFlight is on 64, so 54 would be
   rejected by Apple even though Google Play is only on 53.

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
