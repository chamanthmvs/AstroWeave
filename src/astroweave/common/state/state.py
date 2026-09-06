from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class Message(TypedDict):
    message_id: str
    role: str
    content: str


class ToolResult(TypedDict):
    tool_name: str
    result: Any


class StageResult(TypedDict):
    stage: str
    result: Any


class ExecutionEvent(TypedDict):
    step: int
    entry_point: str
    node: str
    action: str
    state_keys: list[str]
    state_before: dict[str, Any]
    state_updates: dict[str, Any]
    state_after: dict[str, Any]
    context: dict[str, Any]
    runnable_config: dict[str, Any]


def keep_latest_five(
    current: list[StageResult], update: list[StageResult]
) -> list[StageResult]:
    """Append new stage results while keeping the state bounded."""

    return (current + update)[-5:]


class State(TypedDict, total=False):
    user_query: str
    messages: Annotated[list[Message], operator.add]
    plan: list[str]
    current_task: str
    tool_results: Annotated[list[ToolResult], operator.add]
    stage_results: Annotated[list[StageResult], keep_latest_five]
    specialist_analysis: str
    evaluation: str
    needs_replanning: bool
    iteration_count: int
    answer: str
    errors: Annotated[list[str], operator.add]
    is_sufficient: bool
    selected_specialists: list[str]
    specialist_results: Annotated[list[dict[str, Any]], operator.add]
    execution_trace: Annotated[list[ExecutionEvent], operator.add]
