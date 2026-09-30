"""Orchestrator-facing registry of specialist agents.

Add a new specialist by creating agents/specialists/<name>/prompts.py with a
`<NAME>_SPECIALIST_PROMPT` constant and registering an AgentDefinition here.
Each definition owns the tools available only to that specialist.
"""

from astroweave.agents.registry import AgentDefinition, AgentRegistry
from astroweave.agents.specialists.career.prompts import CAREER_SPECIALIST_PROMPT
from astroweave.agents.specialists.career.tools import CAREER_TOOLS
from astroweave.agents.specialists.finance.prompts import FINANCE_SPECIALIST_PROMPT
from astroweave.agents.specialists.finance.tools import FINANCE_TOOLS
from astroweave.agents.specialists.love.prompts import LOVE_SPECIALIST_PROMPT
from astroweave.agents.specialists.love.tools import LOVE_TOOLS
from astroweave.agents.specialists.sports.prompts import SPORTS_SPECIALIST_PROMPT
from astroweave.agents.specialists.sports.tools import SPORTS_TOOLS
from astroweave.common.tools import ToolRegistry

SPECIALIST_REGISTRY = AgentRegistry(
    [
        AgentDefinition(
            name="career",
            description="Interprets career, work, and professional direction.",
            prompt=CAREER_SPECIALIST_PROMPT,
            tools=ToolRegistry(CAREER_TOOLS),
        ),
        AgentDefinition(
            name="finance",
            description="Interprets finances, wealth, and material stability.",
            prompt=FINANCE_SPECIALIST_PROMPT,
            tools=ToolRegistry(FINANCE_TOOLS),
        ),
        AgentDefinition(
            name="love",
            description="Interprets relationships, compatibility, and partnership.",
            prompt=LOVE_SPECIALIST_PROMPT,
            tools=ToolRegistry(LOVE_TOOLS),
        ),
        AgentDefinition(
            name="sports",
            description="Interprets sports performance and competitive timing.",
            prompt=SPORTS_SPECIALIST_PROMPT,
            tools=ToolRegistry(SPORTS_TOOLS),
        ),
    ]
)

__all__ = ["SPECIALIST_REGISTRY"]
