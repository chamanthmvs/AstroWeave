"""Claude chat model on the official Anthropic SDK.

Exposes the small surface the graphs already use - `invoke(messages)` returning
an object with `.content` (text) and `.response_metadata` - so Claude slots
into the provider registry next to the LangChain-based providers.

Request shape for current Claude models (Opus 5.5 by default):
- adaptive thinking is always on; `output_config.effort` controls its depth
  (sampling parameters such as temperature are not accepted),
- responses are streamed, since thinking plus a long analysis can be large,
- the system prompt is cached (specialist prompts are long and identical
  across requests),
- JSON-producing calls pass a JSON schema as a structured output,
- a safety-classifier refusal is retried server-side on Anthropic's
  recommended fallback model (`fallbacks: "default"`).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from astroweave.common.config import get_logger

logger = get_logger(__name__)

REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept server-side refusal fallbacks (`fallbacks: "default"`). Others -
# e.g. Claude Haiku 5.5, Claude Sonnet 5, Claude Sonnet 4.6 - get no fallback parameter.
SERVER_FALLBACK_MODELS = frozenset({
    "claude-fable-5-1", "claude-fable-5", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
})
_ROLE_BY_MESSAGE_TYPE = {"system": "system", "human": "user", "user": "user", "ai": "assistant", "assistant": "assistant"}

_client_lock = threading.Lock()
_shared_client: Any = None


def _default_client() -> Any:
    """One SDK client per process: it is thread-safe and pools connections."""
    global _shared_client
    with _client_lock:
        if _shared_client is None:
            import anthropic

            # Credentials resolve from the environment (ANTHROPIC_API_KEY, ...).
            _shared_client = anthropic.Anthropic()
        return _shared_client


class ClaudeRefusalError(ValueError):
    """Claude (and its fallback) declined the request."""


class ClaudeConfigurationError(RuntimeError):
    """No Anthropic credentials could be resolved."""


@dataclass
class ChatResponse:
    content: str
    response_metadata: dict[str, Any] = field(default_factory=dict)


class AnthropicChatModel:
    """Minimal chat-model adapter: `invoke(messages, json_schema=None)`."""

    supports_json_schema = True

    def __init__(self, model: str, max_tokens: int, effort: str, client: Any = None) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self._client = client

    def invoke(self, messages: list[Any], json_schema: Mapping[str, Any] | None = None) -> ChatResponse:
        system, turns = _split_messages(messages)
        output_config: dict[str, Any] = {"effort": self.effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": dict(json_schema)}
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "thinking": {"type": "adaptive"},
            "output_config": output_config,
            "messages": turns,
        }
        if self.model in SERVER_FALLBACK_MODELS:
            request["betas"] = [REFUSAL_FALLBACK_BETA]
            request["fallbacks"] = "default"
        if system:
            request["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

        client = self._client or _default_client()
        try:
            with client.beta.messages.stream(**request) as stream:
                message = stream.get_final_message()
        except TypeError as error:
            # The SDK resolves credentials lazily and reports a missing key as a TypeError.
            if "authentication" not in str(error).lower():
                raise
            raise ClaudeConfigurationError(
                "No Anthropic credentials found. Set ANTHROPIC_API_KEY in .env.development "
                "(or the environment), or choose another provider with ASTROWEAVE_LLM_PROVIDER."
            ) from error

        usage = getattr(message, "usage", None)
        metadata = {
            "finish_reason": message.stop_reason,
            "model": getattr(message, "model", self.model),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
        }
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None)
            logger.warning("Claude declined the request category=%s model=%s", category, metadata["model"])
            raise ClaudeRefusalError(f"The model declined this request (category: {category or 'unspecified'}).")

        text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        logger.info(
            "Claude response model=%s stop_reason=%s input_tokens=%s output_tokens=%s cache_read=%s",
            metadata["model"], metadata["finish_reason"], metadata["input_tokens"],
            metadata["output_tokens"], metadata["cache_read_input_tokens"],
        )
        return ChatResponse(content=text, response_metadata=metadata)


def _split_messages(messages: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    """Split LangChain-style or dict messages into a system prompt and turns."""
    system_parts: list[str] = []
    turns: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, Mapping):
            role, content = message.get("role", "user"), message.get("content", "")
        else:
            role, content = getattr(message, "type", "user"), getattr(message, "content", "")
        role = _ROLE_BY_MESSAGE_TYPE.get(role, "user")
        if role == "system":
            system_parts.append(content)
        else:
            turns.append({"role": role, "content": content})
    return "\n\n".join(part for part in system_parts if part), turns
