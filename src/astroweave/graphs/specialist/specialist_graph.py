from __future__ import annotations

import json
from collections.abc import Mapping

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from astroweave.agents.specialists import SPECIALIST_PROMPTS
from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.llm import get_llm, parse_json_response
from astroweave.common.state import State

logger = get_logger(__name__)


def _planner(state: State) -> State:
    logger.debug("specialist node 'planner' executing for '%s'", state.get("current_task"))
    return {}


def _executor(state: State) -> State:
    specialist_name = state.get("current_task", "")
    logger.debug("specialist node 'executor' executing for '%s'", specialist_name)

    prompt = SPECIALIST_PROMPTS.get(specialist_name)
    if prompt is None:
        return {
            "errors": [f"Unknown specialist '{specialist_name}'"],
            "specialist_results": [],
        }

    llm = get_llm("specialist", agent_name=specialist_name)
    response = llm.invoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=(
                    f"User question: {state.get('user_query', '')}\n"
                    f"Methodology: {state.get('methodology', 'vedic')}\n"
                    f"Birth chart data (JSON): {json.dumps(state.get('chart_data', {}))}"
                )
            ),
        ]
    )
    try:
        parsed = parse_json_response(f"{specialist_name}_executor", response.content)
    except ValueError as error:
        return {"errors": [str(error)], "specialist_results": []}

    return {
        "specialist_analysis": parsed.get("analysis", ""),
        "evaluation": parsed.get("confidence", ""),
        "specialist_results": [
            {
                "specialist": specialist_name,
                "analysis": parsed.get("analysis", ""),
                "conclusion": parsed.get("conclusion", ""),
                "confidence": parsed.get("confidence", "low"),
            }
        ],
    }


def _collector(state: State) -> State:
    logger.debug("specialist node 'collector' executing")
    return {}


def _evaluator(state: State) -> State:
    logger.debug("specialist node 'evaluator' executing")
    # v1 runs a single planner/executor pass per specialist; re-planning loops
    # are reserved for when specialists gain tool access worth retrying.
    return {"is_sufficient": True}


def _synthesizer(state: State) -> State:
    logger.debug("specialist node 'synthesizer' executing")
    return {}


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    if state.get("is_sufficient", True):
        logger.debug("evaluation sufficient; routing to synthesizer")
        return "synthesizer"
    logger.debug("evaluation insufficient; routing back to planner")
    return "planner"


def build_specialist_graph():
    """Build the shared workflow used by every specialist astrologer.

    The executor looks up a domain prompt from SPECIALIST_PROMPTS by
    `state["current_task"]`, calls that specialist's configured LLM with the
    user's question, methodology, and chart data, and records the parsed
    analysis/conclusion/confidence into `state["specialist_results"]`.
    """

    logger.info("Building specialist graph")
    graph = StateGraph(State, context_schema=Context)
    graph.add_node("planner", _planner)
    graph.add_node("executor", _executor)
    graph.add_node("collector", _collector)
    graph.add_node("evaluator", _evaluator)
    graph.add_node("synthesizer", _synthesizer)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "collector")
    graph.add_edge("collector", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        _route_after_evaluation,
        {"planner": "planner", "synthesizer": "synthesizer"},
    )
    graph.add_edge("synthesizer", END)

    return graph.compile()
