from __future__ import annotations

from typing import Any

from .config import resolve_llm_config
from .providers import build_llm


def get_llm(role: str, agent_name: str | None = None) -> Any:
    """Return a chat model configured for the given role/agent.

    `role` is typically "orchestrator" or "specialist"; pass `agent_name`
    (e.g. "career") to let that specific agent override the role's default
    provider/model. See `resolve_llm_config` for the env var lookup order.
    """
    config = resolve_llm_config(role, agent_name)
    return build_llm(config)
