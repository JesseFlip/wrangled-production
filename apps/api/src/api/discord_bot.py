"""Discord bot — optional gateway task inside the api process.

Starts only when DISCORD_BOT_TOKEN is set. Registers both slash commands
(/led ...) and message-prefix commands (!led ...).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from wrangled_contracts import (
    EFFECT_FX_ID,
    PRESETS,
    RGB,
    BrightnessCommand,
    ColorCommand,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    PushResult,
    TextCommand,
    command_from_emoji,
)

from api.discord_queue import (
    DiscordQueue,
    EnqueueResult,
    pick_queue_full,
    pick_queued,
    pick_unicode,
    pick_user_limit,
)

if TYPE_CHECKING:
    from api.matrix_mode import MatrixModeManager
    from api.moderation import ModerationStore
    from api.server.hub import Hub
    from api.server.stream import CommandEventBus

logger = logging.getLogger(__name__)

EFFECT_NAMES = list(EFFECT_FX_ID.keys())
PRESET_NAMES = list(PRESETS.keys())


def _first_mac(hub: Hub) -> str | None:
    """Get the MAC of the first known device (convenience for single-matrix setups)."""
    devices = hub.all_devices()
    return devices[0].mac if devices else None


def _summarize_cmd(cmd: object) -> str:
    """Short description of a command for the event stream."""
    if isinstance(cmd, TextCommand):
        return cmd.text
    if isinstance(cmd, EffectCommand):
        return cmd.name
    if isinstance(cmd, ColorCommand):
        return f"color({cmd.color.r},{cmd.color.g},{cmd.color.b})"
    if isinstance(cmd, PresetCommand):
        return cmd.name
    if isinstance(cmd, PowerCommand):
        return f"power({'on' if cmd.on else 'off'})"
    return getattr(cmd, "kind", "?")


async def _send(  # noqa: C901, PLR0913, PLR0911, PLR0912, PLR0915
    hub: Hub,
    command,  # noqa: ANN001
    mac: str | None = None,
    *,
    mod: ModerationStore | None = None,
    event_bus: CommandEventBus | None = None,
    mode_mgr: MatrixModeManager | None = None,
    user_id: str = "unknown",
    username: str = "unknown",
) -> PushResult | str:
    """Push a command to the hub with moderation checks."""
    if mode_mgr is not None:
        await mode_mgr.interrupt()
    if mod is not None:
        if mod.bot_paused:
            return "Bot is paused by admin."
        if mod.is_banned(user_id):
            return "You are banned."
        remaining = mod.check_rate_limit(user_id)
        if remaining is not None:
            return f"Cooldown: {remaining}s remaining."
        if mod.preset_only and not isinstance(command, (PresetCommand, PowerCommand)):
            return "Preset-only mode is active."
        if isinstance(command, TextCommand):
            match = mod.check_profanity(command.text)
            if match:
                return "Blocked content."
        # Clamp brightness
        cap = mod.brightness_cap
        if hasattr(command, "brightness") and command.brightness is not None:  # noqa: SIM102
            if command.brightness > cap:
                command = command.model_copy(update={"brightness": cap})
        if isinstance(command, BrightnessCommand) and command.brightness > cap:
            command = BrightnessCommand(brightness=cap)

    targets = [mac] if mac else [d.mac for d in hub.all_devices()]
    if not targets:
        return "No WLED devices connected."

    last_result: PushResult | str = "No devices reached."
    hit_targets: list[str] = []
    ok_count = 0
    fail_count = 0
    for target in targets:
        if mod is not None and mod.is_device_locked(target):
            continue
        try:
            result = await hub.send_command(target, command)
        except Exception as exc:  # noqa: BLE001
            last_result = str(exc)
            fail_count += 1
            hit_targets.append(target)
            continue
        if result.ok:
            ok_count += 1
        else:
            fail_count += 1
        hit_targets.append(target)
        last_result = result

    if hit_targets and mod is not None:
        mod.record_command(user_id)
        if ok_count and not fail_count:
            agg_result = "ok"
        elif ok_count and fail_count:
            agg_result = f"partial ({ok_count}/{len(hit_targets)} ok)"
        else:
            agg_result = "fail"
        mod.log_command(
            who=f"{username} ({user_id})",
            source="discord",
            device_mac="all" if mac is None else mac,
            command_kind=getattr(command, "kind", "?"),
            detail=str(getattr(command, "model_dump", dict)())[:200],
            result=agg_result,
        )
        if event_bus is not None:
            from api.server.stream import CommandEvent  # noqa: PLC0415

            event_bus.publish(
                CommandEvent(
                    who=f"{username}",
                    source="discord",
                    command_kind=getattr(command, "kind", "?"),
                    content=_summarize_cmd(command),
                    target="all" if mac is None else mac,
                    result=agg_result,
                )
            )
    return last_result


def _parse_color(value: str) -> RGB | None:
    """Try to parse a color string (name, hex, emoji)."""
    try:
        return RGB.parse(value.strip())
    except (ValueError, TypeError):
        return None


class WrangledBot(commands.Bot):
    """Discord bot that drives WLED matrices via the Hub."""

    def __init__(
        self,
        hub: Hub,
        guild_ids: list[int] | None = None,
        mod: ModerationStore | None = None,
        event_bus: CommandEventBus | None = None,
        mode_mgr: MatrixModeManager | None = None,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.hub = hub
        self.mod = mod
        self.event_bus = event_bus
        self.mode_mgr = mode_mgr
        self.queue = DiscordQueue()
        self._guild_ids = guild_ids or []
        self._setup_slash_commands()

    def _build_dispatch(self, command, uid: str, uname: str):  # noqa: ANN001, ANN202
        """Closure the worker runs when the command's slot comes up."""

        async def _dispatch() -> None:
            await _send(
                self.hub,
                command,
                mod=self.mod,
                event_bus=self.event_bus,
                mode_mgr=self.mode_mgr,
                user_id=uid,
                username=uname,
            )

        return _dispatch

    def enqueue_for_interaction(
        self,
        interaction: discord.Interaction,
        command,  # noqa: ANN001
    ) -> str:
        """Queue a command from a slash interaction and return the ack message."""
        uid = str(interaction.user.id)
        uname = str(interaction.user)
        result = self.queue.try_enqueue(uid, self._build_dispatch(command, uid, uname))
        if result == EnqueueResult.QUEUED:
            return pick_queued(self.queue.depth())
        if result == EnqueueResult.QUEUE_FULL:
            return pick_queue_full()
        return pick_user_limit()

    def enqueue_for_ctx(
        self,
        ctx: commands.Context,
        command,  # noqa: ANN001
    ) -> str:
        """Queue a command from a prefix-command context."""
        uid = str(ctx.author.id)
        uname = str(ctx.author)
        result = self.queue.try_enqueue(uid, self._build_dispatch(command, uid, uname))
        if result == EnqueueResult.QUEUED:
            return pick_queued(self.queue.depth())
        if result == EnqueueResult.QUEUE_FULL:
            return pick_queue_full()
        return pick_user_limit()

    def enqueue_for_message(
        self,
        message: discord.Message,
        command,  # noqa: ANN001
    ) -> str:
        """Queue a command from a raw message (e.g. emoji trigger)."""
        uid = str(message.author.id)
        uname = str(message.author)
        result = self.queue.try_enqueue(uid, self._build_dispatch(command, uid, uname))
        if result == EnqueueResult.QUEUED:
            return pick_queued(self.queue.depth())
        if result == EnqueueResult.QUEUE_FULL:
            return pick_queue_full()
        return pick_user_limit()

    def _setup_slash_commands(self) -> None:
        led_group = app_commands.Group(name="led", description="Control the WrangLED matrix")

        @led_group.command(name="color", description="Set a solid color")
        @app_commands.describe(color="Color name, #hex, or emoji", brightness="0-200 (optional)")
        async def slash_color(
            interaction: discord.Interaction, color: str, brightness: int | None = None
        ) -> None:
            rgb = _parse_color(color)
            if rgb is None:
                await interaction.response.send_message(f"Unknown color: `{color}`", ephemeral=True)
                return
            cmd = ColorCommand(color=rgb, brightness=brightness)
            await interaction.response.send_message(self.enqueue_for_interaction(interaction, cmd))

        @led_group.command(name="brightness", description="Set brightness (0-200)")
        @app_commands.describe(level="Brightness level 0-200")
        async def slash_brightness(interaction: discord.Interaction, level: int) -> None:
            cmd = BrightnessCommand(brightness=min(max(level, 0), 200))
            await interaction.response.send_message(self.enqueue_for_interaction(interaction, cmd))

        @led_group.command(name="effect", description="Run a named effect")
        @app_commands.describe(name="Effect name", speed="Speed 0-255", intensity="Intensity 0-255")
        @app_commands.choices(name=[app_commands.Choice(name=n, value=n) for n in EFFECT_NAMES])
        async def slash_effect(
            interaction: discord.Interaction,
            name: app_commands.Choice[str],
            speed: int | None = None,
            intensity: int | None = None,
        ) -> None:
            cmd = EffectCommand(name=name.value, speed=speed, intensity=intensity)
            await interaction.response.send_message(self.enqueue_for_interaction(interaction, cmd))

        @led_group.command(name="text", description="Scroll a message across the matrix")
        @app_commands.describe(
            message="Text to display (max 64 chars, ASCII only)",
            color="Color (optional)",
            speed="Scroll speed 32-240",
        )
        async def slash_text(
            interaction: discord.Interaction,
            message: str,
            color: str | None = None,
            speed: int = 225,
        ) -> None:
            if not message.isascii():
                await interaction.response.send_message(pick_unicode(), ephemeral=True)
                return
            rgb = _parse_color(color) if color else None
            cmd = TextCommand(text=message[:64], color=rgb, speed=min(max(speed, 32), 240))
            await interaction.response.send_message(self.enqueue_for_interaction(interaction, cmd))

        @led_group.command(name="preset", description="Apply a preset scene")
        @app_commands.describe(name="Preset name")
        async def slash_preset(
            interaction: discord.Interaction,
            name: str,
        ) -> None:
            if name not in PRESET_NAMES:
                await interaction.response.send_message(
                    f"Unknown preset. Available: {', '.join(PRESET_NAMES)}"
                )
                return
            cmd = PresetCommand(name=name)
            await interaction.response.send_message(self.enqueue_for_interaction(interaction, cmd))

        @slash_preset.autocomplete("name")
        async def _preset_autocomplete(
            interaction: discord.Interaction,
            current: str,  # noqa: ARG001
        ) -> list[app_commands.Choice[str]]:
            return [
                app_commands.Choice(name=n, value=n)
                for n in PRESET_NAMES
                if current.lower() in n.lower()
            ][:25]

        @led_group.command(name="on", description="Turn the matrix on")
        async def slash_on(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(
                self.enqueue_for_interaction(interaction, PowerCommand(on=True))
            )

        @led_group.command(name="off", description="Turn the matrix off")
        async def slash_off(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(
                self.enqueue_for_interaction(interaction, PowerCommand(on=False))
            )

        @led_group.command(name="status", description="Show current matrix state")
        async def slash_status(interaction: discord.Interaction) -> None:
            mac = _first_mac(self.hub)
            if mac is None:
                await interaction.response.send_message("No devices connected.", ephemeral=True)
                return
            try:
                state = await self.hub.get_state(mac)
                on = state.get("on", False)
                bri = state.get("bri", "?")
                seg = state.get("seg", [{}])[0] if state.get("seg") else {}
                fx = seg.get("fx", "?")
                col = seg.get("col", [[0, 0, 0]])[0]
                status_line = (
                    f"{'🟢' if on else '🔴'} {'ON' if on else 'OFF'}"
                    f" · bri {bri} · fx {fx}"
                    f" · rgb({col[0]},{col[1]},{col[2]})"
                )
                await interaction.response.send_message(status_line)
            except Exception as exc:  # noqa: BLE001
                await interaction.response.send_message(
                    f"Could not read state: {exc}", ephemeral=True
                )

        self.tree.add_command(led_group)

    async def setup_hook(self) -> None:
        await self.queue.start()
        if self._guild_ids:
            for gid in self._guild_ids:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info("discord: synced slash commands to guild %s", gid)
        else:
            await self.tree.sync()
            logger.info("discord: synced slash commands globally (may take ~1h to propagate)")

    async def close(self) -> None:
        await self.queue.stop()
        await super().close()

    async def on_ready(self) -> None:
        logger.info("discord: logged in as %s (id=%s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        # Process prefix commands
        await self.process_commands(message)
        # Also check for standalone emoji
        content = message.content.strip()
        max_emoji_len = 4
        if len(content) <= max_emoji_len and not content.startswith("!"):
            cmd = command_from_emoji(content)
            if cmd is not None:
                reply = self.enqueue_for_message(message, cmd)
                await message.reply(reply, mention_author=False)


def setup_prefix_commands(bot: WrangledBot) -> None:  # noqa: C901, PLR0915
    """Register !led prefix commands."""

    @bot.command(name="led")
    async def led_command(ctx: commands.Context, *, args: str = "") -> None:  # noqa: C901, PLR0911, PLR0912, PLR0915
        parts = args.strip().split(maxsplit=1)
        if not parts:
            await ctx.reply(
                "Usage: `!led <color|effect|text|preset|on|off|status|brightness> [args]`"
            )
            return

        verb = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if verb in ("on", "power-on"):
            await ctx.reply(bot.enqueue_for_ctx(ctx, PowerCommand(on=True)))
        elif verb in ("off", "power-off"):
            await ctx.reply(bot.enqueue_for_ctx(ctx, PowerCommand(on=False)))
        elif verb == "status":
            mac = _first_mac(bot.hub)
            if mac is None:
                await ctx.reply("No devices connected.")
                return
            try:
                state = await bot.hub.get_state(mac)
                on = state.get("on", False)
                bri = state.get("bri", "?")
                seg = state.get("seg", [{}])[0] if state.get("seg") else {}
                fx = seg.get("fx", "?")
                col = seg.get("col", [[0, 0, 0]])[0]
                status_line = (
                    f"{'🟢' if on else '🔴'} {'ON' if on else 'OFF'}"
                    f" · bri {bri} · fx {fx}"
                    f" · rgb({col[0]},{col[1]},{col[2]})"
                )
                await ctx.reply(status_line)
            except Exception as exc:  # noqa: BLE001
                await ctx.reply(f"Could not read state: {exc}")
        elif verb in {"brightness", "bri"}:
            try:
                level = int(rest)
            except ValueError:
                await ctx.reply("Usage: `!led brightness <0-200>`")
                return
            await ctx.reply(
                bot.enqueue_for_ctx(ctx, BrightnessCommand(brightness=min(max(level, 0), 200)))
            )
        elif verb in {"effect", "fx"}:
            name = rest.strip().lower()
            if name not in EFFECT_NAMES:
                await ctx.reply(f"Unknown effect. Available: {', '.join(EFFECT_NAMES)}")
                return
            await ctx.reply(bot.enqueue_for_ctx(ctx, EffectCommand(name=name)))
        elif verb == "text":
            if not rest:
                await ctx.reply("Usage: `!led text <message>`")
                return
            if not rest.isascii():
                await ctx.reply(pick_unicode())
                return
            await ctx.reply(bot.enqueue_for_ctx(ctx, TextCommand(text=rest[:64], speed=225)))
        elif verb == "preset":
            name = rest.strip().lower()
            if name not in PRESET_NAMES:
                await ctx.reply(f"Unknown preset. Available: {', '.join(PRESET_NAMES)}")
                return
            await ctx.reply(bot.enqueue_for_ctx(ctx, PresetCommand(name=name)))
        else:
            # Try as a color
            rgb = _parse_color(verb)
            if rgb is not None:
                await ctx.reply(bot.enqueue_for_ctx(ctx, ColorCommand(color=rgb)))
            else:
                # Try as emoji
                cmd = command_from_emoji(verb)
                if cmd is not None:
                    await ctx.reply(bot.enqueue_for_ctx(ctx, cmd))
                else:
                    verbs = "color, effect, text, preset, brightness, on, off, status"
                    await ctx.reply(f"Unknown command: `{verb}`. Try: {verbs}")


async def run_discord_bot(  # noqa: PLR0913
    hub: Hub,
    token: str,
    guild_ids: list[int] | None = None,
    mod: ModerationStore | None = None,
    event_bus: CommandEventBus | None = None,
    mode_mgr: MatrixModeManager | None = None,
) -> None:
    """Start the Discord bot. Runs forever (call as asyncio.create_task)."""
    bot = WrangledBot(
        hub,
        guild_ids=guild_ids,
        mod=mod,
        event_bus=event_bus,
        mode_mgr=mode_mgr,
    )
    setup_prefix_commands(bot)
    try:
        await bot.start(token)
    except Exception:
        logger.exception("discord bot crashed")
    finally:
        if not bot.is_closed():
            await bot.close()
