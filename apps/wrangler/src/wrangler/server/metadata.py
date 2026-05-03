"""Metadata routes: curated effects, presets, emoji shortcuts."""

from __future__ import annotations

from fastapi import APIRouter
from wrangled_contracts import (
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
)


def _summarize(cmd: Command) -> str:
    if isinstance(cmd, EffectCommand):
        return cmd.name
    if isinstance(cmd, ColorCommand):
        return f"color({cmd.color.r},{cmd.color.g},{cmd.color.b})"
    if isinstance(cmd, PowerCommand):
        return f"power({'on' if cmd.on else 'off'})"
    return cmd.kind


def build_metadata_router() -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/effects")
    def list_effects() -> dict[str, list[str]]:
        return {"effects": list(EFFECT_FX_ID.keys())}

    @router.get("/presets")
    def list_presets() -> dict[str, list[str]]:
        return {"presets": list(PRESETS.keys())}

    @router.get("/emoji")
    def list_emoji() -> dict[str, dict[str, str]]:
        return {"emoji": {k: _summarize(v) for k, v in EMOJI_COMMANDS.items()}}

    return router
