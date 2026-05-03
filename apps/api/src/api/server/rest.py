"""REST routes for external callers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from wrangled_contracts import (
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
    PushResult,
    WledDevice,
)

from api.server.auth import build_rest_auth_dep
from api.server.hub import (
    NoWranglerForDeviceError,
    WranglerTimeoutError,
)

if TYPE_CHECKING:
    from api.matrix_mode import MatrixModeManager
    from api.moderation import ModerationStore
    from api.server.auth import AuthChecker
    from api.server.hub import Hub
    from api.server.stream import CommandEventBus


def _summarize(cmd: Command) -> str:
<<<<<<< HEAD
    from wrangled_contracts import PresetCommand, TextCommand
=======
    from wrangled_contracts import PresetCommand, TextCommand  # noqa: PLC0415

>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
    if isinstance(cmd, EffectCommand):
        return cmd.name
    if isinstance(cmd, ColorCommand):
        return f"color({cmd.color.r},{cmd.color.g},{cmd.color.b})"
    if isinstance(cmd, PowerCommand):
        return f"power({'on' if cmd.on else 'off'})"
    if isinstance(cmd, PresetCommand):
        return cmd.name
    if isinstance(cmd, TextCommand):
        return cmd.text
    return cmd.kind


class _RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=32)


def build_metadata_router() -> APIRouter:
    """Read-only metadata routes — no auth, no hub dependency."""
    router = APIRouter(prefix="/api")

    @router.get("/effects")
    def list_effects() -> dict[str, list[str]]:
        return {"effects": list(EFFECT_FX_ID.keys())}

    @router.get("/presets")
    def list_presets() -> dict[str, list[str]]:
        return {"presets": list(PRESETS.keys())}

    @router.get("/emoji")
    def list_emoji() -> dict[str, dict[str, dict]]:
        return {
<<<<<<< HEAD
            "emoji": {
                k: {"label": _summarize(v), "command": v}
                for k, v in EMOJI_COMMANDS.items()
            }
=======
            "emoji": {k: {"label": _summarize(v), "command": v} for k, v in EMOJI_COMMANDS.items()}
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
        }

    return router


def build_rest_router(  # noqa: C901, PLR0915
    hub: Hub,
    auth: AuthChecker,
    mod: ModerationStore | None = None,
    event_bus: CommandEventBus | None = None,
    mode_mgr: MatrixModeManager | None = None,
) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api", dependencies=[Depends(dep)])

    @router.get("/devices")
    def list_devices() -> dict[str, list[WledDevice]]:
        return {"devices": hub.all_devices()}

    @router.get("/devices/{mac}")
    def get_device(mac: str) -> WledDevice:
        device = hub.find_device(mac)
        if device is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        return device

    @router.get("/devices/{mac}/state")
    async def get_state(mac: str) -> dict:
        if hub.find_device(mac) is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        try:
            state = await hub.get_state(mac)
        except NoWranglerForDeviceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WranglerTimeoutError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"state": state}

    @router.post("/devices/{mac}/commands")
    async def post_command(mac: str, command: Command) -> PushResult:  # noqa: C901, PLR0912
        if hub.find_device(mac) is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        if mode_mgr is not None:
            await mode_mgr.interrupt()
        # Moderation checks
        if mod is not None:
            if mod.is_device_locked(mac):
                raise HTTPException(status_code=403, detail="device is locked by admin")
            from wrangled_contracts import (  # noqa: PLC0415
                BrightnessCommand,
                PresetCommand,
                TextCommand,
            )

            if mod.preset_only and not isinstance(command, (PresetCommand, PowerCommand)):
                raise HTTPException(status_code=403, detail="preset-only mode is active")
            if isinstance(command, TextCommand):
                match = mod.check_profanity(command.text)
                if match:
                    if event_bus:
                        from api.server.stream import CommandEvent  # noqa: PLC0415

                        blocked_content = (
                            command.text
                            if hasattr(command, "text")
                            else str(command.model_dump())[:200]
                        )
                        event_bus.publish(
                            CommandEvent(
                                who="api-user",
                                source="rest",
                                command_kind=command.kind,
                                content=blocked_content,
                                target=mac,
                                result="blocked",
                                flag="content_blocked",
                                flag_reason=match,
                            )
                        )
                    raise HTTPException(status_code=403, detail="blocked content")
            # Clamp brightness
            cap = mod.brightness_cap
            if hasattr(command, "brightness") and command.brightness is not None:  # noqa: SIM102
                if command.brightness > cap:
                    command = command.model_copy(update={"brightness": cap})
            if isinstance(command, BrightnessCommand) and command.brightness > cap:
                command = BrightnessCommand(brightness=cap)
        try:
            result = await hub.send_command(mac, command)
        except NoWranglerForDeviceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WranglerTimeoutError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        # Log
        if mod is not None:
            mod.log_command(
                who="api-user",
                source="rest",
                device_mac=mac,
                command_kind=command.kind,
                detail=str(command.model_dump(exclude={"raw_info"}))[:200],
                result="ok" if result.ok else (result.error or "fail"),
            )
        if event_bus:
            from api.server.stream import CommandEvent  # noqa: PLC0415

            event_bus.publish(
                CommandEvent(
                    who="api-user",
                    source="rest",
                    command_kind=command.kind,
                    content=_summarize(command),
                    target=mac,
                    result="ok" if result.ok else (result.error or "fail"),
                )
            )
        return result

    @router.put("/devices/{mac}/name")
    async def put_name(mac: str, body: _RenameBody) -> WledDevice:
        if hub.find_device(mac) is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        try:
            return await hub.send_rename(mac, body.name)
        except NoWranglerForDeviceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WranglerTimeoutError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/scan")
    async def run_scan() -> dict[str, list[WledDevice]]:
        devices = await hub.rescan_all()
        return {"devices": devices}

    @router.get("/wranglers")
    def wranglers() -> list[dict]:
        return hub.wranglers_summary()

    @router.get("/commands/recent")
    def recent_commands(limit: int = 100) -> dict[str, list[dict]]:
        """Recent command history from the persistent log, oldest first.

        Used by the dashboard stream view to backfill history on page load
        before the live SSE subscription takes over.
        """
        if mod is None:
            return {"events": []}
        capped = max(1, min(limit, 500))
        rows = mod.get_history(limit=capped)
        # get_history returns newest-first; reverse for stream-append order.
        rows.reverse()
        events = [
            {
                "who": row.get("who", ""),
                "source": row.get("source", ""),
                "command_kind": row.get("command_kind", ""),
                "content": row.get("detail", ""),
                "target": row.get("device_mac", ""),
                "result": row.get("result", ""),
                "flag": False,
                "flag_reason": "",
                "timestamp": row.get("timestamp", ""),
            }
            for row in rows
        ]
        return {"events": events}

    return router
