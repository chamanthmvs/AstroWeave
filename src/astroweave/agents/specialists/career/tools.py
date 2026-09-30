"""Prompt-only analysis tools for career intents."""

from astroweave.common.tools import PromptTool

CAREER_TOOLS = (
    PromptTool(
        "career_role_fit",
        "salaried_employment",
        "Assess role and work-style fit from the supplied chart. Prioritize the 2nd, 6th, 10th, and 11th houses and their lords; use D10, planetary strength, and relevant periods only when provided. Distinguish supportive tendencies from certainty and do not invent placements.",
    ),
    PromptTool(
        "career_promotion",
        "salaried_employment",
        "Evaluate promotion, authority, recognition, and responsibility themes. Connect the 10th and 11th houses, their lords, relevant significators, and active dasha/bhukti or KP periods when present; explain both supporting and delaying factors without promising an outcome.",
    ),
    PromptTool(
        "career_job_change",
        "salaried_employment",
        "Assess whether the supplied chart suggests a period of job transition versus consolidation. Compare career houses and lords with the active periods, state what evidence is missing, and frame timing as a broad astrological window rather than a guaranteed event date.",
    ),
    PromptTool(
        "business_suitability",
        "business_ownership",
        "Assess chart indications for independent work or entrepreneurship versus structured employment. Consider the 2nd, 7th, 10th, and 11th houses, their lords, and relevant periods when available; describe strengths and pressures without claiming business success is assured.",
    ),
    PromptTool(
        "business_partnerships",
        "business_ownership",
        "Analyze professional partnership themes using the 7th house and lord alongside career and income houses. Identify chart-supported cooperation or friction patterns, avoid judging an absent person's chart, and distinguish symbolic interpretation from practical due diligence.",
    ),
    PromptTool(
        "business_launch_timing",
        "business_ownership",
        "Review broad periods that may support preparation, launch, or cautious reassessment of a venture. Use only supplied dasha, transit, divisional-chart, or KP data and explain the method used; never give a fabricated date or financial guarantee.",
    ),
    PromptTool(
        "career_vocation",
        "career_direction",
        "Synthesize vocational themes and recurring strengths from supplied placements, house lords, and relevant divisional data. Relate interpretations to the user's stated interests, avoid assigning a single unavoidable destiny, and flag when chart data is incomplete.",
    ),
    PromptTool(
        "career_transition",
        "career_direction",
        "Evaluate a proposed career change by comparing indicators for continuity, transition, and skill-building. Use the 6th, 9th, 10th, and 11th houses and active periods only where chart data supports them; give balanced possibilities rather than a directive to quit or stay.",
    ),
    PromptTool(
        "career_learning",
        "career_direction",
        "Interpret education, certification, and skill-development themes relevant to the user's career question. Examine supplied 4th, 5th, and 9th-house factors and timing periods when available; do not infer qualifications or guarantee admission or employment.",
    ),
    PromptTool(
        "workplace_dynamics",
        "workplace_growth",
        "Explore chart-supported themes in workplace routines, service, colleagues, and professional relationships. Focus on relevant 6th- and 10th-house factors and supplied periods; avoid diagnosing coworkers or presenting symbolic tendencies as facts about real people.",
    ),
    PromptTool(
        "leadership_style",
        "workplace_growth",
        "Assess leadership, visibility, and decision-making tendencies from the supplied career indicators, planetary condition, and D10 if present. Present strengths with possible blind spots and do not claim authority or promotion is inevitable.",
    ),
    PromptTool(
        "career_stability",
        "workplace_growth",
        "Review indicators of professional continuity, workload pressure, and resilience across the chart and active periods. Separate temporary timing themes from enduring chart factors, use only available data, and offer more than one plausible interpretation when indicators conflict.",
    ),
)