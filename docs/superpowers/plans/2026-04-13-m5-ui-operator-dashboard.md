# M5-UI: Operator Control Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static dashboard with an operator control surface (device grid + shared controls + global fanout + system footer), add metadata + rename endpoints to api, port wrangler-ui's control components.

**Architecture:** Dashboard becomes a two-view React app (hash routing: `#/` = Control, `#/about` = Story). API gains metadata endpoints (contracts data) + WS-proxied rename. Control view ports wrangler-ui's tab components, adds DeviceGrid with per-card live state, AuthGate for token prompt, and "Apply to ALL" fanout.

**Tech Stack:** Vite + React (plain JSX), FastAPI, pydantic v2. Same design tokens as wrangler-ui. No new npm deps.

Spec: `docs/superpowers/specs/2026-04-13-m5-ui-operator-dashboard-design.md`

## File Structure

```
packages/contracts/src/wrangled_contracts/
  hub.py                          # MODIFY: add SetDeviceName, SetDeviceNameResult to unions

apps/api/src/api/server/
  rest.py                         # MODIFY: add metadata + rename endpoints
  hub.py                          # MODIFY: add send_rename method
  ws.py                           # MODIFY: dispatch SetDeviceNameResult

apps/wrangler/src/wrangler/
  hub_client.py                   # MODIFY: handle SetDeviceName

apps/dashboard/
  vite.config.js                  # MODIFY: outDir → ../api/static/dashboard
  package.json                    # MODIFY: build script outDir
  src/
    App.jsx                       # REWRITE: hash router + nav
    index.css                     # REWRITE: copy wrangler-ui design tokens
    api.js                        # CREATE: fetch wrappers with bearer auth
    views/
      ControlView.jsx             # CREATE: main operator view
      StoryView.jsx               # CREATE: extracted from current App.jsx
    components/
      AuthGate.jsx                # CREATE
      DeviceGrid.jsx              # CREATE
      DeviceCard.jsx              # CREATE
      ControlPanel.jsx            # CREATE
      SystemFooter.jsx            # CREATE
      ColorTab.jsx                # PORT from wrangler-ui (read + adapt)
      EffectTab.jsx               # PORT from wrangler-ui
      TextTab.jsx                 # PORT from wrangler-ui
      PresetTab.jsx               # PORT from wrangler-ui
      EmojiTab.jsx                # PORT from wrangler-ui
      BrightnessSlider.jsx        # PORT from wrangler-ui
```

---

## Task 1: Protocol — SetDeviceName + SetDeviceNameResult

**Files:**
- Modify: `packages/contracts/src/wrangled_contracts/hub.py`
- Modify: `packages/contracts/src/wrangled_contracts/__init__.py`
- Modify: `packages/contracts/tests/test_hub_contracts.py`

- [ ] **Step 1: Add 2 roundtrip tests** for SetDeviceName and SetDeviceNameResult in `test_hub_contracts.py`. Assert kind discriminator works, field validation (name min_length=1, max_length=32).

- [ ] **Step 2: Run — verify fail** (`ImportError`)

- [ ] **Step 3: Add the two classes to `hub.py`**

```python
class SetDeviceName(_Frozen):
    kind: Literal["set_device_name"] = "set_device_name"
    request_id: str
    mac: str
    name: str = Field(min_length=1, max_length=32)

class SetDeviceNameResult(_Frozen):
    kind: Literal["set_device_name_result"] = "set_device_name_result"
    request_id: str
    device: WledDevice | None = None
    error: str | None = None
```

Add `SetDeviceName` to `ApiMessage` union. Add `SetDeviceNameResult` to `WranglerMessage` union. Export both from `__init__.py`.

- [ ] **Step 4: Run tests + lint + commit**

```bash
git commit -m "feat(contracts): add SetDeviceName/Result WS envelope"
```

---

## Task 2: api — metadata endpoints + rename (REST + Hub)

**Files:**
- Modify: `apps/api/src/api/server/rest.py`
- Modify: `apps/api/src/api/server/hub.py`
- Modify: `apps/api/src/api/server/ws.py`
- Create: `apps/api/tests/test_rest_metadata.py`
- Modify: `apps/api/tests/test_rest_routing.py` (add rename test)
- Create: `apps/api/tests/test_hub_rename.py`

### Metadata endpoints (in `rest.py`)

Add to `build_rest_router`:

```python
from wrangled_contracts import EFFECT_FX_ID, EMOJI_COMMANDS, PRESETS
# ... (import the _summarize helper or inline it)

@router.get("/effects")
def list_effects(): return {"effects": list(EFFECT_FX_ID.keys())}

@router.get("/presets")
def list_presets(): return {"presets": list(PRESETS.keys())}

@router.get("/emoji")
def list_emoji(): return {"emoji": {k: _summarize(v) for k, v in EMOJI_COMMANDS.items()}}
```

Port the `_summarize` function from `apps/wrangler/src/wrangler/server/metadata.py`.

### Rename endpoint (in `rest.py`)

```python
from pydantic import BaseModel, Field

class _RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=32)

@router.put("/devices/{mac}/name")
async def put_name(mac: str, body: _RenameBody) -> WledDevice:
    # ... lookup device, call hub.send_rename, return result
```

### Hub.send_rename (in `hub.py`)

Same pattern as `send_command` — create future, send `SetDeviceName`, await `SetDeviceNameResult`, return the `WledDevice`. Add `SetDeviceNameResult` handling to `resolve_response`.

### WS dispatch (in `ws.py`)

Add `SetDeviceNameResult` to the imports and pass it through `hub.resolve_response` in `_main_loop`.

### Tests

- `test_rest_metadata.py` — 3 tests: effects returns 10 names, presets returns 3, emoji has fire/rainbow.
- `test_hub_rename.py` — Hub.send_rename resolves when SetDeviceNameResult arrives; times out.
- `test_rest_routing.py` — append: PUT /api/devices/{mac}/name succeeds with fake wrangler + 404 on unknown mac.

- [ ] **Step 1: Write all failing tests**
- [ ] **Step 2: Run — verify fail**
- [ ] **Step 3: Implement metadata + rename + hub method + ws dispatch**
- [ ] **Step 4: Run tests + lint + commit**

```bash
git commit -m "feat(api): metadata endpoints + WS-proxied rename"
```

---

## Task 3: Wrangler hub_client — handle SetDeviceName

**Files:**
- Modify: `apps/wrangler/src/wrangler/hub_client.py`
- Modify: `apps/wrangler/tests/test_hub_client.py`

- [ ] **Step 1: Add failing test** — fake WS server sends SetDeviceName → hub_client calls `set_name` (mocked) + `probe_device` (mocked) → sends SetDeviceNameResult. Pattern: identical to the existing `test_hub_client_responds_to_command` but with rename message shapes.

- [ ] **Step 2: Implement** — add `_handle_set_device_name` method to HubClient following the exact pattern of `_handle_command`:

```python
async def _handle_set_device_name(self, msg: SetDeviceName) -> None:
    device = self._registry.get(msg.mac)
    if device is None:
        result = SetDeviceNameResult(request_id=msg.request_id, error=f"unknown: {msg.mac}")
    else:
        async with httpx.AsyncClient() as client:
            try:
                await set_name(client, device, msg.name)
                refreshed = await probe_device(client, device.ip, source="mdns", timeout=2.0)
                result = SetDeviceNameResult(request_id=msg.request_id, device=refreshed)
                if refreshed:
                    self._registry.put(refreshed)
            except WledUnreachableError as exc:
                result = SetDeviceNameResult(request_id=msg.request_id, error=str(exc))
    await self._send(result.model_dump_json())
```

Wire the dispatch in `_handle` alongside RelayCommand/GetState/Rescan.

- [ ] **Step 3: Run tests + lint + commit**

```bash
git commit -m "feat(wrangler): hub_client handles SetDeviceName rename"
```

---

## Task 4: Dashboard restructure — extract StoryView, hash routing, design tokens, vite config

**Files:**
- Modify: `apps/dashboard/vite.config.js`
- Modify: `apps/dashboard/package.json`
- Rewrite: `apps/dashboard/src/index.css`
- Rewrite: `apps/dashboard/src/App.jsx`
- Create: `apps/dashboard/src/views/StoryView.jsx`
- Create: `apps/dashboard/src/views/ControlView.jsx` (placeholder for now)

**Key steps:**

- [ ] **Step 1: Read `apps/dashboard/src/App.jsx`** — the entire current content (500+ lines of PyTexas story). Move ALL of it into `views/StoryView.jsx` as `export default function StoryView()`. Keep every element, every style, every section identical.

- [ ] **Step 2: Write new `App.jsx`** — hash-based routing:

```jsx
import { useEffect, useState } from 'react';
import ControlView from './views/ControlView.jsx';
import StoryView from './views/StoryView.jsx';

export default function App() {
  const [view, setView] = useState(location.hash === '#/about' ? 'about' : 'control');
  useEffect(() => {
    const h = () => setView(location.hash === '#/about' ? 'about' : 'control');
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);
  return (
    <div className="app-shell">
      <nav className="app-header">
        <h1 className="app-title">Wrang<span className="app-title-accent">LED</span></h1>
        <a href="#/" className={view === 'control' ? 'nav-link active' : 'nav-link'}>Control</a>
        <a href="#/about" className={view === 'about' ? 'nav-link active' : 'nav-link'}>Story</a>
      </nav>
      {view === 'control' ? <ControlView /> : <StoryView />}
    </div>
  );
}
```

- [ ] **Step 3: Placeholder ControlView** — `export default function ControlView() { return <p>Control coming next…</p>; }`

- [ ] **Step 4: Copy design tokens** — read `apps/wrangler-ui/src/index.css` and copy its `:root` block + base styles into `apps/dashboard/src/index.css`. Add nav styles (`.nav-link`, `.nav-link.active`).

- [ ] **Step 5: Update `vite.config.js`** — add `build: { outDir: '../api/static/dashboard', emptyOutDir: true }`. Update `server.port: 8510`. Add proxy config: `'/api': 'http://localhost:8500'`, `'/healthz': 'http://localhost:8500'`.

- [ ] **Step 6: Update `package.json`** build script if needed.

- [ ] **Step 7: `npm install && npm run build && npm run lint`**

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(dashboard): extract StoryView, add hash routing + design tokens"
```

---

## Task 5: api.js + AuthGate

**Files:**
- Create: `apps/dashboard/src/api.js`
- Create: `apps/dashboard/src/components/AuthGate.jsx`

- [ ] **Step 1: `api.js`** — same pattern as wrangler-ui's `api.js` but with bearer auth header from localStorage. Read `apps/wrangler-ui/src/api.js` for the exact pattern. Add `Authorization: Bearer <token>` to every request when token is set. Export: `listDevices`, `getState`, `sendCommand`, `rename`, `rescan`, `listEffects`, `listPresets`, `listEmoji`, `listWranglers`.

- [ ] **Step 2: `AuthGate.jsx`** — wraps app. On mount: try `listDevices()`. If succeeds, render children. If 401, show modal with input + submit. On submit, save token to localStorage + retry. "Logout" = clear localStorage + reload.

- [ ] **Step 3: Wire AuthGate into App.jsx** — wrap the router content in `<AuthGate>...</AuthGate>`.

- [ ] **Step 4: Lint + commit**

```bash
git commit -m "feat(dashboard): api.js fetch layer + AuthGate token prompt"
```

---

## Task 6: DeviceGrid + DeviceCard

**Files:**
- Create: `apps/dashboard/src/components/DeviceGrid.jsx`
- Create: `apps/dashboard/src/components/DeviceCard.jsx`
- Modify: `apps/dashboard/src/views/ControlView.jsx`

- [ ] **Step 1: `DeviceCard.jsx`** — displays: name (bold), ON/OFF dot, color swatch (64px with glow like wrangler-ui's LiveState), bri, fx, IP + matrix dims, ✏️ rename inline, selected = orange left-border. Read `apps/wrangler-ui/src/components/LiveState.jsx` for the swatch + glow pattern. Read `apps/wrangler-ui/src/components/DeviceSelector.jsx` for the inline-rename pattern.

- [ ] **Step 2: `DeviceGrid.jsx`** — CSS grid of DeviceCards. Polls `api.listDevices()` every 5s. Passes `onSelect(mac)` to cards. Selected card polls `api.getState(mac)` every 2s. Rescan button fires `api.rescan()`.

- [ ] **Step 3: Wire into ControlView** — `<DeviceGrid selectedMac={selectedMac} onSelect={setSelectedMac} />`

- [ ] **Step 4: Lint + commit**

```bash
git commit -m "feat(dashboard): DeviceGrid + DeviceCard with live state polling"
```

---

## Task 7: ControlPanel + port all 5 tabs + BrightnessSlider

**Files:**
- Create: `apps/dashboard/src/components/ControlPanel.jsx`
- Create: `apps/dashboard/src/components/ColorTab.jsx`
- Create: `apps/dashboard/src/components/EffectTab.jsx`
- Create: `apps/dashboard/src/components/TextTab.jsx`
- Create: `apps/dashboard/src/components/PresetTab.jsx`
- Create: `apps/dashboard/src/components/EmojiTab.jsx`
- Create: `apps/dashboard/src/components/BrightnessSlider.jsx`
- Modify: `apps/dashboard/src/views/ControlView.jsx`

- [ ] **Step 1: Port each tab** — read each file from `apps/wrangler-ui/src/components/` and create the dashboard version. Changes needed per file:
  - Import `{ api }` from `'../api.js'` instead of wrangler-ui's api.
  - For `EffectTab`, `PresetTab`, `EmojiTab`: the api calls (`api.listEffects()`, etc.) are the same shape.
  - Otherwise identical code.

- [ ] **Step 2: `ControlPanel.jsx`** — "Apply to ALL" toggle checkbox, tab nav (Color/Effect/Text/Preset/Emoji), active tab content, brightness + power. Takes props: `selectedMac`, `allMacs`, `applyToAll`, `onToggleAll`, `onSend(command)`.

- [ ] **Step 3: Wire into ControlView** — `onSend` logic: if `applyToAll`, iterate `allMacs` and `api.sendCommand(mac, cmd)` for each; else `api.sendCommand(selectedMac, cmd)`.

- [ ] **Step 4: Lint + commit**

```bash
git commit -m "feat(dashboard): control panel with ported tabs + Apply to ALL"
```

---

## Task 8: SystemFooter + ControlView assembly

**Files:**
- Create: `apps/dashboard/src/components/SystemFooter.jsx`
- Modify: `apps/dashboard/src/views/ControlView.jsx` (final assembly)

- [ ] **Step 1: `SystemFooter.jsx`** — polls `api.listWranglers()` every 10s. Renders:
  ```
  Wranglers: pi-venue (1 device, 3s ago) · pi-home (1 device, 1s ago)
  Discord: ⚫ not configured
  ```
  Time formatting: `Date.now() - Date.parse(last_pong_at)` → "Ns ago" / "Nm ago".

- [ ] **Step 2: Assemble ControlView** — final layout:
  ```
  DeviceGrid (top)
  ControlPanel (middle)
  SystemFooter (bottom)
  ```
  State: `selectedMac`, `applyToAll`, `error`. All wired together.

- [ ] **Step 3: Lint + commit**

```bash
git commit -m "feat(dashboard): SystemFooter + complete ControlView assembly"
```

---

## Task 9: Build integration + scripts

**Files:**
- Modify: `build.sh`
- Modify: `apps/dashboard/CLAUDE.md`

- [ ] **Step 1: `build.sh`** — the existing step `cd apps/dashboard && npm install && npm run build` already works; the vite config change (Task 4) repoints the output. Verify `apps/api/static/dashboard/index.html` exists after build.

- [ ] **Step 2: Update `apps/dashboard/CLAUDE.md`** — document the two views, the hash routing, the auth flow, the api dependency.

- [ ] **Step 3: Run `./build.sh`**

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(m5-ui): update build + CLAUDE.md for operator dashboard"
```

---

## Task 10: Live verification

Manual, against real hardware.

- [ ] **Step 1: Start api + wrangler** (three terminals as before)
- [ ] **Step 2: Open `http://localhost:8500/`** — auth modal → enter token → Control view loads
- [ ] **Step 3: Verify device grid shows 1+ WLEDs with live state swatches**
- [ ] **Step 4: Click a color chip → matrix changes, swatch updates on next poll**
- [ ] **Step 5: Toggle "Apply to ALL" + click a preset → all devices change**
- [ ] **Step 6: Rename a device → card label updates**
- [ ] **Step 7: Click "Story" nav link → PyTexas build-log page renders**
- [ ] **Step 8: SystemFooter shows connected wranglers**
- [ ] **Step 9: CLI `wrangler scan` / `wrangler send` still work locally**

---

## Self-Review Notes

**Spec coverage:**
- Metadata endpoints → T2
- Rename via WS proxy → T1 (protocol) + T2 (api hub+rest) + T3 (wrangler handler)
- Dashboard restructure → T4
- AuthGate → T5
- DeviceGrid + DeviceCard → T6
- Control tabs → T7
- SystemFooter + Apply to ALL → T8
- Build integration → T9
- Live verification → T10

**Type consistency:** `SetDeviceName`/`SetDeviceNameResult` referenced consistently across T1 (definition), T2 (hub dispatch), T3 (wrangler handler). Hub method `send_rename(mac, name, timeout)` consistent between T2 definition and T2 REST caller.

**No placeholders.** Backend tasks have concrete code. UI tasks reference specific source files to read + adapt from (wrangler-ui). Every step ends with a lint + commit.
