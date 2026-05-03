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


_HEX_SHORT = 3
_HEX_LONG = 6
_CHAN_MAX = 255


def _hex_to_tuple(value: str) -> tuple[int, int, int] | None:
    s = value.lstrip("#")
    if len(s) == _HEX_SHORT and all(c in "0123456789abcdefABCDEF" for c in s):
        return (int(s[0] * 2, 16), int(s[1] * 2, 16), int(s[2] * 2, 16))
    if len(s) == _HEX_LONG and all(c in "0123456789abcdefABCDEF" for c in s):
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

            def _valid_chan(v: object) -> bool:
                return isinstance(v, int) and 0 <= v <= _CHAN_MAX

            if len(value) != _HEX_SHORT or not all(_valid_chan(v) for v in value):
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


from typing import Annotated, Literal  # noqa: E402

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
    # Added for PyTexas preset pack
    "plasma",      # 2D Plasma (fx 119)
    "metaballs",   # 2D Metaballs (fx 111)
    "wavingcell",  # 2D Waving Cell (fx 116)
    "blink",       # Blink (fx 1) — Discord alert flash
    "ripple",      # 2D Ripple (fx 113)
    "meteor",      # Meteor (fx 65)
    "sweep",       # Sweep (fx 26)
    "theater",     # Theater / Chase (fx 10)
    "police",      # Police / Strobe (fx 40)
    "noise",       # Noise (fx 70)
]

PresetName = Literal[
    # ── PyTexas Lore Overhaul 2026 ───────────────────────────────────────────
    "pytexas",        # 🤠 Brand marquee
    "party",          # 🎉 Rainbow celebration
    "chill",          # 🌊 Layered cosmic chill
    "love_it",        # ❤️ Hype celebration
    "snake_attack",   # 🐍 Python matrix rain
    "the_gil",        # 🔒 Global Interpreter Lock
    "whitespace",     # ⌨️ Significant Whitespace
    "import_gravity", # 🛸 import gravity (xkcd)
    "zen",            # 🧘 Zen of Python
    "deep_heart",     # ❤️ Deep in the Heart
    "bluebonnets",    # 🪻 Bluebonnet Field
    "yellow_rose",    # 🌹 The Yellow Rose
    "tumbleweed",     # 🌾 Tumbleweed
    "prod_down",      # 🚨 Production is Down
    "merge_conflict", # ⚔️ Merge Conflict
    "off_by_one",     # 🔢 Off-by-One Error
    "garbage_collector", # 🧹 Garbage Collector
    "spam_eggs",      # 🍳 Spam & Eggs (Monty Python)
    "borg",           # 🤖 Borg Assimilation
    "pep8",           # 📏 Pep 8 Check
    "asyncio_loop",   # 🔄 Asyncio Loop
    "duck_typer",     # 🦆 Duck Typer
    "discord_alert",  # ⚡ visual ack
    # ── Moderator & Lore expansion ──────────────────────────────────────────
    "howdy",          # 👋 Standard greeting
    "breaktime",      # ☕ Breaktime
    "networking",     # 🤝 Networking Event
    "respectful",     # 🤝 Be Respectful!
    "silent_phones",  # 📵 Silence Phones
    "talk_soon",      # 🎙️ Talk Starting
    "found_item",     # 🎒 Lost & Found
    "qa_session",     # ❓ Q&A Session
    "five_min",       # ⏱️ 5 min remaining
]


class ColorCommand(BaseModel):
    """Set solid color (and optionally brightness)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["color"] = "color"
    color: RGB
    brightness: int | None = Field(default=None, ge=0, le=200)
    start: int | None = None
    stop: int | None = None


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
    start: int | None = None
    stop: int | None = None


class TextCommand(BaseModel):
    """Scroll a short text message across the matrix."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text"] = "text"
    text: str = Field(max_length=200, min_length=1)
    color: RGB | None = None
<<<<<<< HEAD
    speed: int = Field(default=20, ge=0, le=240)
=======
    speed: int = Field(default=225, ge=0, le=240)
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
    intensity: int | None = Field(default=None, ge=0, le=255)
    brightness: int | None = Field(default=None, ge=0, le=200)
    start: int | None = None
    stop: int | None = None


class PresetCommand(BaseModel):
    """Apply a named preset scene (expands to multiple commands)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["preset"] = "preset"
    name: PresetName
    speed_override: int | None = Field(default=None, ge=0, le=255)


class PowerCommand(BaseModel):
    """Toggle power on/off."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["power"] = "power"
    on: bool


Command = Annotated[
    ColorCommand | BrightnessCommand | EffectCommand | TextCommand | PresetCommand | PowerCommand,
    Field(discriminator="kind"),
]


EFFECT_FX_ID: dict[EffectName, int] = {
    "solid": 0,
    "blink": 1,
    "breathe": 2,
    "rainbow": 9,
    "fire": 149,  # Firenoise (2D-native); fx 66 "Fire 2012" is 1D-only
    "sparkle": 20,
    "fireworks": 42,
    "matrix": 63,
    "pride": 93,
    "chase": 28,
    "noise": 70,
    "metaballs": 111,   # 2D Metaballs
    "wavingcell": 116,  # 2D Waving Cell
    "plasma": 119,      # 2D Plasma
    "ripple": 113,      # 2D Ripple
    "meteor": 65,       # Meteor
    "sweep": 26,        # Sweep
    "theater": 10,      # Theater / Chase
    "police": 40,       # Police / Strobe
    "noise": 70,        # Noise
}

# Per-effect default parameter overrides.
# Applied by the pusher *only* when the EffectCommand leaves those fields as None.
# Tuned by taste — primary goal: avoid seizure-inducing defaults at the conference.
EFFECT_DEFAULTS: dict[EffectName, dict[str, int]] = {
    "solid": {},
    "blink": {"speed": 255, "intensity": 255},
    "breathe": {"speed": 48},
    "rainbow": {"speed": 140},
    "fire": {"speed": 160, "intensity": 128},
    "sparkle": {"speed": 180, "intensity": 100, "brightness": 140},
    "fireworks": {"speed": 200, "intensity": 180, "brightness": 140},
    "matrix": {"speed": 10, "intensity": 128},
    "pride": {"speed": 140},
    "chase": {"speed": 150},
    "noise": {"speed": 80},
    "plasma": {"speed": 80, "intensity": 160},
    "metaballs": {"speed": 60, "intensity": 100},
    "wavingcell": {"speed": 100, "intensity": 140},
}


def _color(r: int, g: int, b: int) -> ColorCommand:
    return ColorCommand(color=RGB(r=r, g=g, b=b))


EMOJI_COMMANDS: dict[str, Command] = {
    "🔥": EffectCommand(name="fire"),
    "🌈": EffectCommand(name="rainbow"),
    "⚡": EffectCommand(name="sparkle", speed=220),
    "🎉": EffectCommand(name="fireworks"),
    "🐍": PresetCommand(name="snake_attack"),   # !idle
    "💥": PresetCommand(name="love_it"),        # !hype
    "🤠": PresetCommand(name="pytexas"),        # !texas / registration
    "⭐": PresetCommand(name="zen"),             # !zen ambient
    "🌙": PresetCommand(name="chill"),           # !chill
    "🌊": PresetCommand(name="asyncio_loop"),    # !loop
    "❤️": PresetCommand(name="love_it"),
    "🔒": PresetCommand(name="the_gil"),
    "⌨️": PresetCommand(name="whitespace"),
    "🛸": PresetCommand(name="import_gravity"),
    "🧘": PresetCommand(name="zen"),
    "🚨": PresetCommand(name="prod_down"),
    "⚔️": PresetCommand(name="merge_conflict"),
    "📏": PresetCommand(name="pep8"),
    "🧹": PresetCommand(name="garbage_collector"),
    "🍳": PresetCommand(name="spam_eggs"),
    "🤖": PresetCommand(name="borg"),
    "🦆": PresetCommand(name="duck_typer"),
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
    # ── Foundation ──────────────────────────────────────────────────────────
    # ── PyTexas Brand ───────────────────────────────────────────────────────
    # 🤠 PyTexas 2026 — Clean white scrolling text on black background
    "pytexas": [
         TextCommand(
            text="PyTexas 2026",
            color=RGB(r=255, g=255, b=255),
<<<<<<< HEAD
            speed=22, # Medium speed
=======
            speed=225,
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
        ),
    ],
    # 👋 Howdy — Standard PyTexas Greeting
    "howdy": [
        TextCommand(
            text="Welcome to PyTexas 2026",
            color=RGB(r=255, g=122, b=0),
<<<<<<< HEAD
            speed=25, # Medium speed
=======
            speed=225,
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
        ),
    ],
    # ☕ Breaktime
    "breaktime": [
<<<<<<< HEAD
        TextCommand(text="Breaktime", color=RGB(r=0, g=200, b=255), speed=18), # Short text -> Slow
    ],
    # 🤝 Networking
    "networking": [
        TextCommand(text="PyTexas Networking Event", color=RGB(r=200, g=100, b=255), speed=28), # Medium-long
    ],
    # 🤝 Be Respectful
    "respectful": [
        TextCommand(text="Be Respectful!", color=RGB(r=255, g=255, b=0), speed=18), # Short
=======
        TextCommand(text="Breaktime", color=RGB(r=0, g=200, b=255), speed=225),
    ],
    # 🤝 Networking
    "networking": [
        TextCommand(text="PyTexas Networking Event", color=RGB(r=200, g=100, b=255), speed=225),
    ],
    # 🤝 Be Respectful
    "respectful": [
        TextCommand(text="Be Respectful!", color=RGB(r=255, g=255, b=0), speed=225),
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
    ],

    # ── Moderator Pack ──────────────────────────────────────────────────────
    # 📵 Silence Phones
    "silent_phones": [
<<<<<<< HEAD
        TextCommand(text="Silence your phones!", color=RGB(r=255, g=0, b=0), speed=25),
    ],
    # 🎙️ Talk Starting
    "talk_soon": [
        TextCommand(text="Next talk starting soon", color=RGB(r=0, g=255, b=0), speed=25),
    ],
    # 🎒 Lost & Found
    "found_item": [
        TextCommand(text="Found Item - See Registration", color=RGB(r=255, g=255, b=255), speed=30),
    ],
    # ❓ Q&A Session
    "qa_session": [
        TextCommand(text="Q&A Session", color=RGB(r=255, g=200, b=0), speed=20),
    ],
    # ⏱️ 5 Minutes Remaining
    "five_min": [
        TextCommand(text="5 Minutes Remaining", color=RGB(r=255, g=165, b=0), speed=25),
=======
        TextCommand(text="Silence your phones!", color=RGB(r=255, g=0, b=0), speed=225),
    ],
    # 🎙️ Talk Starting
    "talk_soon": [
        TextCommand(text="Next talk starting soon", color=RGB(r=0, g=255, b=0), speed=225),
    ],
    # 🎒 Lost & Found
    "found_item": [
        TextCommand(text="Found Item - See Registration", color=RGB(r=255, g=255, b=255), speed=225),
    ],
    # ❓ Q&A Session
    "qa_session": [
        TextCommand(text="Q&A Session", color=RGB(r=255, g=200, b=0), speed=225),
    ],
    # ⏱️ 5 Minutes Remaining
    "five_min": [
        TextCommand(text="5 Minutes Remaining", color=RGB(r=255, g=165, b=0), speed=225),
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
    ],
    "party": [EffectCommand(name="rainbow", speed=240, brightness=200)],
    "chill": [
        EffectCommand(
            name="breathe",
            color=RGB(r=0, g=60, b=180),
            speed=48,
            brightness=120,
        ),
        TextCommand(
            text="We Chillin'",
            color=RGB(r=255, g=255, b=255),
            speed=128,
        ),
    ],
    "love_it": [
        BrightnessCommand(brightness=200),
        EffectCommand(name="breathe", color=RGB(r=255, g=0, b=0), speed=100, brightness=150),
        TextCommand(
            text="* * * LOVE IT * * *",
            color=RGB(r=255, g=0, b=0),
            speed=180,
        ),
    ],
    "snake_attack": [
        EffectCommand(
            name="matrix",
            color=RGB(r=255, g=212, b=59),   # Python yellow
            speed=140,
            intensity=200,
            brightness=180,
        ),
    ],

    # ── The "Pythonic" Classics ─────────────────────────────────────────────
    # 🐍 The Global Interpreter Lock (GIL) — white "lock" on flickering grid
    "the_gil": [
        EffectCommand(name="noise", color=RGB(r=30, g=30, b=30), speed=200, brightness=80, start=0, stop=512),
        ColorCommand(color=RGB(r=255, g=255, b=255), brightness=200, start=32, stop=33), # one "locked" pixel
    ],
    # ⌨️ Significant Whitespace — rigid grid pattern
    "whitespace": [
        EffectCommand(name="theater", color=RGB(r=255, g=255, b=255), speed=0, intensity=100),
    ],
    # 🛸 Import Gravity — flying blue/white xkcd reference
    "import_gravity": [
        EffectCommand(name="meteor", color=RGB(r=55, g=118, b=171), speed=200, intensity=100), # Python Blue
    ],
    # 🧘 Zen of Python — slow meditative breathe in Blue/Gold
    "zen": [
        EffectCommand(name="breathe", color=RGB(r=55, g=118, b=171), speed=30, brightness=120), # Python Blue
        ColorCommand(color=RGB(r=255, g=212, b=59), brightness=60), # Python Gold (layered via colors)
    ],

    # ── The "PyTexas" Flair ─────────────────────────────────────────────────
    # ❤️ Deep in the Heart — pulsing red center-out ripple (heartbeat)
    "deep_heart": [
        EffectCommand(name="ripple", color=RGB(r=255, g=0, b=0), speed=80, intensity=255, brightness=200),
    ],
    # 🪻 Bluebonnet Field — vibrant blues/purples
    "bluebonnets": [
        EffectCommand(name="plasma", color=RGB(r=0, g=0, b=255), speed=20, intensity=120, brightness=100),
    ],
    # 🌹 The Yellow Rose — blooming yellow effect
    "yellow_rose": [
        EffectCommand(name="ripple", color=RGB(r=255, g=212, b=59), speed=60, intensity=180, brightness=180),
    ],
    # 🌾 Tumbleweed — rolling amber ball
    "tumbleweed": [
        EffectCommand(name="meteor", color=RGB(r=255, g=191, b=0), speed=250), # fast amber meteor
    ],

    # ── Developer Humor & Lore ──────────────────────────────────────────────
    # 🚨 Production is Down — aggressive strobe red
    "prod_down": [
        EffectCommand(name="police", color=RGB(r=255, g=0, b=0), speed=255, intensity=255),
    ],
    # ⚔️ Merge Conflict — Red/Green collision
    "merge_conflict": [
        EffectCommand(name="police", color=RGB(r=255, g=0, b=0), speed=200, intensity=100),
        EffectCommand(name="police", color=RGB(r=0, g=200, b=0), speed=205, intensity=110),
    ],
    # 🔢 Off-by-One Error — entire 64x8 grid lit except the last pixel
    "off_by_one": [
        ColorCommand(color=RGB(r=255, g=255, b=255), brightness=100, start=0, stop=511), # 511 of 512
    ],
    # 🧹 Garbage Collector — sweep effect clearing static
    "garbage_collector": [
        EffectCommand(name="noise", color=RGB(r=50, g=50, b=50), speed=255, brightness=100),
        EffectCommand(name="sweep", color=RGB(r=0, g=200, b=0), speed=180, intensity=128),
    ],
    # 🍳 Spam & Eggs — pink and yellow alternating
    "spam_eggs": [
        EffectCommand(name="theater", color=RGB(r=255, g=120, b=180), speed=120), # Pink
        EffectCommand(name="theater", color=RGB(r=255, g=212, b=59), speed=125),  # Yellow
    ],

    # ── Matrix Visuals ──────────────────────────────────────────────────────
    # 🤖 Borg Assimilation — horizontal Matrix (green)
    "borg": [
        EffectCommand(name="matrix", color=RGB(r=0, g=200, b=0), speed=200, intensity=200),
    ],
    # 📏 Pep 8 Check — green scroll with red blip
    "pep8": [
        EffectCommand(name="sweep", color=RGB(r=0, g=200, b=0), speed=100),
        EffectCommand(name="blink", color=RGB(r=255, g=0, b=0), speed=10, start=32, stop=33),
    ],
    # 🔄 Asyncio Loop — moving loading spinner
    "asyncio_loop": [
        EffectCommand(name="theater", color=RGB(r=0, g=200, b=200), speed=255, intensity=10),
    ],
    # 🦆 Duck Typer — yellow sparkle dots
    "duck_typer": [
        EffectCommand(name="sparkle", color=RGB(r=255, g=212, b=59), speed=200, intensity=255),
    ],
    "discord_alert": [
        EffectCommand(
            name="blink",
            color=RGB(r=88, g=101, b=242),   # Discord purple
            speed=255,
            intensity=255,
            brightness=200,
        ),
    ],
}


def command_from_emoji(emoji: str) -> Command | None:
    """Resolve a single emoji to its mapped Command, or None if unknown."""
    stripped = emoji.strip()
    return EMOJI_COMMANDS.get(stripped)
