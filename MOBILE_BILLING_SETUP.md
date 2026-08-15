# Mobile billing setup

The web app continues to use Stripe. Apps distributed through the Apple App
Store or Google Play use their native subscription systems and send the store
receipt to the server for verification.

## Where the code lives, and what is current

Four places hold this code and they drift apart, which is the single biggest
source of confusion. Check this before debugging anything.

| Place | How to check it | Notes |
| --- | --- | --- |
| GitHub `main` | `git ls-remote --heads origin main` | Source of truth. |
| Mac clone `~/development/flutter` | `git status` / `git log -1` | `origin` is the project; `flutter-sdk` is the Flutter SDK repo. |
| Windows clone | `git log -1` on that machine | Deploys from here. |
| Production server | see below | **Deployed separately - lags behind GitHub.** |
| iPhone | TestFlight build number | App code, not server code. |

**A purchase failure is usually the server lagging, not a new bug.** The app
sends whatever product id the server told it to use, and the server rejects any
product id it does not know. After changing tiers or product ids, the server
must be redeployed or every purchase fails as "Unknown Apple subscription
product".

To check what the server is running without SSH, probe a route that only exists
in newer code - `404` means old, `302`/`401` means the route is there:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  https://everydayadvertise.com/api/auth/apple/link
```

Deploy is `deploy_automated.ps1` from the Windows clone (`git pull` first). It
uploads `app.py`, `config.py` and `.env.production`, restarts
`everydayadvertise_tv`, health-checks and auto-rolls-back. It does **not**
touch systemd drop-ins, so secrets stored there survive. `.env.production` is
gitignored and lives only on the Windows machine - check it before deploying,
because the deploy overwrites the server's copy with it.

## Product IDs

The stores price a product, not a quantity, so per-screen billing is expressed
as a tier ladder. All tiers live in one subscription group, and adding screens
past a tier is an upgrade the store prorates, not a second purchase.

**Product IDs are case sensitive and cannot be renamed after creation.** These
are the exact ids registered in App Store Connect. Note `Screen_1` is singular
while the rest are plural - that is what exists, not a typo to "fix":

| Product ID | Screens covered | USD price | Group level |
| --- | --- | --- | --- |
| `Screens_10` | up to 10 | $14.99 | 1 (highest) |
| `Screens_5` | up to 5 | $7.99 | 2 |
| `Screens_3` | up to 3 | $4.99 | 3 |
| `Screen_1` | 1 | $1.99 | 4 (lowest) |

Apple treats **level 1 as the highest tier**, so more screens must rank nearer
1. With the order reversed, moving up a tier registers as a downgrade and is
deferred to the next renewal instead of applying immediately.

The server picks the tier from the user's screen count and returns it as
`apple_product_id` / `google_product_id` from `/api/subscription/summary`, so
the app never hardcodes a product. Change the ladder with `MOBILE_IAP_TIERS`
as JSON, no app release required:

```
MOBILE_IAP_TIERS=[{"product_id":"Screen_1","screens":1},{"product_id":"Screens_3","screens":3}]
```

`_mobile_product_ids()` accepts any configured tier plus the legacy
`screens_monthly`, so old purchases keep verifying.

Ten screens is the ceiling in the app. Beyond that `add_screen` refuses with a
plan-limit response rather than selling a bigger tier.

**Prices and free trials are set in App Store Connect / Play Console, not in the
admin.** The admin's `price_per_screen` and `trial_days` still drive Stripe on
the web, but a store subscription charges whatever the store says. The paywall
reads the real localized price from StoreKit for that reason.

## Apple App Store

1. In App Store Connect, open the app whose bundle ID is
   `com.everydayadvertise.everydayMobile`.
2. Create one subscription group and add all four tiers to it. Separate groups
   would let a user hold several at once and be charged for each.
3. Each tier needs a duration (1 month), a price, an **App Store Localization**
   and a **review screenshot**. Without all four the product sits in
   `MISSING_METADATA` and StoreKit will not return it — the app then shows
   "Failed to get response from platform".
4. Add a **2 Weeks Free Trial** introductory offer to each tier. Apple has no
   "14 days" option; 2 weeks is the same length. A customer gets the trial once
   per group, so upgrading tiers never grants another one.
5. Generate or copy the App-Specific Shared Secret from App Store Connect.
6. Set `APPLE_IAP_SHARED_SECRET` and `APPLE_IAP_BUNDLE_ID` in the production
   server environment. `APPLE_IAP_PRODUCT_ID` is only the legacy fallback now;
   the tier ladder supplies the real IDs.
7. Test with a Sandbox Apple Account, or through TestFlight which uses the
   sandbox automatically. The Paid Applications agreement must be **Active**
   or no products load at all, whatever else is configured.

### Apple status as at 2026-08-15 (verified against the App Store Connect API)

- App record: **Everyday Advertise**, id `6800590059`, SKU
  `everydayadvertise-mobile`, bundle `com.everydayadvertise.everydayMobile`.
- Subscription group: **EverydayAdvertise Screens**, id `22306458`, localized
  `en-US` as "Everyday Advertise Screens".
- All four products are **READY_TO_SUBMIT**: price, localization, review
  screenshot and a 2-week free trial each.
- Paid Applications agreement: **Active**.
- `APPLE_IAP_SHARED_SECRET` is set on the server in the systemd drop-in
  `/etc/systemd/system/everydayadvertise_tv.service.d/apple-iap.conf`. It is
  **not** in `.env.production`, so a deploy does not overwrite it.
- TestFlight: build `1.1.0 (57)` is current and in beta testing. Internal group
  "Testing Group A".
- Product display names still read e.g. "EverydayAdvertie Screen Subcription"
  (typos, inconsistent). Customers see these on Apple's purchase sheet; they
  should be renamed to plain "1 Screen" / "3 Screens" / "5 Screens" /
  "10 Screens".

### Things that cost hours to find - do not rediscover them

- **StoreKit 1 is pinned deliberately.** `in_app_purchase_storekit` 0.4.x
  defaults to StoreKit 2, which sets `serverVerificationData` to a JWS
  transaction. `_verify_apple_mobile_purchase()` posts that to Apple's legacy
  `verifyReceipt`, which only reads a base64 app receipt, so every purchase
  failed. `pubspec.yaml` pins `in_app_purchase 3.2.2` +
  `in_app_purchase_storekit 0.3.22+1`. Do not bump these until the server moves
  to the App Store Server API. Switching at runtime does not work:
  `registerPlatform()` builds either the SK1 or SK2 observer at startup and
  leaves the other uninitialised.
- **The subscription group needs its own localization**, separate from each
  product's. Without it iOS cannot render the change-plan sheet and upgrades
  fail with `ASDServerErrorDomain - An unknown error occurred`, while first
  purchases still succeed.
- **Transactions must be finished even when verification fails.** Unfinished
  transactions are replayed forever and block new purchases. `purchase()` and
  `drainPendingTransactions()` finish them either way; the receipt keeps them
  recoverable through restore.
- **A transaction still mid-flight cannot be finished.** Buying the same
  product again returns `storekit_duplicate_product_object`. The app now
  detects this before purchasing and asks the user to wait.
- **`MISSING_METADATA` products are listed but often not sellable.** Prices can
  appear in the paywall while the purchase fails at Apple's servers.
- **The shared secret is on the In-App Purchases page**, even though all
  products are Subscriptions. It is not the Sign in with Apple `.p8`, and not
  an In-App Purchase Key under Users and Access - those are for the App Store
  Server API.

The Sign in with Apple `.p8` key is not the receipt shared secret used by this
verification endpoint. Keep those credentials separate.

## Google Play

1. In Play Console, create a monthly subscription product with ID
   `screens_monthly` in the Android app package
   `com.everydayadvertise.everyday_mobile`.
2. Create a Google Cloud service account for server-to-server verification.
3. Grant that service account access to the app in Play Console with the
   subscription/order management permission needed by the Google Play
   Developer API.
4. Store the service-account JSON outside Git on the server, for example
   `/etc/everydayadvertise/google-play-service-account.json`.
5. Set `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`, `GOOGLE_PLAY_PACKAGE_NAME`, and
   `GOOGLE_PLAY_PRODUCT_ID` in the production server environment.
6. Test using an internal testing track and a tester account; unpublished
   subscriptions are not returned to ordinary production users.

### Current server configuration (as of the Play Console setup pass)

- Service account: `everydayadvertise-billing@everydayadvertise.iam.gserviceaccount.com`
  (project `everydayadvertise`), granted access under Play Console →
  **Users and permissions**. (Note: this replaced the old standalone "API access"
  page — inviting a service account there works the same as inviting a human user,
  just without an email-accept step.) It currently has **Admin** permission on the
  `everydaymobile` app, granted for testing convenience. Before going to real
  production traffic, tighten this to just **View app information** + **View
  financial data** (the only two things `_verify_google_mobile_purchase()` in
  `app.py` actually needs) so a leaked key can't be used to publish app updates,
  edit the store listing, or issue refunds.
- Key file lives on the server at `/etc/everydayadvertise/google-play-billing.json`,
  owned by `ubuntu:ubuntu`, mode `600`. `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` is set to
  that file path (not the raw JSON) in the `google-play-billing.conf` systemd
  drop-in — `_google_play_credentials()` in `app.py` accepts either a path or raw
  JSON, and a file path avoids any risk of the private key getting mangled by
  systemd/shell quoting.
  `GOOGLE_PLAY_PACKAGE_NAME` / `GOOGLE_PLAY_PRODUCT_ID` are left unset since the
  code's defaults (`com.everydayadvertise.everyday_mobile` / `screens_monthly`)
  already match.
- New Play Console permission grants can take several minutes (observed ~2-3 min
  here) to actually propagate to the Android Publisher API — a freshly granted
  service account will 401 with `permissionDenied` until it does. If verification
  calls are failing right after granting access, that's the first thing to rule
  out before assuming the setup is wrong.
- **Still outstanding:** the `screens_monthly` subscription product itself has not
  been confirmed as created in Play Console → Monetize → Subscriptions yet. Until
  it exists, purchase verification has nothing to verify against even though the
  service account plumbing is live.

### Play Store submission status (everyday_mobile)

- Release signing was already configured before this pass:
  `everyday_mobile/android/key.properties` / `everydayadvertise.keystore`
  (alias `everydayadvertise`).
- A signed release AAB (version `1.1.0+50`) was built with
  `flutter build appbundle --release` and uploaded to Play Console's
  **Internal testing** track.
- The Play App Signing SHA-1 (see the Google Sign-In section in
  `DEVELOPMENT_GUIDE.md`) was registered on the Android OAuth client so
  Google Sign-In works on Play-distributed builds, not just local debug builds.
- A generated 512×512 app icon and 1024×500 feature graphic (matching the
  existing `ea` gradient mark from `static/ea-logo.svg`) are ready but not yet
  confirmed uploaded to the store listing — needed before the app can leave
  internal testing.
- Store listing basics (description, content rating questionnaire, Data safety
  form, target audience) have not been completed yet.

## Outstanding as at 2026-08-15

1. **Deploy the server.** It still has the old lowercase product ids, so
   `Screens_3` / `Screens_5` / `Screens_10` are rejected as unknown products. A
   `Screens_3` subscription was bought successfully in TestFlight and cannot be
   activated until this lands. After deploying, "Restore purchases" in the app
   verifies it - no second purchase needed.
2. Rename the product display names (typos, see above).
3. Create a **demo account** for App Review and put it in App Review
   Information. The app is login-gated, so review fails without it.
4. Android: the Play subscription products for the same tiers do not exist yet.
   Play still expects a single `screens_monthly`.
5. Deployment target is iOS 14.0; Apple requires 15.0 from Spring 2027.
6. The launch image is still Flutter's placeholder.

## How to test a purchase end to end

1. Install the current build from TestFlight. TestFlight uses the sandbox
   automatically with the tester's real Apple ID - no Sandbox Apple Account
   needed. A development build side-loaded from Xcode does need one, under
   Settings > Developer > Sandbox Apple Account, or it fails with "not
   authorized to make purchases in Sandbox".
2. Sign in, open Stores & Screens, add a screen to reach the paywall.
3. The paywall must show real store prices (localized, e.g. AUD 2.99 for a
   USD 1.99 tier). Server text prices mean the product did not load.
4. Buy. A first purchase and a plan change are different code paths - test
   both, since upgrades fail for reasons first purchases do not.
5. If a purchase succeeds at Apple but the app shows an error, check the server
   first: the failure is nearly always verification, not the store.

## Server dependency

Install the updated Python dependencies before restarting the service:

```bash
pip install -r requirements.txt
```

The verification endpoint is `/api/billing/mobile/verify`. It never trusts a
client-provided “paid” flag; it verifies the receipt with Apple or the purchase
token with Google before activating the account subscription.
