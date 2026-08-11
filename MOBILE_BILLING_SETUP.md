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

## Server dependency

Install the updated Python dependencies before restarting the service:

```bash
pip install -r requirements.txt
```

The verification endpoint is `/api/billing/mobile/verify`. It never trusts a
client-provided “paid” flag; it verifies the receipt with Apple or the purchase
token with Google before activating the account subscription.
