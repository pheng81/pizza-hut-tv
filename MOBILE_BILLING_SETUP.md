# Mobile billing setup

The web app continues to use Stripe. Apps distributed through the Apple App
Store or Google Play use their native subscription systems and send the store
receipt to the server for verification.

## Product IDs

Create one auto-renewing monthly subscription in both stores with the product
ID `screens_monthly`. The Flutter client uses this ID by default. A different
ID can be compiled with `--dart-define=IAP_PRODUCT_ID=...`, but the server
environment variables must use the same value.

## Apple App Store

1. In App Store Connect, open the app whose bundle ID is
   `com.everydayadvertise.everydayMobile`.
2. Create a subscription group and a monthly auto-renewable subscription named
   `screens_monthly`.
3. Add the 14-day introductory free trial to the subscription if required.
4. Generate or copy the App-Specific Shared Secret from App Store Connect.
5. Set `APPLE_IAP_SHARED_SECRET`, `APPLE_IAP_PRODUCT_ID`, and
   `APPLE_IAP_BUNDLE_ID` in the production server environment.
6. Test with a Sandbox Apple Account. A real App Store build is required for
   production purchase testing; the simulator cannot complete a real charge.

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
