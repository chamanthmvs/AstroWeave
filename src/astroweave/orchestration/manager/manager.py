"""The Astrologer Manager's entry node: understands intent, starts the run.

Kept intentionally small for v1 - it validates that a question was actually
asked and initializes the iteration counter. Deeper intent understanding
(e.g. detecting missing birth details before planning) can grow here later.
"""

from __future__ import annotations

from astroweave.common.config import get_logger
from astroweave.common.state import State

logger = get_logger(__name__)


def run_manager(state: State) -> State:
    user_query = (state.get("user_query") or "").strip()
    logger.info("manager received query: %s", user_query)

    if not user_query:
        logger.warning("manager received an empty user query")
        return {"errors": ["No question was provided."], "is_sufficient": True, "answer": ""}

    return {"iteration_count": state.get("iteration_count", 0)}
