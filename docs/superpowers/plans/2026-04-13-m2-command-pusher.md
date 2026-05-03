# M2: Command Contract + WLED Pusher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a typed, tested `Command` pydantic model in `packages/contracts/` plus a `pusher` module + `wrangler send` CLI in `apps/wrangler/` that drives the WLED matrix at `10.0.6.207`.

**Architecture:** Discriminated union of six Command variants (color / brightness / effect / text / preset / power). Pusher dispatches via `match` to one pure `_build_*` function per variant; `push_command` POSTs the resulting body (or bodies, for presets) to `/json/state`. CLI adds a `send` subcommand group that constructs Commands from argv and calls the pusher.

**Tech Stack:** pydantic v2, httpx (async), respx (httpx mock), argparse. All existing — no new dependencies.

## Spec reference

Read first: `docs/superpowers/specs/2026-04-13-m2-command-pusher-design.md`.

## File Structure

```
packages/contracts/
├── src/wrangled_contracts/
│   ├── __init__.py               # add re-exports
│   └── commands.py               # NEW: RGB, Command variants, lookups, helpers
└── tests/
    └── test_commands.py          # NEW

apps/wrangler/
├── src/wrangler/
│   ├── pusher.py                 # NEW: PushResult, _build_*, push_command
│   └── cli.py                    # MODIFY: add `send` subparser
└── tests/
    ├── test_pusher.py            # NEW
    ├── test_cli_send.py          # NEW
    └── test_live.py              # MODIFY: add second live test
```

---

## Task 1: `RGB` model + `RGB.parse` helper

**Files:**
- Create: `packages/contracts/src/wrangled_contracts/commands.py`
- Modify: `packages/contracts/src/wrangled_contracts/__init__.py`
- Create: `packages/contracts/tests/test_commands.py`

- [ ] **Step 1: Write failing tests**

`packages/contracts/tests/test_commands.py`:

```python
"""Tests for wrangled_contracts.commands."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wrangled_contracts import RGB


def test_rgb_accepts_valid_ints() -> None:
    assert RGB(r=1, g=2, b=3).model_dump() == {"r": 1, "g": 2, "b": 3}


@pytest.mark.parametrize("bad", [-1, 256, 1000])
def test_rgb_rejects_out_of_range(bad: int) -> None:
    with pytest.raises(ValidationError):
        RGB(r=bad, g=0, b=0)


def test_rgb_parse_passes_through_rgb() -> None:
    base = RGB(r=10, g=20, b=30)
    assert RGB.parse(base) == base


def test_rgb_parse_accepts_tuple() -> None:
    assert RGB.parse((255, 0, 170)) == RGB(r=255, g=0, b=170)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#ff00aa", RGB(r=255, g=0, b=170)),
        ("ff00aa", RGB(r=255, g=0, b=170)),
        ("#FFF", RGB(r=255, g=255, b=255)),
        ("FFF", RGB(r=255, g=255, b=255)),
    ],
)
def test_rgb_parse_hex(value: str, expected: RGB) -> None:
    assert RGB.parse(value) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("red", RGB(r=255, g=0, b=0)),
        ("blue", RGB(r=0, g=0, b=255)),
        ("orange", RGB(r=255, g=100, b=0)),
        ("RED", RGB(r=255, g=0, b=0)),
        ("  green  ", RGB(r=0, g=200, b=0)),
    ],
)
def test_rgb_parse_named(name: str, expected: RGB) -> None:
    assert RGB.parse(name) == expected


@pytest.mark.parametrize(
    ("emoji", "expected"),
    [
        ("🔴", RGB(r=255, g=0, b=0)),
        ("🟢", RGB(r=0, g=200, b=0)),
        ("🔵", RGB(r=0, g=0, b=255)),
        ("🟠", RGB(r=255, g=100, b=0)),
    ],
)
def test_rgb_parse_color_emoji(emoji: str, expected: RGB) -> None:
    assert RGB.parse(emoji) == expected


@pytest.mark.parametrize("bad", ["", "notacolor", "#gg0000", "#12345", "rgb(1,2,3)"])
def test_rgb_parse_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError, match="cannot parse"):
        RGB.parse(bad)


def test_rgb_parse_rejects_out_of_range_tuple() -> None:
    with pytest.raises(ValueError, match="cannot parse"):
        RGB.parse((300, 0, 0))
```

- [ ] **Step 2: Run to verify fail**

```bash
cd packages/contracts
uv run pytest tests/test_commands.py -v
```
Expected: ImportError — `RGB` not in `wrangled_contracts`.

- [ ] **Step 3: Implement RGB**

`packages/contracts/src/wrangled_contracts/commands.py`:

```python
"""Command vocabulary for controlling a WLED device end-to-end.

Every user intent (color change, effect, scrolling text, preset, power)
is expressed as a typed Command variant in a discriminated union. The
wrangler pusher consumes these; the api and Discord bot produce them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (255, 0, 0),
    "green": (0, 200, 0),
    "blue": (0, 0, 255),
    "orange": (255, 100, 0),
    "yellow": (255, 220, 0),
    "cyan": (0, 200, 200),
    "magenta": (255, 0, 180),
    "pink": (255, 120, 180),
    "purple": (180, 0, 255),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "teal": (0, 180, 180),
    "brown": (130, 70, 20),
}

_COLOR_EMOJI: dict[str, tuple[int, int, int]] = {
    "🔴": (255, 0, 0),
    "🟢": (0, 200, 0),
    "🔵": (0, 0, 255),
    "🟠": (255, 100, 0),
    "🟡": (255, 220, 0),
    "🟣": (180, 0, 255),
    "⚫": (0, 0, 0),
    "⚪": (255, 255, 255),
    "🟤": (130, 70, 20),
    "🟥": (255, 0, 0),
    "🟩": (0, 200, 0),
    "🟦": (0, 0, 255),
    "🟧": (255, 100, 0),
    "🟨": (255, 220, 0),
    "🟪": (180, 0, 255),
    "🟫": (130, 70, 20),
}


def _hex_to_tuple(value: str) -> tuple[int, int, int] | None:
    s = value.lstrip("#")
    if len(s) == 3 and all(c in "0123456789abcdefABCDEF" for c in s):
        return (int(s[0] * 2, 16), int(s[1] * 2, 16), int(s[2] * 2, 16))
    if len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s):
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    return None


class RGB(BaseModel):
    """An RGB color, each channel 0-255."""

    model_config = ConfigDict(frozen=True)

    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)

    @classmethod
    def parse(cls, value: object) -> RGB:
        """Parse any supported color input to RGB.

        Accepted forms:
        - RGB instance (returned as-is)
        - dict with r/g/b keys
        - tuple/list of 3 ints 0-255
        - CSS-style named color ("red", "orange", "magenta"...)
        - Hex string with or without '#', 3 or 6 chars
        - Single color emoji (🔴🟢🔵🟠🟡🟣⚫⚪🟤 and the 🟥 family)

        Raises ValueError on unparseable input.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.model_validate(value)
        if isinstance(value, (tuple, list)):
            if len(value) != 3 or not all(isinstance(v, int) and 0 <= v <= 255 for v in value):
                msg = f"cannot parse RGB from tuple: {value!r}"
                raise ValueError(msg)
            r, g, b = value
            return cls(r=r, g=g, b=b)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                msg = "cannot parse RGB from empty string"
                raise ValueError(msg)
            if stripped in _COLOR_EMOJI:
                r, g, b = _COLOR_EMOJI[stripped]
                return cls(r=r, g=g, b=b)
            lowered = stripped.lower()
            if lowered in _NAMED_COLORS:
                r, g, b = _NAMED_COLORS[lowered]
                return cls(r=r, g=g, b=b)
            hex_parsed = _hex_to_tuple(stripped)
            if hex_parsed is not None:
                r, g, b = hex_parsed
                return cls(r=r, g=g, b=b)
        msg = f"cannot parse RGB from {value!r}"
        raise ValueError(msg)
```

Update `packages/contracts/src/wrangled_contracts/__init__.py`:

```python
"""Shared pydantic models for the WrangLED monorepo."""

from wrangled_contracts.commands import RGB
from wrangled_contracts.wled import WledDevice, WledMatrix

__all__ = ["RGB", "WledDevice", "WledMatrix"]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_commands.py -v
```
Expected: all tests pass (RGB + parse variants). Count roughly ~20.

- [ ] **Step 5: Lint clean**

```bash
uv run ruff check .
uv run ruff format --check .
```
Fix trivial findings with `--fix` / `format .`.

- [ ] **Step 6: Commit**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
git add packages/contracts/src packages/contracts/tests/test_commands.py
git commit -m "feat(contracts): add RGB model with multi-format parser"
```

---

## Task 2: Command variant classes + discriminated union

**Files:**
- Modify: `packages/contracts/src/wrangled_contracts/commands.py`
- Modify: `packages/contracts/src/wrangled_contracts/__init__.py`
- Modify: `packages/contracts/tests/test_commands.py`

- [ ] **Step 1: Append failing tests**

Append to `packages/contracts/tests/test_commands.py`:

```python
from typing import cast

from pydantic import TypeAdapter

from wrangled_contracts import (
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    TextCommand,
)

_COMMAND_ADAPTER = TypeAdapter(Command)


def test_color_command_roundtrip() -> None:
    cmd = ColorCommand(color=RGB(r=255, g=0, b=0), brightness=100)
    data = cmd.model_dump(mode="json")
    assert data["kind"] == "color"
    parsed = _COMMAND_ADAPTER.validate_python(data)
    assert parsed == cmd


def test_brightness_command_roundtrip() -> None:
    cmd = BrightnessCommand(brightness=80)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast(BrightnessCommand, parsed).brightness == 80


def test_effect_command_roundtrip() -> None:
    cmd = EffectCommand(name="fire", speed=180, brightness=150)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast(EffectCommand, parsed).name == "fire"


def test_text_command_roundtrip() -> None:
    cmd = TextCommand(text="Hello", color=RGB(r=0, g=0, b=255), speed=128)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast(TextCommand, parsed).text == "Hello"


def test_preset_command_roundtrip() -> None:
    cmd = PresetCommand(name="pytexas")
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast(PresetCommand, parsed).name == "pytexas"


def test_power_command_roundtrip() -> None:
    cmd = PowerCommand(on=False)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast(PowerCommand, parsed).on is False


def test_discriminator_dispatch_from_dict() -> None:
    parsed = _COMMAND_ADAPTER.validate_python(
        {"kind": "color", "color": {"r": 1, "g": 2, "b": 3}},
    )
    assert isinstance(parsed, ColorCommand)
    assert parsed.color == RGB(r=1, g=2, b=3)


def test_brightness_cap_at_200() -> None:
    with pytest.raises(ValidationError):
        BrightnessCommand(brightness=201)


def test_color_command_brightness_cap() -> None:
    with pytest.raises(ValidationError):
        ColorCommand(color=RGB(r=0, g=0, b=0), brightness=201)


def test_text_length_cap_at_64() -> None:
    with pytest.raises(ValidationError):
        TextCommand(text="x" * 65)


def test_text_speed_range() -> None:
    with pytest.raises(ValidationError):
        TextCommand(text="hi", speed=31)
    with pytest.raises(ValidationError):
        TextCommand(text="hi", speed=241)


def test_effect_name_is_constrained() -> None:
    with pytest.raises(ValidationError):
        EffectCommand.model_validate({"kind": "effect", "name": "not-a-real-effect"})


def test_preset_name_is_constrained() -> None:
    with pytest.raises(ValidationError):
        PresetCommand.model_validate({"kind": "preset", "name": "nope"})
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_commands.py -v
```
Expected: ImportError — the Command variants do not exist.

- [ ] **Step 3: Add Command variants**

Append to `packages/contracts/src/wrangled_contracts/commands.py`:

```python
from typing import Annotated, Literal

EffectName = Literal[
    "solid",
    "breathe",
    "rainbow",
    "fire",
    "sparkle",
    "fireworks",
    "matrix",
    "pride",
    "chase",
    "noise",
]

PresetName = Literal["pytexas", "party", "chill"]


class ColorCommand(BaseModel):
    """Set solid color (and optionally brightness)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["color"] = "color"
    color: RGB
    brightness: int | None = Field(default=None, ge=0, le=200)


class BrightnessCommand(BaseModel):
    """Change brightness only."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["brightness"] = "brightness"
    brightness: int = Field(ge=0, le=200)


class EffectCommand(BaseModel):
    """Run a named effect (optionally with color / speed / intensity / brightness)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["effect"] = "effect"
    name: EffectName
    color: RGB | None = None
    speed: int | None = Field(default=None, ge=0, le=255)
    intensity: int | None = Field(default=None, ge=0, le=255)
    brightness: int | None = Field(default=None, ge=0, le=200)


class TextCommand(BaseModel):
    """Scroll a short text message across the matrix."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text"] = "text"
    text: str = Field(max_length=64, min_length=1)
    color: RGB | None = None
    speed: int = Field(default=128, ge=32, le=240)
    brightness: int | None = Field(default=None, ge=0, le=200)


class PresetCommand(BaseModel):
    """Apply a named preset scene (expands to multiple commands)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["preset"] = "preset"
    name: PresetName


class PowerCommand(BaseModel):
    """Toggle power on/off."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["power"] = "power"
    on: bool


Command = Annotated[
    ColorCommand
    | BrightnessCommand
    | EffectCommand
    | TextCommand
    | PresetCommand
    | PowerCommand,
    Field(discriminator="kind"),
]
```

Update `packages/contracts/src/wrangled_contracts/__init__.py`:

```python
"""Shared pydantic models for the WrangLED monorepo."""

from wrangled_contracts.commands import (
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    EffectName,
    PowerCommand,
    PresetCommand,
    PresetName,
    TextCommand,
)
from wrangled_contracts.wled import WledDevice, WledMatrix

__all__ = [
    "RGB",
    "BrightnessCommand",
    "ColorCommand",
    "Command",
    "EffectCommand",
    "EffectName",
    "PowerCommand",
    "PresetCommand",
    "PresetName",
    "TextCommand",
    "WledDevice",
    "WledMatrix",
]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_commands.py -v
```
Expected: all tests pass (all variants + roundtrips + caps + discriminator).

- [ ] **Step 5: Lint**

```bash
uv run ruff check .
uv run ruff format --check .
```
Fix trivial findings. If ruff complains about `Command = Annotated[...]` being a "module-level type alias" (e.g. wants `type Command = ...`), stick with the `Annotated` form — pydantic discriminator needs the concrete Annotated alias, not a PEP 695 `type` statement.

- [ ] **Step 6: Commit**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
git add packages/contracts
git commit -m "feat(contracts): add Command variants + discriminated union"
```

---

## Task 3: Lookups (EFFECT_FX_ID, EMOJI_COMMANDS, PRESETS) + `command_from_emoji`

**Files:**
- Modify: `packages/contracts/src/wrangled_contracts/commands.py`
- Modify: `packages/contracts/src/wrangled_contracts/__init__.py`
- Modify: `packages/contracts/tests/test_commands.py`

- [ ] **Step 1: Append failing tests**

Append to `packages/contracts/tests/test_commands.py`:

```python
from wrangled_contracts import (
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    command_from_emoji,
)


def test_effect_fx_id_covers_all_effect_names() -> None:
    expected = {
        "solid", "breathe", "rainbow", "fire", "sparkle",
        "fireworks", "matrix", "pride", "chase", "noise",
    }
    assert set(EFFECT_FX_ID.keys()) == expected


def test_effect_fx_id_values_are_wled_ids() -> None:
    assert EFFECT_FX_ID["solid"] == 0
    assert EFFECT_FX_ID["fire"] == 66
    assert EFFECT_FX_ID["matrix"] == 63


def test_emoji_commands_covers_expected_keys() -> None:
    for key in ["🔥", "🌈", "⚡", "🎉", "🐍", "❤️", "💙", "💚", "💜", "🧡", "🖤"]:
        assert key in EMOJI_COMMANDS


def test_command_from_emoji_fire() -> None:
    cmd = command_from_emoji("🔥")
    assert isinstance(cmd, EffectCommand)
    assert cmd.name == "fire"


def test_command_from_emoji_color() -> None:
    cmd = command_from_emoji("💙")
    assert isinstance(cmd, ColorCommand)
    assert cmd.color == RGB(r=0, g=0, b=255)


def test_command_from_emoji_power_off() -> None:
    cmd = command_from_emoji("🖤")
    assert isinstance(cmd, PowerCommand)
    assert cmd.on is False


def test_command_from_emoji_color_square() -> None:
    cmd = command_from_emoji("🔴")
    assert isinstance(cmd, ColorCommand)
    assert cmd.color == RGB(r=255, g=0, b=0)


def test_command_from_emoji_unknown_returns_none() -> None:
    assert command_from_emoji("🦑") is None


def test_command_from_emoji_strips_whitespace() -> None:
    cmd = command_from_emoji("  🔥  ")
    assert isinstance(cmd, EffectCommand)
    assert cmd.name == "fire"


def test_presets_cover_expected_names() -> None:
    assert set(PRESETS.keys()) == {"pytexas", "party", "chill"}


def test_pytexas_preset_is_color_then_text() -> None:
    seq = PRESETS["pytexas"]
    assert len(seq) == 2
    assert isinstance(seq[0], ColorCommand)
    assert isinstance(seq[1], TextCommand)
    assert "PyTexas" in seq[1].text


def test_party_preset_is_rainbow() -> None:
    seq = PRESETS["party"]
    assert len(seq) == 1
    assert isinstance(seq[0], EffectCommand)
    assert seq[0].name == "rainbow"


def test_chill_preset_is_breathe() -> None:
    seq = PRESETS["chill"]
    assert len(seq) == 1
    assert isinstance(seq[0], EffectCommand)
    assert seq[0].name == "breathe"
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_commands.py -v
```
Expected: ImportError — `EFFECT_FX_ID`, `EMOJI_COMMANDS`, `PRESETS`, `command_from_emoji` not defined.

- [ ] **Step 3: Append lookups + helper**

Append to `packages/contracts/src/wrangled_contracts/commands.py`:

```python
EFFECT_FX_ID: dict[EffectName, int] = {
    "solid": 0,
    "breathe": 2,
    "rainbow": 9,
    "fire": 66,
    "sparkle": 20,
    "fireworks": 42,
    "matrix": 63,
    "pride": 93,
    "chase": 28,
    "noise": 70,
}


def _color(r: int, g: int, b: int) -> ColorCommand:
    return ColorCommand(color=RGB(r=r, g=g, b=b))


EMOJI_COMMANDS: dict[str, Command] = {
    "🔥": EffectCommand(name="fire"),
    "🌈": EffectCommand(name="rainbow"),
    "⚡": EffectCommand(name="sparkle", speed=220),
    "🎉": EffectCommand(name="fireworks"),
    "🐍": EffectCommand(name="matrix"),
    "❤️": _color(255, 0, 0),
    "💙": _color(0, 0, 255),
    "💚": _color(0, 200, 0),
    "💜": _color(180, 0, 255),
    "🧡": _color(255, 100, 0),
    "🖤": PowerCommand(on=False),
    "🔴": _color(255, 0, 0),
    "🟢": _color(0, 200, 0),
    "🔵": _color(0, 0, 255),
    "🟠": _color(255, 100, 0),
    "🟡": _color(255, 220, 0),
    "🟣": _color(180, 0, 255),
    "⚫": PowerCommand(on=False),
    "⚪": _color(255, 255, 255),
    "🟤": _color(130, 70, 20),
    "🟥": _color(255, 0, 0),
    "🟩": _color(0, 200, 0),
    "🟦": _color(0, 0, 255),
    "🟧": _color(255, 100, 0),
    "🟨": _color(255, 220, 0),
    "🟪": _color(180, 0, 255),
    "🟫": _color(130, 70, 20),
}


PRESETS: dict[PresetName, list[Command]] = {
    "pytexas": [
        ColorCommand(color=RGB(r=191, g=87, b=0), brightness=180),
        TextCommand(
            text="PyTexas 2026",
            color=RGB(r=255, g=100, b=0),
            speed=160,
        ),
    ],
    "party": [EffectCommand(name="rainbow", speed=240, brightness=200)],
    "chill": [
        EffectCommand(
            name="breathe",
            color=RGB(r=0, g=60, b=180),
            speed=48,
            brightness=120,
        ),
    ],
}


def command_from_emoji(emoji: str) -> Command | None:
    """Resolve a single emoji to its mapped Command, or None if unknown."""
    stripped = emoji.strip()
    return EMOJI_COMMANDS.get(stripped)
```

Update `__init__.py`:

```python
"""Shared pydantic models for the WrangLED monorepo."""

from wrangled_contracts.commands import (
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    EffectName,
    PowerCommand,
    PresetCommand,
    PresetName,
    TextCommand,
    command_from_emoji,
)
from wrangled_contracts.wled import WledDevice, WledMatrix

__all__ = [
    "EFFECT_FX_ID",
    "EMOJI_COMMANDS",
    "PRESETS",
    "RGB",
    "BrightnessCommand",
    "ColorCommand",
    "Command",
    "EffectCommand",
    "EffectName",
    "PowerCommand",
    "PresetCommand",
    "PresetName",
    "TextCommand",
    "WledDevice",
    "WledMatrix",
    "command_from_emoji",
]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_commands.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add packages/contracts
git commit -m "feat(contracts): add effect/emoji/preset lookups and command_from_emoji"
```

---

## Task 4: Pusher — pure `_build_*` functions

**Files:**
- Create: `apps/wrangler/src/wrangler/pusher.py`
- Create: `apps/wrangler/tests/test_pusher.py`

- [ ] **Step 1: uv sync to pick up new contracts symbols**

```bash
cd apps/wrangler
uv sync
```
Expected: editable contracts package picks up the new exports. No new downloads (all deps cached).

- [ ] **Step 2: Write failing tests for the builders**

`apps/wrangler/tests/test_pusher.py`:

```python
"""Tests for wrangler.pusher."""

from __future__ import annotations

from wrangled_contracts import (
    BrightnessCommand,
    ColorCommand,
    EffectCommand,
    PowerCommand,
    RGB,
    TextCommand,
)

from wrangler.pusher import (
    _build_brightness,
    _build_color,
    _build_effect,
    _build_power,
    _build_text,
)


def test_build_color_includes_brightness_when_set() -> None:
    body = _build_color(ColorCommand(color=RGB(r=10, g=20, b=30), brightness=100))
    assert body == {
        "on": True,
        "bri": 100,
        "seg": [{"fx": 0, "col": [[10, 20, 30], [0, 0, 0], [0, 0, 0]]}],
    }


def test_build_color_omits_brightness_when_absent() -> None:
    body = _build_color(ColorCommand(color=RGB(r=1, g=2, b=3)))
    assert "bri" not in body
    assert body["on"] is True
    assert body["seg"][0]["fx"] == 0
    assert body["seg"][0]["col"] == [[1, 2, 3], [0, 0, 0], [0, 0, 0]]


def test_build_brightness_is_bri_only() -> None:
    assert _build_brightness(BrightnessCommand(brightness=50)) == {"bri": 50}


def test_build_power_on() -> None:
    assert _build_power(PowerCommand(on=True)) == {"on": True}


def test_build_power_off() -> None:
    assert _build_power(PowerCommand(on=False)) == {"on": False}


def test_build_effect_minimal() -> None:
    body = _build_effect(EffectCommand(name="fire"))
    assert body == {"on": True, "seg": [{"fx": 66}]}


def test_build_effect_full() -> None:
    body = _build_effect(
        EffectCommand(
            name="rainbow",
            color=RGB(r=0, g=0, b=255),
            speed=200,
            intensity=150,
            brightness=180,
        ),
    )
    assert body["on"] is True
    assert body["bri"] == 180
    seg = body["seg"][0]
    assert seg["fx"] == 9  # rainbow
    assert seg["sx"] == 200
    assert seg["ix"] == 150
    assert seg["col"] == [[0, 0, 255], [0, 0, 0], [0, 0, 0]]


def test_build_text_uses_fx_122_and_segment_name() -> None:
    body = _build_text(
        TextCommand(text="Hello", color=RGB(r=0, g=0, b=255), speed=160, brightness=150),
    )
    seg = body["seg"][0]
    assert body["on"] is True
    assert body["bri"] == 150
    assert seg["fx"] == 122
    assert seg["n"] == "Hello"
    assert seg["sx"] == 160
    assert seg["o1"] is False  # force scroll even if fits
    assert seg["col"] == [[0, 0, 255], [0, 0, 0], [0, 0, 0]]


def test_build_text_without_color_omits_col() -> None:
    body = _build_text(TextCommand(text="hi"))
    seg = body["seg"][0]
    assert "col" not in seg
    assert seg["fx"] == 122
    assert seg["n"] == "hi"
```

- [ ] **Step 3: Run to verify fail**

```bash
uv run pytest tests/test_pusher.py -v
```
Expected: ImportError — `wrangler.pusher` missing.

- [ ] **Step 4: Implement builders**

`apps/wrangler/src/wrangler/pusher.py`:

```python
"""Translate a Command into WLED /json/state bodies and POST them."""

from __future__ import annotations

from wrangled_contracts import (
    EFFECT_FX_ID,
    PRESETS,
    RGB,
    BrightnessCommand,
    ColorCommand,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    TextCommand,
)


def _rgb_triplet(color: RGB) -> list[list[int]]:
    return [[color.r, color.g, color.b], [0, 0, 0], [0, 0, 0]]


def _build_color(cmd: ColorCommand) -> dict:
    body: dict = {
        "on": True,
        "seg": [{"fx": 0, "col": _rgb_triplet(cmd.color)}],
    }
    if cmd.brightness is not None:
        body["bri"] = cmd.brightness
    return body


def _build_brightness(cmd: BrightnessCommand) -> dict:
    return {"bri": cmd.brightness}


def _build_power(cmd: PowerCommand) -> dict:
    return {"on": cmd.on}


def _build_effect(cmd: EffectCommand) -> dict:
    seg: dict = {"fx": EFFECT_FX_ID[cmd.name]}
    if cmd.speed is not None:
        seg["sx"] = cmd.speed
    if cmd.intensity is not None:
        seg["ix"] = cmd.intensity
    if cmd.color is not None:
        seg["col"] = _rgb_triplet(cmd.color)
    body: dict = {"on": True, "seg": [seg]}
    if cmd.brightness is not None:
        body["bri"] = cmd.brightness
    return body


def _build_text(cmd: TextCommand) -> dict:
    seg: dict = {
        "fx": 122,  # Scrolling Text
        "n": cmd.text,
        "sx": cmd.speed,
        "ix": 128,
        "o1": False,  # force scroll even when the text fits
    }
    if cmd.color is not None:
        seg["col"] = _rgb_triplet(cmd.color)
    body: dict = {"on": True, "seg": [seg]}
    if cmd.brightness is not None:
        body["bri"] = cmd.brightness
    return body
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_pusher.py -v
```
Expected: 9 passed.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/pusher.py apps/wrangler/tests/test_pusher.py
git commit -m "feat(wrangler): add pusher body builders for each Command variant"
```

---

## Task 5: Pusher — `push_command` HTTP dispatch for single-body variants

**Files:**
- Modify: `apps/wrangler/src/wrangler/pusher.py`
- Modify: `apps/wrangler/tests/test_pusher.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_pusher.py`:

```python
from datetime import UTC, datetime
from ipaddress import IPv4Address

import httpx
import pytest
import respx

from wrangled_contracts import WledDevice

from wrangler.pusher import PushResult, push_command


def _fake_device(ip: str = "10.0.6.207") -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
@respx.mock
async def test_push_color_happy_path() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            ColorCommand(color=RGB(r=10, g=20, b=30), brightness=100),
        )
    assert result == PushResult(ok=True, status=200)
    assert route.called
    sent = route.calls.last.request
    assert sent.read() == b'{"on": true, "seg": [{"fx": 0, "col": [[10, 20, 30], [0, 0, 0], [0, 0, 0]]}], "bri": 100}'


@pytest.mark.asyncio
@respx.mock
async def test_push_brightness_happy_path() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), BrightnessCommand(brightness=50))
    assert result.ok is True
    assert route.calls.last.request.read() == b'{"bri": 50}'


@pytest.mark.asyncio
@respx.mock
async def test_push_power_off_happy_path() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PowerCommand(on=False))
    assert result.ok is True
    assert route.calls.last.request.read() == b'{"on": false}'


@pytest.mark.asyncio
@respx.mock
async def test_push_effect_happy_path() -> None:
    respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            EffectCommand(name="fire", speed=200),
        )
    assert result.ok is True


@pytest.mark.asyncio
@respx.mock
async def test_push_text_happy_path() -> None:
    respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            TextCommand(text="hi", color=RGB(r=0, g=0, b=255)),
        )
    assert result.ok is True


@pytest.mark.asyncio
@respx.mock
async def test_push_returns_error_on_timeout() -> None:
    respx.post("http://10.0.6.207/json/state").mock(side_effect=httpx.ReadTimeout)
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            ColorCommand(color=RGB(r=0, g=0, b=0)),
        )
    assert result.ok is False
    assert result.status is None
    assert result.error
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
@respx.mock
async def test_push_returns_error_on_non_200() -> None:
    respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(500, text="oops"),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            ColorCommand(color=RGB(r=0, g=0, b=0)),
        )
    assert result.ok is False
    assert result.status == 500
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_pusher.py -v
```
Expected: ImportError — `PushResult` / `push_command` missing.

- [ ] **Step 3: Implement `push_command` (single-body variants only)**

Append to `apps/wrangler/src/wrangler/pusher.py`:

```python
import logging

import httpx
from pydantic import BaseModel

from wrangled_contracts import Command, WledDevice

logger = logging.getLogger(__name__)


class PushResult(BaseModel):
    """Outcome of a single-command push operation."""

    ok: bool
    status: int | None = None
    error: str | None = None


async def _post_one(
    client: httpx.AsyncClient,
    device: WledDevice,
    body: dict,
    *,
    timeout: float,
) -> PushResult:
    url = f"http://{device.ip}/json/state"
    try:
        response = await client.post(url, json=body, timeout=timeout)
    except httpx.TimeoutException as exc:
        logger.debug("push %s: timeout: %s", device.ip, exc)
        return PushResult(ok=False, error=f"timeout: {exc}")
    except httpx.HTTPError as exc:
        logger.debug("push %s: transport error: %s", device.ip, exc)
        return PushResult(ok=False, error=str(exc))

    if response.status_code != httpx.codes.OK:
        return PushResult(ok=False, status=response.status_code, error=response.text[:200])
    return PushResult(ok=True, status=response.status_code)


async def push_command(
    client: httpx.AsyncClient,
    device: WledDevice,
    command: Command,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> PushResult:
    """Send a Command to a WLED device. Never raises."""
    match command:
        case ColorCommand():
            body = _build_color(command)
        case BrightnessCommand():
            body = _build_brightness(command)
        case EffectCommand():
            body = _build_effect(command)
        case TextCommand():
            body = _build_text(command)
        case PowerCommand():
            body = _build_power(command)
        case PresetCommand():
            # Handled in a later task (preset expansion).
            msg = "PresetCommand not yet supported"
            return PushResult(ok=False, error=msg)
    return await _post_one(client, device, body, timeout=timeout)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_pusher.py -v
```
Expected: single-body happy-path tests + error-path tests pass. Preset tests will come in Task 6.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/pusher.py apps/wrangler/tests/test_pusher.py
git commit -m "feat(wrangler): add push_command async dispatch for single-body variants"
```

---

## Task 6: Pusher — preset expansion

**Files:**
- Modify: `apps/wrangler/src/wrangler/pusher.py`
- Modify: `apps/wrangler/tests/test_pusher.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_pusher.py`:

```python
from wrangled_contracts import PresetCommand


@pytest.mark.asyncio
@respx.mock
async def test_push_preset_pytexas_posts_twice() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PresetCommand(name="pytexas"))
    assert result.ok is True
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_push_preset_party_posts_once() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PresetCommand(name="party"))
    assert result.ok is True
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_push_preset_stops_on_first_failure() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        side_effect=[
            httpx.Response(200, json={"success": True}),
            httpx.Response(500, text="boom"),
        ],
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PresetCommand(name="pytexas"))
    assert result.ok is False
    assert result.status == 500
    assert route.call_count == 2
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_pusher.py -v
```
Expected: 3 new preset tests fail — current implementation returns "not yet supported" error.

- [ ] **Step 3: Implement preset expansion**

Modify `apps/wrangler/src/wrangler/pusher.py`: replace the `case PresetCommand()` handler, and add `_build_preset_bodies`:

```python
def _build_command_body(command: Command) -> dict:
    """Build a single WLED body for any non-preset Command. Internal helper."""
    match command:
        case ColorCommand():
            return _build_color(command)
        case BrightnessCommand():
            return _build_brightness(command)
        case EffectCommand():
            return _build_effect(command)
        case TextCommand():
            return _build_text(command)
        case PowerCommand():
            return _build_power(command)
        case PresetCommand():
            msg = "cannot build a single body from a PresetCommand"
            raise ValueError(msg)


def _build_preset_bodies(cmd: PresetCommand) -> list[dict]:
    """Expand a PresetCommand into a list of WLED bodies."""
    return [_build_command_body(sub) for sub in PRESETS[cmd.name]]
```

Rewrite `push_command` to dispatch on preset vs. single:

```python
async def push_command(
    client: httpx.AsyncClient,
    device: WledDevice,
    command: Command,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> PushResult:
    """Send a Command to a WLED device. Never raises."""
    if isinstance(command, PresetCommand):
        bodies = _build_preset_bodies(command)
    else:
        bodies = [_build_command_body(command)]

    last: PushResult = PushResult(ok=True, status=200)
    for body in bodies:
        last = await _post_one(client, device, body, timeout=timeout)
        if not last.ok:
            return last
    return last
```

Also update the test helper `_build_*` imports — `_build_power`, `_build_color`, etc. must remain publicly accessible from the module's top level (they already are; the new `_build_command_body` sits alongside them).

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_pusher.py -v
```
Expected: all pusher tests pass (single-body + preset + error paths).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/pusher.py apps/wrangler/tests/test_pusher.py
git commit -m "feat(wrangler): expand PresetCommand into sequential pushes, fail fast"
```

---

## Task 7: CLI — `send` subparser + color / brightness / power subcommands

**Files:**
- Modify: `apps/wrangler/src/wrangler/cli.py`
- Create: `apps/wrangler/tests/test_cli_send.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_cli_send.py`:

```python
"""Tests for wrangler.cli `send` subcommand."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest

from wrangled_contracts import (
    BrightnessCommand,
    ColorCommand,
    Command,
    PowerCommand,
    RGB,
    WledDevice,
)

from wrangler.cli import main
from wrangler.pusher import PushResult


def _fake_device() -> WledDevice:
    return WledDevice(
        ip=IPv4Address("10.0.6.207"),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def capture_push() -> tuple[AsyncMock, list[Command]]:
    sent: list[Command] = []

    async def _capture(_client, _device, command, *, timeout=2.0):  # noqa: ARG001
        sent.append(command)
        return PushResult(ok=True, status=200)

    return AsyncMock(side_effect=_capture), sent


def _patch_device_and_push(push_mock: AsyncMock):
    return (
        patch("wrangler.cli._resolve_device", AsyncMock(return_value=_fake_device())),
        patch("wrangler.cli.push_command", push_mock),
    )


def test_send_color_named(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "color", "red"])
    assert exit_code == 0
    assert sent == [ColorCommand(color=RGB(r=255, g=0, b=0))]


def test_send_color_hex_with_brightness(
    capture_push: tuple[AsyncMock, list[Command]],
) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(
            ["send", "--ip", "10.0.6.207", "color", "#ff00aa", "--brightness", "120"],
        )
    assert exit_code == 0
    assert sent == [ColorCommand(color=RGB(r=255, g=0, b=170), brightness=120)]


def test_send_brightness(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "brightness", "80"])
    assert exit_code == 0
    assert sent == [BrightnessCommand(brightness=80)]


def test_send_power_off(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "power", "off"])
    assert exit_code == 0
    assert sent == [PowerCommand(on=False)]


def test_send_power_on(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "power", "on"])
    assert exit_code == 0
    assert sent == [PowerCommand(on=True)]


def test_send_reports_push_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fail = AsyncMock(return_value=PushResult(ok=False, status=500, error="boom"))
    patches = _patch_device_and_push(fail)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "power", "off"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "500" in captured.err or "boom" in captured.err
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_cli_send.py -v
```
Expected: ImportError — `_resolve_device` does not exist yet, nor does the `send` subparser.

- [ ] **Step 3: Extend `cli.py`**

Modify `apps/wrangler/src/wrangler/cli.py`. Keep the existing `scan` logic as-is. Add:

```python
import sys
from ipaddress import IPv4Address

import httpx

from wrangled_contracts import (
    BrightnessCommand,
    ColorCommand,
    Command,
    PowerCommand,
    RGB,
    WledDevice,
)

from wrangler.pusher import PushResult, push_command
from wrangler.scanner import ScanOptions, scan
from wrangler.scanner.probe import probe_device
```

Add the `send` subparser to `_build_parser()` after the `scan` subparser:

```python
    send_parser = sub.add_parser("send", help="Push a command to a WLED.")
    send_parser.add_argument(
        "--ip", type=IPv4Address, default=None, help="Target WLED IP (skips mDNS).",
    )
    send_parser.add_argument(
        "--name", default=None, help="Filter discovered devices by name substring.",
    )
    send_sub = send_parser.add_subparsers(dest="send_cmd", required=True)

    color_p = send_sub.add_parser("color", help="Set solid color.")
    color_p.add_argument("value", help="Named color, #hex, or color emoji.")
    color_p.add_argument("--brightness", type=int, default=None)

    bri_p = send_sub.add_parser("brightness", help="Set brightness (0-200).")
    bri_p.add_argument("level", type=int)

    power_p = send_sub.add_parser("power", help="Toggle power.")
    power_p.add_argument("state", choices=["on", "off"])
```

Add these top-level functions:

```python
async def _resolve_device(
    *,
    ip: IPv4Address | None,
    name: str | None,
) -> WledDevice:
    """Find the target WLED. Raises on ambiguous / missing."""
    if ip is not None:
        async with httpx.AsyncClient() as client:
            device = await probe_device(client, ip, source="sweep", timeout=2.0)
        if device is None:
            msg = f"no WLED answering at {ip}"
            raise RuntimeError(msg)
        return device

    devices = await scan(ScanOptions(mdns_timeout=2.0))
    if name is not None:
        devices = [d for d in devices if name.lower() in d.name.lower()]
    if not devices:
        msg = "no WLED devices found"
        raise RuntimeError(msg)
    if len(devices) > 1:
        listing = ", ".join(f"{d.ip} ({d.name})" for d in devices)
        msg = f"multiple devices found ({listing}); pass --ip or --name"
        raise RuntimeError(msg)
    return devices[0]


def _command_from_send_args(args) -> Command:  # noqa: ANN001
    if args.send_cmd == "color":
        color = RGB.parse(args.value)
        return ColorCommand(color=color, brightness=args.brightness)
    if args.send_cmd == "brightness":
        return BrightnessCommand(brightness=args.level)
    if args.send_cmd == "power":
        return PowerCommand(on=args.state == "on")
    msg = f"unknown send subcommand: {args.send_cmd}"
    raise ValueError(msg)


async def _run_send(args) -> int:  # noqa: ANN001
    try:
        device = await _resolve_device(ip=args.ip, name=args.name)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        command = _command_from_send_args(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    async with httpx.AsyncClient() as client:
        result: PushResult = await push_command(client, device, command)
    if not result.ok:
        tag = result.status or "error"
        print(f"push failed: {tag} {result.error or ''}".strip(), file=sys.stderr)
        return 1
    print(f"ok -> {device.ip} ({device.name})")
    return 0
```

Update `main` to dispatch the new subcommand:

```python
def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        return asyncio.run(_run_scan(_opts_from_args(args), as_json=args.as_json))
    if args.command == "send":
        return asyncio.run(_run_send(args))
    return 1
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_send.py -v
```
Expected: 6 passed. Run full suite:

```bash
uv run pytest -v
```
Expected: all prior tests + new ones pass (no regressions).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/cli.py apps/wrangler/tests/test_cli_send.py
git commit -m "feat(wrangler): add send subcommand for color/brightness/power"
```

---

## Task 8: CLI — `send effect` + `send text`

**Files:**
- Modify: `apps/wrangler/src/wrangler/cli.py`
- Modify: `apps/wrangler/tests/test_cli_send.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_cli_send.py`:

```python
from wrangled_contracts import EffectCommand, TextCommand


def test_send_effect_minimal(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "effect", "fire"])
    assert exit_code == 0
    assert sent == [EffectCommand(name="fire")]


def test_send_effect_with_flags(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(
            [
                "send", "--ip", "10.0.6.207",
                "effect", "rainbow",
                "--speed", "200",
                "--intensity", "150",
                "--color", "orange",
                "--brightness", "180",
            ],
        )
    assert exit_code == 0
    assert sent == [
        EffectCommand(
            name="rainbow",
            speed=200,
            intensity=150,
            color=RGB(r=255, g=100, b=0),
            brightness=180,
        ),
    ]


def test_send_text_minimal(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "text", "hi"])
    assert exit_code == 0
    assert sent == [TextCommand(text="hi")]


def test_send_text_with_flags(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(
            [
                "send", "--ip", "10.0.6.207",
                "text", "Hello PyTexas",
                "--color", "blue",
                "--speed", "160",
                "--brightness", "150",
            ],
        )
    assert exit_code == 0
    assert sent == [
        TextCommand(
            text="Hello PyTexas",
            color=RGB(r=0, g=0, b=255),
            speed=160,
            brightness=150,
        ),
    ]


def test_send_text_rejects_too_long(capsys: pytest.CaptureFixture[str]) -> None:
    push = AsyncMock()
    patches = _patch_device_and_push(push)
    long_text = "x" * 65
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "text", long_text])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "text" in captured.err.lower()
    push.assert_not_awaited()
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_cli_send.py -v
```
Expected: new tests fail — `effect` and `text` subcommands don't exist.

- [ ] **Step 3: Extend `cli.py`**

In `_build_parser()`, after the `power_p` subparser, append:

```python
    effect_p = send_sub.add_parser("effect", help="Run a named effect.")
    effect_p.add_argument(
        "name",
        choices=list(EFFECT_FX_ID.keys()),
        help="Effect name.",
    )
    effect_p.add_argument("--speed", type=int, default=None)
    effect_p.add_argument("--intensity", type=int, default=None)
    effect_p.add_argument("--color", default=None)
    effect_p.add_argument("--brightness", type=int, default=None)

    text_p = send_sub.add_parser("text", help="Scroll a short text message.")
    text_p.add_argument("text")
    text_p.add_argument("--color", default=None)
    text_p.add_argument("--speed", type=int, default=128)
    text_p.add_argument("--brightness", type=int, default=None)
```

Add the `EFFECT_FX_ID` import at the top of the file:

```python
from wrangled_contracts import (
    BrightnessCommand,
    ColorCommand,
    Command,
    EFFECT_FX_ID,
    EffectCommand,
    PowerCommand,
    RGB,
    TextCommand,
    WledDevice,
)
```

Extend `_command_from_send_args`:

```python
def _command_from_send_args(args) -> Command:  # noqa: ANN001
    from pydantic import ValidationError

    if args.send_cmd == "color":
        color = RGB.parse(args.value)
        return ColorCommand(color=color, brightness=args.brightness)
    if args.send_cmd == "brightness":
        return BrightnessCommand(brightness=args.level)
    if args.send_cmd == "power":
        return PowerCommand(on=args.state == "on")
    if args.send_cmd == "effect":
        color = RGB.parse(args.color) if args.color is not None else None
        return EffectCommand(
            name=args.name,
            color=color,
            speed=args.speed,
            intensity=args.intensity,
            brightness=args.brightness,
        )
    if args.send_cmd == "text":
        try:
            color = RGB.parse(args.color) if args.color is not None else None
            return TextCommand(
                text=args.text,
                color=color,
                speed=args.speed,
                brightness=args.brightness,
            )
        except ValidationError as exc:
            msg = f"invalid text command: {exc}"
            raise ValueError(msg) from exc
    msg = f"unknown send subcommand: {args.send_cmd}"
    raise ValueError(msg)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_send.py -v
```
Expected: all CLI send tests pass.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/cli.py apps/wrangler/tests/test_cli_send.py
git commit -m "feat(wrangler): add send effect + send text subcommands"
```

---

## Task 9: CLI — `send preset`, `send emoji`, device-targeting edge cases

**Files:**
- Modify: `apps/wrangler/src/wrangler/cli.py`
- Modify: `apps/wrangler/tests/test_cli_send.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_cli_send.py`:

```python
from wrangled_contracts import PresetCommand


def test_send_preset_pytexas(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "preset", "pytexas"])
    assert exit_code == 0
    assert sent == [PresetCommand(name="pytexas")]


def test_send_emoji_fire(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "emoji", "🔥"])
    assert exit_code == 0
    assert sent == [EffectCommand(name="fire")]


def test_send_emoji_unknown_errors(capsys: pytest.CaptureFixture[str]) -> None:
    push = AsyncMock()
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "emoji", "🦑"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "emoji" in captured.err.lower()
    push.assert_not_awaited()


def _two_devices() -> list[WledDevice]:
    from datetime import UTC, datetime
    from ipaddress import IPv4Address
    base = {
        "version": "0.15.0",
        "led_count": 256,
        "matrix": None,
        "udp_port": 21324,
        "raw_info": {},
        "discovered_via": "mdns",
        "discovered_at": datetime.now(tz=UTC),
    }
    return [
        WledDevice(ip=IPv4Address("10.0.6.207"), name="A", mac="aa:bb:cc:dd:ee:01", **base),
        WledDevice(ip=IPv4Address("10.0.6.208"), name="B", mac="aa:bb:cc:dd:ee:02", **base),
    ]


def test_ambiguous_discovery_fails_with_helpful_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    push = AsyncMock()
    scan_mock = AsyncMock(return_value=_two_devices())
    with (
        patch("wrangler.cli.scan", scan_mock),
        patch("wrangler.cli.push_command", push),
    ):
        exit_code = main(["send", "color", "red"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--ip" in captured.err or "multiple" in captured.err.lower()
    push.assert_not_awaited()


def test_name_filter_selects_one(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    scan_mock = AsyncMock(return_value=_two_devices())
    with (
        patch("wrangler.cli.scan", scan_mock),
        patch("wrangler.cli.push_command", push),
    ):
        exit_code = main(["send", "--name", "B", "color", "red"])
    assert exit_code == 0
    assert sent == [ColorCommand(color=RGB(r=255, g=0, b=0))]
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_cli_send.py -v
```
Expected: new tests fail — preset/emoji subcommands missing.

- [ ] **Step 3: Extend `cli.py`**

In `_build_parser()`, after the `text_p` subparser:

```python
    preset_p = send_sub.add_parser("preset", help="Run a named preset.")
    preset_p.add_argument("name", choices=["pytexas", "party", "chill"])

    emoji_p = send_sub.add_parser("emoji", help="Resolve a single emoji to a command.")
    emoji_p.add_argument("glyph")
```

Add the `command_from_emoji` and `PresetCommand` imports:

```python
from wrangled_contracts import (
    BrightnessCommand,
    ColorCommand,
    Command,
    EFFECT_FX_ID,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    RGB,
    TextCommand,
    WledDevice,
    command_from_emoji,
)
```

Extend `_command_from_send_args` — add after the text branch, before the final `msg`:

```python
    if args.send_cmd == "preset":
        return PresetCommand(name=args.name)
    if args.send_cmd == "emoji":
        cmd = command_from_emoji(args.glyph)
        if cmd is None:
            msg = f"unknown emoji: {args.glyph!r}"
            raise ValueError(msg)
        return cmd
```

- [ ] **Step 4: Run full suite**

```bash
uv run pytest -v
```
Expected: every test passes.

- [ ] **Step 5: Smoke-run the CLI locally**

```bash
uv run wrangler send --help
uv run wrangler send color --help
uv run wrangler send effect --help
uv run wrangler send preset --help
uv run wrangler send emoji --help
```
Expected: help text shows all flags cleanly.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/cli.py apps/wrangler/tests/test_cli_send.py
git commit -m "feat(wrangler): add send preset + emoji, name-filter discovery"
```

---

## Task 10: Live test extension + end-to-end verification

**Files:**
- Modify: `apps/wrangler/tests/test_live.py`

- [ ] **Step 1: Append the live push test**

Append to `apps/wrangler/tests/test_live.py`:

```python
import httpx

from wrangled_contracts import ColorCommand, RGB

from wrangler.pusher import push_command
from wrangler.scanner.probe import probe_device


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_push_color_changes_state() -> None:
    from ipaddress import IPv4Address

    async with httpx.AsyncClient() as client:
        # Probe first so we have a real WledDevice to pass.
        device = await probe_device(
            client, IPv4Address(LIVE_IP), source="mdns", timeout=2.0,
        )
        assert device is not None, f"no WLED at {LIVE_IP}"

        # Send a known-good command: dim blue.
        result = await push_command(
            client,
            device,
            ColorCommand(color=RGB(r=0, g=0, b=255), brightness=1),
        )
        assert result.ok, f"push failed: {result}"

        # Re-probe and check the new state is reflected.
        after = await probe_device(
            client, IPv4Address(LIVE_IP), source="mdns", timeout=2.0,
        )
        assert after is not None
        assert after.raw_info.get("bri") == 1 or after.raw_info.get("state", {}).get("bri") == 1
```

Note: the `/json/info` response used by `probe_device` does not always include the current `bri` — on some WLED versions you need `/json/state`. If this assertion fails for that reason, relax it: the fact that `push_command` returned `ok=True` is sufficient proof.

- [ ] **Step 2: Confirm default run still skips live tests**

```bash
cd apps/wrangler
uv run pytest -v
```
Expected: all non-live tests pass; live tests deselected.

- [ ] **Step 3: Manual end-to-end checks**

Run each of these against the real matrix at `10.0.6.207`. Verify the matrix responds. Leave the matrix in a low-brightness blue state at the end.

```bash
cd apps/wrangler

uv run wrangler send --ip 10.0.6.207 color orange --brightness 50
uv run wrangler send --ip 10.0.6.207 brightness 10
uv run wrangler send --ip 10.0.6.207 effect fire --speed 180
uv run wrangler send --ip 10.0.6.207 text "Hello PyTexas" --color orange --speed 160
uv run wrangler send --ip 10.0.6.207 preset pytexas
uv run wrangler send --ip 10.0.6.207 emoji 🐍
uv run wrangler send --ip 10.0.6.207 power off
uv run wrangler send --ip 10.0.6.207 color blue --brightness 1

uv run pytest -m live -v
```

Each should print `ok -> 10.0.6.207 (WLED-Gledopto)` on success.

- [ ] **Step 4: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/tests/test_live.py
git commit -m "test(wrangler): add opt-in live push-color test"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Command contract → T1 (RGB), T2 (variants + union), T3 (lookups + helpers).
  - Pusher → T4 (builders), T5 (single-body dispatch + errors), T6 (preset expansion + mid-failure).
  - CLI → T7 (color/brightness/power), T8 (effect/text), T9 (preset/emoji/name filter/ambiguity).
  - Live test → T10.
  - Safety caps → covered by variant validation tests in T2.
  - Emoji shortcuts → T3 lookup test + T9 CLI test.
  - 3 presets → T3 lookup test + T6 pusher expansion test + T9 CLI.

- **Placeholder scan:** no TBDs, no "add appropriate error handling" — every step has executable code and exact commands.

- **Type consistency:** `ColorCommand`/`BrightnessCommand`/`EffectCommand`/`TextCommand`/`PresetCommand`/`PowerCommand` referenced consistently; every field name used in tests matches the class definition. `push_command(client, device, command, *, timeout=2.0)` signature is identical across pusher tests and CLI mocks. `PushResult(ok: bool, status: int | None, error: str | None)` consistent across all test assertions.

- **Scope:** milestone 1 foundation (contracts package, wrangler scanner, CLI structure) is reused. No new dependencies. Tasks are incremental and each produces a passing build + commit.
