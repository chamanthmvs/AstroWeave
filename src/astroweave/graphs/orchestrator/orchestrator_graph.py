from collections.abc import Mapping

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from astroweave.common.config import get_logger
from astroweave.common.context import Context
from astroweave.common.llm import (
    ContextLimitExceededError,
    enforce_context_limit,
    get_llm,
    invoke_json_response,
)
from astroweave.common.state import State
from astroweave.methodologies import normalize_methodology
from astroweave.orchestration.dispatcher.dispatcher import execute_specialist
from astroweave.orchestration.manager.manager import run_manager

from .prompts import ORCHESTRATOR_ROUTING_PROMPT, ORCHESTRATOR_SYNTHESIS_PROMPT

logger = get_logger(__name__)


def _resolve_conversation_context(state: State) -> State:
    logger.info(
        "resolve-conversation-context: placeholder active; validating query without loading history"
    )
    return run_manager(state)


def _classify_request(state: State, runtime: Runtime[Context]) -> State:
    logger.info("classify-request: selecting specialists and methodology")
    if state.get("errors"):
        return {}

    forced_methodology = normalize_methodology((runtime.context or {}).get("methodology"))
    has_birth_details = bool((runtime.context or {}).get("birth_details"))

    llm = get_llm("orchestrator")
    try:
        parsed = invoke_json_response(
            "classify-request",
            llm,
            [
                SystemMessage(content=ORCHESTRATOR_ROUTING_PROMPT),
                HumanMessage(
                    content=(
                        f"User question: {state.get('user_query', '')}\n"
                        f"Birth details available: {'yes' if has_birth_details else 'no'}"
                    )
                ),
            ],
        )
    except ValueError as error:
        return {"errors": [str(error)]}

    specialists = parsed.get("specialists") or []
    methodology = forced_methodology or parsed.get("methodology") or "vedic"
    plan = state.get("plan", []) + [parsed.get("reasoning", "")]
    logger.info(
        "classify-request selected specialists=%s methodology=%s",
        specialists,
        methodology,
    )

    return {"specialists": specialists, "methodology": methodology, "plan": plan}


def _plan_specialist_tasks(state: State) -> State:
    specialists = state.get("specialists") or []
    if not specialists:
        logger.warning(
            "plan-specialist-tasks could not create tasks because no specialists were selected"
        )
        return {"pending_tasks": [], "completed_tasks": [], "errors": [
            "No specialist could be determined for this question."
        ]}

    tasks = list(dict.fromkeys(specialists))
    logger.info("plan-specialist-tasks created %d task(s): %s", len(tasks), tasks)
    return {"pending_tasks": tasks, "completed_tasks": [], "current_task": ""}


def _select_next_task(state: State) -> State:
    pending_tasks = state.get("pending_tasks") or []
    if not pending_tasks:
        logger.info("select-next-task: queue empty; response synthesis is ready")
        return {"current_task": ""}

    current_task = pending_tasks[0]
    logger.info(
        "select-next-task selected '%s' (%d task(s) queued)",
        current_task,
        len(pending_tasks),
    )
    return {"current_task": current_task}


def _run_specialist(state: State, runtime: Runtime[Context]) -> State:
    current_task = state.get("current_task", "")
    if not current_task:
        logger.warning("run-specialist reached without a current task")
        return {"errors": ["No specialist task was ready for execution."]}
    return execute_specialist(state, runtime, current_task)


def _collect_specialist_result(state: State) -> State:
    current_task = state.get("current_task", "")
    pending_tasks = list(state.get("pending_tasks") or [])
    completed_tasks = list(state.get("completed_tasks") or [])
    if current_task:
        if pending_tasks and pending_tasks[0] == current_task:
            pending_tasks.pop(0)
        elif current_task in pending_tasks:
            pending_tasks.remove(current_task)
        completed_tasks.append(current_task)

    logger.info(
        "collect-specialist-result recorded '%s'; completed=%d pending=%d",
        current_task,
        len(completed_tasks),
        len(pending_tasks),
    )
    return {
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "current_task": "",
        "iteration_count": len(completed_tasks),
    }


def _synthesize_response(state: State) -> State:
    logger.info(
        "synthesize-response combining %d specialist result(s)",
        len(state.get("specialist_results") or []),
    )
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
    user_content = (
        f"User question: {state.get('user_query', '')}\n\n"
        "Specialist findings:\n" + "\n".join(summary_lines)
    )
    try:
        enforce_context_limit("synthesizer", user_content)
    except ContextLimitExceededError as error:
        logger.warning("synthesizer falling back to raw conclusions: %s", error)
        fallback = " ".join(
            f"{result['specialist']}: {result.get('conclusion', '')}" for result in specialist_results
        )
        return {"answer": fallback, "errors": errors + [str(error)]}

    llm = get_llm("orchestrator")
    response = llm.invoke(
        [
            SystemMessage(content=ORCHESTRATOR_SYNTHESIS_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    return {"answer": response.content}


def _route_after_context_resolution(state: Mapping[str, object]) -> str:
    destination = "synthesize-response" if state.get("errors") else "classify-request"
    logger.info("resolve-conversation-context routing to '%s'", destination)
    return destination


def _route_selected_task(state: Mapping[str, object]) -> str:
    destination = "run-specialist" if state.get("current_task") else "synthesize-response"
    logger.info("select-next-task routing to '%s'", destination)
    return destination


def _route_after_collection(state: Mapping[str, object]) -> str:
    destination = (
        "select-next-task" if state.get("pending_tasks") else "synthesize-response"
    )
    logger.info("collect-specialist-result routing to '%s'", destination)
    return destination


def build_orchestrator_graph():
    """Build the top-level workflow for the Astrologer Manager.

    Conversation-context resolution is a placeholder in this phase. Request
    classification selects specialists and methodology, task planning creates
    a queue, and each selected task invokes one specialist subgraph before its
    result is collected. Response synthesis handles errors and completed work.
    """

    logger.info("Building orchestrator graph")
    graph = StateGraph(State, context_schema=Context)
    graph.add_node("resolve-conversation-context", _resolve_conversation_context)
    graph.add_node("classify-request", _classify_request)
    graph.add_node("plan-specialist-tasks", _plan_specialist_tasks)
    graph.add_node("select-next-task", _select_next_task)
    graph.add_node("run-specialist", _run_specialist)
    graph.add_node("collect-specialist-result", _collect_specialist_result)
    graph.add_node("synthesize-response", _synthesize_response)

    graph.add_edge(START, "resolve-conversation-context")
    graph.add_conditional_edges(
        "resolve-conversation-context",
        _route_after_context_resolution,
        {
            "classify-request": "classify-request",
            "synthesize-response": "synthesize-response",
        },
    )
    graph.add_edge("classify-request", "plan-specialist-tasks")
    graph.add_edge("plan-specialist-tasks", "select-next-task")
    graph.add_conditional_edges(
        "select-next-task",
        _route_selected_task,
        {
            "run-specialist": "run-specialist",
            "synthesize-response": "synthesize-response",
        },
    )
    graph.add_edge("run-specialist", "collect-specialist-result")
    graph.add_conditional_edges(
        "collect-specialist-result",
        _route_after_collection,
        {
            "select-next-task": "select-next-task",
            "synthesize-response": "synthesize-response",
        },
    )
    graph.add_edge("synthesize-response", END)

    return graph.compile()