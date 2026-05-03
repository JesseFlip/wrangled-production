# Milestone 3: Wrangler FastAPI Server + Wrangler-UI — Design

**Date:** 2026-04-13
**Status:** Approved (brainstorm complete, pending written spec review)
**Targets:** `apps/wrangler/` (new `serve` subcommand, FastAPI surface), `apps/wrangler-ui/` (new Vite/React app)

## Context

M1 shipped the scanner (`wrangler scan`). M2 shipped the Command contract, pusher module, and `wrangler send` CLI — proven live against the WLED-Gledopto matrix at `10.0.6.207`. M3 adds a local HTTP + browser UI on top of the existing scanner + pusher so the user can drive the matrix interactively without typing curl commands or CLI flags, and so the friend-facing workflow gets a place to land well before the upstream hub (`apps/api`) or Discord bot exist.

Scope is deliberately narrow: **wrangler alone**, no WebSocket to an upstream hub, no auth, no persistence. The goal is an interactive testing panel the user can open at PyTexas and trust.

## Goals

1. `wrangler serve` starts a FastAPI server on port 8501 that wraps the existing scanner + pusher as HTTP endpoints.
2. `apps/wrangler-ui/` is a Vite/React app that gets built into static assets and served by that FastAPI.
3. UI covers every Command variant already in `wrangled_contracts` (color / brightness / effect / text / preset / emoji / power).
4. Multi-device aware: UI lists discovered WLEDs, lets the user switch between them, and rename them (by setting the WLED's own `cfg.id.name`).
5. Live state polling — UI reflects the currently-selected WLED's state every 2 seconds.
6. Existing `wrangler scan` and `wrangler send` CLIs keep working — `serve` is additive.

## Non-goals (future milestones)

- WebSocket hub (`apps/api`) and wrangler-to-hub WS client.
- Discord bot.
- Auth / user identity.
- Persistence (no database on wrangler's side; nothing stored under `~/.config/wrangled/`).
- Multi-device command fanout (pushing one Command to many WLEDs simultaneously).
- UI tests (no Vitest/jsdom scaffolding this milestone).
- Scheduled / recurring scans (initial scan only, plus user-triggered rescan).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  apps/wrangler-ui (Vite/React, served as static)     │   │
│  │  • Device selector (GET /api/devices)                │   │
│  │  • Controls (POST /api/devices/{mac}/commands)       │   │
│  │  • Live state panel (GET /api/devices/{mac}/state)   │   │
│  │  • Rename (PUT /api/devices/{mac}/name)              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │ HTTP (same-origin, :8501)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  apps/wrangler (FastAPI + scanner + pusher)                 │
│  • `wrangler serve` → FastAPI on :8501                      │
│  • Serves apps/wrangler/static/wrangler-ui/ as "/"          │
│  • In-memory dict[mac, WledDevice] registry                 │
│  • Initial scan on startup, user-triggered rescans          │
│  • REST under /api/*                                        │
└─────────────────────────────────────────────────────────────┘
          │ HTTP (LAN)
          ▼
 WLEDs on the network (10.0.6.207, …)
```

### Runtime concerns inside `wrangler serve`

1. **Registry.** In-memory `dict[str, WledDevice]` keyed by MAC. Populated by a single asyncio lock-protected `scan_and_register()` helper. Startup runs one scan (unless `--no-initial-scan` is passed). Further scans happen only on `POST /api/scan` from the UI.
2. **State probes.** `GET /api/devices/{mac}/state` always fetches live from the WLED. No caching. If WLED is unreachable, return 502.
3. **Command dispatch.** `POST /api/devices/{mac}/commands` pulls the device from the registry, calls existing `push_command()` from `wrangler.pusher`, returns the `PushResult`.
4. **Rename.** `PUT /api/devices/{mac}/name` POSTs to WLED's `/json/cfg` with `{"id":{"name":"..."}}`, re-probes the device (`/json/info`) to refresh the registry entry, returns the updated `WledDevice`.

### Concurrency

- Single `asyncio.Lock` around scans. If a second `POST /api/scan` arrives while a scan is in progress, it awaits the same result (returns the same device list the in-progress scan produces). No 409.
- Command pushes are not serialized — multiple clients firing commands concurrently is allowed; WLED itself handles overlapping `/json/state` POSTs (last-write-wins).

---

## API endpoints

All under `/api/`. JSON request/response. No auth. CORS set to `allow_origins=["*"]` (the Vite dev server runs on a different origin in dev; production same-origin).

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| `GET` | `/api/devices` | — | `{"devices": [WledDevice, ...]}` | registry snapshot |
| `POST` | `/api/scan` | — | `{"devices": [WledDevice, ...]}` | awaits lock + scan |
| `GET` | `/api/devices/{mac}` | — | `WledDevice` | 404 if unknown |
| `GET` | `/api/devices/{mac}/state` | — | `{"on": bool, "bri": int, "seg": [...]}` | live fetch from WLED; 502 if unreachable |
| `POST` | `/api/devices/{mac}/commands` | `Command` | `PushResult` | pydantic discriminates kind |
| `PUT` | `/api/devices/{mac}/name` | `{"name": "Stage-Left"}` | updated `WledDevice` | proxies to WLED `/json/cfg`; re-probes |
| `GET` | `/api/effects` | — | `{"effects": ["solid","fire",...]}` | from `EFFECT_FX_ID` keys |
| `GET` | `/api/presets` | — | `{"presets": ["pytexas","party","chill"]}` | from `PRESETS` keys |
| `GET` | `/api/emoji` | — | `{"emoji": {"🔥":"fire",...}}` | from `EMOJI_COMMANDS`, mapped to a short label |
| `GET` | `/healthz` | — | `{"ok": true}` | liveness |

### MAC in URL paths

MAC is already the canonical lowercase colon-separated form from our `WledDevice` validator. Colons are URL-safe as path segments, but the UI URL-encodes to `aa%3Abb%3A...` defensively. FastAPI path parameters handle that.

### Error shape

FastAPI's default `{"detail": "..."}` with the appropriate 4xx/5xx code. Specifically:

- 404 — unknown MAC in the registry.
- 422 — pydantic validation failed on `Command` body (default FastAPI behavior).
- 502 — WLED reached but returned non-200, or network error probing `/json/state` / `/json/cfg` / `/json/info`.

---

## Wrangler-side implementation

### Directory

```
apps/wrangler/
├── pyproject.toml                       # add fastapi, uvicorn[standard]
├── src/wrangler/
│   ├── cli.py                           # add `serve` subcommand
│   └── server/
│       ├── __init__.py                  # exports create_app
│       ├── app.py                       # FastAPI app factory (CORS, static mount)
│       ├── devices.py                   # APIRouter with /api/devices/*, /api/scan, /api/effects, /api/presets, /api/emoji, /healthz
│       ├── registry.py                  # in-memory dict + asyncio.Lock + scan_and_register()
│       └── wled_client.py               # httpx read helpers: fetch_state, set_name (proxy /json/cfg)
├── static/wrangler-ui/                  # build target for the Vite UI (gitignored)
└── tests/
    ├── test_server_app.py
    ├── test_server_devices.py
    └── test_server_registry.py
```

`pusher.py` is not touched. `server/wled_client.py` covers the *read* (`GET /json/state`) and *config* (`POST /json/cfg`) paths that pusher doesn't need.

### `wrangler serve` CLI

```
uv run wrangler serve                                # :8501, initial scan
uv run wrangler serve --host 0.0.0.0 --port 8501
uv run wrangler serve --no-initial-scan              # skips startup scan (useful for tests)
```

Implementation: `asyncio.run(uvicorn.Config(app=create_app(...), host=..., port=...).serve())` or `uvicorn.run(app_factory_string, ...)`. The startup scan runs inside a FastAPI startup event handler.

### `create_app()` signature

```python
def create_app(
    *,
    initial_scan: bool = True,
    scan_options: ScanOptions | None = None,
) -> FastAPI: ...
```

Takes dependencies explicitly so tests can inject a stubbed scanner / registry without relying on networking.

### Registry

```python
class Registry:
    def __init__(self) -> None:
        self._devices: dict[str, WledDevice] = {}
        self._lock = asyncio.Lock()

    async def scan(self, opts: ScanOptions) -> list[WledDevice]: ...
    def all(self) -> list[WledDevice]: ...
    def get(self, mac: str) -> WledDevice | None: ...
    def put(self, device: WledDevice) -> None: ...
```

`scan()` acquires the lock, calls `wrangler.scanner.scan(opts)`, replaces `_devices` with the fresh set keyed by `device.mac`, returns the list. Concurrent callers await the same task (one scan in flight at a time).

### Static mount

```python
if (app_root / "static" / "wrangler-ui").is_dir():
    app.mount(
        "/",
        StaticFiles(directory=app_root / "static" / "wrangler-ui", html=True),
        name="wrangler-ui",
    )
```

When the UI hasn't been built yet (fresh clone before `npm run build`), the static dir is skipped and `/` returns 404 — `GET /api/*` and `/healthz` still work. The test suite asserts this graceful-absent behavior.

### Dependencies

Added to `apps/wrangler/pyproject.toml`:

```toml
dependencies = [
    # ...existing...
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]

[dependency-groups]
dev = [
    # ...existing...
    "httpx>=0.27",  # already present; FastAPI TestClient uses it
]
```

---

## UI implementation (`apps/wrangler-ui/`)

### Scaffolding

Plain JS (not TypeScript) — matches `apps/dashboard/`. Created with `npm create vite@latest wrangler-ui -- --template react`. The default example is stripped; project-root ESLint flat config is copied from `apps/dashboard/`.

### Files

```
apps/wrangler-ui/
├── package.json
├── vite.config.js              # dev port 8511, proxy /api/* and /healthz → :8501
├── eslint.config.js            # inherits monorepo rules
├── index.html
├── CLAUDE.md
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api.js                  # fetch wrappers
    ├── index.css               # tokens + base styles
    └── components/
        ├── DeviceSelector.jsx
        ├── LiveState.jsx
        ├── BrightnessSlider.jsx
        ├── ColorTab.jsx
        ├── EffectTab.jsx
        ├── TextTab.jsx
        ├── PresetTab.jsx
        ├── EmojiTab.jsx
        └── PowerTab.jsx
```

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Wrangler                                         [ Rescan 🔄 ]     │
│  Device: [ Stage-Left ▼ ]  ✏️                                       │
│          (10.0.6.207 · 64x8 · 0.15.1 · d4:e9:…)                     │
├─────────────────────────────────────────────────────────────────────┤
│  LIVE STATE                                                          │
│  ● ON   bri 80   fx: Firenoise   ■ #ff5000                          │
├─────────────────────────────────────────────────────────────────────┤
│  CONTROLS                                                            │
│  [Color] [Effect] [Text] [Preset] [Emoji] [Power]                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  (active tab)                                                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  Brightness: [──────●──────] 80 / 200                               │
└─────────────────────────────────────────────────────────────────────┘
```

- **Device selector:** dropdown populated from `GET /api/devices`. Selection persists in `localStorage` under key `wrangler.selectedMac`. On mount, preferred mac is: localStorage value → first device in list.
- **Rescan:** button fires `POST /api/scan`; spinner shown on the button while the fetch is in flight. Success updates device list.
- **Rename:** pencil icon opens inline input; Enter → `PUT /api/devices/{mac}/name`; on success refetch `/api/devices`.
- **Live state panel:** `GET /api/devices/{mac}/state` on a `setInterval(2000)`. Cleared + restarted when selected device changes or tab is hidden (page-visibility API).
- **Brightness slider:** 0–200. Value committed on `onChange` release (`onPointerUp`), not every frame — fires `BrightnessCommand`.
- **Tabs:** horizontal button group; one tab active at a time; content swaps below.
- **Color tab:** named-color chip grid (red/blue/orange/etc.), hex input with live swatch preview, color-emoji chip row. Each click fires a `ColorCommand` immediately (no "apply" button — direct manipulation).
- **Effect tab:** dropdown of effect names from `/api/effects`, optional sliders for speed and intensity, optional color chip row, "Fire" button to send `EffectCommand`.
- **Text tab:** textarea (maxLength 64, live char counter), color picker, speed slider (32–240). Send button → `TextCommand`.
- **Preset tab:** three big buttons (`pytexas` / `party` / `chill`) → `PresetCommand`.
- **Emoji tab:** chip grid from `/api/emoji`. Each click fires the mapped Command; label shows both the emoji and the resolved action ("🔥 fire").
- **Power tab:** two big buttons (On / Off) → `PowerCommand`.

### Error handling

Top-of-page banner. Shown if any recent fetch errored. Messages: "Matrix unreachable — retry?" (502 on state or command), "Wrangler unreachable" (network error on any call). Banner dismisses on next successful poll. No toasts.

### Optimistic UI

Command clicks update the local "last sent" marker immediately; the next 2s poll confirms or reverts the displayed `LiveState`. This is fine for slow commands — feedback is instant even when WLED takes 100–300 ms to respond.

---

## Build + dev workflow

### Dev

```bash
# terminal 1
cd apps/wrangler && uv run wrangler serve        # FastAPI on :8501

# terminal 2
cd apps/wrangler-ui && npm run dev                # Vite on :8511
# open http://localhost:8511
```

Vite dev server proxies `/api/*` and `/healthz` to `localhost:8501`, so the React code calls `fetch('/api/devices')` in both dev and prod.

### Build / production

```bash
cd apps/wrangler-ui && npm install && npm run build
# → writes apps/wrangler/static/wrangler-ui/

cd apps/wrangler && uv run wrangler serve
# → http://localhost:8501/  serves UI + API
```

`build.sh` gains a `wrangler-ui` step that runs `npm install && npm run build` and leaves the output at the correct static path. `.gitignore` excludes `apps/wrangler/static/wrangler-ui/`.

`dev.sh` gains a second concurrent process (Vite on 8511) so `./dev.sh` starts dashboard Vite + wrangler FastAPI + wrangler-ui Vite together.

---

## Tests

### Server (FastAPI TestClient, no real WLED)

- **`test_server_app.py`** — `create_app(initial_scan=False)` is callable; `/healthz` returns `{"ok": true}`; static mount is present when `static/wrangler-ui/` exists, absent otherwise; `GET /` returns 404 when no build present.
- **`test_server_registry.py`** — `scan()` populates the map; two concurrent `scan()` calls serialize through the lock and return the same snapshot; `put()` replaces an existing mac; `get()` returns `None` for unknown mac.
- **`test_server_devices.py`** — one happy-path test per endpoint using `TestClient` and a mocked `Registry` + mocked `wled_client` / `push_command`:
  - `GET /api/devices` returns list.
  - `POST /api/scan` invokes `Registry.scan`.
  - `GET /api/devices/{mac}` 200 / 404.
  - `GET /api/devices/{mac}/state` returns mocked WLED state; 502 on httpx error.
  - `POST /api/devices/{mac}/commands` with a `ColorCommand` body dispatches to `push_command` and returns `PushResult`; 422 on invalid body; 404 on unknown mac.
  - `PUT /api/devices/{mac}/name` calls `wled_client.set_name`, re-probes, returns updated device.
  - `GET /api/effects`, `/api/presets`, `/api/emoji` return the expected keys.

### UI

None this milestone. Manual verification is part of M3's acceptance: "open `http://localhost:8501/` after `./build.sh`, click through every tab against the real matrix at 10.0.6.207."

---

## Deliverable

At the end of M3:

```bash
./build.sh
cd apps/wrangler && uv run wrangler serve
# → open http://localhost:8501/
```

Opens on the UI. Device is auto-selected (first discovered). Click color chips, run effects, scroll text, fire presets, toggle power — all drive the matrix and the live-state panel reflects what's on it. Rename "WLED-Gledopto" to "Stage-Left" and it sticks. All new FastAPI tests green. CLI (`scan`, `send`) still works unchanged. Branch ready to push.

## Out of scope (intentionally)

- WebSocket streaming state (polling is fine at 2s).
- Auth / bearer tokens.
- Multi-device fanout.
- Persistence on wrangler's side (no DB).
- UI tests.
- Recurring background scans.
- Mobile-optimized layout (responsive-ish but not heavily tested on phones).
