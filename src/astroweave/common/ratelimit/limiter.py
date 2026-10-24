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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, text
from sqlalchemy.engine import Connection, Engine

from astroweave.common.config import get_logger
from astroweave.common.database import resolve_engine

logger = get_logger(__name__)

_metadata = MetaData()

# One row per (UTC day, owner); the global tally lives under owner "*".
usage_daily = Table(
    "usage_daily",
    _metadata,
    Column("day", String, primary_key=True),
    Column("owner", String, primary_key=True),
    Column("request_count", Integer, nullable=False, server_default=text("0")),
)

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
    """Daily run counter, safe across threads and processes.

    Backed by the shared engine (SQLite locally, Postgres in production). The
    read-check-increment runs inside one transaction: both tallies are
    incremented, and if either cap is now exceeded the whole transaction is
    rolled back, so two concurrent requests cannot both slip past a cap and a
    refused request leaves the counts untouched.
    """

    def __init__(self, db_path: Path | None = None, engine: Engine | None = None) -> None:
        self.db_path = db_path
        self._engine = resolve_engine(db_path, engine)
        self._initialize()

    def _initialize(self) -> None:
        usage_daily.create(bind=self._engine, checkfirst=True)

    def _count(self, connection: Connection, day: str, owner: str) -> int:
        value = connection.execute(
            text("SELECT request_count FROM usage_daily WHERE day = :day AND owner = :owner"),
            {"day": day, "owner": owner},
        ).scalar()
        return int(value) if value is not None else 0

    def _increment(self, connection: Connection, day: str, owner: str) -> int:
        """Atomically bump one tally and return its new value."""
        connection.execute(
            text(
                """
                INSERT INTO usage_daily (day, owner, request_count) VALUES (:day, :owner, 1)
                ON CONFLICT (day, owner) DO UPDATE SET request_count = usage_daily.request_count + 1
                """
            ),
            {"day": day, "owner": owner},
        )
        return self._count(connection, day, owner)

    def check_and_consume(self, owner: str) -> RateLimitResult:
        """Reserve one run for ``owner`` today, or refuse if a cap is reached."""
        per_user = per_user_limit()
        overall = global_limit()
        if per_user <= 0 and overall <= 0:
            return RateLimitResult(allowed=True)  # limiting disabled entirely

        now = _utc_now()
        day = now.date().isoformat()
        connection = self._engine.connect()
        transaction = connection.begin()
        try:
            # Count every run against both the per-user and the global tally, so
            # the global figure stays meaningful even while its cap is disabled.
            user_used = self._increment(connection, day, owner)
            overall_used = self._increment(connection, day, _GLOBAL_OWNER)
            if per_user > 0 and user_used > per_user:
                transaction.rollback()
                logger.warning("Rate limit hit (user) owner=%s used=%d limit=%d", owner, user_used - 1, per_user)
                return RateLimitResult(False, "user", per_user, user_used - 1, _seconds_until_utc_midnight(now))
            if overall > 0 and overall_used > overall:
                transaction.rollback()
                logger.warning("Rate limit hit (global) used=%d limit=%d", overall_used - 1, overall)
                return RateLimitResult(False, "global", overall, overall_used - 1, _seconds_until_utc_midnight(now))
            transaction.commit()
            return RateLimitResult(allowed=True, scope="user", limit=per_user or None, used=user_used)
        finally:
            connection.close()

    def usage_today(self, owner: str) -> dict[str, object]:
        """Report ``owner``'s and the global run counts for today (no consumption)."""
        now = _utc_now()
        day = now.date().isoformat()
        with self._engine.connect() as connection:
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
