"""Free (no-API) tests for the eval runner's deterministic honesty checks.

The LLM-judge part of the eval needs paid calls, but the deterministic checks -
no invented dates, no leaked confidence label, cites concrete chart factors -
can and should be verified for free so the grader's objective half can't rot.
"""

import importlib.util
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "evals" / "run_eval.py"
_spec = importlib.util.spec_from_file_location("run_eval", _PATH)
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

# A chart whose data contains one real dasha date.
CHART = {"dasha_bhukti": [{"start_date": "2026-09-19"}], "current_dasha": {"maha_start": "2024-02-09"}}


class DeterministicCheckTests(unittest.TestCase):
    def test_fabricated_date_is_flagged(self):
        answer = "A promotion is likely between 2026-09-19 and 2030-01-01."  # 2nd date invented
        checks = run_eval._deterministic_checks(answer, CHART)
        self.assertEqual(checks["dates_ok"], 0)
        self.assertEqual(checks["_fabricated_dates"], ["2030-01-01"])

    def test_dates_present_in_chart_pass(self):
        answer = "The window is 2026-09-19 onward; your current period began 2024-02-09."
        self.assertEqual(run_eval._deterministic_checks(answer, CHART)["dates_ok"], 1)

    def test_answer_with_no_dates_passes_the_date_check(self):
        self.assertEqual(run_eval._deterministic_checks("No specific timing is indicated.", CHART)["dates_ok"], 1)

    def test_confidence_label_leak_is_flagged(self):
        for leak in ["Confidence is medium.", "confidence: high", "Confidence level: low"]:
            self.assertEqual(run_eval._deterministic_checks(leak, CHART)["no_label_leak"], 0, leak)
        self.assertEqual(run_eval._deterministic_checks("I'm fairly sure about this.", CHART)["no_label_leak"], 1)

    def test_cites_concrete_chart_factors(self):
        self.assertEqual(run_eval._deterministic_checks("Your 10th house lord Jupiter is strong.", CHART)["cites_factors"], 1)
        self.assertEqual(run_eval._deterministic_checks("Saturn aspects the ascendant.", CHART)["cites_factors"], 1)
        self.assertEqual(run_eval._deterministic_checks("Good things are coming your way soon.", CHART)["cites_factors"], 0)

    def test_metrics_and_cases_are_consistent(self):
        import json
        flow = Path(__file__).resolve().parents[2] / ".claude" / "hillclimb" / "astrology-reading"
        cases = json.loads((flow / "cases.json").read_text())
        self.assertGreaterEqual(len(cases), 15)  # guide's floor for a first eval
        for case in cases:
            self.assertEqual({"id", "tags", "methodology", "birth", "question", "must", "must_not", "notes"}, set(case))
        state = json.loads((flow / "_state.json").read_text())
        self.assertEqual(state["metrics"][0]["id"], "pass")  # headline metric is first


if __name__ == "__main__":
    unittest.main()
