# Mobile billing setup

The web app continues to use Stripe. Apps distributed through the Apple App
Store or Google Play use their native subscription systems and send the store
receipt to the server for verification.

## Product IDs

The stores price a product, not a quantity, so per-screen billing is expressed
as a tier ladder. All tiers live in one subscription group, and adding screens
past a tier is an upgrade the store prorates, not a second purchase.

| Product ID | Screens covered | Price |
| --- | --- | --- |
| `screens_1` | 1 | $1.99 |
| `screens_3` | up to 3 | $4.99 |
| `screens_5` | up to 5 | $7.99 |
| `screens_10` | up to 10 | $14.99 |

The server picks the tier from the user's screen count and returns it as
`apple_product_id` / `google_product_id` from `/api/subscription/summary`, so
the app never hardcodes a product. Change the ladder with `MOBILE_IAP_TIERS`
as JSON, no app release required:

```
MOBILE_IAP_TIERS=[{"product_id":"screens_1","screens":1},{"product_id":"screens_3","screens":3}]
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

### Apple status (verified against the App Store Connect API)

- App record: **Everyday Advertise**, id `6800590059`, SKU
  `everydayadvertise-mobile`.
- Subscription group: **EverydayAdvertise Screens**, id `22306458`.
- `screens_1` — created, price set, `en-US` localization set, but still
  `MISSING_METADATA`: **no review screenshot** and **no free trial** yet.
- `screens_3`, `screens_5`, `screens_10` — not created yet.
- Build `1.1.0 (52)` uploaded to App Store Connect.

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

## Server dependency

Install the updated Python dependencies before restarting the service:

```bash
pip install -r requirements.txt
```

The verification endpoint is `/api/billing/mobile/verify`. It never trusts a
client-provided “paid” flag; it verifies the receipt with Apple or the purchase
token with Google before activating the account subscription.
