# WrangLED Architecture & Scanner — Design

**Date:** 2026-04-13
**Status:** Approved (brainstorm complete, pending spec review)
**First implementation target:** `wrangler/` scanner module (milestone 1)

## Context

The existing repo (`wrangled-dashboard`) is a Vite/React "Command Center" UI only. The dashboard references an end-to-end architecture (Discord → bot → VPS → Pi → WLED) that does not exist as code yet. This design establishes the full runtime architecture, the monorepo layout, the shared tooling/linting/dev workflow, and specifies the first implementation milestone: a WLED network scanner inside the Pi-side agent (`wrangler`).

Development happens on Linux; the long-term deployment target for `wrangler` is a Raspberry Pi 4. The `api` is a single process (no dedicated VPS assumption) that can run in a container on any server, fronted by Caddy for HTTPS.

Jim (CowboyQuant) owns end-to-end for now; Kevin/Mason can later carve out pieces. Design reflects "easier to tweak than to put paint on the canvas" — optimize for a clean first cut, not for Kevin's eventual takeover.

## Goals

1. Name all processes and establish monorepo folder structure.
2. Define the data flow end-to-end (Discord/dashboard → api → wrangler → WLED).
3. Lock in development tooling: ports, linting, build scripts, per-module CLAUDE.md convention.
4. Deliver milestone 1: `wrangler` scanner that discovers WLEDs on the LAN, with a confirmed device at `10.0.6.207` for live testing.

## Non-goals (for this spec)

- WebSocket client between `wrangler` and `api` (future milestone)
- Command payload protocol beyond initial sketch (future milestone)
- Persistence / history / leaderboard (future milestone)
- Auth between `wrangler` and `api` (future milestone)
- Dockerization, CI/CD pipelines (future milestone — noted as a known direction)

---

## System Architecture

### Runtime processes

| Process | Runs on | Serves | Talks to |
|---|---|---|---|
| `api` | Server (container + Caddy) | dashboard static + REST + WS hub + Discord gateway (optional) | `wrangler` (inbound WS), Discord (outbound WSS), browsers |
| `wrangler` | Raspberry Pi | wrangler-ui static + local REST | `api` (outbound WS), WLEDs (HTTP), multicast (mDNS) |
| Browsers | Anywhere | — | `api` or `wrangler` |

### Monorepo layout

```
wrangled/
├── apps/
│   ├── dashboard/      # Vite/React — Command Center UI (existing)
│   ├── api/            # FastAPI hub
│   ├── wrangler-ui/    # Vite/React — Pi config panel
│   └── wrangler/       # FastAPI + agent — runs on the Pi
├── packages/
│   └── contracts/      # shared pydantic models + generated TS types
├── infra/
│   └── pi/             # systemd units, install scripts
├── docs/
├── lint.sh
├── build.sh
├── dev.sh
└── CLAUDE.md
```

Each directory in `apps/`, `packages/`, and `infra/` has its own `CLAUDE.md` describing purpose, local run/test commands, key files, and gotchas. The root `CLAUDE.md` lists them and describes monorepo conventions (ports, scripts, linting).

Each Python app has its own `pyproject.toml` and is independently installable via `uv`. A future move to a uv workspace is possible but not required for milestone 1.

### Data flow (end-to-end command)

```
Discord user:  /led red
  → Discord gateway WSS → api (discord.py background task)
  → api validates, emits Command event
  → api fans out via WebSocket to: dashboard browsers, wrangler
  → wrangler receives Command
  → wrangler translates to WLED JSON (per-device)
  → wrangler HTTP POSTs to each WLED /json/state
  → wrangler reports ack → api → dashboards
```

The same path is used for dashboard-initiated commands; Discord is just one input interface among several.

### Design principles

- **Hub model.** `api` is the single authority for "what is the current state." All interfaces (Discord, dashboard, future CLIs) produce Commands into the hub. `wrangler` is a Command consumer that pushes to physical WLEDs.
- **Outbound-only `wrangler`.** It dials `api` via WSS. No inbound ports exposed on the Pi beyond the local config UI on the LAN. Works behind NAT, at conference venues, etc.
- **Optional interfaces.** Discord gateway starts only if `DISCORD_BOT_TOKEN` is set. `wrangler` connects to `api` only if `WRANGLED_API_URL` is set.
- **Shared contracts.** `packages/contracts/` holds pydantic models imported by every Python app; TS types are generated from the same schemas for the React UIs. No drift between producer and consumer.

---

## Tooling, Linting, Dev Workflow

### Port allocation (8500 block)

| Service | Port | Notes |
|---|---|---|
| `api` FastAPI | **8500** | REST + WS + dashboard static in prod |
| `wrangler` FastAPI | **8501** | REST + wrangler-ui static in prod |
| `dashboard` Vite dev | **8510** | `/api/*` and `/ws` proxy → `localhost:8500` |
| `wrangler-ui` Vite dev | **8511** | `/api/*` and `/ws` proxy → `localhost:8501` |

Vite proxy config makes dev mode visually identical to prod — React code calls `/api/...` in both modes.

### Python linting (Ruff, maxed)

Per-app `pyproject.toml` inherits a shared config:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "D",                # pydocstyle — opt-in per app later
    "ANN101", "ANN102", # self/cls annotations (redundant)
    "COM812", "ISC001", # formatter conflicts
]

[tool.ruff.lint.mccabe]
max-complexity = 15

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004"]
```

Formatting via `ruff format`. Optional `mypy --strict` is a stretch goal per app.

### JS/TS linting (ESLint flat config, maxed)

- `@eslint/js` recommended + `typescript-eslint` strict
- `eslint-plugin-react` + `eslint-plugin-react-hooks`
- `eslint-plugin-jsx-a11y`
- `eslint-plugin-import` with order enforcement
- `complexity: ["error", 15]`
- Prettier for formatting

### Root scripts

- **`lint.sh`** — runs ruff (check + format --check) across all Python apps, ESLint across both JS apps. Non-zero on failure. Accepts `--fix` to apply autofixes.
- **`build.sh`** — ensures `uv` and Node are present, installs deps for all four apps, builds both Vite UIs into their respective FastAPI `static/` dirs, runs `lint.sh`, runs all pytest suites. End state: apps runnable locally.
- **`dev.sh`** — starts all four dev processes concurrently (api, wrangler, both Vite dev servers). Implementation likely via `honcho` or a `Procfile`.

### CLAUDE.md convention

Every sub-module has a `CLAUDE.md` documenting: one-paragraph description, how to run locally, how to test, key files, gotchas. Root `CLAUDE.md` indexes them and documents monorepo-wide conventions.

### CI/CD (future, not milestone 1)

GitHub Actions on push to main: `lint.sh` + tests, build `api` and `wrangler` Docker images, push to Docker Hub tagged with short SHA + `latest`. Separate workflow per image so Pi and server pull independently.

---

## Milestone 1: The Scanner

**Deliverable:** `uv run wrangler scan` discovers WLEDs on the LAN (confirmed device: `10.0.6.207`), prints a formatted table. Importable as a library for the future WS client and wrangler-ui to reuse. Fully tested.

### What milestone 1 includes beyond the scanner itself

The full monorepo skeleton must be stood up, because the scanner imports from `packages/contracts/` and lives inside a real monorepo layout that future milestones will extend. Milestone 1 therefore produces:

- Root-level: `lint.sh`, `build.sh`, `dev.sh`, `CLAUDE.md`, shared config files (ruff, eslint, prettier, .gitignore additions).
- `apps/wrangler/` — fully implemented (scanner + CLI + tests + `CLAUDE.md`).
- `packages/contracts/` — fully implemented for the `WledDevice` / `WledMatrix` models + `CLAUDE.md`. Installable as a local uv dep from `apps/wrangler/`.
- `apps/api/`, `apps/dashboard/`, `apps/wrangler-ui/`, `infra/pi/` — placeholder directories each containing a `CLAUDE.md` describing intended purpose and stating "not yet implemented." The existing Vite/React dashboard files move into `apps/dashboard/` as part of this milestone. No functional changes to the dashboard.
- `lint.sh` and `build.sh` succeed on the current tree (they skip the placeholder apps gracefully).

### Module layout

```
apps/wrangler/
├── pyproject.toml
├── CLAUDE.md
├── src/wrangler/
│   ├── __init__.py
│   ├── __main__.py            # python -m wrangler → CLI entry
│   ├── cli.py                 # argparse or typer; subcommand: scan
│   ├── scanner/
│   │   ├── __init__.py        # public: scan(opts) -> list[WledDevice]
│   │   ├── mdns.py            # zeroconf-based discovery
│   │   ├── sweep.py           # IP range sweep via httpx + asyncio
│   │   ├── probe.py           # GET /json/info → WledDevice
│   │   └── netinfo.py         # detect local subnet(s)
│   └── settings.py            # pydantic-settings
└── tests/
    ├── test_mdns.py
    ├── test_sweep.py
    ├── test_probe.py
    ├── test_scan_integration.py
    └── fixtures/
        └── wled_info_v0_15.json
```

### Public API

```python
from wrangler.scanner import scan, ScanOptions
from wrangled_contracts import WledDevice

devices: list[WledDevice] = await scan(ScanOptions(
    mdns_timeout=3.0,
    sweep=None,           # None = fallback (sweep only if mdns finds nothing);
                          # True = force; False = never
    sweep_subnet=None,    # None = auto-detect /24 from local interface
    include=None,         # optional allowlist of IPs to probe
))
```

### Behavior

1. Listen on `_wled._tcp.local` for `mdns_timeout` seconds (default 3.0). Collect candidate IPs.
2. If `sweep is True` OR (`sweep is None` AND candidates is empty) → run sweep on `sweep_subnet` (auto-detected `/24` if unset). If `sweep is False`, skip sweep entirely.
3. For every candidate IP, concurrently `GET http://{ip}/json/info` (httpx, 2s timeout, 32-way semaphore).
4. Parse responses into `WledDevice`. Drop non-WLED / failed responses silently (debug-log only).
5. Return list deduplicated by MAC, sorted by IP ascending.

### `WledDevice` model (lives in `packages/contracts/`)

```python
class WledMatrix(BaseModel):
    width: int
    height: int

class WledDevice(BaseModel):
    ip: IPv4Address
    name: str
    mac: str                     # canonical lowercase, colon-separated
    version: str
    led_count: int
    matrix: WledMatrix | None    # populated for 2D panels only
    udp_port: int | None
    raw_info: dict = Field(exclude=True, repr=False)
    discovered_via: Literal["mdns", "sweep"]
    discovered_at: datetime
```

### CLI shape

```
$ uv run wrangler scan
Scanning via mDNS (3s)... found 1
Probing 1 candidate...

  IP             NAME           MAC                VER       LEDS    MATRIX  VIA
  10.0.6.207     WLED-Matrix    aa:bb:cc:dd:ee:ff  0.15.0    256     16x16   mdns

1 device.

$ uv run wrangler scan --sweep              # force sweep in addition to mdns
$ uv run wrangler scan --no-mdns            # sweep only
$ uv run wrangler scan --subnet 10.0.6.0/24 # explicit subnet
$ uv run wrangler scan --json               # machine-readable output
```

### Error handling

- mDNS unavailable / bind failure → warn-log, continue. If `sweep is None`, treat mDNS as having found nothing and fall through to sweep.
- Subnet auto-detect fails (multi-homed or unusual setup) → require `--subnet`, exit 2 with a message naming detected interfaces.
- Probe failure (timeout, non-200, non-JSON, missing required fields) → dropped silently; summary line at end reports count of non-responsive candidates.
- Zero devices found → exit 0 with `"0 devices found."` — not an error condition.

### Testing approach (TDD)

- **`test_probe.py`** — parse fixture JSON into `WledDevice`; covers v0.15 shape (and earlier versions if locatable).
- **`test_sweep.py`** — mock httpx with `respx`; assert concurrency cap, timeout handling, dedup by MAC.
- **`test_mdns.py`** — mock zeroconf service browser; assert candidates surface, resolve to IPs correctly.
- **`test_scan_integration.py`** — mock both mDNS and sweep; assert the mdns-first/fallback orchestration rules across all `sweep` values.
- **Live test (`@pytest.mark.live`)** — opt-in, real network call to `10.0.6.207`; skipped in CI, run locally for confidence.

Work proceeds in small TDD increments with commits at each green step: red test → minimum code to green → refactor → commit.

### Out of scope for milestone 1

- WS client to `api`
- Sending commands to WLEDs (only probe `/json/info` here, never `/json/state`)
- `wrangler-ui` (the local config panel)
- Persistence of scan results
- Auth

Each follows as its own milestone after the scanner is proven on the Pi.

---

## Stack

- **Python 3.11+**, **uv** for environment and dep management
- **httpx** (async HTTP), **zeroconf** (mDNS), **pydantic v2** (models), **pydantic-settings** (env config)
- **pytest** + **pytest-asyncio** + **respx** (httpx mocking) for tests
- **Ruff** (lint + format) with `max-complexity = 15`, `select = ["ALL"]` minus narrow ignores
- **ESLint** flat config (maxed) + **Prettier** for JS/TS

## Open questions for future milestones

- Command payload shape — exact schema in `contracts/` (colors, effects, segments, matrix coords).
- Auth between `wrangler` and `api` — shared-secret bearer token vs. mTLS vs. something else.
- Multi-WLED routing — how `wrangler` decides which device a Command targets when multiple are present.
- Whether `wrangler` persists scan results (SQLite vs. JSON file vs. in-memory only).

These are intentionally deferred; the scanner milestone is complete without resolving them.
