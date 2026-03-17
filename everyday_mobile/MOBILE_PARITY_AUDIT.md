# Mobile Parity Audit (Website ↔ Mobile ↔ Pi/TV)

## Current Snapshot
- Mobile currently covers core auth, basic stores/screens listing, upload+assign, Android TV commands, and basic profile.
- Major website parity gaps remain in store/screen CRUD, advanced playlist control, cross-store operations, Pi manager, diagnostics, and billing/account tooling.

## Coverage Matrix

### Fully Covered
- Login/session + logout
- Basic profile read/update name/password
- Regenerate link code
- Store list + screen list
- Upload media + assign to selected screen
- Android TV command tab (device list + commands)

### Partially Covered
- Playlist/media management
  - Present: screen popup, media preview, timeline/edit controls, schedule windows CRUD in mobile popup
  - Missing: full playlist list operations parity (delete/reorder/full power-user controls), YouTube item flow parity
- Diagnostics
  - Present: minimal device status in commands tab
  - Missing: website-level event/debug views and full health monitoring UI

### Not Covered Yet
- Store CRUD and screen CRUD/rename
- Cross-store operations (`apply_to_all`, replicate/replace flows)
- Pi manager workflows (configure/assign/restart/close screen and monitoring)
- Library/folder browser + import-from-URL operations
- Orientation/rotation/protection controls parity
- Subscription/billing + phone verification + avatar/profile advanced account panel

## Backend Endpoints Already Relevant for Mobile Expansion
- Stores/screens topology:
  - `POST /add_store`, `POST /delete_store`
  - `POST /add_screen`, `POST /delete_screen`
  - `POST /update_screen_name`
- Playlist and schedule:
  - `GET /playlist/<store_id>/<screen_id>`
  - `PATCH /playlist/item/<store_id>/<screen_id>/<item_id>`
  - `DELETE /playlist/item/<store_id>/<screen_id>/<item_id>`
  - `POST/PATCH/DELETE /playlist/item/<...>/schedule...`
- Bulk operations:
  - `POST /apply_to_all`, `POST /replicate_screen`
- Status/diagnostics:
  - `GET /api/screen_status/<store_id>`
  - `GET /api/screen_events/<store_id>/<screen_id>`
  - `GET /api/debug_item_status/<store_id>/<screen_id>`
- Pi integration:
  - `POST /api/configure_remote_pi`, `GET /api/connected-pis`
  - `POST /api/pi-close-screen`, `POST /api/pi-restart`
- Orientation/rotation:
  - `POST /update_rotation`, `POST /update_orientation`, `POST /set_orientation_mode`

## Critical Integration Paths (Website + Mobile + Pi/TV)
1. **Content lifecycle**: upload/import → assign playlist item → schedule windows/days → TV/Pi refresh.
2. **Topology lifecycle**: add/delete stores/screens and map devices to the right targets.
3. **Operations lifecycle**: monitor online/offline + event errors and send corrective commands quickly.
4. **Scale lifecycle**: apply/replicate content across many stores safely.

## Phased Delivery Plan

### P0 (Must-have parity)
- Store/screen CRUD + rename in mobile
- Screen status monitoring in stores tab (online/offline + last seen)
- Playlist item delete + robust item editing parity

### P1 (High-value operations)
- Full playlist management tab (multi-item management parity)
- YouTube item support parity
- Diagnostics tab (events + debug status)

### P2 (Advanced parity)
- Cross-store apply/replace flows
- Pi manager tab (configure/restart/close/status)
- Rotation/orientation/protection controls

### P3 (Account/commercial parity)
- Avatar upload
- Phone verification
- Subscription/billing panel hooks

## Immediate Next 5 Implementation Tasks
1. Add store/screen CRUD + rename APIs and UI in Stores tab.
2. Add screen status polling in Stores tab (`/api/screen_status/<store_id>`).
3. Add playlist item delete action in popup/list UI.
4. Add dedicated diagnostics view for screen events/debug item status.
5. Add cross-store apply/replace starter flow.

---

This file is the implementation contract to ensure mobile catches up to website while preserving Pi/TV integration behavior.
