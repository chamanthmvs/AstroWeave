from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph

from astroweave.common.context import Context
from astroweave.common.state import State


def _pass_through(state: State) -> State:
    return state


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    if state.get("is_sufficient", True):
        return "synthesizer"
    return "planner"


def build_specialist_graph():
    """Build the shared workflow used by every specialist astrologer.

    Node behavior is intentionally still pass-through. State and context are
    defined now so later node implementations share one stable contract.
    """

    graph = StateGraph(State, context_schema=Context)
    graph.add_node("planner", _pass_through)
    graph.add_node("executor", _pass_through)
    graph.add_node("collector", _pass_through)
    graph.add_node("evaluator", _pass_through)
    graph.add_node("synthesizer", _pass_through)

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
