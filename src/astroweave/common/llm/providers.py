from __future__ import annotations

from collections.abc import Callable
from typing import Any

from astroweave.common.config import get_logger

from .config import LLMConfig

logger = get_logger(__name__)

_ProviderBuilder = Callable[[LLMConfig], Any]

_PROVIDER_REGISTRY: dict[str, _ProviderBuilder] = {}


def register_provider(name: str, builder: _ProviderBuilder) -> None:
    """Register a builder for an LLM API provider.

    Use this to add a new provider (or override a built-in one) without
    touching the rest of the codebase - e.g. when an existing provider
    starts charging too much and a cheaper one needs to take over.
    """
    _PROVIDER_REGISTRY[name.lower()] = builder
    logger.debug("registered LLM provider '%s'", name.lower())


def build_llm(config: LLMConfig) -> Any:
    """Instantiate a chat model for the resolved provider/model/temperature."""
    try:
        builder = _PROVIDER_REGISTRY[config.provider]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDER_REGISTRY)) or "none"
        raise ValueError(
            f"Unknown LLM provider '{config.provider}'. Registered providers: {known}"
        ) from exc
    logger.debug("building LLM: provider=%s model=%s", config.provider, config.model)
    return builder(config)


def _build_openai(config: LLMConfig) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=config.model, temperature=config.temperature)


def _build_anthropic(config: LLMConfig) -> Any:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=config.model, temperature=config.temperature)


def _build_groq(config: LLMConfig) -> Any:
    import os

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        reasoning_effort="high",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY"),
    )


register_provider("openai", _build_openai)
register_provider("anthropic", _build_anthropic)
register_provider("groq", _build_groq)
