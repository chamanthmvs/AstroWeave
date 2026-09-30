"""Prompt-only analysis tools for finance intents."""

from astroweave.common.tools import PromptTool

FINANCE_TOOLS = (
    PromptTool(
        "income_capacity",
        "income_building",
        "Interpret earning and resource-building themes from supplied chart data. Focus on the 2nd, 10th, and 11th houses, their lords, and relevant periods; distinguish capacity from realized income and never invent placements or promise wealth.",
    ),
    PromptTool(
        "savings_pattern",
        "income_building",
        "Assess chart-supported themes around retaining resources, spending pressure, and gradual accumulation, using the 2nd and 11th houses and relevant periods when available. Keep the reading nonjudgmental and do not present astrology as a substitute for budgeting advice.",
    ),
    PromptTool(
        "multiple_income",
        "income_building",
        "Review indications for varied income sources or gains through professional, independent, or network-related activity. Connect relevant houses and lords only when present in the supplied chart; describe possibilities rather than asserting a specific source or amount.",
    ),
    PromptTool(
        "investment_risk_themes",
        "investing_assets",
        "Describe symbolic chart themes around patience, volatility tolerance, and decision discipline using supplied planetary and house data. Do not recommend securities, trades, allocations, or risk levels; explicitly separate astrological reflection from regulated financial advice.",
    ),
    PromptTool(
        "asset_accumulation",
        "investing_assets",
        "Interpret broad themes related to building and preserving assets using the 2nd, 4th, 8th, and 11th houses when supported by the chart. Avoid naming specific products or promising returns, and note when relevant divisional or timing data is unavailable.",
    ),
    PromptTool(
        "property_finances",
        "investing_assets",
        "Assess astrological themes relevant to property and long-term material commitments, especially supplied 4th-house, 2nd-house, and period indicators. Do not tell the user to buy, sell, borrow, or transact; recommend independent practical evaluation for real decisions.",
    ),
    PromptTool(
        "debt_pressure",
        "debt_and_risk",
        "Review chart indicators associated with obligations, borrowing pressure, and repayment discipline using relevant supplied houses, lords, and periods. Do not infer actual debt or shame the user; frame the reading as reflective and avoid financial instructions.",
    ),
    PromptTool(
        "financial_volatility",
        "debt_and_risk",
        "Identify chart-supported periods that may symbolically correspond with financial uncertainty or changing resources. Balance challenging and supportive indicators, avoid catastrophic language, and never state that a loss is certain.",
    ),
    PromptTool(
        "financial_resilience",
        "debt_and_risk",
        "Assess themes of recovery, resourcefulness, and rebuilding after a financial setback from the supplied chart. Separate symbolic interpretation from the user's real circumstances and point out missing data rather than filling gaps with assumptions.",
    ),
    PromptTool(
        "wealth_periods",
        "financial_timing",
        "Interpret broad financial opportunity periods from the supplied dasha/bhukti, KP significators, or other stated timing method. Explain the evidence and uncertainty; do not fabricate dates, promise gains, or imply that timing overrides practical risk assessment.",
    ),
    PromptTool(
        "financial_decision_window",
        "financial_timing",
        "Compare broad periods for research, caution, or reassessment using only timing factors actually present in the chart. Do not make a transaction recommendation or claim a uniquely correct date; provide a measured astrological perspective, not financial advice.",
    ),
    PromptTool(
        "financial_cycles",
        "financial_timing",
        "Synthesize longer-term cycles affecting earning, expenditure, and asset themes from the chart and supplied periods. Separate natal tendencies from temporary activation, include mixed signals, and avoid deterministic claims about wealth or loss.",
    ),
)