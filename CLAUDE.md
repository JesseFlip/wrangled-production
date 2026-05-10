# WrangLED — Monorepo Conventions

## Layout
- `apps/dashboard/` — Vite/React "Command Center" UI. Built static assets served by `apps/api/` in prod; deployed standalone to GitHub Pages for the public build log.
- `apps/api/` — FastAPI central hub. Holds outbound WS connections from wranglers (dial-home), exposes REST for command senders, serves built dashboard static. Pre-shared key auth via `WRANGLED_AUTH_TOKEN` (unset = dev mode).
- `apps/wrangler-ui/` — Vite/React local config panel. Built static assets served by `apps/wrangler/`.
- `apps/wrangler/` — FastAPI + agent running on the Raspberry Pi. Scans for WLEDs, holds WS to api, pushes to WLEDs.
- `packages/contracts/` — Shared pydantic v2 models imported by every Python app.
- `infra/pi/` — systemd units, install scripts for Pi deployment.

## Ports
| Service                | Port  |
|------------------------|-------|
| `api` FastAPI          | 8500  |
| `wrangler` FastAPI     | 8501  |
| `dashboard` Vite dev   | 8510  |
| `wrangler-ui` Vite dev | 8511  |

Vite dev servers proxy `/api/*` and `/ws` to their paired FastAPI so the React code is environment-agnostic.

## Scripts
- `./build.sh` — install all deps, build UIs, lint, test.
- `./lint.sh [--fix]` — run Ruff + ESLint across the repo.
- `./dev.sh` — start all dev processes concurrently.

## Python
- Python 3.11+ via `uv`. Each app owns its own `pyproject.toml` and `.venv`.
- Ruff config lives at repo root (`ruff.toml`). Every app's `pyproject.toml` uses `extend = "../../ruff.toml"`.
- Tests via pytest. Models live in `packages/contracts/` and are imported as `wrangled_contracts`.

## JS/TS
- Vite + React, ESLint flat config maxed (strict TS-style rules, a11y, import order, complexity ≤ 15). Prettier for formatting.

## Design principles
- `api` is the command hub. Interfaces (Discord, dashboard, CLIs) produce Commands into it.
- `wrangler` is outbound-only. It dials `api`; no inbound ports exposed beyond the local LAN config UI.
- Optional interfaces: Discord gateway only if `DISCORD_BOT_TOKEN` is set; `wrangler` connects only if `WRANGLED_API_URL` is set.
- Shared pydantic `contracts/` prevents schema drift between producer and consumer.

## Deployment & Synchronization
- **Production Sync**: Changes made to `index.html` in `wrangled-production` MUST be synchronized back to `wrangled-dashboard/apps/dashboard/original_index.html`.
- **GitHub Pushing**: ALWAYS push changes to GitHub immediately after making edits to ensure synchronization between local and remote environments.
    - Command: `git add <files>; git commit -m "<message>"; git push origin master`
