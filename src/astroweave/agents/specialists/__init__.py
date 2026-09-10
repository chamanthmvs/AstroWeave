"""Registry mapping specialist domain names to their system prompts.

Add a new specialist by creating agents/specialists/<name>/prompts.py with a
`<NAME>_SPECIALIST_PROMPT` constant and registering it here - the dispatcher
and specialist executor look specialists up only through this registry.
"""

from astroweave.agents.specialists.career.prompts import CAREER_SPECIALIST_PROMPT
from astroweave.agents.specialists.finance.prompts import FINANCE_SPECIALIST_PROMPT
from astroweave.agents.specialists.love.prompts import LOVE_SPECIALIST_PROMPT
from astroweave.agents.specialists.sports.prompts import SPORTS_SPECIALIST_PROMPT

SPECIALIST_PROMPTS: dict[str, str] = {
    "career": CAREER_SPECIALIST_PROMPT,
    "finance": FINANCE_SPECIALIST_PROMPT,
    "love": LOVE_SPECIALIST_PROMPT,
    "sports": SPORTS_SPECIALIST_PROMPT,
}

__all__ = ["SPECIALIST_PROMPTS"]
