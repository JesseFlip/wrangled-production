# apps/wrangler — Pi Agent

## Purpose
Runs on the Raspberry Pi. Responsible for:
- Discovering WLEDs on the LAN (mDNS + sweep).
- Holding a WebSocket connection out to `apps/api` (future milestone).
- Pushing commands to WLEDs via their HTTP JSON API (future milestone).
- Serving `apps/wrangler-ui/dist/` as a local config panel (future milestone).

**Milestones shipped:** M1 scanner (discovery + CLI), M2 command pusher (`wrangler send ...`).

## Run locally

    cd apps/wrangler
    uv sync

    # Discovery
    uv run wrangler scan             # mDNS-first with sweep fallback
    uv run wrangler scan --sweep     # force sweep in addition to mDNS
    uv run wrangler scan --no-mdns   # sweep only
    uv run wrangler scan --json      # JSON output

    # Push commands (uses mDNS auto-discovery; --ip or --name to target explicitly)
    uv run wrangler send color red --brightness 120
    uv run wrangler send brightness 80
    uv run wrangler send effect fire --speed 180
    uv run wrangler send text "Hello PyTexas" --color orange --speed 160
    uv run wrangler send preset pytexas       # curated scene
    uv run wrangler send emoji 🔥             # emoji shortcut
    uv run wrangler send power off

    # Web UI + REST API (serves built wrangler-ui at :8501)
    uv run wrangler serve                     # http://localhost:8501
    uv run wrangler serve --host 0.0.0.0 --port 8501
    uv run wrangler serve --no-initial-scan

### Dial home to the central api

Set these env vars so `wrangler serve` opens an outbound WS to `apps/api`:

    export WRANGLED_API_URL=ws://localhost:8500/ws
    export WRANGLED_AUTH_TOKEN=devtoken
    export WRANGLED_WRANGLER_ID=pi-venue    # optional; defaults to hostname

Without `WRANGLED_API_URL`, the hub client is inactive — wrangler runs
exactly as before.

For UI development with live reload, run the Vite dev server too:

    cd ../wrangler-ui && npm run dev          # :8511 with /api/* proxied to :8501

## Test

    uv run pytest                    # unit tests
    uv run pytest -m live            # opt-in live test against 10.0.6.207

## Key modules
- `scanner/mdns.py` — zeroconf-based discovery
- `scanner/sweep.py` — concurrent HTTP probe across a subnet
- `scanner/probe.py` — parses `/json/info` into a `WledDevice`
- `scanner/netinfo.py` — detects the local `/24`
- `scanner/__init__.py` — public `scan(opts)` orchestrator
- `pusher.py` — takes a `Command` from `wrangled_contracts`, POSTs `/json/state`
- `server/app.py` — FastAPI factory (CORS, static UI mount, healthz)
- `server/devices.py` — `/api/devices/*` + `/api/scan` routes
- `server/metadata.py` — `/api/effects` + `/api/presets` + `/api/emoji`
- `server/registry.py` — in-memory device map with scan lock
- `server/wled_client.py` — WLED read + cfg HTTP helpers
- `cli.py` — argparse CLI (`scan` + `send` + `serve` subcommands)

## Gotchas
- Some networks block mDNS. The scanner falls back to sweep when mDNS returns zero candidates.
- The probe timeout is 2s per device; 32-way concurrency by default.
