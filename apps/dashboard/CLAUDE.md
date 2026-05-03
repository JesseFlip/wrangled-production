# apps/dashboard — Operator Dashboard + PyTexas Story

## Purpose
Two-view Vite/React app served by `apps/api/` on port 8500:
- **`#/` (Control)** — Operator dashboard: device grid with live state, color/effect/text/preset/emoji/power controls, brightness slider, "Apply to ALL" toggle, wranglers + Discord footer.
- **`#/about` (Story)** — PyTexas build-log story (timeline, hardware, team, conference details).

Auth-gated: prompts for a bearer token on first visit (stored in localStorage).

## Run locally

    cd apps/dashboard
    npm install
    npm run dev      # Vite on http://localhost:8510, proxies /api/* to :8500

Requires `apps/api` running on :8500 in another terminal.

## Build

    npm run build    # outputs to ../api/static/dashboard/

## Key files
- `src/App.jsx` — hash router + nav (Control / Story)
- `src/api.js` — fetch wrappers with bearer auth from localStorage
- `src/views/ControlView.jsx` — operator dashboard
- `src/views/StoryView.jsx` — PyTexas story (extracted from original App.jsx)
- `src/components/AuthGate.jsx` — token prompt
- `src/components/DeviceGrid.jsx` + `DeviceCard.jsx` — device list + live state
- `src/components/ControlPanel.jsx` — tabs + power + brightness
- `src/components/ColorTab.jsx`, `EffectTab.jsx`, `TextTab.jsx`, `PresetTab.jsx`, `EmojiTab.jsx` — ported from wrangler-ui
- `src/components/SystemFooter.jsx` — wranglers list + Discord placeholder

## Gotchas
- Build output goes to `../api/static/dashboard/`, NOT local `dist/`.
- GitHub Pages deploy (`.github/workflows/deploy.yml`) still points at this app but the story is now at `#/about`. Deploy may need rework.
- Design tokens in `index.css` match `apps/wrangler-ui/` — same dark theme.
