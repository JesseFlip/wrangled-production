"""Wrangled api command-line interface."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from collections.abc import Sequence

from api.server import create_app
from api.settings import ApiSettings, DiscordSettings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api", description="WrangLED central hub.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the api HTTP server.")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument(
        "--no-auth",
        dest="auth_disabled",
        action="store_true",
        help="Force auth disabled regardless of WRANGLED_AUTH_TOKEN.",
    )
    return parser


def _run_serve(args: argparse.Namespace) -> int:
    settings = ApiSettings()
    discord = DiscordSettings()
    host = args.host or settings.host
    port = args.port or settings.port
    token = None if args.auth_disabled else settings.auth_token
    # Parse guild IDs: prefer comma-separated DISCORD_GUILD_IDS, fall back to single DISCORD_GUILD_ID
    guild_ids: list[int] = []
    if discord.guild_ids:
        guild_ids = [int(g.strip()) for g in discord.guild_ids.split(",") if g.strip()]
    elif discord.guild_id:
        guild_ids = [discord.guild_id]

    app = create_app(
        auth_token=token,
        discord_token=discord.bot_token,
        discord_guild_ids=guild_ids,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "serve":
        return _run_serve(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
