"""Unit tests for api.discord_queue."""

from __future__ import annotations

import asyncio
from itertools import pairwise

import pytest

from api.discord_queue import (
    DiscordQueue,
    EnqueueResult,
    pick_queue_full,
    pick_queued,
    pick_unicode,
    pick_user_limit,
)


def _noop():
    async def _c() -> None:
        return

    return _c()


def test_enqueue_accepts_up_to_max_size() -> None:
    q = DiscordQueue(interval=0.01, max_size=20, max_per_user=20)
    for i in range(20):
        assert q.try_enqueue(f"user-{i}", _noop) == EnqueueResult.QUEUED
    assert q.try_enqueue("user-overflow", _noop) == EnqueueResult.QUEUE_FULL


def test_enqueue_enforces_per_user_limit() -> None:
    q = DiscordQueue(interval=0.01, max_size=20, max_per_user=3)
    for _ in range(3):
        assert q.try_enqueue("alice", _noop) == EnqueueResult.QUEUED
    assert q.try_enqueue("alice", _noop) == EnqueueResult.USER_LIMIT
    # But another user is fine.
    assert q.try_enqueue("bob", _noop) == EnqueueResult.QUEUED


async def test_user_count_decrements_after_dispatch() -> None:
    dispatched = asyncio.Event()

    async def slow_dispatch() -> None:
        dispatched.set()

    q = DiscordQueue(interval=0.05, max_size=20, max_per_user=3)
    await q.start()
    try:
        # Fill alice's slots.
        for _ in range(3):
            assert q.try_enqueue("alice", slow_dispatch) == EnqueueResult.QUEUED
        assert q.user_count("alice") == 3

        # Wait for the first pop.
        await asyncio.wait_for(dispatched.wait(), timeout=1.0)
        # Worker pops item, decrements count, then sleeps for interval.
        await asyncio.sleep(0)  # let worker finish decrement step

        assert q.user_count("alice") == 2
        # Alice can now enqueue again.
        assert q.try_enqueue("alice", slow_dispatch) == EnqueueResult.QUEUED
    finally:
        await q.stop()


async def test_dispatch_pacing() -> None:
    timestamps: list[float] = []
    loop = asyncio.get_running_loop()

    async def record() -> None:
        timestamps.append(loop.time())

    interval = 0.1
    q = DiscordQueue(interval=interval, max_size=20, max_per_user=5)
    await q.start()
    try:
        for _ in range(3):
            assert q.try_enqueue("alice", record) == EnqueueResult.QUEUED
        # Wait long enough for 3 dispatches (~2 * interval past the last one).
        await asyncio.sleep(interval * 3 + 0.05)
        assert len(timestamps) == 3
        # Each gap should be ≥ interval (allow small scheduling slack).
        for a, b in pairwise(timestamps):
            gap = b - a
            assert gap >= interval * 0.9, f"gap {gap} < interval {interval}"
    finally:
        await q.stop()


async def test_fire_and_forget_dispatch_does_not_block_worker() -> None:
    """A slow dispatch must not push out the next dispatch slot."""
    pop_times: list[float] = []
    loop = asyncio.get_running_loop()

    async def slow_dispatch() -> None:
        pop_times.append(loop.time())
        await asyncio.sleep(0.5)  # much longer than interval

    interval = 0.05
    q = DiscordQueue(interval=interval, max_size=20, max_per_user=5)
    await q.start()
    try:
        for _ in range(3):
            assert q.try_enqueue("alice", slow_dispatch) == EnqueueResult.QUEUED
        # Three pops should happen within a few intervals even though each
        # dispatch sleeps 10x the interval.
        await asyncio.sleep(interval * 3 + 0.05)
        assert len(pop_times) == 3
    finally:
        await q.stop()


async def test_stop_cancels_cleanly() -> None:
    q = DiscordQueue(interval=0.05, max_size=20, max_per_user=5)
    await q.start()
    for _ in range(5):
        q.try_enqueue("alice", _noop)
    await q.stop()
    # Double-stop should be a no-op.
    await q.stop()


def test_message_pickers_return_strings() -> None:
    assert "#3" in pick_queued(3)
    assert isinstance(pick_queue_full(), str)
    assert isinstance(pick_user_limit(), str)
    assert isinstance(pick_unicode(), str)


@pytest.mark.parametrize("position", [1, 7, 20])
def test_queued_message_includes_position(position: int) -> None:
    msg = pick_queued(position)
    assert f"#{position}" in msg
