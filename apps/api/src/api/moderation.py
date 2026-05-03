"""Moderation state — TinyDB-backed persistence for admin controls.

Tables:
- config:       singleton with toggle states (bot_paused, preset_only, brightness_cap, etc.)
- device_locks: per-MAC lock flags
- banned_users: Discord user bans
- command_log:  append-only audit trail
- rate_limits:  per-user cooldown tracking
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tinydb import Query, TinyDB
from tinydb.middlewares import CachingMiddleware
from tinydb.storages import JSONStorage

logger = logging.getLogger(__name__)

# Default profanity patterns (case-insensitive)
_DEFAULT_BLOCKLIST = [
    r"\bfuck\b",
    r"\bshit\b",
    r"\bass\b",
    r"\bbitch\b",
    r"\bdick\b",
    r"\bcunt\b",
    r"\bnigger\b",
    r"\bfaggot\b",
    r"\bretard\b",
]

_DEFAULT_CONFIG = {
    "id": "main",
    "bot_paused": False,
    "preset_only_mode": False,
    "brightness_cap": 200,
    "cooldown_seconds": 3,
    "profanity_blocklist": _DEFAULT_BLOCKLIST,
}


class ModerationStore:
    """TinyDB-backed moderation state."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            # Default: data/ dir next to the running module, or cwd
            data_dir = Path(__file__).resolve().parents[2] / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "moderation.db.json"
        self._lock = threading.Lock()
        self._db = TinyDB(str(db_path), storage=CachingMiddleware(JSONStorage))
        self._config = self._db.table("config")
        self._device_locks = self._db.table("device_locks")
        self._banned = self._db.table("banned_users")
        self._log = self._db.table("command_log")
        self._rates = self._db.table("rate_limits")
        self._quick_texts = self._db.table("quick_texts")
        self._device_groups = self._db.table("device_groups")
        self._ensure_config()

    def _read(self, fn):  # noqa: ANN001, ANN202
        """Thread-safe TinyDB read."""
        with self._lock:
            return fn()

    def _write(self, fn):  # noqa: ANN001, ANN202
        """Thread-safe TinyDB write."""
        with self._lock:
            return fn()

    def close(self) -> None:
        """Flush cache and close the database."""
        self._db.close()

    def _ensure_config(self) -> None:
        with self._lock:
            q = Query()
            if not self._config.search(q.id == "main"):
                self._config.insert(dict(_DEFAULT_CONFIG))

    # ── Config ────────────────────────────────────────────────────────

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            q = Query()
            doc = self._config.search(q.id == "main")
            return doc[0] if doc else dict(_DEFAULT_CONFIG)

    def update_config(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        with self._lock:
            q = Query()
            allowed = {
                "bot_paused",
                "preset_only_mode",
                "brightness_cap",
                "cooldown_seconds",
                "profanity_blocklist",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if updates:
                self._config.update(updates, q.id == "main")
        return self.get_config()

    @property
    def bot_paused(self) -> bool:
        return self.get_config().get("bot_paused", False)

    @property
    def preset_only(self) -> bool:
        return self.get_config().get("preset_only_mode", False)

    @property
    def brightness_cap(self) -> int:
        return self.get_config().get("brightness_cap", 200)

    @property
    def cooldown_seconds(self) -> int:
        return self.get_config().get("cooldown_seconds", 3)

    # ── Device locks ──────────────────────────────────────────────────

    def is_device_locked(self, mac: str) -> bool:
        with self._lock:
            q = Query()
            results = self._device_locks.search(q.mac == mac)
            return bool(results and results[0].get("locked"))

    def lock_device(self, mac: str, reason: str = "") -> None:
        with self._lock:
            q = Query()
            if self._device_locks.search(q.mac == mac):
                self._device_locks.update({"locked": True, "reason": reason}, q.mac == mac)
            else:
                self._device_locks.insert({"mac": mac, "locked": True, "reason": reason})

    def unlock_device(self, mac: str) -> None:
        with self._lock:
            q = Query()
            self._device_locks.update({"locked": False, "reason": ""}, q.mac == mac)

    def list_device_locks(self) -> list[dict]:
        with self._lock:
            return self._device_locks.all()

    # ── Banned users ──────────────────────────────────────────────────

    def is_banned(self, user_id: str) -> bool:
        with self._lock:
            q = Query()
            return bool(self._banned.search(q.user_id == str(user_id)))

    def ban_user(self, user_id: str, username: str = "", reason: str = "") -> None:
        with self._lock:
            q = Query()
            if not self._banned.search(q.user_id == str(user_id)):
                self._banned.insert(
                    {
                        "user_id": str(user_id),
                        "username": username,
                        "reason": reason,
                        "banned_at": datetime.now(tz=UTC).isoformat(),
                    }
                )

    def unban_user(self, user_id: str) -> None:
        with self._lock:
            q = Query()
            self._banned.remove(q.user_id == str(user_id))

    def list_banned(self) -> list[dict]:
        with self._lock:
            return self._banned.all()

    # ── Rate limiting ─────────────────────────────────────────────────

    def check_rate_limit(self, user_id: str) -> float | None:
        """Return seconds remaining on cooldown, or None if clear."""
        with self._lock:
            q = Query()
            results = self._rates.search(q.user_id == str(user_id))
        if not results:
            return None
        last = results[0].get("last_command_at", 0)
        elapsed = time.time() - last
        cooldown = self.cooldown_seconds
        if elapsed < cooldown:
            return round(cooldown - elapsed, 1)
        return None

    def record_command(self, user_id: str) -> None:
        """Stamp this user's last-command time."""
        with self._lock:
            q = Query()
            now = time.time()
            if self._rates.search(q.user_id == str(user_id)):
                self._rates.update({"last_command_at": now}, q.user_id == str(user_id))
            else:
                self._rates.insert({"user_id": str(user_id), "last_command_at": now})

    # ── Command log ───────────────────────────────────────────────────

    def log_command(  # noqa: PLR0913
        self,
        *,
        who: str,
        source: str,
        device_mac: str,
        command_kind: str,
        detail: str = "",
        result: str = "ok",
    ) -> None:
        with self._lock:
            self._log.insert(
                {
                    "who": who,
                    "source": source,
                    "device_mac": device_mac,
                    "command_kind": command_kind,
                    "detail": detail,
                    "result": result,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )

    def get_history(self, limit: int = 100) -> list[dict]:
        """Return most recent commands, newest first."""
        with self._lock:
            all_docs = self._log.all()
        all_docs.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
        return all_docs[:limit]

    # ── Profanity filter ──────────────────────────────────────────────

    def check_profanity(self, text: str) -> str | None:
        """Return the matched pattern if profanity found, else None.

        Uses better-profanity as the primary check, then falls back to
        the regex blocklist from config.
        """
        from better_profanity import profanity

        if profanity.contains_profanity(text):
            return "profanity_detected"

        patterns = self.get_config().get("profanity_blocklist", [])
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return pattern
            except re.error:
                continue
        return None

    # ── Emergency off ─────────────────────────────────────────────────
    # (The actual "send power off to all" is done by the caller via Hub;
    #  this just logs + pauses the bot.)

    def emergency_off(self) -> None:
        """Pause the bot and log the emergency."""
        self.update_config(bot_paused=True)
        self.log_command(
            who="admin",
            source="api-ui",
            device_mac="*",
            command_kind="emergency_off",
            detail="All devices powered off, bot paused",
        )

    # ── Quick texts (persisted) ──────────────────────────────────────

    def list_quick_texts(self) -> list[str]:
        with self._lock:
            docs = self._quick_texts.all()
        return [d["text"] for d in docs]

    def add_quick_text(self, text: str) -> list[str]:
        with self._lock:
            q = Query()
            if not self._quick_texts.search(q.text == text):
                self._quick_texts.insert({"text": text})
        return self.list_quick_texts()

    def remove_quick_text(self, text: str) -> list[str]:
        with self._lock:
            q = Query()
            self._quick_texts.remove(q.text == text)
        return self.list_quick_texts()

    # ── Device groups (persisted) ────────────────────────────────────

    def list_device_groups(self) -> list[dict]:
        with self._lock:
            return self._device_groups.all()

    def set_device_group(self, mac: str, group: str) -> None:
        with self._lock:
            q = Query()
            if self._device_groups.search(q.mac == mac):
                self._device_groups.update({"group": group}, q.mac == mac)
            else:
                self._device_groups.insert({"mac": mac, "group": group})

    def get_device_group(self, mac: str) -> str | None:
        with self._lock:
            q = Query()
            results = self._device_groups.search(q.mac == mac)
            return results[0]["group"] if results else None
