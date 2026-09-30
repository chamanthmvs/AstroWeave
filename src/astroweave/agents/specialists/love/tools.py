"""Prompt-only analysis tools for relationship intents."""

from astroweave.common.tools import PromptTool

LOVE_TOOLS = (
    PromptTool(
        "romantic_patterns",
        "dating_and_romance",
        "Interpret relationship preferences and recurring romantic themes from supplied placements, focusing on relevant 5th- and 7th-house factors and Venus when present. Avoid treating symbolic patterns as fixed personality facts and do not invent chart details.",
    ),
    PromptTool(
        "dating_opportunities",
        "dating_and_romance",
        "Review broad periods that may support meeting people, dating, or clarifying relationship priorities using only supplied timing factors. Do not guarantee a meeting or identify a specific person; state uncertainty and avoid fabricated dates.",
    ),
    PromptTool(
        "relationship_readiness",
        "dating_and_romance",
        "Explore chart-supported themes of emotional readiness, boundaries, and openness to partnership in response to the user's question. Keep the interpretation compassionate and non-prescriptive; do not infer trauma, consent, or private behavior from placements.",
    ),
    PromptTool(
        "marriage_indications",
        "marriage_and_commitment",
        "Assess commitment and marriage themes through supplied 7th-house factors, relevant significators, divisional data, and stated methodology. Distinguish promise from timing, acknowledge mixed indicators, and never claim marriage is certain or impossible from one factor.",
    ),
    PromptTool(
        "commitment_timing",
        "marriage_and_commitment",
        "Evaluate broad commitment or marriage windows from the provided dasha/bhukti or KP indicators. Explain which supplied factors support the window, avoid exact-date certainty, and do not override the user's agency or real relationship circumstances.",
    ),
    PromptTool(
        "partner_themes",
        "marriage_and_commitment",
        "Describe broad partnership qualities symbolically indicated by the supplied chart, using relevant 7th-house and relationship significators only when available. Do not claim to identify a future spouse or make assertions about a real person's identity, appearance, or character.",
    ),
    PromptTool(
        "chart_compatibility",
        "compatibility",
        "Compare both supplied charts for areas of ease and adjustment, considering emotional, communicative, and commitment themes under the stated methodology. Use only data for both people that is actually present; do not reduce compatibility to a score or declare a relationship destined to succeed or fail.",
    ),
    PromptTool(
        "emotional_communication_fit",
        "compatibility",
        "Explore complementary and contrasting emotional or communication patterns using supplied chart factors for both people. Phrase observations as hypotheses for reflection, avoid diagnosing either person, and clearly state when one chart or birth-time accuracy is missing.",
    ),
    PromptTool(
        "long_term_partnership_fit",
        "compatibility",
        "Review long-term partnership themes across the two supplied charts, balancing supportive and demanding indicators and respecting the selected Vedic or KP approach. Do not offer a binary verdict, claim certainty, or substitute astrology for honest communication and consent.",
    ),
    PromptTool(
        "relationship_conflict",
        "relationship_challenges",
        "Interpret possible sources of tension in the relationship question using only supplied chart factors. Avoid assigning blame or claiming to know another person's motives; offer balanced symbolic themes and distinguish them from established facts.",
    ),
    PromptTool(
        "reconciliation_themes",
        "relationship_challenges",
        "Assess whether supplied chart timing and relationship indicators suggest a period for renewed communication or closure. Do not promise reconciliation, encourage unwanted contact, or minimize safety concerns; preserve the user's autonomy and boundaries.",
    ),
    PromptTool(
        "relationship_stability",
        "relationship_challenges",
        "Review themes of continuity, adaptation, and change in the supplied chart or charts. Present more than one plausible interpretation when factors conflict, avoid predicting separation as inevitable, and do not replace professional support where needed.",
    ),
)