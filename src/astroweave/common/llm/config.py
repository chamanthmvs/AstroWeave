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

_DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "groq": "openai/gpt-oss-120b",
}
_DEFAULT_TEMPERATURE = 0.2
# Claude thinks before answering and its thinking counts toward max_tokens, so it
# needs far more headroom than a non-thinking completion (requests are streamed, so
# a large ceiling costs nothing unless it is used).
_DEFAULT_MAX_TOKENS = {"anthropic": 64000}
_FALLBACK_MAX_TOKENS = 4096
# Specialists do the hard chart judgment; routing and synthesis are lighter work.
_DEFAULT_EFFORT = {"specialist": "high", "match": "high"}
_FALLBACK_EFFORT = "medium"


@dataclass(frozen=True)
class LLMConfig:
    """Resolved provider/model settings for one LLM call site.

    `temperature` applies to providers that accept it; Claude's current models
    do not, and are steered with `effort` (low|medium|high|xhigh|max) instead.
    """

    provider: str
    model: str
    temperature: float
    max_tokens: int
    effort: str = _FALLBACK_EFFORT


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

    Env vars checked, most specific wins (<SETTING> is PROVIDER, MODEL,
    TEMPERATURE, MAX_TOKENS or EFFORT):
      ASTROWEAVE_LLM_<SETTING>_<AGENT>, ASTROWEAVE_LLM_<SETTING>_<ROLE>, ASTROWEAVE_LLM_<SETTING>
    Unset model and max_tokens default per provider; unset effort defaults per role.
    """
    role_key = role.upper()
    agent_key = agent_name.upper() if agent_name else None

    def setting(name: str) -> str | None:
        return _first_env(_env_names(f"ASTROWEAVE_LLM_{name}", role_key, agent_key))

    provider = (setting("PROVIDER") or _DEFAULT_PROVIDER).lower()
    temperature_raw = setting("TEMPERATURE")
    max_tokens_raw = setting("MAX_TOKENS")

    return LLMConfig(
        provider=provider,
        model=setting("MODEL") or _DEFAULT_MODELS.get(provider, _DEFAULT_MODELS["groq"]),
        temperature=float(temperature_raw) if temperature_raw else _DEFAULT_TEMPERATURE,
        max_tokens=int(max_tokens_raw) if max_tokens_raw else _DEFAULT_MAX_TOKENS.get(provider, _FALLBACK_MAX_TOKENS),
        effort=(setting("EFFORT") or _DEFAULT_EFFORT.get(role.lower(), _FALLBACK_EFFORT)).lower(),
    )
