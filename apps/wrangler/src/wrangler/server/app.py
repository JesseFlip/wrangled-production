"""FastAPI app factory for the wrangler agent."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wrangler.hub_client import HubClient
from wrangler.scanner import ScanOptions, scan
from wrangler.server.devices import build_devices_router
from wrangler.server.metadata import build_metadata_router
from wrangler.server.schedule import build_schedule_router
from wrangler.server.registry import Registry
from wrangler.settings import WranglerSettings


def create_app(
    *,
    initial_scan: bool = True,
    registry: Registry | None = None,
    scan_options: ScanOptions | None = None,
) -> FastAPI:
    """Build the wrangler FastAPI application."""
    app = FastAPI(title="wrangler", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    reg = registry if registry is not None else Registry(scanner=scan)
    opts = scan_options or ScanOptions(mdns_timeout=2.0)
    settings = WranglerSettings()

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(build_devices_router(reg))
    app.include_router(build_metadata_router())
    app.include_router(build_schedule_router())

    hub_client: HubClient | None = None
    if settings.api_url:
        hub_client = HubClient(
            api_url=settings.api_url,
            auth_token=settings.auth_token,
            wrangler_id=settings.wrangler_id,
            registry=reg,
        )
        reg.on_changed(hub_client.notify_devices_changed)

    if initial_scan or hub_client is not None:

        @app.on_event("startup")
        async def _startup() -> None:
            if initial_scan:
                await reg.scan(opts)
            if hub_client is not None:
                app.state.hub_task = asyncio.create_task(hub_client.run())

        @app.on_event("shutdown")
        async def _shutdown() -> None:
            task = getattr(app.state, "hub_task", None)
            if task is not None:
                task.cancel()

    static_dir = Path(__file__).resolve().parents[3] / "static" / "wrangler-ui"
    if static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=static_dir, html=True),
            name="wrangler-ui",
        )

    return app
