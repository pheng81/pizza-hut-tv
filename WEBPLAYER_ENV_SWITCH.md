# Web Player Local vs Production Switching

The Android TV web player can now automatically choose between a local development server and the production server.

## Auto Probe
On launch (debug build or when `debug=true` extra is passed) it probes in order:
1. Local: `http://10.0.2.2:5000/health`
2. Production (from `ApiClient.baseUrl` BuildConfig)

The first host returning HTTP 2xx/3xx is used.
If neither responds within ~1.5s each, it falls back to the first in the order.

Overlay background tint:
# Web Player Environment Switching & Persistence

The Android TV WebView player can operate against Local, Production, or Auto mode with persistence across launches plus an offline HTML asset fallback.

## Environment Modes
Stored in shared preferences (`EnvPreferences`). Cycle via long‑press DPAD UP.

Modes:
1. AUTO (default): Probe or reuse last environment.
2. LOCAL: Always use `http://10.0.2.2:5000`.
3. PROD: Always use production base from `ApiClient` / `BuildConfig`.

Current mode + environment indicated in the overlay:
- Green tint = LOCAL in use
- Blue tint = PROD in use
Overlay text shows `LOCAL (forced)`, `PROD (forced)`, or `AUTO(...)` states.

## Auto Behavior Details
In AUTO mode (debug build or `debug=true` intent extra):
1. If a last successful environment exists and still appropriate (sticky), it can skip probe.
2. Otherwise it probes in preferred order (Local first in debug, else Prod first):
	- Local: `http://10.0.2.2:5000/health`
	- Production base URL `/health`
3. First 2xx/3xx response wins; fallback if both fail.

Persistence:
- Last successful environment stored (`local` or `prod`).
- Mode (`AUTO|LOCAL|PROD`) stored until user cycles again.

## Runtime Controls (Long‑press until repeat)
- DPAD LEFT: Toggle current environment (LOCAL <-> PROD) within the active mode (updates last environment; if mode is AUTO it just flips preference now).
- DPAD CENTER: Reload current page.
- DPAD RIGHT: Load example.com test page (diagnostics).
- DPAD UP: Cycle Mode (AUTO → LOCAL → PROD → AUTO) and immediately apply.

## Offline Asset Fallback
If network loads 404 or fails through fallback chain, app may attempt to load bundled asset: `assets/webplayer_embed.html`.
This shows a clearly marked offline screen and still emits heartbeats to native layer.

## Local Mode Requirements
Run backend locally with endpoints:
- `/health` returning HTTP 200.
- `/webplayer_embed.html` serving the player HTML.
Expose any media slices / static content as expected by the HTML logic.

## Security
`WebPlayerActivity` is not exported; launch through the in-app launcher. External adb starts will fail unless manifest changed in a debug-only variant.

## Troubleshooting
- Expected LOCAL but got PROD: Ensure `/health` answers < 1500ms; verify host firewall allows emulator access.
- 404 on production: The HTML file is missing on deployed host; inspect server logs.
- Long‑press keys not triggering: Hold the DPAD key until you see overlay action (repeat count threshold > 20).
- Asset fallback appears unexpectedly: Both remote hosts failed or returned 404 repeatedly.

## Future Enhancements (Possible)
- UI settings page for explicit environment selection.
- Persist per-store environment overrides.
- Additional diagnostic panel (latency, probe timings).

---
Revision: Enhanced with persistence, mode cycling, offline asset (this document updated accordingly).
