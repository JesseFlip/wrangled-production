"""Matrix mode REST routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.server.auth import AuthChecker, build_rest_auth_dep

if TYPE_CHECKING:
    from api.matrix_mode import MatrixModeManager


class ModeBody(BaseModel):
    mode: str  # idle, clock, countdown_to, countdown_minutes, schedule
    target: str | None = None  # ISO datetime for countdown_to
    minutes: int | None = None  # for countdown_minutes
    color: dict[str, int] | None = None  # {r, g, b}
    speed: int | None = None
    brightness: int | None = None


def build_mode_router(manager: MatrixModeManager, auth: AuthChecker) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api/mode", dependencies=[Depends(dep)])

    @router.get("")
    def get_mode() -> dict[str, Any]:
        return manager.config

    @router.put("")
    async def set_mode(body: ModeBody) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if body.target:
            kwargs["target"] = body.target
        if body.minutes is not None:
            kwargs["minutes"] = body.minutes
        if body.color:
            kwargs["color"] = body.color
        if body.speed is not None:
            kwargs["speed"] = body.speed
        if body.brightness is not None:
            kwargs["brightness"] = body.brightness
        return await manager.set_mode(body.mode, **kwargs)

    @router.patch("")
    async def update_mode_config(body: ModeBody) -> dict[str, Any]:
        """Update mode config (e.g. color) without changing/restarting mode."""
        kwargs: dict[str, Any] = {}
        if body.color:
            kwargs["color"] = body.color
        if body.speed is not None:
            kwargs["speed"] = body.speed
        if body.brightness is not None:
            kwargs["brightness"] = body.brightness
        return manager.update_config(**kwargs)

    @router.post("/idle")
    async def go_idle() -> dict[str, Any]:
        return await manager.set_mode("idle")

    return router
