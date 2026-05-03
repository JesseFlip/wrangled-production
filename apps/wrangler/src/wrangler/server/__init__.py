"""Wrangler FastAPI server."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wrangler.server.app import create_app

__all__ = ["create_app"]


def __getattr__(name: str) -> object:
    if name == "create_app":
        from wrangler.server.app import create_app  # noqa: PLC0415

        return create_app
    raise AttributeError(name)
