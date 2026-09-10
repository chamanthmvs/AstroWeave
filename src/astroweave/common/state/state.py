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


def keep_latest_five(
    current: list[StageResult], update: list[StageResult]
) -> list[StageResult]:
    """Append new stage results while keeping the state bounded."""

    return (current + update)[-5:]


class SpecialistResult(TypedDict):
    specialist: str
    analysis: str
    conclusion: str
    confidence: str


class State(TypedDict, total=False):
    user_query: str
    messages: Annotated[list[Message], operator.add]
    plan: list[str]
    current_task: str
    tool_results: Annotated[list[ToolResult], operator.add]
    stage_results: Annotated[list[StageResult], keep_latest_five]
    specialists: list[str]
    methodology: str
    chart_data: dict[str, Any]
    specialist_analysis: str
    specialist_results: Annotated[list[SpecialistResult], operator.add]
    evaluation: str
    needs_replanning: bool
    iteration_count: int
    answer: str
    errors: Annotated[list[str], operator.add]
    is_sufficient: bool
