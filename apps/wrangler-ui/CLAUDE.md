# apps/wrangler-ui — Pi Config Panel (Vite + React)

## Purpose
Browser UI for `apps/wrangler/`. Shipped as static assets served by wrangler's FastAPI on port 8501. Lets the user drive a WLED matrix (color, brightness, effect, text, preset, emoji, power) and rename devices.

## Run locally

    cd apps/wrangler-ui
    npm install
    npm run dev               # Vite on http://localhost:8511
                              # proxies /api/* and /healthz to :8501

## Build

    npm run build             # writes ../wrangler/static/wrangler-ui/

## Dev prerequisite
Run `apps/wrangler/` in another terminal: `uv run wrangler serve`

## Key modules
- `src/App.jsx` — top-level layout + tabs
- `src/api.js` — fetch() wrappers (typed by hand)
- `src/components/*` — DeviceSelector, LiveState, Color/Effect/Text/Preset/Emoji/Power tabs, BrightnessSlider

## Gotchas
- Same-origin in prod. Dev server uses Vite's proxy.
- No TypeScript — plain JSX to match apps/dashboard.
