from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from astroweave.common.config import AgentConfig
from astroweave.common.context import Context
from astroweave.common.state import State
from astroweave.common.trace import record_event


def _tool_for_domain(domain: str):
    if domain == "career":
        from astroweave.agents.specialists.career.tools import run_demo_tool
    elif domain == "sports":
        from astroweave.agents.specialists.sports.tools import run_demo_tool
    elif domain == "finance":
        from astroweave.agents.specialists.finance.tools import run_demo_tool
    else:
        from astroweave.agents.specialists.love.tools import run_demo_tool
    return run_demo_tool


def _planner(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "specialist_planner",
        "Created a deterministic demo task.",
        runtime.context or {},
        config,
        {"plan": ["run_specialist_demo_tool"], "current_task": "run_specialist_demo_tool", "iteration_count": state.get("iteration_count", 0) + 1},
    )
    return {
        **event,
        "plan": ["run_specialist_demo_tool"],
        "current_task": "run_specialist_demo_tool",
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _executor(
    state: State,
    runtime: Runtime[Context],
    config: RunnableConfig,
    agent_config: AgentConfig,
) -> dict[str, Any]:
    query = state.get("user_query", "")
    tool_result = _tool_for_domain(agent_config["domain"])(query)
    event = record_event(
        state,
        "specialist_executor",
        f"Ran {agent_config['domain']} demo tool.",
        runtime.context or {},
        config,
        {"tool_results": [{"tool_name": agent_config["allowed_tools"][0], "result": tool_result}], "stage_results": [{"stage": "executor", "result": tool_result}]},
    )
    return {
        **event,
        "tool_results": [
            {"tool_name": agent_config["allowed_tools"][0], "result": tool_result}
        ],
        "stage_results": [{"stage": "executor", "result": tool_result}],
    }


def _collector(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "specialist_collector",
        "Collected demo tool results.",
        runtime.context or {},
        config,
        {"specialist_analysis": str(state.get("tool_results", []))},
    )
    return {**event, "specialist_analysis": str(state.get("tool_results", []))}


def _evaluator(
    state: State, runtime: Runtime[Context], config: RunnableConfig
) -> dict[str, Any]:
    event = record_event(
        state,
        "specialist_evaluator",
        "Marked the deterministic demo result sufficient.",
        runtime.context or {},
        config,
        {"evaluation": "sufficient", "is_sufficient": True},
    )
    return {**event, "evaluation": "sufficient", "is_sufficient": True}


def _synthesizer(
    state: State,
    runtime: Runtime[Context],
    config: RunnableConfig,
    agent_config: AgentConfig,
) -> dict[str, Any]:
    event = record_event(
        state,
        "specialist_synthesizer",
        "Created a deterministic specialist answer.",
        runtime.context or {},
        config,
        {"answer": f"Demo {agent_config['domain']} specialist completed analysis for: {state.get('user_query', '')}"},
    )
    return {
        **event,
        "answer": (
            f"Demo {agent_config['domain']} specialist completed analysis for: "
            f"{state.get('user_query', '')}"
        ),
    }


def _route_after_evaluation(state: Mapping[str, object]) -> str:
    return "synthesizer" if state.get("is_sufficient", True) else "planner"


def build_specialist_graph(agent_config: AgentConfig | None = None):
    """Build the reusable specialist workflow for one agent configuration."""

    selected_config = agent_config or {
        "agent_name": "demo_specialist",
        "domain": "career",
        "enabled_methodologies": ["Vedic", "KP"],
        "allowed_tools": ["career_demo_tool"],
        "retrieval_namespace": "career",
    }
    graph = StateGraph(State, context_schema=Context)
    graph.add_node("planner", _planner)
    graph.add_node(
        "executor",
        lambda state, runtime, config: _executor(
            state, runtime, config, selected_config
        ),
    )
    graph.add_node("collector", _collector)
    graph.add_node("evaluator", _evaluator)
    graph.add_node(
        "synthesizer",
        lambda state, runtime, config: _synthesizer(
            state, runtime, config, selected_config
        ),
    )
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
