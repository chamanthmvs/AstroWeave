from collections.abc import Mapping

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.llm import get_llm, parse_json_response
from astroweave.common.state import State
from astroweave.methodologies import normalize_methodology
from astroweave.orchestration.dispatcher.dispatcher import run_dispatcher
from astroweave.orchestration.manager.manager import run_manager

from .prompts import ORCHESTRATOR_ROUTING_PROMPT, ORCHESTRATOR_SYNTHESIS_PROMPT

logger = get_logger(__name__)

_MAX_ITERATIONS = 2


def _manager(state: State) -> State:
    logger.debug("orchestrator node 'manager' executing")
    return run_manager(state)


def _planner(state: State, runtime: Runtime[Context]) -> State:
    logger.debug("orchestrator node 'planner' executing")
    if state.get("errors"):
        return {}

    forced_methodology = normalize_methodology((runtime.context or {}).get("methodology"))

    llm = get_llm("orchestrator")
    response = llm.invoke(
        [
            SystemMessage(content=ORCHESTRATOR_ROUTING_PROMPT),
            HumanMessage(content=f"User question: {state.get('user_query', '')}"),
        ]
    )
    try:
        parsed = parse_json_response("planner", response.content)
    except ValueError as error:
        return {"errors": [str(error)]}

    specialists = parsed.get("specialists") or []
    methodology = forced_methodology or parsed.get("methodology") or "vedic"
    plan = state.get("plan", []) + [parsed.get("reasoning", "")]

    return {"specialists": specialists, "methodology": methodology, "plan": plan}


def _dispatcher(state: State, runtime: Runtime[Context]) -> State:
    logger.debug("orchestrator node 'dispatcher' executing")
    return run_dispatcher(state, runtime)


def _collector(state: State) -> State:
    logger.debug("orchestrator node 'collector' executing")
    return {}


def _evaluator(state: State) -> State:
    logger.debug("orchestrator node 'evaluator' executing")
    if state.get("errors"):
        return {"is_sufficient": True}

    specialists = state.get("specialists") or []
    specialist_results = state.get("specialist_results") or []
    iteration_count = state.get("iteration_count", 0) + 1

    is_sufficient = bool(specialist_results) or iteration_count >= _MAX_ITERATIONS
    if not is_sufficient:
        logger.info(
            "evaluator: only %d/%d specialist results, re-planning",
            len(specialist_results),
            len(specialists),
        )
    return {"is_sufficient": is_sufficient, "iteration_count": iteration_count}


def _synthesizer(state: State) -> State:
    logger.debug("orchestrator node 'synthesizer' executing")
    errors = state.get("errors") or []
    specialist_results = state.get("specialist_results") or []

    if not specialist_results:
        answer = " ".join(errors) or "I wasn't able to produce an answer for this question."
        return {"answer": answer}

    summary_lines = [
        f"[{result['specialist']}] (confidence: {result.get('confidence', 'unknown')}) "
        f"{result.get('conclusion', '')} -- {result.get('analysis', '')}"
        for result in specialist_results
    ]
    llm = get_llm("orchestrator")
    response = llm.invoke(
        [
            SystemMessage(content=ORCHESTRATOR_SYNTHESIS_PROMPT),
            HumanMessage(
                content=(
                    f"User question: {state.get('user_query', '')}\n\n"
                    "Specialist findings:\n" + "\n".join(summary_lines)
                )
            ),
        ]
    )
    return {"answer": response.content}


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    if state.get("is_sufficient", True):
        logger.debug("evaluation sufficient; routing to synthesizer")
        return "synthesizer"
    logger.debug("evaluation insufficient; routing back to planner")
    return "planner"


def build_orchestrator_graph():
    """Build the top-level workflow for the Astrologer Manager.

    manager understands the query, planner asks an LLM to pick specialists
    and a methodology, dispatcher fetches the birth chart and fans out to
    specialist subgraphs, evaluator decides whether results are sufficient,
    and synthesizer combines specialist conclusions into one final answer.
    """

    logger.info("Building orchestrator graph")
    graph = StateGraph(State, context_schema=Context)
    graph.add_node("manager", _manager)
    graph.add_node("planner", _planner)
    graph.add_node("dispatcher", _dispatcher)
    graph.add_node("collector", _collector)
    graph.add_node("evaluator", _evaluator)
    graph.add_node("synthesizer", _synthesizer)

    graph.add_edge(START, "manager")
    graph.add_edge("manager", "planner")
    graph.add_edge("planner", "dispatcher")
    graph.add_edge("dispatcher", "collector")
    graph.add_edge("collector", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        _route_after_evaluation,
        {"planner": "planner", "synthesizer": "synthesizer"},
    )
    graph.add_edge("synthesizer", END)

    return graph.compile()