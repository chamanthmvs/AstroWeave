import unittest

from astroweave.common.numerology import (
    birthday_number,
    build_numerology,
    expression,
    life_path,
    personality,
    soul_urge,
)


class NumerologyTests(unittest.TestCase):
    def test_life_path_reduces_components_then_sums(self):
        # 1990-01-01: year 1+9+9+0=19->1, month 1, day 1 -> 1+1+1 = 3.
        self.assertEqual(life_path("1990-01-01"), 3)
        # 2000-12-25: year 2, month 12->3, day 25->7 -> 12 -> 3.
        self.assertEqual(life_path("2000-12-25"), 3)

    def test_master_numbers_are_preserved(self):
        self.assertEqual(birthday_number("1990-01-29"), 11)  # 29 -> 11, kept

    def test_name_numbers_follow_pythagorean_values(self):
        # JOHN: J=1 O=6 H=8 N=5 = 20 -> 2
        self.assertEqual(expression("John"), 2)
        # vowels: O=6 -> 6
        self.assertEqual(soul_urge("John"), 6)
        # consonants: J=1 H=8 N=5 = 14 -> 5
        self.assertEqual(personality("John"), 5)

    def test_build_includes_core_numbers_and_meanings(self):
        result = build_numerology("Maya Patel", "1990-01-01")
        self.assertEqual(result["method"], "Pythagorean")
        nums = result["numbers"]
        for key in ("life_path", "birthday", "expression", "soul_urge", "personality"):
            self.assertIn(key, nums)
            self.assertTrue(nums[key]["meaning"])
            self.assertTrue(nums[key]["about"])

    def test_name_numbers_omitted_when_no_letters(self):
        nums = build_numerology("", "1990-01-01")["numbers"]
        self.assertIn("life_path", nums)
        self.assertNotIn("expression", nums)


if __name__ == "__main__":
    unittest.main()
