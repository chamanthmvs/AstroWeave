from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph

from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.state import State

logger = get_logger(__name__)


def _make_pass_through(node_name: str):
    def _run(state: State) -> State:
        logger.debug("orchestrator node '%s' executing", node_name)
        return state

    return _run


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    if state.get("is_sufficient", True):
        logger.debug("evaluation sufficient; routing to synthesizer")
        return "synthesizer"
    logger.debug("evaluation insufficient; routing back to planner")
    return "planner"


def build_orchestrator_graph():
    """Build the top-level workflow for the Astrologer Manager.

    Node behavior is intentionally still pass-through. Specialist selection,
    subgraph invocation, and final synthesis will be implemented later.
    """

    logger.info("Building orchestrator graph")
    graph = StateGraph(State, context_schema=Context)
    graph.add_node("manager", _make_pass_through("manager"))
    graph.add_node("planner", _make_pass_through("planner"))
    graph.add_node("dispatcher", _make_pass_through("dispatcher"))
    graph.add_node("collector", _make_pass_through("collector"))
    graph.add_node("evaluator", _make_pass_through("evaluator"))
    graph.add_node("synthesizer", _make_pass_through("synthesizer"))

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