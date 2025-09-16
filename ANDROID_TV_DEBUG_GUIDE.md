# Android TV integration guide

This guide shows how to play sliced videos reliably with ExoPlayer and how to render images without unwanted zooming.

## Playlist contract (what the backend provides)

Each playlist item may include the following fields that Android should honor:

- `url`: The default media URL. For Android UA the backend may already set this to the slice URL.
- `slice_url`: Explicit URL to the slice endpoint (e.g. /slice-video/...). Always present for slice-aware items.
- `preferred_url`: UA-agnostic pointer to the slice URL when slicing is applicable. Prefer this on Android.
- `image_fit`: Semantic hint for images. Typically "contain" to preserve aspect and letterbox if needed.
- `image_scale`: Android hint matching ImageView.ScaleType semantics. Typically "fit_center".

Recommendation on Android: use `preferred_url` if present, else fallback to `url`.

## ExoPlayer setup for slice playback

Configure ExoPlayer to follow redirects and handle HTTP Range requests (server supports this fully):

```kotlin
// Build a user agent (optional but helpful for diagnostics)
val userAgent = "AndroidTV-ExoPlayer"

// HTTP data source that follows redirects
val httpFactory = DefaultHttpDataSource.Factory()
	.setUserAgent(userAgent)
	.setAllowCrossProtocolRedirects(true)

// ExoPlayer instance
val player = ExoPlayer.Builder(context)
	.setTrackSelector(DefaultTrackSelector(context))
	.build()

// Preferred media URL (slice when available)
val mediaUrl = item.preferred_url ?: item.url
val mediaItem = MediaItem.fromUri(mediaUrl)

// Prepare player
val mediaSource = ProgressiveMediaSource.Factory(httpFactory)
	.createMediaSource(mediaItem)

player.setMediaSource(mediaSource)
player.prepare()
player.playWhenReady = true

// Ensure the PlayerView resizes to fit without cropping
playerView.resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
playerView.useController = false // optional for kiosk mode
playerView.player = player
```

Notes:

- The backend sets correct headers: `Accept-Ranges: bytes`, `Content-Range`, and 206 responses for partial requests.
- The slice endpoint may issue a 302 to the cached file path; `setAllowCrossProtocolRedirects(true)` ensures ExoPlayer follows it.
- MIME types are standard (`video/mp4`).

## Image rendering without zoom

To avoid zoom/crop and keep full image visible with letterboxing if needed:

```kotlin
imageView.scaleType = ImageView.ScaleType.FIT_CENTER // or CENTER_INSIDE

// If using Glide:
Glide.with(imageView)
	.load(imageUrl)
	.fitCenter()
	.into(imageView)
```

If you parse `image_scale` from the playlist, map it:

- `fit_center` -> ImageView.ScaleType.FIT_CENTER
- `center_inside` -> ImageView.ScaleType.CENTER_INSIDE

## Troubleshooting playback

- If playback stalls at 0s, check network logs to confirm the first request is 206 with `Content-Range: bytes 0-.../size` and `Accept-Ranges: bytes`.
- If you see a 302 from `/slice-video`, ensure the DataSource follows redirects (see config above).
- Test directly in a browser: GET `http://<server>:5002/slice-video/<video>?slice_mode=split-h&slice_count=3&slice_order=1`.
- Server also supports HEAD and open-ended ranges like `Range: bytes=0-` which ExoPlayer commonly uses.

## Quick server restart on Windows

Use the helper script we added to safely stop whatever is using port 5002 and start the server:

- `scripts/restart_server.ps1` stops processes bound to port 5002 and runs `start_server.bat`.
- Logs go to `server.log` in the repo root.

If needed, adjust the script port parameter: `./scripts/restart_server.ps1 -Port 5002`.

