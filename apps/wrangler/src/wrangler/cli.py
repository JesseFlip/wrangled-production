"""Wrangler command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence  # noqa: TC003
from ipaddress import IPv4Address, IPv4Network

import httpx
import uvicorn
from wrangled_contracts import (
    EFFECT_FX_ID,
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    TextCommand,
    WledDevice,
    command_from_emoji,
)

from wrangler.pusher import PushResult, push_command
from wrangler.scanner import ScanOptions, scan
from wrangler.scanner.probe import probe_device
from wrangler.server import create_app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wrangler", description="WrangLED Pi-side agent.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="Discover WLEDs on the LAN.")
    scan_parser.add_argument(
        "--sweep",
        action="store_true",
        help="Force IP-range sweep in addition to mDNS.",
    )
    scan_parser.add_argument(
        "--no-mdns",
        dest="use_mdns",
        action="store_false",
        help="Skip mDNS; sweep only.",
    )
    scan_parser.add_argument(
        "--subnet",
        type=IPv4Network,
        default=None,
        help="Override subnet to sweep (e.g. 10.0.6.0/24).",
    )
    scan_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Per-host probe timeout seconds (default: 2.0).",
    )
    scan_parser.add_argument(
        "--mdns-timeout",
        type=float,
        default=3.0,
        help="mDNS listen duration (default: 3.0).",
    )
    scan_parser.add_argument(
        "--concurrency",
        type=int,
        default=32,
        help="Max concurrent probes during sweep (default: 32).",
    )
    scan_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit results as JSON instead of a table.",
    )

    send_parser = sub.add_parser("send", help="Push a command to a WLED.")
    send_parser.add_argument(
        "--ip",
        type=IPv4Address,
        default=None,
        help="Target WLED IP (skips mDNS).",
    )
    send_parser.add_argument(
        "--name",
        default=None,
        help="Filter discovered devices by name substring.",
    )
    send_sub = send_parser.add_subparsers(dest="send_cmd", required=True)

    color_p = send_sub.add_parser("color", help="Set solid color.")
    color_p.add_argument("value", help="Named color, #hex, or color emoji.")
    color_p.add_argument("--brightness", type=int, default=None)

    bri_p = send_sub.add_parser("brightness", help="Set brightness (0-200).")
    bri_p.add_argument("level", type=int)

    power_p = send_sub.add_parser("power", help="Toggle power.")
    power_p.add_argument("state", choices=["on", "off"])

    effect_p = send_sub.add_parser("effect", help="Run a named effect.")
    effect_p.add_argument(
        "name",
        choices=list(EFFECT_FX_ID.keys()),
        help="Effect name.",
    )
    effect_p.add_argument("--speed", type=int, default=None)
    effect_p.add_argument("--intensity", type=int, default=None)
    effect_p.add_argument("--color", default=None)
    effect_p.add_argument("--brightness", type=int, default=None)

    text_p = send_sub.add_parser("text", help="Scroll a short text message.")
    text_p.add_argument("text")
    text_p.add_argument("--color", default=None)
    text_p.add_argument("--speed", type=int, default=128)
    text_p.add_argument("--brightness", type=int, default=None)

    preset_p = send_sub.add_parser("preset", help="Run a named preset.")
    preset_p.add_argument("name", choices=["pytexas", "party", "chill", "love_it", "snake_attack", "lone_star", "applause", "crowd_hype", "pride_ride", "sine_wave", "late_night"])

    emoji_p = send_sub.add_parser("emoji", help="Resolve a single emoji to a command.")
    emoji_p.add_argument("glyph")

    serve_parser = sub.add_parser("serve", help="Run the wrangler HTTP server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8501)
    serve_parser.add_argument(
        "--no-initial-scan",
        dest="initial_scan",
        action="store_false",
        help="Skip the startup scan.",
    )

    return parser


def _opts_from_args(args: argparse.Namespace) -> ScanOptions:
    return ScanOptions(
        use_mdns=args.use_mdns,
        mdns_timeout=args.mdns_timeout,
        sweep=True if args.sweep else None,
        sweep_subnet=args.subnet,
        probe_timeout=args.timeout,
        probe_concurrency=args.concurrency,
    )


def _print_table(devices: list[WledDevice]) -> None:
    if not devices:
        print("0 devices found.")
        return
    header = (
        f"{'IP':<15} {'NAME':<20} {'MAC':<18} {'VER':<10} {'LEDS':>5}  {'MATRIX':<7} {'VIA':<6}"
    )
    print(header)
    for d in devices:
        matrix = f"{d.matrix.width}x{d.matrix.height}" if d.matrix else "-"
        print(
            f"{d.ip!s:<15} {d.name[:20]:<20} {d.mac:<18} {d.version:<10} "
            f"{d.led_count:>5}  {matrix:<7} {d.discovered_via:<6}",
        )
    print(f"\n{len(devices)} device{'s' if len(devices) != 1 else ''}.")


def _print_json(devices: list[WledDevice]) -> None:
    payload = [d.model_dump(mode="json") for d in devices]
    print(json.dumps(payload, indent=2))


async def _run_scan(opts: ScanOptions, *, as_json: bool) -> int:
    devices = await scan(opts)
    if as_json:
        _print_json(devices)
    else:
        _print_table(devices)
    return 0


async def _resolve_device(
    *,
    ip: IPv4Address | None,
    name: str | None,
) -> WledDevice:
    """Find the target WLED. Raises on ambiguous / missing."""
    if ip is not None:
        async with httpx.AsyncClient() as client:
            device = await probe_device(client, ip, source="sweep", timeout=2.0)
        if device is None:
            msg = f"no WLED answering at {ip}"
            raise RuntimeError(msg)
        return device

    devices = await scan(ScanOptions(mdns_timeout=2.0))
    if name is not None:
        devices = [d for d in devices if name.lower() in d.name.lower()]
    if not devices:
        msg = "no WLED devices found"
        raise RuntimeError(msg)
    if len(devices) > 1:
        listing = ", ".join(f"{d.ip} ({d.name})" for d in devices)
        msg = f"multiple devices found ({listing}); pass --ip or --name"
        raise RuntimeError(msg)
    return devices[0]


def _command_from_send_args(args: argparse.Namespace) -> Command:  # noqa: PLR0911
    if args.send_cmd == "color":
        color = RGB.parse(args.value)
        return ColorCommand(color=color, brightness=args.brightness)
    if args.send_cmd == "brightness":
        return BrightnessCommand(brightness=args.level)
    if args.send_cmd == "power":
        return PowerCommand(on=args.state == "on")
    if args.send_cmd == "effect":
        color = RGB.parse(args.color) if args.color is not None else None
        return EffectCommand(
            name=args.name,
            color=color,
            speed=args.speed,
            intensity=args.intensity,
            brightness=args.brightness,
        )
    if args.send_cmd == "text":
        from pydantic import ValidationError  # noqa: PLC0415

        try:
            color = RGB.parse(args.color) if args.color is not None else None
            return TextCommand(
                text=args.text,
                color=color,
                speed=args.speed,
                brightness=args.brightness,
            )
        except ValidationError as exc:
            msg = f"invalid text command: {exc}"
            raise ValueError(msg) from exc
    if args.send_cmd == "preset":
        return PresetCommand(name=args.name)
    if args.send_cmd == "emoji":
        cmd = command_from_emoji(args.glyph)
        if cmd is None:
            msg = f"unknown emoji: {args.glyph!r}"
            raise ValueError(msg)
        return cmd
    msg = f"unknown send subcommand: {args.send_cmd}"
    raise ValueError(msg)


def _run_serve(args: argparse.Namespace) -> int:
    """Start the FastAPI server under uvicorn (blocking)."""
    app = create_app(initial_scan=args.initial_scan)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


async def _run_send(args: argparse.Namespace) -> int:
    try:
        device = await _resolve_device(ip=args.ip, name=args.name)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        command = _command_from_send_args(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    async with httpx.AsyncClient() as client:
        result: PushResult = await push_command(client, device, command)
    if not result.ok:
        tag = result.status or "error"
        print(f"push failed: {tag} {result.error or ''}".strip(), file=sys.stderr)
        return 1
    print(f"ok -> {device.ip} ({device.name})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        return asyncio.run(_run_scan(_opts_from_args(args), as_json=args.as_json))
    if args.command == "send":
        return asyncio.run(_run_send(args))
    if args.command == "serve":
        return _run_serve(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
