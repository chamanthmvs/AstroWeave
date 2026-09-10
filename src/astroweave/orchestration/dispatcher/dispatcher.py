"""Dispatcher: fetches the birth chart once, then runs each planned specialist.

Each specialist is an independently invoked specialist subgraph (see
astroweave.graphs.specialist.specialist_graph) - the dispatcher's job is only
to fan work out to them and fold their results back into the top-level state.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
from langgraph.runtime import Runtime

from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.state import State
from astroweave.common.tools.chart_client import get_birth_chart
from astroweave.graphs.specialist.specialist_graph import build_specialist_graph

logger = get_logger(__name__)

_specialist_graph = None

# The full chart payload (all divisional charts + the entire 120-year dasha
# cycle + ashtakavarga) comfortably clears small-provider token-per-minute
# limits (e.g. Groq's free tier). Specialists only need the currently-relevant
# slice of it, so the dispatcher fetches a lighter chart and trims dasha
# periods down to what's actually relevant to "now".
_DASHA_WINDOW_YEARS_PAST = 3
_DASHA_WINDOW_YEARS_FUTURE = 15
_MAX_DASHA_ENTRIES = 15


def _get_specialist_graph():
    global _specialist_graph
    if _specialist_graph is None:
        _specialist_graph = build_specialist_graph()
    return _specialist_graph


def _trim_dasha_bhukti(entries: list[dict]) -> list[dict]:
    today = date.today()
    window_start = today.replace(year=today.year - _DASHA_WINDOW_YEARS_PAST)
    window_end = today.replace(year=today.year + _DASHA_WINDOW_YEARS_FUTURE)

    def _in_window(entry: dict) -> bool:
        try:
            start = datetime.strptime(entry["start_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            return True
        return window_start <= start <= window_end

    relevant = [entry for entry in entries if _in_window(entry)]
    return (relevant or entries)[:_MAX_DASHA_ENTRIES]


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
        chart_data = get_birth_chart(
            **birth_details,
            varga_factors=[9, 10],
            include_ashtakavarga=False,
        )
    except httpx.HTTPError as error:
        logger.exception("chart_service call failed")
        return {"errors": [f"Could not compute a birth chart: {error}"]}

    if chart_data.get("dasha_bhukti"):
        chart_data["dasha_bhukti"] = _trim_dasha_bhukti(chart_data["dasha_bhukti"])

    methodology = state.get("methodology") or "vedic"
    user_query = state.get("user_query", "")
    specialist_results = []
    errors = []

    for specialist_name in specialists:
        logger.info("dispatching specialist '%s'", specialist_name)
        try:
            result = _get_specialist_graph().invoke(
                {
                    "user_query": user_query,
                    "current_task": specialist_name,
                    "methodology": methodology,
                    "chart_data": chart_data,
                },
                context=runtime.context,
            )
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

