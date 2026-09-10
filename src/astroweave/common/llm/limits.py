"""Optional, configurable character-limit guard for inter-agent payloads.

By default AstroWeave does not limit how much context one agent (or tool)
hands another - answer quality matters more than fitting some provider's
token window. Set ASTROWEAVE_CONTEXT_CHAR_LIMIT to a positive integer to
enable a hard cutoff (e.g. when running against a rate-limited free-tier
provider); leaving it unset, blank, or 0 disables the check entirely.
"""

from __future__ import annotations

import os

from astroweave.common.config import get_logger

logger = get_logger(__name__)

_ENV_VAR = "ASTROWEAVE_CONTEXT_CHAR_LIMIT"


class ContextLimitExceededError(ValueError):
    """Raised when a payload exceeds the configured context character limit."""


def get_context_char_limit() -> int | None:
    """Return the configured limit, or None if the check is disabled."""
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        return None
    try:
        limit = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer; ignoring", _ENV_VAR, raw)
        return None
    return limit if limit > 0 else None


def enforce_context_limit(node_name: str, payload: str) -> None:
    """Raise ContextLimitExceededError if payload exceeds the configured limit.

    No-op whenever ASTROWEAVE_CONTEXT_CHAR_LIMIT is unset/0 (the default) -
    see the module docstring. Call this at every hand-off between agents (and
    between an agent and a tool) so the same rule applies everywhere.
    """
    limit = get_context_char_limit()
    if limit is None:
        return
    length = len(payload)
    if length > limit:
        logger.warning(
            "%s payload of %d chars exceeds configured limit of %d chars",
            node_name,
            length,
            limit,
        )
        raise ContextLimitExceededError(
            f"{node_name} payload of {length} chars exceeds the configured "
            f"context limit of {limit} chars (set via {_ENV_VAR})"
        )
