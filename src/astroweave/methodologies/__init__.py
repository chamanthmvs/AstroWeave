"""Astrology methodology boundary: vedic, kp, or both.

Methodologies are analytical lenses applied by specialists, independent of
domain (career/finance/love/sports). For v1 there is no methodology-specific
retrieval yet (that arrives with the knowledge/RAG layer); this module just
normalizes user- or LLM-provided methodology labels to a canonical value.
"""

from __future__ import annotations

VEDIC = "vedic"
KP = "kp"
BOTH = "both"
_VALID = {VEDIC, KP, BOTH}

_UI_LABELS = {
    "let the system decide": None,
    "vedic": VEDIC,
    "kp": KP,
    "both": BOTH,
}


def normalize_methodology(value: str | None) -> str | None:
    """Map a UI label or LLM-chosen value to 'vedic' | 'kp' | 'both' | None.

    None means "let the system decide" - the orchestrator planner should
    pick one via the LLM in that case.
    """
    if not value:
        return None
    key = value.strip().lower()
    if key in _UI_LABELS:
        return _UI_LABELS[key]
    return key if key in _VALID else None
