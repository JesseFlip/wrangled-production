"""Tests for wrangled_contracts.commands."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError

from wrangled_contracts import (
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    TextCommand,
    command_from_emoji,
)

_COMMAND_ADAPTER = TypeAdapter(Command)


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


def test_color_command_roundtrip() -> None:
    cmd = ColorCommand(color=RGB(r=255, g=0, b=0), brightness=100)
    data = cmd.model_dump(mode="json")
    assert data["kind"] == "color"
    parsed = _COMMAND_ADAPTER.validate_python(data)
    assert parsed == cmd


def test_brightness_command_roundtrip() -> None:
    cmd = BrightnessCommand(brightness=80)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast("BrightnessCommand", parsed).brightness == 80


def test_effect_command_roundtrip() -> None:
    cmd = EffectCommand(name="fire", speed=180, brightness=150)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast("EffectCommand", parsed).name == "fire"


def test_text_command_roundtrip() -> None:
    cmd = TextCommand(text="Hello", color=RGB(r=0, g=0, b=255), speed=128)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast("TextCommand", parsed).text == "Hello"


def test_preset_command_roundtrip() -> None:
    cmd = PresetCommand(name="pytexas")
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast("PresetCommand", parsed).name == "pytexas"


def test_power_command_roundtrip() -> None:
    cmd = PowerCommand(on=False)
    parsed = _COMMAND_ADAPTER.validate_python(cmd.model_dump(mode="json"))
    assert cast("PowerCommand", parsed).on is False


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


def test_text_length_cap() -> None:
    with pytest.raises(ValidationError):
        TextCommand(text="x" * 201)  # Jesse bumped to 200


def test_text_speed_range() -> None:
    # Jesse widened speed range to 0-240
    TextCommand(text="hi", speed=0)  # now valid
    with pytest.raises(ValidationError):
        TextCommand(text="hi", speed=241)


def test_effect_name_is_constrained() -> None:
    with pytest.raises(ValidationError):
        EffectCommand.model_validate({"kind": "effect", "name": "not-a-real-effect"})


def test_preset_name_is_constrained() -> None:
    with pytest.raises(ValidationError):
        PresetCommand.model_validate({"kind": "preset", "name": "nope"})


def test_effect_fx_id_covers_all_effect_names() -> None:
    effects = set(EFFECT_FX_ID.keys())
    # Must include originals + Jesse's PyTexas additions
    assert effects >= {"solid", "fire", "rainbow", "matrix", "plasma", "blink", "police"}
    assert len(effects) >= 19



def test_effect_fx_id_values_are_wled_ids() -> None:
    assert EFFECT_FX_ID["solid"] == 0
    assert EFFECT_FX_ID["fire"] == 149
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
    presets = set(PRESETS.keys())
    expected = {
        "pytexas", "party", "chill",
        "snake_attack", "howdy",
    }
    assert presets >= expected
    assert len(presets) >= 32



def test_pytexas_preset_exists() -> None:
    seq = PRESETS["pytexas"]
    assert len(seq) >= 1


def test_party_preset_exists() -> None:
    seq = PRESETS["party"]
    assert len(seq) >= 1


def test_chill_preset_exists() -> None:
    seq = PRESETS["chill"]
    assert len(seq) >= 1
