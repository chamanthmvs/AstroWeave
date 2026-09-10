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
