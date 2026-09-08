from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from astroweave.common.state import ExecutionEvent, State


logger = logging.getLogger("astroweave.execution")

STATE_DEFAULTS: dict[str, Any] = {
    "user_query": "",
    "messages": [],
    "plan": [],
    "current_task": "",
    "tool_results": [],
    "stage_results": [],
    "specialist_analysis": "",
    "evaluation": "",
    "needs_replanning": False,
    "iteration_count": 0,
    "answer": "",
    "errors": [],
    "is_sufficient": False,
    "selected_specialists": [],
    "specialist_results": [],
}


def serializable_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only JSON-friendly runtime config values for the demo trace."""

    result: dict[str, Any] = {}
    configurable = config.get("configurable", {})
    if isinstance(configurable, Mapping) and "thread_id" in configurable:
        result["configurable"] = {"thread_id": configurable["thread_id"]}

    metadata = config.get("metadata", {})
    if isinstance(metadata, Mapping):
        result["metadata"] = {
            key: metadata[key]
            for key in ("session_id", "methodology")
            if key in metadata
        }

    tags = config.get("tags", [])
    if isinstance(tags, list):
        result["tags"] = list(dict.fromkeys(tags))

    if "recursion_limit" in config:
        result["recursion_limit"] = config["recursion_limit"]

    for key, value in list(result.items()):
        try:
            json.dumps(value)
        except TypeError:
            result[key] = repr(value)
        else:
            result[key] = value
    return result


def record_event(
    state: State,
    node: str,
    message: str,
    context: Mapping[str, Any],
    config: Mapping[str, Any],
    state_updates: Mapping[str, Any] | None = None,
) -> dict[str, list[ExecutionEvent]]:
    state_updates = dict(state_updates or {})
    state_before = normalized_state(state)
    state_after = apply_state_updates(state_before, state_updates)
    metadata = config.get("metadata", {})
    trace_offset = metadata.get("_trace_offset", 0) if isinstance(metadata, Mapping) else 0
    step = trace_offset + len(state.get("execution_trace", [])) + 1
    event: ExecutionEvent = {
        "step": step,
        "entry_point": node,
        "node": node,
        "action": message,
        "state_keys": sorted(state_before.keys()),
        "state_before": state_before,
        "state_updates": state_updates,
        "state_after": state_after,
        "context": dict(context),
        "runnable_config": serializable_config(config),
    }
    logger.info(
        "STEP-%s | ENTRY POINT: %s | ACTION: %s | STATE: %s",
        step,
        node,
        message,
        event["state_keys"],
    )
    print(
        f"STEP-{step} | ENTRY POINT: {node} | ACTION: {message} "
        f"| STATE KEYS: {event['state_keys']}"
    )
    return {"execution_trace": [event]}


def normalized_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Show one stable state shape instead of raw LangGraph channel growth."""

    return {
        **STATE_DEFAULTS,
        **{key: value for key, value in state.items() if key != "execution_trace"},
    }


def apply_state_updates(
    state: Mapping[str, Any], updates: Mapping[str, Any]
) -> dict[str, Any]:
    """Approximate the visible post-node state using the project's reducers."""

    result = {**state}
    for key, value in updates.items():
        if key in {"messages", "tool_results", "errors", "specialist_results"}:
            result[key] = [*result.get(key, []), *value]
        elif key == "stage_results":
            result[key] = [*result.get(key, []), *value][-5:]
        else:
            result[key] = value
    return result


def renumber_events(events: list[ExecutionEvent]) -> list[ExecutionEvent]:
    """Give nested specialist events one continuous top-level timeline."""

    return [
        {**event, "step": step}
        for step, event in enumerate(events, start=1)
    ]