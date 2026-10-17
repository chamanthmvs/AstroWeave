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

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astroweave.common.config import get_logger
from astroweave.common.conversation.store import get_conversation_db_path

logger = get_logger(__name__)

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


class UsageStore:
    """SQLite-backed per-run token/cost records, one row per model per run."""

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
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    conversation_id TEXT,
                    message_id TEXT,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cache_read_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_usage_owner_day ON usage_events(owner, day)")

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
            rows.append((
                now.date().isoformat(), now.isoformat(timespec="seconds"), owner,
                conversation_id, message_id, model,
                counts["input_tokens"], counts["output_tokens"], counts["cache_read_tokens"], cost,
            ))
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO usage_events
                    (day, created_at, owner, conversation_id, message_id,
                     model, input_tokens, output_tokens, cache_read_tokens, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        logger.info("Recorded usage owner=%s models=%s cost=$%.4f", owner, list(totals), run_cost)
        return round(run_cost, 6)

    def summary(self, days: int = 30, top: int = 100) -> dict[str, Any]:
        """Aggregates for the admin dashboard: overall, per user, per day, per model."""
        with self._connect() as connection:
            overall = dict(connection.execute(
                """
                SELECT COUNT(DISTINCT owner) AS users,
                       COUNT(DISTINCT message_id) AS runs,
                       COALESCE(SUM(input_tokens + output_tokens + cache_read_tokens), 0) AS tokens,
                       COALESCE(ROUND(SUM(cost_usd), 6), 0) AS cost_usd
                FROM usage_events
                """
            ).fetchone())
            by_day = [dict(row) for row in connection.execute(
                """
                SELECT day,
                       COUNT(DISTINCT message_id) AS runs,
                       SUM(input_tokens + output_tokens + cache_read_tokens) AS tokens,
                       ROUND(SUM(cost_usd), 6) AS cost_usd
                FROM usage_events GROUP BY day ORDER BY day DESC LIMIT ?
                """,
                (max(1, days),),
            ).fetchall()][::-1]  # oldest first, for a left-to-right time axis
            by_model = [dict(row) for row in connection.execute(
                """
                SELECT model,
                       COUNT(DISTINCT message_id) AS runs,
                       SUM(input_tokens + output_tokens + cache_read_tokens) AS tokens,
                       ROUND(SUM(cost_usd), 6) AS cost_usd
                FROM usage_events GROUP BY model ORDER BY cost_usd DESC, tokens DESC
                """
            ).fetchall()]
        return {"overall": overall, "by_user": self.totals_by_user(top), "by_day": by_day, "by_model": by_model}

    def totals_by_user(self, limit: int = 100) -> list[dict[str, Any]]:
        """Per-user lifetime totals, most expensive first (for the admin dashboard)."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT owner,
                       COUNT(DISTINCT message_id) AS runs,
                       SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens,
                       SUM(cache_read_tokens) AS cache_read_tokens,
                       ROUND(SUM(cost_usd), 6) AS cost_usd
                FROM usage_events
                GROUP BY owner
                ORDER BY cost_usd DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [dict(row) for row in rows]
