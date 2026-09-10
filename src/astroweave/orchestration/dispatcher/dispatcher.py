"""Dispatcher: fetches the birth chart once, then runs each planned specialist.

Each specialist is an independently invoked specialist subgraph (see
astroweave.graphs.specialist.specialist_graph) - the dispatcher's job is only
to fan work out to them and fold their results back into the top-level state.

The full chart (every divisional chart, the whole dasha-bhukti cycle,
ashtakavarga) is always fetched and passed on as-is - specialists get
whatever data they need to answer accurately. See
astroweave.common.llm.enforce_context_limit for the opt-in, configurable
guard against oversized hand-offs (disabled by default).
"""

from __future__ import annotations

import json

import httpx
from langgraph.runtime import Runtime

from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.llm import ContextLimitExceededError, enforce_context_limit
from astroweave.common.state import State
from astroweave.common.tools.chart_client import get_birth_chart
from astroweave.graphs.specialist.specialist_graph import build_specialist_graph

logger = get_logger(__name__)

_specialist_graph = None


def _get_specialist_graph():
    global _specialist_graph
    if _specialist_graph is None:
        _specialist_graph = build_specialist_graph()
    return _specialist_graph


def run_dispatcher(state: State, runtime: Runtime[Context]) -> State:
    if state.get("errors"):
        # manager already flagged a hard error (e.g. empty query); skip work.
        return {}

    specialists = state.get("specialists") or []
    if not specialists:
        logger.warning("dispatcher has no specialists to invoke")
        return {"errors": ["No specialist could be determined for this question."]}

    birth_details = (runtime.context or {}).get("birth_details")
    if not birth_details:
        logger.warning("dispatcher missing birth details; cannot compute a chart")
        return {"errors": ["Birth details (date, time, place) are required to answer this."]}

    try:
        chart_data = get_birth_chart(**birth_details)
    except httpx.HTTPError as error:
        logger.exception("chart_service call failed")
        return {"errors": [f"Could not compute a birth chart: {error}"]}

    methodology = state.get("methodology") or "vedic"
    user_query = state.get("user_query", "")
    specialist_results = []
    errors = []

    for specialist_name in specialists:
        logger.info("dispatching specialist '%s'", specialist_name)
        try:
            handoff = {
                "user_query": user_query,
                "current_task": specialist_name,
                "methodology": methodology,
                "chart_data": chart_data,
            }
            enforce_context_limit(
                f"dispatcher->{specialist_name}", json.dumps(handoff, default=str)
            )
            result = _get_specialist_graph().invoke(handoff, context=runtime.context)
        except ContextLimitExceededError as error:
            logger.warning("specialist '%s' skipped: %s", specialist_name, error)
            errors.append(str(error))
            continue
        except Exception as error:  # noqa: BLE001 - one specialist failing shouldn't sink the run
            logger.exception("specialist '%s' failed", specialist_name)
            errors.append(f"{specialist_name} specialist failed: {error}")
            continue

        specialist_results.extend(result.get("specialist_results", []))
        errors.extend(result.get("errors", []))

    return {
        "chart_data": chart_data,
        "specialist_results": specialist_results,
        "errors": errors,
    }

