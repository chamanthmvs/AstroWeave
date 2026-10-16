"""Per-user and global daily caps for the paid ``/run`` endpoint.

Every ``/run`` that reaches the model spends real money on the configured LLM
provider's key, and the endpoint is exposed, so one runaway loop or one abusive
account could drain the budget. This limiter counts runs per UTC calendar day
in the same SQLite database the conversation store uses, and refuses a run once
a cap is hit.

Counts are consumed *before* the model is invoked (the cost is incurred the
moment the model is called, even if the run later errors), so a reserved slot
is deliberately not refunded on failure - that is the conservative choice for a
cost guard. Idempotent replays never reach the limiter, so re-reading a saved
answer is always free.

Configuration (both default off-ish; a cap of 0 or blank disables that scope):
- ``ASTROWEAVE_RATE_LIMIT_PER_DAY``        - runs per user per day (default 50)
- ``ASTROWEAVE_RATE_LIMIT_GLOBAL_PER_DAY`` - runs across all users per day (default 0 = off)
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astroweave.common.config import get_logger
from astroweave.common.conversation.store import get_conversation_db_path

logger = get_logger(__name__)

_GLOBAL_OWNER = "*"  # usernames are emails, so this can never collide with a real owner
_DEFAULT_PER_USER_PER_DAY = 50
_DEFAULT_GLOBAL_PER_DAY = 0


def _limit(variable_name: str, default: int) -> int:
    """Read a non-negative integer cap from the environment; 0/blank/invalid disables it."""
    raw = os.environ.get(variable_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", variable_name, raw)
        return default
    return max(0, value)


def per_user_limit() -> int:
    return _limit("ASTROWEAVE_RATE_LIMIT_PER_DAY", _DEFAULT_PER_USER_PER_DAY)


def global_limit() -> int:
    return _limit("ASTROWEAVE_RATE_LIMIT_GLOBAL_PER_DAY", _DEFAULT_GLOBAL_PER_DAY)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_until_utc_midnight(now: datetime) -> int:
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a budget check. ``allowed`` runs may proceed; otherwise the
    ``scope`` ('user' or 'global') that blocked it drives the 429 response."""

    allowed: bool
    scope: str | None = None
    limit: int | None = None
    used: int | None = None
    retry_after_seconds: int | None = None


class RateLimiter:
    """SQLite-backed daily run counter, safe across threads and processes."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_conversation_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_daily (
                    day TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (day, owner)
                )
                """
            )

    def _count(self, connection: sqlite3.Connection, day: str, owner: str) -> int:
        row = connection.execute(
            "SELECT request_count FROM usage_daily WHERE day = ? AND owner = ?",
            (day, owner),
        ).fetchone()
        return int(row["request_count"]) if row else 0

    def check_and_consume(self, owner: str) -> RateLimitResult:
        """Reserve one run for ``owner`` today, or refuse if a cap is reached.

        The read-then-increment runs inside a single ``BEGIN IMMEDIATE``
        transaction so two concurrent requests cannot both pass a cap.
        """
        per_user = per_user_limit()
        overall = global_limit()
        if per_user <= 0 and overall <= 0:
            return RateLimitResult(allowed=True)  # limiting disabled entirely

        now = _utc_now()
        day = now.date().isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            user_used = self._count(connection, day, owner)
            overall_used = self._count(connection, day, _GLOBAL_OWNER)
            if per_user > 0 and user_used >= per_user:
                connection.rollback()
                logger.warning("Rate limit hit (user) owner=%s used=%d limit=%d", owner, user_used, per_user)
                return RateLimitResult(False, "user", per_user, user_used, _seconds_until_utc_midnight(now))
            if overall > 0 and overall_used >= overall:
                connection.rollback()
                logger.warning("Rate limit hit (global) used=%d limit=%d", overall_used, overall)
                return RateLimitResult(False, "global", overall, overall_used, _seconds_until_utc_midnight(now))

            # Count every run against both the per-user and the global tally, so
            # the global figure stays meaningful even while its cap is disabled.
            for key in (owner, _GLOBAL_OWNER):
                connection.execute(
                    """
                    INSERT INTO usage_daily (day, owner, request_count) VALUES (?, ?, 1)
                    ON CONFLICT(day, owner) DO UPDATE SET request_count = request_count + 1
                    """,
                    (day, key),
                )
            connection.commit()
            return RateLimitResult(allowed=True, scope="user", limit=per_user or None, used=user_used + 1)
        finally:
            connection.close()

    def usage_today(self, owner: str) -> dict[str, object]:
        """Report ``owner``'s and the global run counts for today (no consumption)."""
        now = _utc_now()
        day = now.date().isoformat()
        with self._connect() as connection:
            user_used = self._count(connection, day, owner)
            overall_used = self._count(connection, day, _GLOBAL_OWNER)
        per_user = per_user_limit()
        overall = global_limit()
        return {
            "day": day,
            "resets_in_seconds": _seconds_until_utc_midnight(now),
            "user": {
                "used": user_used,
                "limit": per_user or None,
                "remaining": max(0, per_user - user_used) if per_user > 0 else None,
            },
            "global": {
                "used": overall_used,
                "limit": overall or None,
                "remaining": max(0, overall - overall_used) if overall > 0 else None,
            },
        }
