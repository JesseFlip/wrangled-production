"""FastAPI app factory for the wrangled api."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import __version__
from api.matrix_mode import MatrixModeManager
from api.moderation import ModerationStore
from api.server.auth import AuthChecker
from api.server.groups import DeviceGroupStore, build_groups_router
from api.server.hub import Hub
from api.server.mod_routes import build_mod_router
from api.server.mode_routes import build_mode_router
from api.server.rest import build_metadata_router, build_rest_router
from api.server.schedule import build_schedule_router
from api.server.stream import CommandEventBus, build_stream_router
from api.server.ws import build_ws_router

logger = logging.getLogger(__name__)


def create_app(
    *,
    auth_token: str | None = None,
    discord_token: str | None = None,
    discord_guild_ids: list[int] | None = None,
    mod_store: ModerationStore | None = None,
) -> FastAPI:
    """Build the wrangled api application."""
    app = FastAPI(title="wrangled-api", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    checker = AuthChecker(auth_token)
    hub = Hub()
    mod = mod_store or ModerationStore()
    mode_mgr = MatrixModeManager(hub, mod)
    event_bus = CommandEventBus()
    group_store = DeviceGroupStore()
    app.state.auth_checker = checker
    app.state.hub = hub
    app.state.mod = mod
    app.state.mode_mgr = mode_mgr
    app.state.event_bus = event_bus
    app.state.group_store = group_store

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "ok": True,
            "wranglers": len(hub.wranglers_summary()),
            "discord": discord_token is not None,
            "bot_paused": mod.bot_paused,
            "matrix_mode": mode_mgr.mode,
        }

    app.include_router(build_ws_router(hub, checker))
    app.include_router(build_rest_router(hub, checker, mod, event_bus, mode_mgr))
    app.include_router(build_metadata_router())
    app.include_router(build_mod_router(mod, hub, checker, event_bus))
    app.include_router(build_schedule_router())
    app.include_router(build_mode_router(mode_mgr, checker))
    app.include_router(build_stream_router(event_bus, checker))
    app.include_router(build_groups_router(group_store, checker))

    @app.on_event("startup")
    async def _start_mode_mgr() -> None:
        await mode_mgr.start()

    @app.on_event("shutdown")
    async def _stop_mode_mgr() -> None:
        await mode_mgr.stop()

    if discord_token:

        @app.on_event("startup")
        async def _start_discord() -> None:
            from api.discord_bot import run_discord_bot  # noqa: PLC0415

            app.state.discord_task = asyncio.create_task(
                run_discord_bot(
                    hub,
                    discord_token,
                    guild_ids=discord_guild_ids or [],
                    mod=mod,
                    event_bus=event_bus,
                    mode_mgr=mode_mgr,
                ),
            )
            logger.info("discord bot starting (guild_ids=%s)", discord_guild_ids)

        @app.on_event("shutdown")
        async def _stop_discord() -> None:
            task = getattr(app.state, "discord_task", None)
            if task is not None:
                task.cancel()

    @app.on_event("shutdown")
    async def _close_mod_db() -> None:
        mod.close()
        logger.info("moderation db flushed and closed")

    static_dir = Path(__file__).resolve().parents[3] / "static" / "dashboard"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app
