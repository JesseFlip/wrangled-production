# ruff: noqa: ANN401, PLC0415, SIM105, S110
"""Matrix mode — background task that autonomously drives the matrix.

Modes:
- idle:              no auto-push (default)
- clock:             shows current time
- countdown_to:      counts down to a target datetime
- countdown_minutes: counts down N minutes from activation
- schedule:          auto-shows current/next talk from conference data
"""

from __future__ import annotations

# ruff: noqa: ANN401, PLC0415, SIM105, S110
import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from wrangled_contracts import TextCommand

from api.schedule_logic import get_current_session, get_next_session

if TYPE_CHECKING:
    from api.server.hub import Hub

logger = logging.getLogger(__name__)

_TICK_FAST = 1  # countdown modes — every second
_TICK_SLOW = 10  # clock/schedule — every 10s


class MatrixModeManager:
    """Runs a background loop that pushes text commands based on the active mode."""

    def __init__(self, hub: Hub, mod: Any) -> None:
        self._hub = hub
        self._mod = mod
        self._mode: str = "idle"
        self._config: dict[str, Any] = {}
        self._task: asyncio.Task | None = None
        self._countdown_end: datetime | None = None
        self._last_pushed_text: str | None = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def config(self) -> dict[str, Any]:
        return {"mode": self._mode, **self._config}

    def update_config(self, **kwargs: Any) -> dict[str, Any]:
        """Update config without changing mode. Forces an immediate re-push."""
        self._config.update(kwargs)
        # Force immediate re-push by restarting the loop
        # (clearing _last_pushed_text alone isn't enough if tick interval is long)
        self._restart_loop()
        return self.config

    async def set_mode(self, mode: str, **kwargs: Any) -> dict[str, Any]:
        """Switch mode. Restarts the background loop."""
        self._mode = mode
        self._config = dict(kwargs)

        if mode == "countdown_minutes":
            minutes = int(kwargs.get("minutes", 5))
            self._countdown_end = datetime.now(tz=UTC) + timedelta(minutes=minutes)
            self._config["countdown_end"] = self._countdown_end.isoformat()
        elif mode == "countdown_to":
            target = kwargs.get("target")
            if target:
                self._countdown_end = datetime.fromisoformat(target)
                self._config["countdown_end"] = self._countdown_end.isoformat()
        else:
            self._countdown_end = None

        # Log mode change
        self._mod.log_command(
            who="admin",
            source="api-ui",
            device_mac="*",
            command_kind=f"mode:{mode}",
            detail=str(self._config)[:200],
        )

        self._restart_loop()

        # Idle means blank the displays — await so callers don't race
        if mode == "idle":
            await self._blank_all()

        return self.config

    async def _fan_out(self, cmd: object, *, timeout: float = 3.0) -> None:
        """Send a command to all devices concurrently."""

        async def _one(mac: str) -> None:
            try:
                await self._hub.send_command(mac, cmd, timeout=timeout)
            except Exception:  # noqa: BLE001
                logger.debug("fan_out failed for %s", mac)

        await asyncio.gather(*[_one(d.mac) for d in self._hub.all_devices()])

    async def _blank_all(self) -> None:
        """Send solid black to all devices (blank the screen)."""
        from wrangled_contracts import ColorCommand  # noqa: PLC0415

        await self._fan_out(ColorCommand(color={"r": 0, "g": 0, "b": 0}))

    def _restart_loop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if self._mode != "idle":
            self._task = asyncio.create_task(self._run())

    async def start(self) -> None:
        """Called on app startup."""
        if self._mode != "idle":
            self._restart_loop()

    async def stop(self) -> None:
        """Called on app shutdown."""
        if self._task is not None:
            self._task.cancel()

    async def interrupt(self) -> None:
        """Cancel any running mode without blanking, leaving state at idle.

        Called by the command path (discord + REST) so a user-issued command
        isn't overwritten by the mode's next tick. Distinct from `set_mode("idle")`,
        which additionally blanks every device.
        """
        if self._mode == "idle":
            return
        self._mode = "idle"
        self._config = {}
        self._countdown_end = None
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.debug("interrupt: task raised on cancel")
            self._task = None

    def _tick_interval(self) -> float:
        # Clock/countdown: tick every second so display updates promptly.
        # The _last_pushed_text check prevents redundant sends.
        if self._mode in ("clock", "countdown_to", "countdown_minutes"):
            return _TICK_FAST
        return _TICK_SLOW

    async def _run(self) -> None:
        """Background loop — pushes text to all devices at mode-appropriate intervals."""
        self._last_pushed_text = None  # reset on mode change
        try:
            while True:
                text = self._generate_text()
                if text is None and self._mode in ("countdown_to", "countdown_minutes"):
                    # Countdown finished — fireworks then idle
                    await self._countdown_finished()
                    return
                if text and text != self._last_pushed_text:
                    # Short static text (clock/countdown) shouldn't scroll
                    no_scroll = self._mode in ("clock", "countdown_to", "countdown_minutes")
                    await self._push_text(text, speed=0 if no_scroll else None)
                    self._last_pushed_text = text
                await asyncio.sleep(self._tick_interval())
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("matrix mode loop crashed")

    def _generate_text(self) -> str | None:
        """Generate the text to display based on current mode."""
        if self._mode == "clock":
            return self._gen_clock()
        if self._mode in ("countdown_to", "countdown_minutes"):
            return self._gen_countdown()
        if self._mode == "schedule":
            return self._gen_schedule()
        return None

    def _gen_clock(self) -> str:
        now = datetime.now(tz=UTC)
        # Convert to local-ish time (CDT = UTC-5 for Austin)
        local = now - timedelta(hours=5)
        h = local.hour % 12 or 12
        m = local.strftime("%M")
        return f"{h}:{m}"

    def _gen_countdown(self) -> str | None:
        if self._countdown_end is None:
            return None
        now = datetime.now(tz=UTC)
        remaining = self._countdown_end - now
        if remaining.total_seconds() <= 0:
            return None  # signal countdown finished
        total_secs = int(remaining.total_seconds())
        minutes, seconds = divmod(total_secs, 60)
        return f"{minutes}:{seconds:02d}"

    def _gen_schedule(self) -> str | None:
        current = get_current_session()
        if current:
            session, _time_str = current
            text = session.get("title", "")
            speaker = session.get("speaker", "")
            if speaker:
                text = f"{text} - {speaker}"
            return text

        _next_session, next_time = get_next_session()
        if _next_session:
            title = _next_session.get("title", "")
            return f"Up next at {next_time}: {title}"

        return "PyTexas 2026"

    async def _push_text(self, text: str, *, speed: int | None = None) -> None:
        """Send a TextCommand to every connected device via the hub."""
        color_cfg = self._config.get("color", {"r": 255, "g": 255, "b": 255})
        speed = speed if speed is not None else self._config.get("speed", 225)
        brightness = self._config.get("brightness")

        cmd = TextCommand(
            text=text[:200],
            color=color_cfg if isinstance(color_cfg, dict) else None,
            speed=speed,
        )
        if brightness is not None:
            from wrangled_contracts import BrightnessCommand

            bri_cmd = BrightnessCommand(brightness=min(int(brightness), 200))
            await self._fan_out(bri_cmd)

        await self._fan_out(cmd)

    async def _countdown_finished(self) -> None:
        """Fire fireworks effect for 10s, then blank and go idle."""
        from wrangled_contracts import EffectCommand  # noqa: PLC0415

        logger.info("countdown finished — firing fireworks")
        fx = EffectCommand(name="fireworks", speed=128, intensity=200)
        await self._fan_out(fx)
        await asyncio.sleep(10)
        # Go idle: blank screens, stop loop (don't call set_mode from inside _run)
        self._mode = "idle"
        self._config = {}
        self._countdown_end = None
        self._task = None  # this task is about to return
        await self._blank_all()
