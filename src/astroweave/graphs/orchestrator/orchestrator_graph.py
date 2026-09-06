from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from astroweave.common.config import AgentConfig
from astroweave.common.context import Context
from astroweave.common.state import State
from astroweave.common.trace import record_event, serializable_config
from astroweave.graphs.specialist.specialist_graph import build_specialist_graph


AGENT_CONFIGS: dict[str, AgentConfig] = {
    "career": {
        "agent_name": "career_specialist",
        "domain": "career",
        "enabled_methodologies": ["Vedic", "KP"],
        "allowed_tools": ["career_demo_tool"],
        "retrieval_namespace": "career",
    },
    "sports": {
        "agent_name": "sports_specialist",
        "domain": "sports",
        "enabled_methodologies": ["Vedic"],
        "allowed_tools": ["sports_demo_tool"],
        "retrieval_namespace": "sports",
    },
    "finance": {
        "agent_name": "finance_specialist",
        "domain": "finance",
        "enabled_methodologies": ["KP"],
        "allowed_tools": ["finance_demo_tool"],
        "retrieval_namespace": "finance",
    },
    "love": {
        "agent_name": "love_specialist",
        "domain": "love",
        "enabled_methodologies": ["Vedic", "KP"],
        "allowed_tools": ["love_demo_tool"],
        "retrieval_namespace": "love",
    },
}


def _manager(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "manager",
        "Received the user question.",
        runtime.context or {},
        config,
    )
    return event


def _planner(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    query = state.get("user_query", "").lower()
    keywords = {
        "sports": ("sports", "match", "game", "player", "team"),
        "finance": ("finance", "money", "wealth", "investment", "business"),
        "love": ("love", "relationship", "marriage", "partner"),
        "career": ("career", "job", "work", "education", "study"),
    }
    selected = [
        domain for domain, terms in keywords.items() if any(term in query for term in terms)
    ] or ["career"]
    event = record_event(
        state,
        "orchestrator_planner",
        f"Selected specialist domains: {selected}.",
        runtime.context or {},
        config,
        {"selected_specialists": selected, "plan": selected},
    )
    return {**event, "selected_specialists": selected, "plan": selected}


def _dispatcher(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    context = dict(runtime.context or {})
    child_config = serializable_config(config)
    parent_trace = list(state.get("execution_trace", []))
    entry_event = record_event(
        state,
        "dispatcher_entry",
        f"Starting dispatch for {state.get('selected_specialists', ['career'])}.",
        context,
        config,
        {"current_task": "invoke_specialist_subgraphs"},
    )["execution_trace"][0]
    cumulative_trace: list[dict[str, Any]] = [*parent_trace, entry_event]
    specialist_results: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    stage_results: list[dict[str, Any]] = []
    new_child_events: list[dict[str, Any]] = []

    for domain in state.get("selected_specialists", ["career"]):
        agent_config = AGENT_CONFIGS[domain]
        child_config["metadata"] = {
            **child_config.get("metadata", {}),
            "_trace_offset": 0,
        }
        input_trace = list(cumulative_trace)
        child_state = build_specialist_graph(agent_config).invoke(
            {
                "user_query": state.get("user_query", ""),
            "execution_trace": input_trace,
            },
            context=context,
            config=child_config,
        )
        child_trace = child_state.get("execution_trace", [])
        new_child_events.extend(child_trace[len(input_trace) :])
        cumulative_trace = child_trace
        tool_results.extend(child_state.get("tool_results", []))
        stage_results.extend(child_state.get("stage_results", []))
        specialist_results.append(
            {
                "agent_name": agent_config["agent_name"],
                "domain": domain,
                "answer": child_state.get("answer", ""),
            }
        )

    child_config["metadata"] = {
        **child_config.get("metadata", {}),
        "_trace_offset": len(cumulative_trace) - len(parent_trace),
    }
    exit_event = record_event(
        state,
        "dispatcher_exit",
        f"Completed dispatch for {len(specialist_results)} specialist subgraph(s).",
        context,
        child_config,
        {"specialist_results": specialist_results, "tool_results": tool_results, "stage_results": stage_results},
    )
    return {
        **exit_event,
        "execution_trace": [entry_event, *new_child_events, *exit_event["execution_trace"]],
        "specialist_results": specialist_results,
        "tool_results": tool_results,
        "stage_results": stage_results,
    }


def _collector(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "orchestrator_collector",
        "Collected specialist answers.",
        runtime.context or {},
        config,
        {"specialist_analysis": "\n".join(item["answer"] for item in state.get("specialist_results", []))},
    )
    answers = [item["answer"] for item in state.get("specialist_results", [])]
    return {**event, "specialist_analysis": "\n".join(answers)}


def _evaluator(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "orchestrator_evaluator",
        "Marked the demo orchestration result sufficient.",
        runtime.context or {},
        config,
        {"evaluation": "sufficient", "is_sufficient": True},
    )
    return {**event, "evaluation": "sufficient", "is_sufficient": True}


def _synthesizer(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "orchestrator_synthesizer",
        "Created the final deterministic answer.",
        runtime.context or {},
        config,
        {"answer": f"Demo orchestration completed using: {', '.join(state.get('selected_specialists', []))}."},
    )
    domains = ", ".join(state.get("selected_specialists", []))
    return {
        **event,
        "answer": f"Demo orchestration completed using: {domains}.",
    }


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    return "synthesizer" if state.get("is_sufficient", True) else "planner"


def build_orchestrator_graph():
    """Build the deterministic top-level Astrologer Manager demo workflow."""

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
