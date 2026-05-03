"""Discord command queue.

Rate-limits dispatch of LED commands from Discord to the hub so we never
overwhelm the matrix. Replies to the user go out instantly (beating Discord's
3s ack window); the actual wrangler call happens in a background worker at
one dispatch every ~7 seconds.

The queue also caps backlog (global + per-user) so one person can't hog it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 20
MAX_PER_USER = 3
DISPATCH_INTERVAL_SECONDS = 7.0
STOP_DRAIN_TIMEOUT_SECONDS = 5.0


class EnqueueResult(StrEnum):
    """Outcome of try_enqueue."""

    QUEUED = "queued"
    QUEUE_FULL = "queue_full"
    USER_LIMIT = "user_limit"


@dataclass
class QueueItem:
    """One queued command: who asked for it and the closure that runs it."""

    user_id: str
    dispatch: Callable[[], Awaitable[None]]


class DiscordQueue:
    """FIFO queue with per-user caps and paced dispatch."""

    def __init__(
        self,
        interval: float = DISPATCH_INTERVAL_SECONDS,
        max_size: int = MAX_QUEUE_SIZE,
        max_per_user: int = MAX_PER_USER,
    ) -> None:
        self._interval = interval
        self._max_size = max_size
        self._max_per_user = max_per_user
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue(maxsize=max_size)
        self._user_counts: dict[str, int] = defaultdict(int)
        self._worker_task: asyncio.Task[None] | None = None
        self._in_flight: set[asyncio.Task[None]] = set()

    def try_enqueue(
        self,
        user_id: str,
        dispatch: Callable[[], Awaitable[None]],
    ) -> EnqueueResult:
        """Attempt to add a command. Non-blocking, returns result."""
        if self._user_counts[user_id] >= self._max_per_user:
            return EnqueueResult.USER_LIMIT
        try:
            self._queue.put_nowait(QueueItem(user_id=user_id, dispatch=dispatch))
        except asyncio.QueueFull:
            return EnqueueResult.QUEUE_FULL
        self._user_counts[user_id] += 1
        return EnqueueResult.QUEUED

    def depth(self) -> int:
        """Current number of items waiting."""
        return self._queue.qsize()

    def user_count(self, user_id: str) -> int:
        """How many of this user's items are currently queued."""
        return self._user_counts[user_id]

    async def start(self) -> None:
        """Spawn the worker loop (idempotent)."""
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(self._worker(), name="discord-queue-worker")

    async def stop(self) -> None:
        """Cancel the worker, then give in-flight dispatch tasks a chance to finish."""
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        if self._in_flight:
            await asyncio.wait(self._in_flight, timeout=STOP_DRAIN_TIMEOUT_SECONDS)

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            # Decrement user count as soon as the item leaves the queue —
            # "in queue" is what we're tracking, not "in flight".
            if self._user_counts[item.user_id] > 0:
                self._user_counts[item.user_id] -= 1
            if self._user_counts[item.user_id] == 0:
                self._user_counts.pop(item.user_id, None)

            task = asyncio.create_task(self._run_dispatch(item))
            self._in_flight.add(task)
            task.add_done_callback(self._in_flight.discard)

            await asyncio.sleep(self._interval)

    async def _run_dispatch(self, item: QueueItem) -> None:
        try:
            await item.dispatch()
        except Exception:
            logger.exception("discord queue: dispatch failed for user %s", item.user_id)


# --- Playful response copy -------------------------------------------------

_QUEUED_MESSAGES = (
    "Queued! You're #{position} in line. Patience, photon-slinger.",
    "Got it, slotted in at #{position}. The electrons are warming up.",
    "In the loop at #{position}. LEDs prefer to be asked nicely.",
    "Stashed at #{position}. The matrix will get to you in a jiffy.",
)

_QUEUE_FULL_MESSAGES = (
    "Whoa — queue's stuffed (20 deep). Let the photons catch up.",
    "Queue maxed out. The LEDs need a breather. Try again in a bit?",
    "Full house! 20 commands already waiting. Please hold.",
    "Traffic jam on the pixel highway. Try again in a minute.",
)

_USER_LIMIT_MESSAGES = (
    "Easy, cowboy — you've already got 3 in the queue. Let 'em land first.",
    "Three's your limit, friend. Wait your turn so others get a shot.",
    "Hold up! Already juggling 3 of yours. One at a time-ish.",
    "You again? Three in the queue already. Chill for a sec.",
)

_UNICODE_MESSAGES = (
    "ASCII only, please — these LEDs are minimalists. No fancy characters.",
    "Sorry, no unicode. The matrix speaks plain letters only.",
    "Can't render that — ASCII only, if you please. The pixels are picky.",
    "No emoji in text, champ. ASCII only or it's gibberish on the grid.",
)


def pick_queued(position: int) -> str:
    """Random playful 'queued' message."""
    return random.choice(_QUEUED_MESSAGES).format(position=position)  # noqa: S311


def pick_queue_full() -> str:
    """Random playful 'queue full' message."""
    return random.choice(_QUEUE_FULL_MESSAGES)  # noqa: S311


def pick_user_limit() -> str:
    """Random playful 'you have too many queued' message."""
    return random.choice(_USER_LIMIT_MESSAGES)  # noqa: S311


def pick_unicode() -> str:
    """Random playful 'ASCII only' message."""
    return random.choice(_UNICODE_MESSAGES)  # noqa: S311
