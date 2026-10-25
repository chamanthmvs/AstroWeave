"""Per-user birth-chart cache.

A person's birth details are fixed at registration, so their computed chart is
immutable — the perfect thing to cache. We compute it once (an expensive call to
the PyJHora chart service) and store the JSON keyed by user, so later reads are a
single database lookup with no recomputation and no load on the chart service.

Two variants are cached:
- ``light``  : the D1 (rasi) chart only — all that My Chart / the profile need.
             Fully static, so it never expires.
- ``full``   : every section (divisional charts, dashas, shadbala, ...), used for
             readings and the detailed view. A few sections are time-relative
             (transits, the *current* dasha), so this variant is given a TTL and
             recomputed once it is stale.

Bump ``CHART_VERSION`` whenever the chart-building logic changes, so stale shapes
are recomputed rather than served.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, text
from sqlalchemy.engine import Engine

from astroweave.common.config import get_logger
from astroweave.common.database import resolve_engine

logger = get_logger(__name__)

CHART_VERSION = 1

_metadata = MetaData()
user_charts = Table(
    "user_charts",
    _metadata,
    Column("owner", String, primary_key=True),
    Column("variant", String, primary_key=True),
    Column("birth_hash", String, nullable=False),
    Column("chart_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("created_at", Float, nullable=False),  # unix seconds
)


class ChartCache:
    def __init__(self, db_path: Path | None = None, engine: Engine | None = None) -> None:
        self.db_path = db_path
        self._engine = resolve_engine(db_path, engine)
        user_charts.create(bind=self._engine, checkfirst=True)

    def get(
        self,
        owner: str,
        variant: str,
        birth_hash: str,
        max_age_seconds: float | None,
    ) -> dict[str, Any] | None:
        """Return the cached chart if present, matching birth + version, and fresh
        enough (``max_age_seconds`` None = never expires)."""
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT birth_hash, chart_version, payload, created_at
                    FROM user_charts WHERE owner = :owner AND variant = :variant
                    """
                ),
                {"owner": owner, "variant": variant},
            ).mappings().first()
        if row is None:
            return None
        if row["birth_hash"] != birth_hash or int(row["chart_version"]) != CHART_VERSION:
            return None
        if max_age_seconds is not None and (time.time() - float(row["created_at"])) > max_age_seconds:
            return None
        try:
            return json.loads(row["payload"])
        except (ValueError, TypeError):
            return None

    def put(self, owner: str, variant: str, birth_hash: str, payload: dict[str, Any]) -> None:
        row = {
            "owner": owner,
            "variant": variant,
            "birth_hash": birth_hash,
            "chart_version": CHART_VERSION,
            "payload": json.dumps(payload),
            "created_at": time.time(),
        }
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO user_charts (owner, variant, birth_hash, chart_version, payload, created_at)
                    VALUES (:owner, :variant, :birth_hash, :chart_version, :payload, :created_at)
                    ON CONFLICT (owner, variant) DO UPDATE SET
                        birth_hash = :birth_hash, chart_version = :chart_version,
                        payload = :payload, created_at = :created_at
                    """
                ),
                row,
            )
        logger.info("Cached %s chart owner=%s", variant, owner)
