from __future__ import annotations

import json
from typing import Any

from astroweave.common.config import get_logger

logger = get_logger(__name__)


def log_reasoning(node_name: str, response: dict[str, Any]) -> None:
    """Log the LLM's stated reasoning at INFO so answers stay auditable.

    Checks "reasoning" (orchestrator routing) and "analysis" (specialist
    output) - whichever field the calling prompt's JSON contract uses - since
    knowing *why* an answer was given is as important as the answer itself.
    """
    reasoning = response.get("reasoning") or response.get("analysis")
    if reasoning:
        logger.info("%s reasoning: %s", node_name, reasoning)
    else:
        logger.warning("%s response had no reasoning/analysis field to log", node_name)


def parse_json_response(node_name: str, raw_text: str) -> dict[str, Any]:
    """Parse an LLM's JSON response, logging its reasoning at INFO first.

    Raises ValueError on invalid JSON - routing and specialist decisions must
    always be auditable, so a malformed response is treated as a hard error
    rather than something to silently paper over.
    """
    try:
        response = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("%s returned non-JSON response: %s", node_name, raw_text)
        raise ValueError(f"{node_name} returned a non-JSON response") from exc

    log_reasoning(node_name, response)
    return response


def invoke_json_response(
    node_name: str,
    llm: Any,
    messages: list[Any],
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Invoke an LLM and retry once when its JSON response is malformed."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error: ValueError | None = None
    for attempt in range(1, max_attempts + 1):
        response = llm.invoke(messages)
        content = response.content
        metadata = getattr(response, "response_metadata", {}) or {}
        logger.info(
            "%s response attempt=%d/%d content_chars=%d finish_reason=%s",
            node_name,
            attempt,
            max_attempts,
            len(content),
            metadata.get("finish_reason", "unknown"),
        )
        try:
            return parse_json_response(node_name, content)
        except ValueError as error:
            last_error = error
            if attempt < max_attempts:
                logger.warning(
                    "%s produced malformed JSON; retrying (%d/%d)",
                    node_name,
                    attempt + 1,
                    max_attempts,
                )

    raise last_error or ValueError(f"{node_name} did not return JSON")
