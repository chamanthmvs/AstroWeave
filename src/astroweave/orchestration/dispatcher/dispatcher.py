"""Dispatcher helpers for running planned specialist tasks.

Each specialist is an independently invoked specialist subgraph (see
astroweave.graphs.specialist.specialist_graph). The orchestrator uses
``execute_specialist`` for queue-driven execution; ``run_dispatcher`` remains
as a compatibility wrapper that executes every planned specialist.

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


def _get_chart_data(state: State, runtime: Runtime[Context]) -> tuple[dict | None, list[str]]:
    existing_chart = state.get("chart_data")
    if existing_chart:
        logger.debug("reusing chart data for specialist task")
        return existing_chart, []

    birth_details = (runtime.context or {}).get("birth_details")
    if not birth_details:
        logger.warning("dispatcher missing birth details; cannot compute a chart")
        return None, ["Birth details (date, time, place) are required to answer this."]

    try:
        logger.info("fetching birth chart for specialist execution")
        return get_birth_chart(**birth_details), []
    except httpx.HTTPError as error:
        logger.exception("chart_service call failed")
        return None, [f"Could not compute a birth chart: {error}"]


def execute_specialist(
    state: State, runtime: Runtime[Context], specialist_name: str
) -> State:
    """Execute one specialist task and return its state update."""

    logger.info("executing specialist task '%s'", specialist_name)
    chart_data, chart_errors = _get_chart_data(state, runtime)
    if chart_errors:
        return {"errors": chart_errors}

    methodology = state.get("methodology") or "vedic"
    user_query = state.get("user_query", "")
    handoff = {
        "user_query": user_query,
        "current_task": specialist_name,
        "methodology": methodology,
        "chart_data": chart_data,
    }
    try:
        enforce_context_limit(
            f"dispatcher->{specialist_name}", json.dumps(handoff, default=str)
        )
        result = _get_specialist_graph().invoke(handoff, context=runtime.context)
    except ContextLimitExceededError as error:
        logger.warning("specialist '%s' skipped: %s", specialist_name, error)
        return {"chart_data": chart_data, "errors": [str(error)]}
    except Exception as error:  # noqa: BLE001 - one specialist failing shouldn't sink the run
        logger.exception("specialist '%s' failed", specialist_name)
        return {
            "chart_data": chart_data,
            "errors": [f"{specialist_name} specialist failed: {error}"],
        }

    specialist_results = result.get("specialist_results", [])
    errors = result.get("errors", [])
    logger.info(
        "specialist task '%s' finished with %d result(s) and %d error(s)",
        specialist_name,
        len(specialist_results),
        len(errors),
    )

    return {
        "chart_data": chart_data,
        "specialist_results": specialist_results,
        "errors": errors,
    }


def run_dispatcher(state: State, runtime: Runtime[Context]) -> State:
    """Execute all specialists in state; retained for direct callers."""

    if state.get("errors"):
        return {}

    specialists = state.get("specialists") or []
    if not specialists:
        logger.warning("dispatcher has no specialists to invoke")
        return {"errors": ["No specialist could be determined for this question."]}

    working_state = dict(state)
    specialist_results = []
    errors = []
    for specialist_name in specialists:
        update = execute_specialist(working_state, runtime, specialist_name)
        if update.get("chart_data"):
            working_state["chart_data"] = update["chart_data"]
        specialist_results.extend(update.get("specialist_results", []))
        errors.extend(update.get("errors", []))

    return {
        "chart_data": working_state.get("chart_data", {}),
        "specialist_results": specialist_results,
        "errors": errors,
    }

