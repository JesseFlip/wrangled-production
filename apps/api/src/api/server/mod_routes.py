"""Moderation REST routes — admin controls for the operator dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from wrangled_contracts import PowerCommand

from api.server.auth import AuthChecker, build_rest_auth_dep

if TYPE_CHECKING:
    from api.moderation import ModerationStore
    from api.server.hub import Hub
    from api.server.stream import CommandEventBus

# ── Request bodies ────────────────────────────────────────────────────


class ConfigUpdate(BaseModel):
    bot_paused: bool | None = None
    preset_only_mode: bool | None = None
    brightness_cap: int | None = Field(default=None, ge=0, le=255)
    cooldown_seconds: int | None = Field(default=None, ge=0, le=60)


class BanBody(BaseModel):
    user_id: str
    username: str = ""
    reason: str = ""


class LockBody(BaseModel):
    reason: str = ""


# ── Router ────────────────────────────────────────────────────────────


def build_mod_router(mod: ModerationStore, hub: Hub, auth: AuthChecker, event_bus: CommandEventBus | None = None) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api/mod", dependencies=[Depends(dep)])

    # Config
    @router.get("/config")
    def get_config() -> dict:
        cfg = mod.get_config()
        cfg.pop("id", None)
        return cfg

    @router.put("/config")
    def put_config(body: ConfigUpdate) -> dict:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        cfg = mod.update_config(**updates)
        cfg.pop("id", None)
        return cfg

    # Emergency off
    @router.post("/emergency-off")
    async def emergency_off() -> dict:
        mod.emergency_off()
        # Send power off to every connected device
        import contextlib  # noqa: PLC0415

        for device in hub.all_devices():
            with contextlib.suppress(Exception):
                await hub.send_command(device.mac, PowerCommand(on=False), timeout=3.0)
        if event_bus:
            from api.server.stream import CommandEvent  # noqa: PLC0415

            event_bus.publish(CommandEvent(
                who="admin", source="rest", command_kind="emergency_off",
                content="All devices off, bot paused", target="all", result="ok",
            ))
        return {"ok": True, "message": "All devices off, bot paused"}

    # Command history
    @router.get("/history")
    def get_history(limit: int = 100) -> list[dict]:
        return mod.get_history(limit=min(limit, 500))

    # Device locks
    @router.get("/devices")
    def list_locks() -> list[dict]:
        return mod.list_device_locks()

    @router.post("/device/{mac}/lock")
    def lock_device(mac: str, body: LockBody | None = None) -> dict:
        reason = body.reason if body else ""
        mod.lock_device(mac, reason=reason)
        return {"mac": mac, "locked": True, "reason": reason}

    @router.post("/device/{mac}/unlock")
    def unlock_device(mac: str) -> dict:
        mod.unlock_device(mac)
        return {"mac": mac, "locked": False}

    # Banned users
    @router.get("/banned")
    def list_banned() -> list[dict]:
        return mod.list_banned()

    @router.post("/banned")
    def ban_user(body: BanBody) -> dict:
        mod.ban_user(body.user_id, username=body.username, reason=body.reason)
        if event_bus:
            from api.server.stream import CommandEvent  # noqa: PLC0415

            event_bus.publish(CommandEvent(
                who="admin", source="rest", command_kind="ban",
                content=f"Banned {body.username or body.user_id}: {body.reason}",
                target="all", result="ok",
            ))
        return {"ok": True}

    @router.delete("/banned/{user_id}")
    def unban_user(user_id: str) -> dict:
        mod.unban_user(user_id)
        return {"ok": True}

    # Quick texts (persisted canned messages)
    @router.get("/quick-texts")
    def list_quick_texts() -> dict:
        return {"texts": mod.list_quick_texts()}

    @router.post("/quick-texts")
    def add_quick_text(body: dict) -> dict:
        return {"texts": mod.add_quick_text(body.get("text", ""))}

    @router.delete("/quick-texts/{text}")
    def remove_quick_text(text: str) -> dict:
        return {"texts": mod.remove_quick_text(text)}

    # Device group tags
    @router.get("/device-groups")
    def list_device_groups() -> dict:
        return {"groups": mod.list_device_groups()}

    @router.put("/device-groups/{mac}")
    def set_device_group(mac: str, body: dict) -> dict:
        mod.set_device_group(mac, body.get("group", ""))
        return {"ok": True}

    return router
