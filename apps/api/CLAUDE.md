# apps/api — Central Hub (FastAPI)

## Purpose
The central WrangLED server. Holds WebSocket connections to wranglers that dial home, exposes REST for command senders (dashboard, Discord, curl), and serves the built `apps/dashboard/` as static.

## Run locally

    cd apps/api
    uv sync
    WRANGLED_AUTH_TOKEN=devtoken uv run api serve

## Test

    uv run pytest

## Env vars
- `WRANGLED_AUTH_TOKEN` — pre-shared key. Required on both api and wrangler. Unset = dev mode.
- `WRANGLED_HOST` — bind host (default 127.0.0.1)
- `WRANGLED_PORT` — bind port (default 8500)

## Key modules
- `server/app.py` — FastAPI factory, CORS, static mount
- `server/auth.py` — bearer-token dependency
- `server/hub.py` — WranglerConnection manager + command routing
- `server/ws.py` — `/ws` endpoint
- `server/rest.py` — `/api/*` endpoints
- `cli.py` — argparse CLI (`serve`)
