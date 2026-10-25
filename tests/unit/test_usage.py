import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from astroweave.common.usage import (
    PRICING,
    UsageStore,
    aggregate_by_model,
    cost_usd,
    usage_from_response,
)


class CostTests(unittest.TestCase):
    def test_cost_uses_the_per_model_price_table(self):
        # Opus 5.5: $4 / $20 / $0.20 per million (input / output / cache read).
        self.assertAlmostEqual(cost_usd("claude-opus-5-5", 1_000_000, 500_000, 0), 14.0)
        self.assertAlmostEqual(cost_usd("claude-opus-5-5", 0, 0, 1_000_000), 0.20)
        # Sonnet 5.5 is half the Opus input/output price.
        self.assertAlmostEqual(cost_usd("claude-sonnet-5-5", 1_000_000, 1_000_000, 0), 12.0)

    def test_unknown_model_costs_zero_but_is_still_recorded(self):
        self.assertEqual(cost_usd("openai/gpt-oss-120b", 1_000_000, 1_000_000, 0), 0.0)
        self.assertNotIn("openai/gpt-oss-120b", PRICING)


class UsageExtractionTests(unittest.TestCase):
    def test_reads_claude_adapter_metadata(self):
        response = SimpleNamespace(response_metadata={
            "model": "claude-opus-5-5", "input_tokens": 1200,
            "output_tokens": 800, "cache_read_input_tokens": 400,
        })
        self.assertEqual(usage_from_response(response), {
            "model": "claude-opus-5-5", "input_tokens": 1200,
            "output_tokens": 800, "cache_read_tokens": 400,
        })

    def test_reads_langchain_usage_metadata(self):
        response = SimpleNamespace(
            response_metadata={"model_name": "openai/gpt-oss-120b"},
            usage_metadata={"input_tokens": 500, "output_tokens": 300, "input_token_details": {"cache_read": 100}},
        )
        self.assertEqual(usage_from_response(response), {
            "model": "openai/gpt-oss-120b", "input_tokens": 500,
            "output_tokens": 300, "cache_read_tokens": 100,
        })

    def test_returns_none_when_no_usage_reported(self):
        self.assertIsNone(usage_from_response(SimpleNamespace(response_metadata={})))


class UsageStoreTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.store = UsageStore(Path(self._dir.name) / "usage.db")

    def test_aggregate_sums_repeated_model_calls(self):
        usages = [
            {"model": "claude-opus-5-5", "input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 0},
            {"model": "claude-opus-5-5", "input_tokens": 200, "output_tokens": 70, "cache_read_tokens": 10},
            {"model": "claude-sonnet-5-5", "input_tokens": 40, "output_tokens": 10, "cache_read_tokens": 0},
        ]
        self.assertEqual(aggregate_by_model(usages), {
            "claude-opus-5-5": {"input_tokens": 300, "output_tokens": 120, "cache_read_tokens": 10},
            "claude-sonnet-5-5": {"input_tokens": 40, "output_tokens": 10, "cache_read_tokens": 0},
        })

    def test_record_run_writes_one_row_per_model_and_returns_cost(self):
        cost = self.store.record_run("a@x.com", "conv-1", "msg-1", [
            {"model": "claude-opus-5-5", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0},
            {"model": "claude-opus-5-5", "input_tokens": 0, "output_tokens": 1_000_000, "cache_read_tokens": 0},
            {"model": "claude-sonnet-5-5", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0},
        ])
        self.assertAlmostEqual(cost, 4.0 + 20.0 + 2.0)
        totals = self.store.totals_by_user()
        self.assertEqual(len(totals), 1)
        self.assertEqual(totals[0]["owner"], "a@x.com")
        self.assertEqual(totals[0]["runs"], 1)  # one run, despite two models
        self.assertEqual(totals[0]["input_tokens"], 2_000_000)
        self.assertAlmostEqual(totals[0]["cost_usd"], 26.0)

    def test_empty_usage_is_a_no_op(self):
        self.assertEqual(self.store.record_run("a@x.com", "c", "m", []), 0.0)
        self.assertEqual(self.store.totals_by_user(), [])

    def test_summary_aggregates_overall_by_user_day_and_model(self):
        self.store.record_run("a@x.com", "c", "m1", [
            {"model": "claude-opus-5-5", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0},
            {"model": "claude-sonnet-5-5", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0},
        ])
        self.store.record_run("b@x.com", "c", "m2", [
            {"model": "claude-opus-5-5", "input_tokens": 0, "output_tokens": 1_000_000, "cache_read_tokens": 0},
        ])
        summary = self.store.summary()

        self.assertEqual(summary["overall"]["users"], 2)
        self.assertEqual(summary["overall"]["runs"], 2)
        self.assertEqual(summary["overall"]["tokens"], 3_000_000)
        self.assertAlmostEqual(summary["overall"]["cost_usd"], 4.0 + 2.0 + 20.0)
        self.assertEqual({m["model"] for m in summary["by_model"]}, {"claude-opus-5-5", "claude-sonnet-5-5"})
        self.assertEqual(len(summary["by_day"]), 1)  # all rows recorded today
        self.assertAlmostEqual(summary["by_day"][0]["cost_usd"], 26.0)
        self.assertEqual(summary["by_user"][0]["owner"], "b@x.com")  # $20 > $6, ranked first

    def test_user_cost_summary_windows(self):
        # Two runs today for one user.
        self.store.record_run("a@x.com", "c", "m1",
                              [{"model": "claude-opus-5-5", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0}])
        self.store.record_run("a@x.com", "c", "m2",
                              [{"model": "claude-sonnet-5-5", "input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0}])
        summary = self.store.user_cost_summary("a@x.com")
        self.assertEqual(summary["currency"], "USD")
        self.assertTrue(summary["estimated"])
        self.assertEqual(summary["today"]["runs"], 2)
        self.assertAlmostEqual(summary["today"]["cost_usd"], 4.0 + 2.0)
        self.assertEqual(summary["yesterday"]["runs"], 0)
        # Windows include today, so they match today's totals here.
        self.assertAlmostEqual(summary["last_7_days"]["cost_usd"], 6.0)
        self.assertAlmostEqual(summary["total"]["cost_usd"], 6.0)
        self.assertEqual(summary["total"]["runs"], 2)
        # A different user sees nothing.
        self.assertEqual(self.store.user_cost_summary("b@x.com")["total"], {"runs": 0, "cost_usd": 0.0})

    def test_totals_rank_users_by_cost(self):
        self.store.record_run("cheap@x.com", "c", "m1",
                              [{"model": "claude-sonnet-5-5", "input_tokens": 1000, "output_tokens": 1000, "cache_read_tokens": 0}])
        self.store.record_run("spender@x.com", "c", "m2",
                              [{"model": "claude-opus-5-5", "input_tokens": 1_000_000, "output_tokens": 1_000_000, "cache_read_tokens": 0}])
        owners = [row["owner"] for row in self.store.totals_by_user()]
        self.assertEqual(owners, ["spender@x.com", "cheap@x.com"])


if __name__ == "__main__":
    unittest.main()
