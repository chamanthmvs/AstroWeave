"""In-depth AI Kundli compatibility reading over two full charts.

This is a gated, full-chart feature: marriage is a life-shaping decision, so the
reading is admin-unlocked per user and is only offered when the complete chart is
available (never a trimmed one). The module builds the prompt + output contract
and runs the reading; the API layer handles gating, charts and accounting.
"""

from astroweave.agents.match.reading import (
    MATCH_OUTPUT_SCHEMA,
    MatchReadingError,
    run_match_reading,
)

__all__ = ["MATCH_OUTPUT_SCHEMA", "MatchReadingError", "run_match_reading"]
