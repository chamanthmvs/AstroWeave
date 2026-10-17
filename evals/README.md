# AstroWeave reading eval

Measures whether the reading pipeline is **honest and grounded**: every claim tied
to a real chart factor, dates taken from the chart data, limits stated plainly, no
sugar-coating, and the right methodology. Built with the Claude API `build-eval`
method. **Not yet run** (needs API balance).

## What's here

- `.claude/hillclimb/astrology-reading/cases.json` — 18 synthetic cases (reviewed and
  signed off), across all five specialists plus honesty/ethics traps. `cases.md` is the
  human-readable view.
- `.claude/hillclimb/astrology-reading/_state.json` — the metrics the report draws
  (`pass` is the headline) and the per-model prices.
- `evals/run_eval.py` — runs each case through the real orchestrator graph and grades it.

## Grading

- **Deterministic (free, tested in `tests/unit/test_eval_checks.py`):** every ISO date in
  the answer must exist in the chart data (no invented dates); no bare "confidence: medium"
  label; the answer cites concrete chart factors (houses, planets, dasha, …).
- **LLM judge (Opus 5.5, paid):** scores `grounded`, `honest_limits`, `no_sugarcoating`,
  `directly_answers`, `follows_method`, reading the chart data as ground truth.
- `pass` = all judge metrics AND all deterministic checks.

## Running it (costs API credit)

1. Put credit on the `ANTHROPIC_API_KEY` in `.env.development`.
2. Start a chart service and point the runner at it:
   ```bash
   cd chart_service && ./.venv/bin/uvicorn main:app --port 8109 &
   export ASTROWEAVE_CHART_SERVICE_URL=http://127.0.0.1:8109
   ```
3. Pilot a few cases first (recommended before the full run):
   ```bash
   .venv/bin/python evals/run_eval.py --variant baseline --model claude-sonnet-5-5 \
       --ids ethics-death,love-spouse-appearance,career-promotion-timing
   ```
   Read `.claude/hillclimb/astrology-reading/baseline/summary.md` and confirm the grades
   match your judgment (the grading sign-off). Then run the full set on both models:
   ```bash
   .venv/bin/python evals/run_eval.py --variant baseline --model claude-sonnet-5-5
   .venv/bin/python evals/run_eval.py --variant v1       --model claude-opus-5-5
   ```
4. Each variant writes `results.jsonl`, `traces/`, and `summary.md`. Compare `baseline`
   (Sonnet 5.5) vs `v1` (Opus 5.5) to settle the model choice with data.

Estimated cost (pre-run): ~$5–10 for the full 18×2 comparison; confirm from the pilot's
real token usage before the full run.
