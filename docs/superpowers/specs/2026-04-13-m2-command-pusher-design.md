# Milestone 2: Command Contract + WLED Pusher — Design

**Date:** 2026-04-13
**Status:** Approved (brainstorm complete, pending spec review)
**Target:** `packages/contracts/` (Command model + lookups) and `apps/wrangler/` (pusher + CLI `send`)

## Context

Milestone 1 shipped: monorepo scaffold, scanner, CLI `wrangler scan`. Live-tested against the 64×8 WLED matrix at `10.0.6.207`. Remote control via `/json/state` is confirmed working end-to-end (we drove scrolling text, effects, colors, brightness, and panel config by hand with curl).

M2 formalizes that control surface as a typed, tested Python API:

1. A pydantic `Command` contract in `packages/contracts/` — one discriminated union covering every user-intent type (color, brightness, effect, text, preset, power).
2. A `pusher` module in `apps/wrangler/` that turns a `Command` into an HTTP POST to a WLED's `/json/state`.
3. A `wrangler send` CLI subcommand so we can drive the matrix from the shell.

M2 produces the foundation the Discord bot (M4) and the FastAPI hub (M3) will consume without schema changes.

## Goals

1. Typed, validated Command vocabulary that maps cleanly to Discord slash commands and emoji shortcuts.
2. Pure unit-testable pusher (no direct WLED dependency in tests).
3. Live end-to-end validation against the real matrix.
4. CLI coverage for every Command variant (replaces the curl session from M1 verification).

## Non-goals

- WebSocket client between `wrangler` and `api` (M3).
- Discord bot integration (M4).
- Rate limiting / user cooldowns / profanity filtering (M4 concerns; Command model just carries data).
- Multi-device fanout or device-group targeting (single device is fine for the venue's one matrix).
- Persistence of command history.
- Auth.
- PyTexas-logo image rendering to the matrix (future preset, out of scope).

---

## Command Contract (`packages/contracts/src/wrangled_contracts/commands.py`)

### Discriminated union

```python
Command = Annotated[
    ColorCommand | BrightnessCommand | EffectCommand
  | TextCommand | PresetCommand | PowerCommand,
    Field(discriminator="kind"),
]
```

Every variant has a `kind: Literal["..."]` tag so pydantic routes inbound JSON to the right class.

### Variants

| Variant | Fields | Notes |
|---|---|---|
| `ColorCommand` | `color: RGB`, `brightness: int \| None (0-200)` | solid color; `fx=0` on wire |
| `BrightnessCommand` | `brightness: int (0-200)` | bri-only change |
| `EffectCommand` | `name: EffectName`, `color? RGB`, `speed? 0-255`, `intensity? 0-255`, `brightness? 0-200` | curated effect; resolves to WLED fx id |
| `TextCommand` | `text: str (max 64)`, `color? RGB`, `speed: int (32-240, default 128)`, `brightness? 0-200` | scrolling text via fx 122 |
| `PresetCommand` | `name: PresetName` | expands to multiple commands |
| `PowerCommand` | `on: bool` | toggle |

### Enums

```python
EffectName = Literal[
    "solid", "breathe", "rainbow", "fire", "sparkle",
    "fireworks", "matrix", "pride", "chase", "noise",
]
PresetName = Literal["pytexas", "party", "chill"]
```

### Lookups (also in `commands.py`)

```python
EFFECT_FX_ID: dict[EffectName, int] = {
    "solid": 0, "breathe": 2, "rainbow": 9, "fire": 66, "sparkle": 20,
    "fireworks": 42, "matrix": 63, "pride": 93, "chase": 28, "noise": 70,
}

EMOJI_COMMANDS: dict[str, Command] = {
    "🔥": EffectCommand(name="fire"),
    "🌈": EffectCommand(name="rainbow"),
    "⚡": EffectCommand(name="sparkle", speed=220),
    "🎉": EffectCommand(name="fireworks"),
    "🐍": EffectCommand(name="matrix"),
    "❤️": ColorCommand(color=RGB(r=255, g=0, b=0)),
    "💙": ColorCommand(color=RGB(r=0, g=0, b=255)),
    "💚": ColorCommand(color=RGB(r=0, g=200, b=0)),
    "💜": ColorCommand(color=RGB(r=180, g=0, b=255)),
    "🧡": ColorCommand(color=RGB(r=255, g=100, b=0)),
    "🖤": PowerCommand(on=False),
    "🔴": ColorCommand(color=RGB(r=255, g=0, b=0)),
    "🟢": ColorCommand(color=RGB(r=0, g=200, b=0)),
    "🔵": ColorCommand(color=RGB(r=0, g=0, b=255)),
    "🟠": ColorCommand(color=RGB(r=255, g=100, b=0)),
    "🟡": ColorCommand(color=RGB(r=255, g=220, b=0)),
    "🟣": ColorCommand(color=RGB(r=180, g=0, b=255)),
    "⚫": PowerCommand(on=False),
    "⚪": ColorCommand(color=RGB(r=255, g=255, b=255)),
}

PRESETS: dict[PresetName, list[Command]] = {
    "pytexas": [
        ColorCommand(color=RGB(r=191, g=87, b=0), brightness=180),
        TextCommand(text="PyTexas 2026", color=RGB(r=255, g=100, b=0), speed=160),
    ],
    "party":   [EffectCommand(name="rainbow", speed=240, brightness=200)],
    "chill":   [EffectCommand(name="breathe", color=RGB(r=0, g=60, b=180), speed=48, brightness=120)],
}
```

### Helpers

- `RGB.parse(value: str | tuple | RGB | dict) -> RGB` — accepts CSS named colors (`"red"`, `"orange"`, ...), hex (`"#ff00aa"` or `"ff00aa"`), RGB tuples `(255, 0, 170)`, color emoji, or dict/RGB passthrough. Raises `ValueError` on unparseable input.
- `command_from_emoji(emoji: str) -> Command | None` — lookup in `EMOJI_COMMANDS`, returns None if unknown.

### Safety caps (enforced at validation)

| Field | Cap | Reason |
|---|---|---|
| Brightness | 0–200 (not 255) | avoid eye-searing at close range in the venue |
| Text length | ≤ 64 chars | prevents runaway scrolling |
| Text speed | 32–240 | matches WLED's `sx` usable range |
| Effect speed/intensity | 0–255 | WLED's full range, no special cap |

---

## Pusher (`apps/wrangler/src/wrangler/pusher.py`)

### Public surface

```python
class PushResult(BaseModel):
    ok: bool
    status: int | None = None
    error: str | None = None


async def push_command(
    client: httpx.AsyncClient,
    device: WledDevice,
    command: Command,
    *,
    timeout: float = 2.0,
) -> PushResult: ...
```

### Behavior

`push_command` is a `match command` dispatch. Each variant has a private `_build_*` function returning a WLED `/json/state` body (or a list of bodies for presets). The dispatcher then POSTs each body to `http://<device.ip>/json/state` using the provided `httpx.AsyncClient`.

Never raises. Transport / non-200 / JSON errors surface as `PushResult(ok=False, ...)`.

### Builders

```python
def _build_color(cmd: ColorCommand) -> dict: ...
def _build_brightness(cmd: BrightnessCommand) -> dict: ...
def _build_effect(cmd: EffectCommand) -> dict: ...
def _build_text(cmd: TextCommand) -> dict: ...
def _build_power(cmd: PowerCommand) -> dict: ...
def _build_preset(cmd: PresetCommand) -> list[dict]: ...   # fans out
```

### Wire shapes (derived from M1 live testing)

Color (solid):
```json
{"on": true, "bri": 180, "seg": [{"fx": 0, "col": [[r, g, b], [0,0,0], [0,0,0]]}]}
```
`bri` is only included if `cmd.brightness is not None`.

Effect:
```json
{"on": true, "bri": 180, "seg": [{"fx": <id>, "sx": <speed>, "ix": <intensity>, "col": [[r,g,b],[0,0,0],[0,0,0]]}]}
```
`sx`, `ix`, `col`, and `bri` only included if the Command sets them.

Text (scrolling):
```json
{"on": true, "bri": 180, "seg": [{"fx": 122, "n": "<text>", "sx": <speed>, "ix": 128, "o1": false, "col": [[r,g,b],[0,0,0],[0,0,0]]}]}
```
`o1: false` forces scroll even if the text fits in the matrix width (the problem we hit in M1 verification).

Brightness:
```json
{"bri": <0-200>}
```

Power:
```json
{"on": true | false}
```

Preset: the dispatcher calls `_build_preset` which looks up `PRESETS[name]`, recursively builds each sub-command, and returns a list of bodies POSTed sequentially.

---

## CLI Additions (`apps/wrangler/src/wrangler/cli.py`)

New `send` subcommand with one sub-sub-command per Command variant.

```
uv run wrangler send color red
uv run wrangler send color "#ff00aa" --brightness 120
uv run wrangler send brightness 80
uv run wrangler send effect fire --speed 180
uv run wrangler send effect rainbow --color orange
uv run wrangler send text "Hello PyTexas" --color blue --speed 160
uv run wrangler send preset pytexas
uv run wrangler send power off
uv run wrangler send emoji 🔥
```

### Device targeting

Device targeting flags apply to every `send` subcommand:

- No flag (default): quick scan (`mdns_timeout=2.0`), expect exactly one result. Error on 0 or >1 — message tells the user to use `--ip` or `--name`.
- `--ip 10.0.6.207`: skip scan, probe that IP directly.
- `--name WLED-Gledopto`: scan, filter results by name substring.

The CLI prints a one-line ack of the `PushResult` and exits 0 on `ok=True`, non-zero on failure.

---

## Tests

### `packages/contracts/tests/test_commands.py`

- Each variant roundtrip: construct → `model_dump(mode="json")` → `TypeAdapter(Command).validate_python(...)` → equal.
- `RGB.parse` accepts each of: CSS name, hex with `#`, hex without `#`, `(r, g, b)` tuple, color emoji, existing `RGB`.
- `RGB.parse` rejects empty string, unknown name, bad hex length, out-of-range tuple.
- `command_from_emoji` returns the expected Command for each key; returns None for unknown emoji.
- Brightness 201 → `ValidationError`. Text of 65 chars → `ValidationError`. Text speed 31 → `ValidationError`.
- Discriminator dispatch: `{"kind": "color", "color": {"r": 1, "g": 2, "b": 3}}` parses to `ColorCommand`.

### `apps/wrangler/tests/test_pusher.py`

- `_build_color`, `_build_brightness`, `_build_effect`, `_build_text`, `_build_power` — for each, given a Command, produce the expected dict body. Pure, no HTTP.
- `_build_preset` expands `pytexas` to two dict bodies in the right order; `party` to one; `chill` to one.
- `push_command` happy path for each variant using `respx` to mock httpx: assert body sent, returns `PushResult(ok=True, status=200)`.
- `push_command` error paths: `httpx.ReadTimeout` → `PushResult(ok=False, error=...)`; 404 → `PushResult(ok=False, status=404)`.
- Preset happy path: preset POSTs once per sub-command in order; all succeeding yields `PushResult(ok=True)`.
- Preset mid-failure: if the 2nd body fails, `push_command` returns `PushResult(ok=False)` with details about which sub-command failed.

### `apps/wrangler/tests/test_cli_send.py`

- `wrangler send color red` → calls `push_command` with `ColorCommand(color=RGB(r=255,g=0,b=0))`.
- `wrangler send color "#ff00aa" --brightness 120` → `ColorCommand(color=..., brightness=120)`.
- `wrangler send brightness 80` → `BrightnessCommand(brightness=80)`.
- `wrangler send effect fire --speed 180` → `EffectCommand(name="fire", speed=180)`.
- `wrangler send text "Hi" --color blue` → `TextCommand(text="Hi", color=RGB(0,0,255))`.
- `wrangler send preset pytexas` → `PresetCommand(name="pytexas")`.
- `wrangler send power off` → `PowerCommand(on=False)`.
- `wrangler send emoji 🔥` → resolves to `EffectCommand(name="fire")`.
- `--ip 10.0.6.207` bypasses mDNS: device probed directly.
- Device discovery ambiguity: 2 devices found, no `--ip`/`--name` → exit 2 with helpful message.
- Failure from pusher → non-zero exit, error printed to stderr.

### `apps/wrangler/tests/test_live.py` (extension)

Second `@pytest.mark.live` test: sends `ColorCommand(color=RGB(r=0,g=0,b=255), brightness=1)` to `10.0.6.207`, then `probe_device` the same IP and assert `raw_info` shows `on=true` and `bri=1`. Leaves the matrix in a known low-light state.

---

## Dependencies added

- `packages/contracts/` — no new runtime deps (pydantic already present).
- `apps/wrangler/` — no new runtime deps; `httpx` already present.

## Out of scope (for future milestones)

- Command-layering semantics / state diffing (M3 concern: what does api/wrangler do when a Command partially overlaps the current state).
- Animation sequences (timed command chains).
- Device groups / room concepts.
- Per-user quotas (M4 Discord bot).

## Deliverable

At the end of M2:

```bash
uv run wrangler send preset pytexas
```

lights the matrix up in PyTexas orange with "PyTexas 2026" scrolling, and every subcommand above works with live hardware. All tests pass, both live and mocked.
