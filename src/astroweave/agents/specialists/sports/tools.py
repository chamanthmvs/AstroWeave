"""Prompt-only analysis tools for sports intents."""

from astroweave.common.tools import PromptTool

SPORTS_TOOLS = (
    PromptTool(
        "athletic_strengths",
        "athletic_profile",
        "Interpret chart-supported athletic aptitudes and competitive motivations from supplied placements, emphasizing relevant 3rd-, 5th-, 6th-, and 10th-house factors and Mars only when present. Treat these as reflective themes, not measured ability or a substitute for observed performance.",
    ),
    PromptTool(
        "training_discipline",
        "athletic_profile",
        "Review symbolic indicators of consistency, focus, and response to structured practice using available chart data and active periods. Do not prescribe training loads, make physiological claims, or assume information about the athlete's health or coaching.",
    ),
    PromptTool(
        "team_role_fit",
        "athletic_profile",
        "Explore broad themes around individual versus team competition, tactical roles, and collaboration from the supplied chart. Avoid declaring a specific position or selection outcome without real-world evidence; state the limits of the available data.",
    ),
    PromptTool(
        "competition_windows",
        "competition_timing",
        "Assess broad periods that may be symbolically supportive for competition using only supplied dasha/bhukti, KP, or other requested timing data. Explain uncertainty, avoid exact-result predictions, and do not imply that timing replaces preparation or opponent conditions.",
    ),
    PromptTool(
        "selection_recognition",
        "competition_timing",
        "Interpret recognition, selection, and competitive visibility themes from relevant supplied houses, lords, and periods. Distinguish potential from an actual selection decision, never guarantee a result, and note any missing chart or event details.",
    ),
    PromptTool(
        "event_readiness_themes",
        "competition_timing",
        "Synthesize chart timing relevant to preparation and event participation without predicting a score, win, or loss as certain. Use the user's stated methodology and available data, and frame the result as one reflective input among practical performance factors.",
    ),
    PromptTool(
        "sports_pathway",
        "sports_career",
        "Review chart themes related to sustained athletic pursuit, progression, and public recognition using supplied career and competition indicators. Avoid promising professional success and balance astrological interpretation with the user's stated experience and goals.",
    ),
    PromptTool(
        "amateur_professional_transition",
        "sports_career",
        "Assess broad themes around increasing commitment to sport or balancing sport with education and work. Use only relevant supplied chart factors and timing periods; do not direct the user to abandon education, employment, or financial stability.",
    ),
    PromptTool(
        "competitive_longevity",
        "sports_career",
        "Interpret chart-supported themes around adapting roles, sustaining motivation, and navigating changes in a sporting path. Do not predict career-ending events or infer physical capacity from astrology; identify uncertainty and practical factors outside the chart.",
    ),
    PromptTool(
        "pressure_and_confidence",
        "performance_resilience",
        "Explore symbolic patterns in confidence, composure, and response to competitive pressure from the supplied chart. Avoid mental-health diagnosis or claims about a specific performance; keep suggestions reflective and non-clinical.",
    ),
    PromptTool(
        "setback_recovery_themes",
        "performance_resilience",
        "Interpret broad themes of persistence and rebuilding after a setback using relevant chart factors and periods. Do not diagnose or predict injury, prescribe recovery, or replace advice from qualified sports and medical professionals.",
    ),
    PromptTool(
        "motivation_cycles",
        "performance_resilience",
        "Review periods that may symbolically correspond with renewed motivation, fatigue, or changing priorities. Do not infer burnout or health conditions, and present chart-based possibilities as prompts for reflection rather than facts.",
    ),
)