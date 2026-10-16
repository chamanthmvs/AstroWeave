import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from astroweave.common.ratelimit import RateLimiter

PER_USER = "ASTROWEAVE_RATE_LIMIT_PER_DAY"
GLOBAL = "ASTROWEAVE_RATE_LIMIT_GLOBAL_PER_DAY"


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.limiter = RateLimiter(Path(self._dir.name) / "rl.db")

    def test_per_user_cap_blocks_the_run_over_the_limit(self):
        with patch.dict(os.environ, {PER_USER: "2", GLOBAL: "0"}):
            self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)
            self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)
            blocked = self.limiter.check_and_consume("a@x.com")
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.scope, "user")
        self.assertEqual((blocked.limit, blocked.used), (2, 2))
        self.assertGreater(blocked.retry_after_seconds, 0)

    def test_per_user_cap_is_isolated_between_users(self):
        with patch.dict(os.environ, {PER_USER: "1", GLOBAL: "0"}):
            self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)
            self.assertFalse(self.limiter.check_and_consume("a@x.com").allowed)
            self.assertTrue(self.limiter.check_and_consume("b@x.com").allowed)

    def test_global_cap_blocks_across_all_users(self):
        with patch.dict(os.environ, {PER_USER: "0", GLOBAL: "2"}):
            self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)
            self.assertTrue(self.limiter.check_and_consume("b@x.com").allowed)
            blocked = self.limiter.check_and_consume("c@x.com")
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.scope, "global")

    def test_disabled_when_both_caps_are_zero(self):
        with patch.dict(os.environ, {PER_USER: "0", GLOBAL: "0"}):
            for _ in range(100):
                self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)
            self.assertEqual(self.limiter.usage_today("a@x.com")["user"]["used"], 0)

    def test_budget_resets_on_the_next_utc_day(self):
        day1 = datetime(2026, 10, 16, 23, 0, tzinfo=timezone.utc)
        day2 = datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)
        with patch.dict(os.environ, {PER_USER: "1", GLOBAL: "0"}):
            with patch("astroweave.common.ratelimit.limiter._utc_now", return_value=day1):
                self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)
                self.assertFalse(self.limiter.check_and_consume("a@x.com").allowed)
            with patch("astroweave.common.ratelimit.limiter._utc_now", return_value=day2):
                self.assertTrue(self.limiter.check_and_consume("a@x.com").allowed)

    def test_usage_today_reports_remaining_quota(self):
        with patch.dict(os.environ, {PER_USER: "5", GLOBAL: "0"}):
            self.limiter.check_and_consume("a@x.com")
            self.limiter.check_and_consume("a@x.com")
            usage = self.limiter.usage_today("a@x.com")
        self.assertEqual(usage["user"], {"used": 2, "limit": 5, "remaining": 3})
        self.assertIsNone(usage["global"]["limit"])
        self.assertGreater(usage["resets_in_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
