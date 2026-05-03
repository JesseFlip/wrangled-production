"""Translate a Command into WLED /json/state bodies and POST them."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from wrangled_contracts import (
    EFFECT_DEFAULTS,
    EFFECT_FX_ID,
    PRESETS,
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    PushResult,
    TextCommand,
    WledDevice,
)

logger = logging.getLogger(__name__)

# WLED firmware hard limit on the segment 'n' (name) field used by
# the Scrolling Text effect (FX 122). Text beyond this is silently
# truncated by the device, causing mid-word cutoffs.
WLED_TEXT_LIMIT = 64


def _truncate_for_wled(text: str) -> str:
    """Truncate text to fit WLED's 64-byte segment name limit.
    
    Truncates at the last word boundary to avoid mid-word cutoffs.
    Appends '...' only when truncation occurs.
    """
    if len(text) <= WLED_TEXT_LIMIT:
        return text
    # Truncate to limit and cut at last space to avoid mid-word breaks
    truncated = text[:WLED_TEXT_LIMIT].rsplit(' ', 1)[0]
    return truncated + '...'


def _rgb_triplet(color: RGB) -> list[list[int]]:
    return [[color.r, color.g, color.b], [0, 0, 0], [0, 0, 0]]


def _build_segment(cmd: Command, seg_id: int = 0) -> dict | None:
    """Build a WLED segment dictionary if the command is segment-based."""
    if isinstance(cmd, ColorCommand):
        seg = {"id": seg_id, "fx": 0, "col": _rgb_triplet(cmd.color), "on": True}
        if cmd.start is not None:
            seg["start"] = cmd.start
        if cmd.stop is not None:
            seg["stop"] = cmd.stop
        return seg

    if isinstance(cmd, EffectCommand):
        defaults = EFFECT_DEFAULTS.get(cmd.name, {})
        speed = cmd.speed if cmd.speed is not None else defaults.get("speed")
        intensity = cmd.intensity if cmd.intensity is not None else defaults.get("intensity")
        seg: dict = {"id": seg_id, "fx": EFFECT_FX_ID[cmd.name], "m12": 1, "on": True}
        if speed is not None:
            seg["sx"] = speed
        if intensity is not None:
            seg["ix"] = intensity
        if cmd.color is not None:
            seg["col"] = _rgb_triplet(cmd.color)
        if cmd.start is not None:
            seg["start"] = cmd.start
        if cmd.stop is not None:
            seg["stop"] = cmd.stop
        return seg

    if isinstance(cmd, TextCommand):
        seg = {
            "id": seg_id,
            "fx": 122,
            "n": _truncate_for_wled(cmd.text),
            "sx": cmd.speed,
            "ix": cmd.intensity if cmd.intensity is not None else 128,
            "o1": False,
            "on": True,
        }
        if cmd.color is not None:
            seg["col"] = _rgb_triplet(cmd.color)
        if cmd.start is not None:
            seg["start"] = cmd.start
        if cmd.stop is not None:
            seg["stop"] = cmd.stop
        return seg

    return None


def _build_command_body(cmd: Command) -> dict:
    """Build a WLED JSON body for a single command."""
    body: dict = {}

    # Handle global state
    if isinstance(cmd, BrightnessCommand):
        body["bri"] = cmd.brightness
    elif isinstance(cmd, PowerCommand):
        body["on"] = cmd.on
    elif isinstance(cmd, (ColorCommand, EffectCommand, TextCommand)):
        seg = _build_segment(cmd, seg_id=0)
        if seg:
            # Layer the command on ID 0 and clear IDs 1-15 to prevent guest flickers
            body["seg"] = [seg] + [{"id": i, "stop": 0} for i in range(1, 16)]
            body["on"] = True
            if isinstance(cmd, TextCommand):
                body["transition"] = 0
            # Special case: brightness can be per-command
            if hasattr(cmd, "brightness") and cmd.brightness is not None:
                body["bri"] = cmd.brightness

    return body


def _build_preset_body(name: str, speed_override: int | None = None) -> dict:
    """Consolidate all commands in a preset into a single WLED body."""
    commands = PRESETS[name]
    body: dict = {"on": True}
    segments: list[dict] = []
    seg_id = 0

    for cmd in commands:
        if isinstance(cmd, BrightnessCommand):
            body["bri"] = cmd.brightness
        elif isinstance(cmd, PowerCommand):
            body["on"] = cmd.on
        else:
            # Apply speed override to Effect or Text commands
            if speed_override is not None:
                if isinstance(cmd, (EffectCommand, TextCommand)):
                    cmd = cmd.model_copy(update={"speed": speed_override})

            seg = _build_segment(cmd, seg_id=seg_id)
            if seg:
                # Ensure text commands have 0 transition for smooth scrolling
                if isinstance(cmd, TextCommand):
                    body["transition"] = 0
                
                if hasattr(cmd, "brightness") and cmd.brightness is not None:
                    body["bri"] = cmd.brightness
                segments.append(seg)
                seg_id += 1

    if segments:
        # Clear any remaining segments up to 15 to ensure a clean state
        for i in range(seg_id, 16):
            segments.append({"id": i, "stop": 0})
        body["seg"] = segments
    return body


async def _post_one(
    client: httpx.AsyncClient,
    device: WledDevice,
    body: dict,
    *,
    timeout: float,  # noqa: ASYNC109
    retries: int = 2,
) -> PushResult:
    url = f"http://{device.ip}/json/state"
    last_result: PushResult | None = None
    for attempt in range(1 + retries):
        try:
            response = await client.post(
                url,
                content=json.dumps(body, ensure_ascii=False).encode(),
                headers={"content-type": "application/json"},
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            logger.debug("push %s: timeout (attempt %d): %s", device.ip, attempt + 1, exc)
            last_result = PushResult(ok=False, error=f"timeout: {exc}")
        except httpx.HTTPError as exc:
            logger.debug("push %s: transport error (attempt %d): %s", device.ip, attempt + 1, exc)
            last_result = PushResult(ok=False, error=str(exc))
        else:
            if response.status_code != httpx.codes.OK:
                return PushResult(ok=False, status=response.status_code, error=response.text[:200])
            return PushResult(ok=True, status=response.status_code)
        if attempt < retries:
            await asyncio.sleep(0.3)
    return last_result  # type: ignore[return-value]



async def push_command(
    client: httpx.AsyncClient,
    device: WledDevice,
    command: Command,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> PushResult:
    """Send a Command to a WLED device. Never raises."""
    if isinstance(command, PresetCommand):
        bodies = [_build_preset_body(command.name, speed_override=command.speed_override)]
    else:
        bodies = [_build_command_body(command)]

    last: PushResult = PushResult(ok=True, status=200)
    for body in bodies:
        if not body:
            continue
        last = await _post_one(client, device, body, timeout=timeout)
        if not last.ok:
            return last
    return last
