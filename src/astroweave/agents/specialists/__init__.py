"""Orchestrator-facing registry of specialist agents.

Add a new specialist by creating agents/specialists/<name>/prompts.py with a
`<NAME>_SPECIALIST_PROMPT` constant and registering an AgentDefinition here.
Each definition owns the tools available only to that specialist.
"""

from astroweave.agents.registry import AgentDefinition, AgentRegistry
from astroweave.agents.specialists.career.prompts import CAREER_SPECIALIST_PROMPT
from astroweave.agents.specialists.finance.prompts import FINANCE_SPECIALIST_PROMPT
from astroweave.agents.specialists.love.prompts import LOVE_SPECIALIST_PROMPT
from astroweave.agents.specialists.sports.prompts import SPORTS_SPECIALIST_PROMPT

SPECIALIST_REGISTRY = AgentRegistry(
    [
        AgentDefinition(
            name="career",
            description="Interprets career, work, and professional direction.",
            prompt=CAREER_SPECIALIST_PROMPT,
        ),
        AgentDefinition(
            name="finance",
            description="Interprets finances, wealth, and material stability.",
            prompt=FINANCE_SPECIALIST_PROMPT,
        ),
        AgentDefinition(
            name="love",
            description="Interprets relationships, compatibility, and partnership.",
            prompt=LOVE_SPECIALIST_PROMPT,
        ),
        AgentDefinition(
            name="sports",
            description="Interprets sports performance and competitive timing.",
            prompt=SPORTS_SPECIALIST_PROMPT,
        ),
    ]
)

__all__ = ["SPECIALIST_REGISTRY"]
