# Milestone 5-UI: Operator Control Dashboard — Design

**Date:** 2026-04-13
**Status:** Approved (brainstorm complete, pending written spec review)
**Targets:** `apps/dashboard/` (rewrite to two-view app), `apps/api/` (add metadata + rename endpoints + WS rename protocol), `packages/contracts/` (new rename WS messages)

## Context

M1–M4 shipped: scanner, pusher, Command contract, wrangler-ui (local control panel), api hub with WS dial-home, bearer auth. The api's REST surface works end-to-end (proven live: command round-trips from curl → api → wrangler → WLED).

The gap: there is **no browser UI for the api**. The existing `apps/dashboard/` is a static PyTexas build-log story page — no controls, no device list, no live state. To drive the matrix from a phone at the conference today, you curl.

M5-UI replaces the dashboard with a **two-view app**: `/` becomes the operator control surface (device grid, shared controls, global fanout, system status), `/about` preserves the existing PyTexas story page.

## Goals

1. `/` → Operator Control Dashboard: device grid with live state, shared controls panel (color/effect/text/preset/emoji), brightness + power, "Apply to ALL" toggle, system footer (wranglers + Discord placeholder).
2. `/about` → existing PyTexas build-log story, moved from current `/`.
3. api gains `GET /api/effects`, `GET /api/presets`, `GET /api/emoji` (metadata — contracts data served directly).
4. api gains `PUT /api/devices/{mac}/name` via new WS rename protocol messages.
5. Auth handled in the UI via localStorage token prompt (AuthGate component).
6. Same design token system as wrangler-ui (dark indigo + brass + orange).

## Non-goals

- Discord bot integration (M5-proper, next milestone). Discord footer renders "not configured" placeholder.
- WebSocket push from api to browser (polling is fine for 2–5 devices at 2–5s intervals).
- Mobile optimization beyond basic responsive.
- UI tests (same policy as prior milestones).
- GitHub Pages deploy rework (open question — addressed separately).

---

## Architecture

`apps/dashboard/` remains a single Vite/React app. Its build output ships into `apps/api/static/dashboard/` (api already mounts that dir). The app gains hash-based routing (`#/` vs `#/about`) — no React Router dep needed, just conditional render on `location.hash`.

The Control view's fetch layer sends `Authorization: Bearer <token>` on every request. The token comes from `localStorage` (set via a one-time prompt modal on first visit). When api has auth disabled (dev mode), the prompt never appears (api returns 200 without auth).

```
Browser (http://api:8500/)
  ├── #/        → ControlView
  │     ├── DeviceGrid         polls GET /api/devices (5s)
  │     ├── DeviceCard[n]      polls GET /api/devices/{mac}/state (2s, active only)
  │     ├── ControlPanel       POST /api/devices/{mac}/commands
  │     │    ├── ColorTab / EffectTab / TextTab / PresetTab / EmojiTab
  │     │    └── BrightnessSlider + Power buttons
  │     └── SystemFooter       polls GET /api/wranglers (10s)
  └── #/about   → StoryView (existing content)
```

---

## Backend additions on api

### Metadata endpoints (pure contracts data, no hub involvement)

Added to `apps/api/src/api/server/rest.py`:

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/effects` | `{"effects": ["solid","breathe","rainbow",...]}` |
| `GET` | `/api/presets` | `{"presets": ["pytexas","party","chill"]}` |
| `GET` | `/api/emoji` | `{"emoji": {"🔥":"fire","🌈":"rainbow",...}}` |

Implementation: identical to wrangler's `metadata.py` — reads from `EFFECT_FX_ID`, `PRESETS`, `EMOJI_COMMANDS` in `wrangled_contracts`.

### Rename via WS proxy

New protocol messages in `packages/contracts/hub.py`:

```python
# api → wrangler
class SetDeviceName(BaseModel):
    kind: Literal["set_device_name"] = "set_device_name"
    request_id: str
    mac: str
    name: str = Field(min_length=1, max_length=32)

# wrangler → api
class SetDeviceNameResult(BaseModel):
    kind: Literal["set_device_name_result"] = "set_device_name_result"
    request_id: str
    device: WledDevice | None = None
    error: str | None = None
```

Add `SetDeviceName` to `ApiMessage` union. Add `SetDeviceNameResult` to `WranglerMessage` union.

**Flow:**

1. Browser `PUT /api/devices/{mac}/name` with `{"name": "Stage-Left"}`.
2. api's `rest.py` calls `hub.send_rename(mac, name)`.
3. Hub looks up owning wrangler, sends `SetDeviceName(request_id, mac, name)`.
4. Wrangler `hub_client` receives it → calls `wled_client.set_name(client, device, name)` → re-probes device → sends `SetDeviceNameResult(request_id, device=refreshed)`.
5. Hub resolves the pending future, updates its registry with the refreshed device.
6. api returns the updated `WledDevice` to the browser.

**Hub addition:** `send_rename(mac, name, timeout=5.0) -> WledDevice` method. Same pattern as `send_command` / `get_state`.

**Wrangler hub_client addition:** handle `SetDeviceName` message → rename → respond. Same pattern as `RelayCommand` / `GetState`.

### Auth for the UI

No backend changes — the bearer token dependency already works. The UI handles auth client-side:

- On mount, `AuthGate` checks `localStorage.getItem('wrangled.token')`.
- If missing + api returns 401 on a probe request → show a modal: "Enter auth token" + text input.
- On submit, store in localStorage, retry. All subsequent fetches include `Authorization: Bearer <token>`.
- Small "logout" link in header clears localStorage and reloads.
- When api has no `WRANGLED_AUTH_TOKEN` set (dev mode), fetches succeed without a token — modal never shown.

---

## Dashboard UI

### File structure

```
apps/dashboard/
├── src/
│   ├── main.jsx
│   ├── App.jsx                    # REWRITE: hash router + nav
│   ├── index.css                  # REWRITE: import wrangler-ui design tokens
│   ├── api.js                     # CREATE: fetch wrappers with bearer auth
│   ├── views/
│   │   ├── ControlView.jsx        # CREATE: the operator dashboard
│   │   └── StoryView.jsx          # CREATE: extracted from current App.jsx
│   └── components/
│       ├── AuthGate.jsx            # CREATE
│       ├── DeviceGrid.jsx          # CREATE
│       ├── DeviceCard.jsx          # CREATE
│       ├── ControlPanel.jsx        # CREATE
│       ├── ColorTab.jsx            # PORT from wrangler-ui
│       ├── EffectTab.jsx           # PORT from wrangler-ui
│       ├── TextTab.jsx             # PORT from wrangler-ui
│       ├── PresetTab.jsx           # PORT from wrangler-ui
│       ├── EmojiTab.jsx            # PORT from wrangler-ui
│       ├── BrightnessSlider.jsx    # PORT from wrangler-ui
│       └── SystemFooter.jsx        # CREATE
├── vite.config.js                  # MODIFY: build outDir → ../api/static/dashboard
├── eslint.config.js
└── package.json
```

### Routing (`App.jsx`)

```jsx
function App() {
  const [view, setView] = useState(location.hash === '#/about' ? 'about' : 'control');

  useEffect(() => {
    const onHash = () => setView(location.hash === '#/about' ? 'about' : 'control');
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  return (
    <AuthGate>
      <Nav view={view} />
      {view === 'control' ? <ControlView /> : <StoryView />}
    </AuthGate>
  );
}
```

### Design tokens

Copy wrangler-ui's `index.css` `:root` block verbatim (the 40-variable system). Same dark theme, same typography, same accent palette. Both UIs feel like one brand.

### `api.js` — fetch layer

Same shape as wrangler-ui's `api.js` but:
- All requests include `Authorization: Bearer <token>` from localStorage.
- `sendCommand(mac, command)` is the core — when `applyToAll` is on, caller iterates and calls it N times.
- Exports: `listDevices`, `getState`, `sendCommand`, `rename`, `rescan`, `listEffects`, `listPresets`, `listEmoji`, `listWranglers`.

### `DeviceGrid.jsx`

Polls `GET /api/devices` every 5s. Renders a CSS grid of `DeviceCard` components. Clicking a card calls `onSelect(mac)`. A "Rescan" button fires `POST /api/scan` + refreshes.

### `DeviceCard.jsx`

Displays:
- Name (bold) + ✏️ rename inline (same pattern as wrangler-ui's `DeviceSelector`)
- Color swatch (64px, with glow when ON — same as wrangler-ui's `LiveState`)
- ON/OFF dot + brightness + effect name
- IP + matrix dimensions (small monospace)
- Selected state: orange left-border + accent-muted background

Polls `GET /api/devices/{mac}/state` every 2s **only when this card is selected**. Other cards show the device data from the list poll (which has name/ip/version/matrix but NOT live state fields — those come from the state endpoint).

### `ControlPanel.jsx`

- "Apply to ALL devices" toggle (checkbox or toggle switch) at top-right.
- Tab nav: Color / Effect / Text / Preset / Emoji.
- Active tab content below.
- Brightness slider + Power On/Off buttons below tabs (same as wrangler-ui's status-rail layout, but horizontal).

When a command is fired:
- If `applyToAll` is off → `POST /api/devices/{selectedMac}/commands`.
- If `applyToAll` is on → iterate all device MACs, fire N requests, aggregate results. Banner: "3/3 succeeded" or "2/3 succeeded (Stage-Right: timeout)".

### Control tabs (ported from wrangler-ui)

`ColorTab`, `EffectTab`, `TextTab`, `PresetTab`, `EmojiTab`, `BrightnessSlider` — **identical** to wrangler-ui. They call `onSend(commandJson)` — the parent resolves which MAC(s) to target.

### `SystemFooter.jsx`

Polls `GET /api/wranglers` every 10s. Renders:
```
Wranglers: pi-venue (1 device, 3s ago) · pi-home (1 device, 1s ago)
Discord: ⚫ not configured
```

Discord line is a static string for now. When M5-proper ships a `GET /api/discord/status` endpoint, this component calls it instead.

### `AuthGate.jsx`

Wraps the entire app. On mount:
1. Try `GET /api/devices` with the stored token (or no token).
2. If 200 → render children.
3. If 401 → show modal: "Auth token required" + text input + "Connect" button.
4. On submit → store token in localStorage, retry.
5. "Logout" link in nav → clear localStorage, reload.

### Polling intervals

| Endpoint | Interval | Scope |
|---|---|---|
| `GET /api/devices` | 5s | entire device grid |
| `GET /api/devices/{mac}/state` | 2s | selected device only |
| `GET /api/wranglers` | 10s | system footer |

All polls use `setInterval` + cleanup on unmount. Hidden tabs pause polling (page-visibility API).

### Error handling

Same pattern: red banner at top. "Matrix unreachable" on 502. "Wrangler disconnected" on 404 after a device disappears. Banner dismissed on next successful poll.

---

## Protocol additions in `packages/contracts/hub.py`

```python
# api → wrangler (add to ApiMessage union)
class SetDeviceName(BaseModel):
    kind: Literal["set_device_name"] = "set_device_name"
    request_id: str
    mac: str
    name: str = Field(min_length=1, max_length=32)

# wrangler → api (add to WranglerMessage union)
class SetDeviceNameResult(BaseModel):
    kind: Literal["set_device_name_result"] = "set_device_name_result"
    request_id: str
    device: WledDevice | None = None
    error: str | None = None
```

Both directions' discriminated unions get these new variants.

---

## Testing

### api tests (backend additions)

- **`test_rest_metadata.py`** — `GET /api/effects` returns curated list; `GET /api/presets` returns 3; `GET /api/emoji` returns mapping with fire/rainbow/etc.
- **`test_rest_rename.py`** — `PUT /api/devices/{mac}/name` with fake wrangler: rename succeeds → returns updated device; rename fails (WLED unreachable) → 502; unknown MAC → 404.
- **`test_hub_rename.py`** — Hub `send_rename` resolves when `SetDeviceNameResult` arrives; times out when no response.

### wrangler tests (hub_client rename handler)

- **`test_hub_client_rename.py`** — fake WS server sends `SetDeviceName` → hub_client calls `set_name` (mocked) + `probe_device` (mocked) → sends `SetDeviceNameResult` with refreshed device.

### contracts tests

- **`test_hub_contracts.py`** — roundtrip tests for `SetDeviceName` and `SetDeviceNameResult`.

### Dashboard UI tests

None (same policy).

---

## Build changes

### `apps/dashboard/vite.config.js`

```javascript
build: {
  outDir: '../api/static/dashboard',
  emptyOutDir: true,
}
```

The existing `build.sh` already has `cd apps/dashboard && npm install && npm run build`. The output just needs to land in the right place.

### `apps/dashboard/package.json`

The `"build"` script changes to `"vite build --outDir ../api/static/dashboard --emptyOutDir"`.

---

## Deliverable

```bash
./build.sh
cd apps/api && WRANGLED_AUTH_TOKEN=devtoken uv run api serve

# (in another terminal)
WRANGLED_API_URL=ws://localhost:8500/ws \
WRANGLED_AUTH_TOKEN=devtoken \
  cd apps/wrangler && uv run wrangler serve
```

Open `http://localhost:8500/` → auth modal → enter `devtoken` → operator dashboard loads. Device grid shows 1–2 WLEDs. Click one → live state panel with swatch. Click color → matrix changes. Toggle "Apply to ALL" → click preset → all matrices change. Click `#/about` → PyTexas story page. System footer shows connected wranglers.

## Open questions (deferred)

- **GitHub Pages deploy** — currently deploys `apps/dashboard/dist/` as the PyTexas public page. With `/` now being operator UI (auth-gated), the Pages deploy needs rethinking: either drop Pages, OR deploy just the `/about` view as a standalone build, OR keep a separate marketing page build.
- **Discord status endpoint** — stubbed in the UI footer as "not configured"; actual endpoint comes with M5-proper (Discord bot).
