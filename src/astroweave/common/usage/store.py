"""Persist per-run LLM token usage and cost for analytics.

The model adapters report tokens per call, but nothing stored them, so there
was no basis for a spend dashboard or cost-aware evals. This module captures
usage from each model call in a run (routing, every specialist, synthesis),
aggregates it per model, computes the dollar cost from a price table, and
writes it to the same SQLite database the rest of the app uses.

Only counts, model names, ids and cost are stored - never the text of a user's
question or the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    text,
)
from sqlalchemy.engine import Engine

from astroweave.common.config import get_logger
from astroweave.common.database import resolve_engine

logger = get_logger(__name__)

_metadata = MetaData()

# One row per model per run. Defined with SQLAlchemy Core so the DDL is emitted
# correctly for whichever backend is in use (SQLite locally, Postgres in prod).
usage_events = Table(
    "usage_events",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("day", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("owner", String, nullable=False),
    Column("conversation_id", String),
    Column("message_id", String),
    Column("model", String, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cache_read_tokens", Integer, nullable=False),
    Column("cost_usd", Float, nullable=False),
    Index("idx_usage_owner_day", "owner", "day"),
)

# USD per 1,000,000 tokens: (input, output, cache_read). Cost is computed and
# stored at write time, so historical rows stay correct if prices or the
# default model change later. Unknown models are recorded at cost 0.
PRICING: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.25),
    "claude-opus-4-8": (5.0, 25.0, 0.25),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 0.25),
    "claude-haiku-5-5": (1.0, 5.0, 0.10),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read_tokens: int) -> float:
    """Dollar cost of one model's usage; 0.0 for a model not in PRICING."""
    price = PRICING.get(model)
    if not price:
        return 0.0
    per_in, per_out, per_cache = price
    return round(
        input_tokens / 1e6 * per_in + output_tokens / 1e6 * per_out + cache_read_tokens / 1e6 * per_cache,
        6,
    )


def usage_from_response(response: Any) -> dict[str, Any] | None:
    """Extract {model, input/output/cache tokens} from a model response.

    Handles the Claude adapter (tokens on ``response_metadata``) and LangChain
    chat models (tokens on ``usage_metadata``). Returns None when a provider
    reports no usage.
    """
    meta = getattr(response, "response_metadata", None) or {}
    if "input_tokens" in meta or "output_tokens" in meta:  # Claude adapter
        return {
            "model": meta.get("model") or "unknown",
            "input_tokens": int(meta.get("input_tokens") or 0),
            "output_tokens": int(meta.get("output_tokens") or 0),
            "cache_read_tokens": int(meta.get("cache_read_input_tokens") or 0),
        }
    usage_metadata = getattr(response, "usage_metadata", None)  # LangChain chat models
    if usage_metadata:
        details = usage_metadata.get("input_token_details") or {}
        return {
            "model": meta.get("model_name") or meta.get("model") or "unknown",
            "input_tokens": int(usage_metadata.get("input_tokens") or 0),
            "output_tokens": int(usage_metadata.get("output_tokens") or 0),
            "cache_read_tokens": int(details.get("cache_read") or 0),
        }
    return None


def aggregate_by_model(usages: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Sum a run's per-call usage records into one total per model."""
    totals: dict[str, dict[str, int]] = {}
    for usage in usages:
        model = usage.get("model") or "unknown"
        bucket = totals.setdefault(model, {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0})
        for key in bucket:
            bucket[key] += int(usage.get(key) or 0)
    return totals


@dataclass(frozen=True)
class UsageTotals:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    runs: int


_STRING_COLUMNS = {"day", "model", "owner"}


def _as_int_row(mapping: Any) -> dict[str, Any]:
    """Normalize a result row to JSON-friendly native types across backends.

    Postgres returns ``Decimal`` for ``SUM``/aggregate columns while SQLite
    returns ``int``/``float``; this coerces counts to ``int`` and ``cost_usd``
    to a 6-dp ``float`` so callers (and the admin JSON) see the same shape
    regardless of the database in use.
    """
    row: dict[str, Any] = {}
    for key, value in mapping.items():
        if key == "cost_usd":
            row[key] = round(float(value or 0), 6)
        elif key in _STRING_COLUMNS:
            row[key] = value
        else:
            row[key] = int(value or 0)
    return row


class UsageStore:
    """Per-run token/cost records, one row per model per run.

    Backed by the shared engine (SQLite locally, Postgres in production). A
    ``db_path`` or ``engine`` may still be passed to target a specific database
    (tests use a temp file); otherwise it uses ``DATABASE_URL``.
    """

    def __init__(self, db_path: Path | None = None, engine: Engine | None = None) -> None:
        self.db_path = db_path
        self._engine = resolve_engine(db_path, engine)
        self._initialize()

    def _initialize(self) -> None:
        usage_events.create(bind=self._engine, checkfirst=True)

    def record_run(
        self,
        owner: str,
        conversation_id: str | None,
        message_id: str | None,
        usages: list[dict[str, Any]],
    ) -> float:
        """Store one run's usage (one row per model) and return its total cost."""
        totals = aggregate_by_model(usages)
        if not totals:
            return 0.0
        now = datetime.now(timezone.utc)
        rows, run_cost = [], 0.0
        for model, counts in totals.items():
            cost = cost_usd(model, counts["input_tokens"], counts["output_tokens"], counts["cache_read_tokens"])
            run_cost += cost
            rows.append({
                "day": now.date().isoformat(),
                "created_at": now.isoformat(timespec="seconds"),
                "owner": owner,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "model": model,
                "input_tokens": counts["input_tokens"],
                "output_tokens": counts["output_tokens"],
                "cache_read_tokens": counts["cache_read_tokens"],
                "cost_usd": cost,
            })
        with self._engine.begin() as connection:
            connection.execute(insert(usage_events), rows)
        logger.info("Recorded usage owner=%s models=%s cost=$%.4f", owner, list(totals), run_cost)
        return round(run_cost, 6)

    def summary(self, days: int = 30, top: int = 100) -> dict[str, Any]:
        """Aggregates for the admin dashboard: overall, per user, per day, per model."""
        with self._engine.connect() as connection:
            overall = _as_int_row(connection.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT owner) AS users,
                           COUNT(DISTINCT message_id) AS runs,
                           COALESCE(SUM(input_tokens + output_tokens + cache_read_tokens), 0) AS tokens,
                           COALESCE(SUM(cost_usd), 0) AS cost_usd
                    FROM usage_events
                    """
                )
            ).mappings().one())
            by_day = [_as_int_row(row) for row in connection.execute(
                text(
                    """
                    SELECT day,
                           COUNT(DISTINCT message_id) AS runs,
                           SUM(input_tokens + output_tokens + cache_read_tokens) AS tokens,
                           SUM(cost_usd) AS cost_usd
                    FROM usage_events GROUP BY day ORDER BY day DESC LIMIT :limit
                    """
                ),
                {"limit": max(1, days)},
            ).mappings().all()][::-1]  # oldest first, for a left-to-right time axis
            by_model = [_as_int_row(row) for row in connection.execute(
                text(
                    """
                    SELECT model,
                           COUNT(DISTINCT message_id) AS runs,
                           SUM(input_tokens + output_tokens + cache_read_tokens) AS tokens,
                           SUM(cost_usd) AS cost_usd
                    FROM usage_events GROUP BY model ORDER BY cost_usd DESC, tokens DESC
                    """
                )
            ).mappings().all()]
        return {"overall": overall, "by_user": self.totals_by_user(top), "by_day": by_day, "by_model": by_model}

    def totals_by_user(self, limit: int = 100) -> list[dict[str, Any]]:
        """Per-user lifetime totals, most expensive first (for the admin dashboard)."""
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT owner,
                           COUNT(DISTINCT message_id) AS runs,
                           SUM(input_tokens) AS input_tokens,
                           SUM(output_tokens) AS output_tokens,
                           SUM(cache_read_tokens) AS cache_read_tokens,
                           SUM(cost_usd) AS cost_usd
                    FROM usage_events
                    GROUP BY owner
                    ORDER BY cost_usd DESC
                    LIMIT :limit
                    """
                ),
                {"limit": max(1, limit)},
            ).mappings().all()
        return [_as_int_row(row) for row in rows]
