from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph

from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.state import State

logger = get_logger(__name__)


def _make_pass_through(node_name: str):
    def _run(state: State) -> State:
        logger.debug("specialist node '%s' executing", node_name)
        return state

    return _run


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    if state.get("is_sufficient", True):
        logger.debug("evaluation sufficient; routing to synthesizer")
        return "synthesizer"
    logger.debug("evaluation insufficient; routing back to planner")
    return "planner"


def build_specialist_graph():
    """Build the shared workflow used by every specialist astrologer.

    Node behavior is intentionally still pass-through. State and context are
    defined now so later node implementations share one stable contract.
    """

    logger.info("Building specialist graph")
    graph = StateGraph(State, context_schema=Context)
    graph.add_node("planner", _make_pass_through("planner"))
    graph.add_node("executor", _make_pass_through("executor"))
    graph.add_node("collector", _make_pass_through("collector"))
    graph.add_node("evaluator", _make_pass_through("evaluator"))
    graph.add_node("synthesizer", _make_pass_through("synthesizer"))

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
