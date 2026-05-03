# Milestone 4: `apps/api` Hub + Wrangler Dial-Home — Design

**Date:** 2026-04-13
**Status:** Approved (brainstorm complete, pending written spec review)
**Targets:** `apps/api/` (new FastAPI hub), `apps/wrangler/` (new `hub_client` module), `packages/contracts/` (WS protocol envelopes)

## Context

M1–M3.5 shipped the Pi-side half of WrangLED: scanner, pusher, local FastAPI, and a browser UI that drives a single Pi against WLEDs on the same LAN. M4 closes the loop by adding the **central server** (`apps/api`) and teaching the wrangler to **dial home** to it over a persistent WebSocket.

The payoff of M4: any command sender (the dashboard running on a user's phone, a CLI, eventually a Discord bot in M5) can drive a matrix that sits behind NAT on the conference Wi-Fi — no port-forwarding, no VPN for the client, just the wrangler reaching out to a public `api` endpoint.

## Goals

1. `apps/api` — new FastAPI process on port 8500 that holds WebSocket connections from wranglers, exposes REST for command senders, and serves the built `apps/dashboard/` as static.
2. `apps/wrangler` — add a `hub_client` module that opens and maintains a WSS connection to `api` when `WRANGLED_API_URL` is set. Receives relayed commands, state requests, and rescan requests; reports back device lists and results.
3. **Multi-wrangler aware:** multiple wranglers can connect at once (e.g. one at the venue, one at home for testing). Commands route to the wrangler that owns the target MAC.
4. **Pre-shared-key auth** via `WRANGLED_AUTH_TOKEN` env var on both sides. If unset on the api side, auth is disabled (dev mode, logged loudly).
5. Wrangler's existing behavior is **not regressed**: CLI `send`, `wrangler-ui`, and the local REST all keep working directly against the pusher. `hub_client` is additive.

## Non-goals (future milestones)

- Discord bot integration (M5).
- Dashboard interactivity — the existing dashboard stays as-is, built and served by api, made interactive in a later milestone.
- Persistence on api — in-memory only.
- TLS termination — handled by Caddy / container platform at deploy time.
- Message schema versioning — added when we actually break the protocol.
- Per-device or per-user rate limiting (belongs to Discord bot concerns in M5).
- UI tests (still deferred).

---

## Architecture

```
 ┌───────────┐  HTTP/WS  ┌─────────────┐  WSS (dial-home)  ┌──────────┐  HTTP  ┌──────┐
 │  Browser  │ ◄───────► │  apps/api   │ ◄───────────────► │ wrangler │ ─────► │ WLED │
 │ dashboard │           │ FastAPI     │                    │ (Pi)     │        │      │
 └───────────┘           │ :8500       │                    └────┬─────┘        └──────┘
                         │             │                         │
 ┌───────────┐  HTTP     │   (future)  │                    ┌────▼─────┐
 │ Discord   │ ────────► │  discord.py │                    │ wrangler │
 │ (M5)      │           └─────────────┘                    │   -ui    │ ← local LAN UI
 └───────────┘                                              └──────────┘
```

| Process | Python package | Port | Role |
|---|---|---|---|
| `api` (new) | `apps/api/` | 8500 | Central hub — serves dashboard, holds WS connections, routes commands, exposes REST. |
| `wrangler` | `apps/wrangler/` | 8501 | Pi agent — keeps all existing behavior AND a new outbound WS client that dials api. |
| `dashboard` | `apps/dashboard/` | built static | Served by api. |

### Design principles

- **Wrangler `hub_client` is optional.** Starts only if `WRANGLED_API_URL` is set. Without it, wrangler is unchanged.
- **`api` has no physical WLED knowledge.** No scanner, no httpx-to-WLED. Wranglers are the source of truth.
- **Local paths bypass api.** CLI `send`, `wrangler-ui`, and `apps/wrangler`'s own REST continue to hit the pusher directly. api exists for *remote* control.
- **Multi-wrangler by default.** api tracks `dict[wrangler_id, Connection]` and `dict[mac, wrangler_id]`. Wranglers come and go; device registry reflects currently-connected wranglers.
- **Pre-shared key auth.** Sufficient for LAN/Tailscale/Caddy-fronted deploys. TLS and cert-based auth are a deploy-time concern, not an application concern.

---

## WS Protocol (`packages/contracts/src/wrangled_contracts/hub.py`)

Pydantic v2 discriminated unions, one JSON message per WS frame.

### Wrangler → api

| kind | payload |
|---|---|
| `hello` | `wrangler_id: str`, `wrangler_version: str`, `devices: list[WledDevice]` |
| `devices_changed` | `devices: list[WledDevice]` |
| `command_result` | `request_id: str`, `result: PushResult` |
| `state_snapshot` | `request_id: str`, `mac: str`, `state: dict \| None`, `error: str \| None` |
| `pong` | — |

```python
WranglerMessage = Annotated[
    Hello | DevicesChanged | CommandResult | StateSnapshot | Pong,
    Field(discriminator="kind"),
]
```

### api → wrangler

| kind | payload |
|---|---|
| `welcome` | `server_version: str` |
| `command` | `request_id: str`, `mac: str`, `command: Command` |
| `get_state` | `request_id: str`, `mac: str` |
| `rescan` | — |
| `ping` | — |

```python
ApiMessage = Annotated[
    Welcome | RelayCommand | GetState | Rescan | Ping,
    Field(discriminator="kind"),
]
```

### Wire rules

- JSON, one message per WS frame.
- `request_id` is a UUID4 generated by api for request/response correlation.
- Every `command` from api MUST produce exactly one `command_result` from wrangler.
- Every `get_state` from api MUST produce exactly one `state_snapshot` from wrangler.
- `rescan` does NOT correlate — it's an event; wrangler eventually publishes `devices_changed`.
- api pings every 30s; wrangler pongs. Two missed pongs (60s of silence) → api closes the socket.
- On disconnect, wrangler reconnects with exponential backoff: 1s, 2s, 4s, …, capped at 60s; resets to 1s after a successful connect.

### Unknown / malformed messages

- api: log + close with code 1003 (unsupported data).
- wrangler: log + drop + continue. Don't kill the hub_client loop.

---

## `apps/api/` package layout

```
apps/api/
├── pyproject.toml                  # fastapi, uvicorn, websockets, pydantic,
│                                   # pydantic-settings, wrangled-contracts
├── CLAUDE.md
├── src/api/
│   ├── __init__.py
│   ├── __main__.py                 # python -m api
│   ├── cli.py                      # `api serve` subcommand
│   ├── settings.py                 # env-driven config
│   └── server/
│       ├── __init__.py             # exports create_app
│       ├── app.py                  # FastAPI factory, static mount, CORS
│       ├── hub.py                  # Hub class — connection manager, routing
│       ├── connection.py           # WranglerConnection dataclass (state + pending futures)
│       ├── auth.py                 # bearer-token dependency
│       ├── rest.py                 # /api/* REST endpoints
│       └── ws.py                   # /ws endpoint
├── static/dashboard/               # build output — gitignored
└── tests/
    ├── test_server_app.py
    ├── test_hub.py
    ├── test_auth.py
    ├── test_ws_handshake.py
    ├── test_rest_routing.py
    └── test_end_to_end.py
```

### `WranglerConnection`

```python
class WranglerConnection:
    wrangler_id: str
    socket: WebSocket
    wrangler_version: str
    connected_at: datetime
    last_pong_at: datetime
    devices: dict[str, WledDevice]            # keyed by MAC
    pending: dict[str, asyncio.Future]        # request_id → result-carrying future
```

### `Hub`

```python
class Hub:
    def __init__(self) -> None: ...

    async def attach(self, conn: WranglerConnection) -> None:
        """Register a new wrangler connection after Hello is received."""

    async def detach(self, wrangler_id: str) -> None:
        """Remove a wrangler; drop its devices from the registry."""

    async def send_command(self, mac: str, cmd: Command, *, timeout: float = 5.0) -> PushResult:
        """Find the owning wrangler; relay; await CommandResult; return PushResult."""

    async def get_state(self, mac: str, *, timeout: float = 3.0) -> dict:
        """Find owner; request state; return dict. Raises WranglerTimeout on timeout."""

    async def rescan_all(self) -> list[WledDevice]:
        """Fan out rescan to every wrangler; wait briefly for DevicesChanged; return merged list."""

    def all_devices(self) -> list[WledDevice]
    def find_device(self, mac: str) -> WledDevice | None
    def wranglers_summary(self) -> list[dict]
    def apply_devices(self, wrangler_id: str, devices: list[WledDevice]) -> None
    def resolve_response(self, wrangler_id: str, request_id: str, payload: object) -> None
```

- `send_command` looks up `mac` in the ownership map → posts `RelayCommand` → awaits `pending[request_id]` Future → returns. If `mac` isn't owned: `NoWranglerForDevice`. If timeout: `WranglerTimeout`.
- Ownership conflict (two wranglers claim the same MAC in Hello/DevicesChanged): newest claim wins, warning logged, previous owner's entry for that MAC is dropped from the ownership map (its own `devices` dict is not mutated — the wrangler will re-announce or be detached).

### REST endpoints (`rest.py`)

All require bearer auth if `WRANGLED_AUTH_TOKEN` is set. JSON in, JSON out.

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| `GET` | `/api/devices` | — | `{"devices": [...]}` | union across all wranglers |
| `GET` | `/api/devices/{mac}` | — | `WledDevice` or 404 | 404 if no wrangler owns it |
| `GET` | `/api/devices/{mac}/state` | — | `{"state": {...}}` | 404 if unowned, 502 on wrangler timeout |
| `POST` | `/api/devices/{mac}/commands` | `Command` | `PushResult` | 404 if unowned, 502 on timeout |
| `POST` | `/api/scan` | — | `{"devices": [...]}` | fanout rescan, merged return |
| `GET` | `/api/wranglers` | — | `[{wrangler_id, connected_at, device_count, last_pong_at}, ...]` | operational view |
| `GET` | `/healthz` | — | `{"ok": true, "wranglers": int}` | liveness |

### WS endpoint (`ws.py`)

- Path: `/ws`.
- Auth: bearer token accepted in the `Authorization: Bearer <token>` header OR `?token=<token>` query param (for browsers that can't set headers on a WS upgrade). If `WRANGLED_AUTH_TOKEN` is unset on the server, auth is skipped.
- Handshake: accept connection, read first message. If not `Hello` within 5s → close 1002. Otherwise build a `WranglerConnection`, call `hub.attach()`, send `Welcome`.
- Main loop: read JSON frames, validate against `WranglerMessage`, dispatch:
  - `DevicesChanged` → `hub.apply_devices(conn.wrangler_id, devices)`.
  - `CommandResult` → `hub.resolve_response(request_id, result)`.
  - `StateSnapshot` → `hub.resolve_response(request_id, state-or-error)`.
  - `Pong` → update `last_pong_at`.
- Heartbeat: background task pings every 30s; closes if `now - last_pong_at > 70s`.
- On disconnect: `hub.detach(wrangler_id)`. Cancel pending futures with `WranglerDisconnected` error.

### Static mount

```python
if (app_root / "static" / "dashboard").is_dir():
    app.mount("/", StaticFiles(directory=..., html=True), name="dashboard")
```

If absent, `/` returns 404. Test asserts both branches behave correctly.

### `cli.py`

```
uv run api serve                            # :8500
uv run api serve --host 0.0.0.0 --port 8500
uv run api serve --no-auth                  # force auth disabled regardless of env
```

### Settings

`APPS_API_` env prefix:

| env var | default | purpose |
|---|---|---|
| `WRANGLED_AUTH_TOKEN` | None | Pre-shared key. Required on BOTH api and wrangler if set. Unset = dev mode. |
| `API_HOST` | `127.0.0.1` | uvicorn bind |
| `API_PORT` | `8500` | uvicorn bind |

---

## Wrangler `hub_client`

New module `apps/wrangler/src/wrangler/hub_client.py`.

### Public API

```python
class HubClient:
    def __init__(
        self,
        *,
        api_url: str,          # ws:// or wss://…/ws
        auth_token: str | None,
        wrangler_id: str,
        registry: Registry,
    ) -> None: ...

    async def run(self) -> None:
        """Long-running task. Connects, handles messages, reconnects on failure. Never returns."""

    async def notify_devices_changed(self) -> None:
        """Called by Registry when devices change. Emits DevicesChanged if connected."""
```

### Behavior

On `run()`:

1. Compose the WS URL; add `Authorization: Bearer <token>` header if token set.
2. Connect. On success, send `Hello(wrangler_id, wrangler_version, devices=registry.all())`.
3. Wait for `Welcome`. Log mismatch if server_version differs by major version.
4. Main loop (read messages + dispatch):
   - `RelayCommand` → get `WledDevice` from registry; `push_command(client, device, command)`; emit `CommandResult(request_id, result)`.
     - If MAC unknown to registry: emit `CommandResult(ok=False, error="unknown device on this wrangler")`.
   - `GetState` → `fetch_state(client, device)`; emit `StateSnapshot(state)` or `StateSnapshot(state=None, error=...)`.
   - `Rescan` → `await registry.scan(ScanOptions(...))`; Registry's `on_changed` hook will fire `notify_devices_changed`.
   - `Ping` → emit `Pong`.
   - `Welcome` → ignore after first.
5. On any error (disconnect, parse error, auth rejection):
   - Log.
   - Sleep with exponential backoff (1→60s cap).
   - Reset backoff after a successful handshake.

### Registry `on_changed` hook

Small addition to `apps/wrangler/src/wrangler/server/registry.py`:

```python
class Registry:
    def __init__(self, *, scanner: ScanFn) -> None:
        ...
        self._observers: list[Callable[[], Awaitable[None]]] = []

    def on_changed(self, cb: Callable[[], Awaitable[None]]) -> None:
        self._observers.append(cb)

    async def _notify(self) -> None:
        for cb in self._observers:
            try:
                await cb()
            except Exception:
                logger.exception("observer failed")

    async def scan(self, opts): ...       # call _notify after updating _devices
    def put(self, device): ...            # call _notify
```

Observers run asynchronously after scan/put. Failures are logged but don't break the registry.

### Startup in `apps/wrangler/src/wrangler/server/app.py`

```python
if settings.api_url:
    hub = HubClient(
        api_url=settings.api_url,
        auth_token=settings.auth_token,
        wrangler_id=settings.wrangler_id,
        registry=reg,
    )
    reg.on_changed(hub.notify_devices_changed)

    @app.on_event("startup")
    async def _start_hub() -> None:
        app.state.hub_task = asyncio.create_task(hub.run())

    @app.on_event("shutdown")
    async def _stop_hub() -> None:
        app.state.hub_task.cancel()
```

### Wrangler settings additions

```python
class WranglerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WRANGLED_", ...)
    api_url: str | None = None                # already exists
    auth_token: str | None = None             # NEW
    wrangler_id: str = Field(default_factory=socket.gethostname)   # NEW
    ...
```

---

## Testing

### api tests

- **`test_server_app.py`** — `/healthz`; static mount present/absent; `create_app` smoke test.
- **`test_auth.py`** — bearer required when `WRANGLED_AUTH_TOKEN` set; missing → 401; bad → 401; right → 200. `?token=` works on WS. `--no-auth` CLI flag disables.
- **`test_hub.py`** — `Hub` in isolation:
  - attach + detach clean up ownership map.
  - `send_command` resolves when `CommandResult` arrives with the right request_id.
  - `send_command` times out when no response arrives.
  - `send_command` raises `NoWranglerForDevice` when MAC unowned.
  - Ownership conflict: second wrangler claims MAC, first loses ownership, warning logged.
  - `rescan_all` fans out; merged list respects later Hello/DevicesChanged overrides.
- **`test_ws_handshake.py`** — using FastAPI TestClient's WS support:
  - Missing/invalid bearer token → connection closed with 1008 (or similar).
  - Valid token + Hello → Welcome received; hub shows the wrangler.
  - No Hello within 5s → closed.
- **`test_rest_routing.py`** — REST endpoints with a fake wrangler pre-attached to the Hub:
  - `GET /api/devices` returns that wrangler's devices.
  - `GET /api/devices/{mac}` 200 / 404.
  - `GET /api/devices/{mac}/state` — fake wrangler replies with `StateSnapshot`, REST returns the state; wrangler timeout → 502.
  - `POST /api/devices/{mac}/commands` — fake wrangler replies with `CommandResult(ok=True)`, REST returns 200; invalid body → 422; unknown MAC → 404.
  - `POST /api/scan` — fans out to fake wranglers.
  - `GET /api/wranglers` — returns current summary.
- **`test_end_to_end.py`** — spins a real `api` TestClient and a real `HubClient` (with `push_command` patched to a mock) in-process, asserts a `POST /api/devices/{mac}/commands` round-trip actually invokes the mocked pusher on the wrangler side.

### wrangler tests

- **`test_hub_client.py`** — using `aiohttp` or `websockets` in-process server as a fake api:
  - `run()` doesn't start if `api_url` is unset.
  - On connect, Hello is sent with correct shape.
  - `RelayCommand` triggers `push_command` (mocked) and a `CommandResult` is sent.
  - `GetState` triggers `fetch_state` and `StateSnapshot` is sent (happy path + unreachable path).
  - Reconnect with backoff after the fake server closes the connection.
  - `notify_devices_changed` emits `DevicesChanged` when connected, no-ops when not.
- **`test_registry_observer.py`** — Registry notifies registered callbacks after `scan` and `put`.

### No UI tests. (Same policy as M3.)

---

## Deliverable

At the end of M4:

```bash
# terminal 1 — api
cd apps/api && WRANGLED_AUTH_TOKEN=devtoken uv run api serve

# terminal 2 — wrangler on the Pi (or here for dev)
cd apps/wrangler
WRANGLED_API_URL=ws://localhost:8500/ws \
WRANGLED_AUTH_TOKEN=devtoken \
  uv run wrangler serve

# terminal 3 — remote caller
curl -X POST http://localhost:8500/api/devices/<mac>/commands \
  -H 'Authorization: Bearer devtoken' \
  -H 'Content-Type: application/json' \
  -d '{"kind":"color","color":{"r":0,"g":0,"b":255}}'
```

Matrix turns blue. `GET /api/devices` lists the matrix. `GET /api/wranglers` lists one connected wrangler. CLI `wrangler send` still works locally, unchanged. `wrangler-ui` still works locally, unchanged.

## Open questions for future milestones

- Where does api actually get deployed? (Caddy in front + Docker on your server, or a cloud provider.) Once stable, bake the URL as the default `WRANGLED_API_URL` in wrangler.
- Per-user / per-device rate limiting — belongs to Discord bot (M5).
- Moderation / profanity filter on text commands — M5.
- Persistent audit log of commands (who sent what when) — M5 or later.
- Pairing / onboarding flow for new wranglers — currently manual token paste; might want a pairing code flow later.

## Milestone scope boundary

This plan does NOT include:

- Discord bot
- Dashboard interactive controls (existing dashboard stays informational)
- Auth beyond pre-shared key
- Rate limiting / moderation
- Message-schema versioning
- Persistence / audit log
- UI tests
