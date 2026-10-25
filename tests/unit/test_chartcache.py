import tempfile
import time
import unittest
from pathlib import Path

from astroweave.common.chartcache import CHART_VERSION, ChartCache


class ChartCacheTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.cache = ChartCache(Path(self._dir.name) / "cache.db")

    def test_put_then_get_round_trips(self):
        payload = {"d1": {"ascendant": {"sign": "Pisces"}}, "shadbala": {"Sun": 1}}
        self.cache.put("a@x.com", "full", "hash1", payload)
        self.assertEqual(self.cache.get("a@x.com", "full", "hash1", None), payload)

    def test_miss_on_different_birth_hash(self):
        self.cache.put("a@x.com", "light", "hash1", {"d1": {}})
        self.assertIsNone(self.cache.get("a@x.com", "light", "hash2", None))

    def test_miss_on_unknown_owner_or_variant(self):
        self.cache.put("a@x.com", "light", "h", {"d1": {}})
        self.assertIsNone(self.cache.get("b@x.com", "light", "h", None))
        self.assertIsNone(self.cache.get("a@x.com", "full", "h", None))

    def test_ttl_expiry(self):
        self.cache.put("a@x.com", "full", "h", {"d1": {}})
        self.assertIsNotNone(self.cache.get("a@x.com", "full", "h", 3600))  # fresh
        self.assertIsNone(self.cache.get("a@x.com", "full", "h", -1))       # treat as expired

    def test_put_overwrites(self):
        self.cache.put("a@x.com", "light", "h", {"v": 1})
        self.cache.put("a@x.com", "light", "h", {"v": 2})
        self.assertEqual(self.cache.get("a@x.com", "light", "h", None)["v"], 2)

    def test_version_mismatch_is_a_miss(self):
        self.cache.put("a@x.com", "light", "h", {"d1": {}})
        # Simulate an old row by writing a different version directly.
        from sqlalchemy import text
        with self.cache._engine.begin() as conn:
            conn.execute(text("UPDATE user_charts SET chart_version = :v"), {"v": CHART_VERSION + 1})
        self.assertIsNone(self.cache.get("a@x.com", "light", "h", None))


if __name__ == "__main__":
    unittest.main()
