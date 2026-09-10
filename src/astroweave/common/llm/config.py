from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# ASTROWEAVE_ENV picks the dotenv file: .env.development (default), .env.production,
# .env.test, etc. Falls back to a plain .env if the environment-specific file
# doesn't exist, so a single shared .env still works for simple local setups.
_env_name = os.environ.get("ASTROWEAVE_ENV", "development")
if not load_dotenv(f".env.{_env_name}"):
    load_dotenv()

_DEFAULT_PROVIDER = "groq"
_DEFAULT_MODEL = "openai/gpt-oss-20b"
_DEFAULT_TEMPERATURE = 0.2


@dataclass(frozen=True)
class LLMConfig:
    """Resolved provider/model/temperature for one LLM call site."""

    provider: str
    model: str
    temperature: float


def _first_env(names: list[str]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _env_names(prefix: str, role_key: str, agent_key: str | None) -> list[str]:
    # Most specific first: per-agent override, then per-role, then global default.
    names = []
    if agent_key:
        names.append(f"{prefix}_{agent_key}")
    names.append(f"{prefix}_{role_key}")
    names.append(prefix)
    return names


def resolve_llm_config(role: str, agent_name: str | None = None) -> LLMConfig:
    """Resolve which provider/model/temperature to use for a role and agent.

    This is what makes it possible for the orchestrator to use one API
    provider (e.g. OpenAI) while individual specialists use another (e.g.
    Anthropic), and to switch any of them later via env vars alone - no code
    changes needed to swap providers if one gets too expensive.

    `role` is typically "orchestrator" or "specialist". `agent_name` narrows
    the lookup further (e.g. "career") so a single specialist can override
    the role-level default.

    Env vars checked, most specific wins:
      ASTROWEAVE_LLM_PROVIDER_<AGENT>, ASTROWEAVE_LLM_PROVIDER_<ROLE>, ASTROWEAVE_LLM_PROVIDER
      ASTROWEAVE_LLM_MODEL_<AGENT>, ASTROWEAVE_LLM_MODEL_<ROLE>, ASTROWEAVE_LLM_MODEL
      ASTROWEAVE_LLM_TEMPERATURE_<AGENT>, ASTROWEAVE_LLM_TEMPERATURE_<ROLE>, ASTROWEAVE_LLM_TEMPERATURE
    """
    role_key = role.upper()
    agent_key = agent_name.upper() if agent_name else None

    provider = _first_env(_env_names("ASTROWEAVE_LLM_PROVIDER", role_key, agent_key))
    model = _first_env(_env_names("ASTROWEAVE_LLM_MODEL", role_key, agent_key))
    temperature_raw = _first_env(
        _env_names("ASTROWEAVE_LLM_TEMPERATURE", role_key, agent_key)
    )

    return LLMConfig(
        provider=(provider or _DEFAULT_PROVIDER).lower(),
        model=model or _DEFAULT_MODEL,
        temperature=float(temperature_raw) if temperature_raw else _DEFAULT_TEMPERATURE,
    )
