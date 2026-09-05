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


def build_orchestrator_graph():
    """Build the top-level workflow for the Astrologer Manager.

    Node behavior is intentionally still pass-through. Specialist selection,
    subgraph invocation, and final synthesis will be implemented later.
    """

    graph = StateGraph(State, context_schema=Context)
    graph.add_node("manager", _pass_through)
    graph.add_node("planner", _pass_through)
    graph.add_node("dispatcher", _pass_through)
    graph.add_node("collector", _pass_through)
    graph.add_node("evaluator", _pass_through)
    graph.add_node("synthesizer", _pass_through)

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