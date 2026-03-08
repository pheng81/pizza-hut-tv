# everyday_mobile

Flutter mobile app (Android + iOS) for Everyday Advertise.

## Included MVP features

- Login with existing backend session (`/login`)
- Stores and screens browser (`/stores`, `/screens/<store_id>`)
- Media upload + assign to selected screen (`/upload_media`, `/assign_to_screen`)
- Android TV command center (`/api/android_tv_status`, `/api/android_tv_command`)
- Profile actions (`/api/me`, `/api/profile/name`, `/api/profile/password`, `/profile/regenerate_code`)

## Run

```bash
cd everyday_mobile
flutter pub get
flutter run
```

## Notes

- Default API base URL is `https://api.everydayadvertise.com`.
- You can change base URL on the login screen.
- The app uses cookie-based session auth, same as your web dashboard.
