"""Validation tests for Kundli matching (run with the chart_service venv):

    cd chart_service && ./.venv/bin/python -m pytest test_match.py -q
    # or: ./.venv/bin/python test_match.py

These hold PyJHora's Ashtakoota engine to classical rules across ALL 27x27
nakshatra pairs for the decisive, hand-derivable kootas - Nadi, Gana (same-gana),
and for South: Mahendra, Vedha, Rajju, Stree-Dheerga - plus an end-to-end
/match computation. If a PyJHora upgrade changes any rule, these fail.
"""

import unittest

from jhora.horoscope.match.compatibility import Ashtakoota

import main  # noqa: E402  (chart service app module)

# --- classical reference rules, encoded independently ---------------------
AADI = {1, 6, 7, 12, 13, 18, 19, 24, 25}
MADHYA = {2, 5, 8, 11, 14, 17, 20, 23, 26}
def classical_nadi(n): return "Aadi" if n in AADI else ("Madhya" if n in MADHYA else "Antya")

DEVA = {1, 5, 7, 8, 13, 15, 17, 22, 27}
MANUSHYA = {2, 4, 6, 11, 12, 20, 21, 25, 26}
def classical_gana(n): return "Deva" if n in DEVA else ("Manushya" if n in MANUSHYA else "Rakshasa")

# Standard 5-rajju (Shiro/Kantha/Udara/Kati/Paada) grouping.
RAJJU_GROUPS = [
    {5, 14, 23}, {4, 6, 13, 15, 22, 24}, {3, 7, 12, 16, 21, 25},
    {2, 8, 11, 17, 20, 26}, {1, 9, 10, 18, 19, 27},
]
def same_rajju(b, g): return any(b in grp and g in grp for grp in RAJJU_GROUPS)

# South rajju adds aarohana (ascending) / avarohana (descending) direction:
# a pair in the same limb still matches when one ascends and the other descends.
# (neck aaroga is 4,13,22 - the value PyJHora's typo corrupts to 413,22.)
AAROHANA = {1, 10, 19, 4, 13, 22, 2, 11, 20, 3, 12, 21}
def south_rajju_match(b, g):
    if (b in AAROHANA) != (g in AAROHANA):
        return True
    return not same_rajju(b, g)

MAHENDRA_SET = {4, 7, 10, 13, 16, 19, 22, 25}
VEDHA_SUMS = {19, 28, 37}
SOUTH_STREE_THRESHOLD = 7  # classical Tamil Streedheerga: count from girl > 7
def count_from_girl(b, g): return ((b + 27 - g) % 27) + 1


def north(b, g):
    return Ashtakoota(b, 1, g, 1, method="North").compatibility_score()


def south(b, g):
    return Ashtakoota(b, 1, g, 1, method="South").compatibility_score()


class NorthKootaRules(unittest.TestCase):
    def test_nadi_is_zero_exactly_when_same_nadi(self):
        for b in range(1, 28):
            for g in range(1, 28):
                nadi_score = north(b, g)[7]
                self.assertEqual(
                    nadi_score == 0, classical_nadi(b) == classical_nadi(g),
                    f"nadi mismatch b={b} g={g}: score={nadi_score}, nadis {classical_nadi(b)}/{classical_nadi(g)}",
                )

    def test_same_gana_scores_full_six(self):
        for b in range(1, 28):
            for g in range(1, 28):
                if classical_gana(b) == classical_gana(g):
                    self.assertEqual(north(b, g)[2], 6, f"same-gana should be 6 at b={b} g={g}")

    def test_total_is_sum_of_eight_kootas_within_36(self):
        row = north(1, 2)
        self.assertAlmostEqual(row[8], sum(row[:8]))
        self.assertTrue(0 <= row[8] <= 36)


class SouthPoruthamRules(unittest.TestCase):
    def test_mahendra_matches_count_rule(self):
        for b in range(1, 28):
            for g in range(1, 28):
                self.assertEqual(south(b, g)[9], count_from_girl(b, g) in MAHENDRA_SET, f"mahendra b={b} g={g}")

    def test_vedha_fails_exactly_on_classical_sums(self):
        for b in range(1, 28):
            for g in range(1, 28):
                self.assertEqual(south(b, g)[10], (b + g) not in VEDHA_SUMS, f"vedha b={b} g={g}")

    def test_south_rajju_respects_aarohana_avarohana(self):
        for b in range(1, 28):
            for g in range(1, 28):
                self.assertEqual(south(b, g)[11], south_rajju_match(b, g), f"south rajju b={b} g={g}")

    def test_rohini_hasta_neck_typo_is_corrected(self):
        # Regression for PyJHora's neck_aaroga [413,22] typo: Rohini(4)/Hasta(13)
        # are ascending, so against descending neck stars (6,15,24) it must MATCH.
        for ascending in (4, 13):
            for descending in (6, 15, 24):
                self.assertTrue(south(ascending, descending)[11], f"expected match {ascending}-{descending}")

    def test_stree_dheerga_south_uses_count_over_7(self):
        for b in range(1, 28):
            for g in range(1, 28):
                self.assertEqual(south(b, g)[12], count_from_girl(b, g) > SOUTH_STREE_THRESHOLD, f"stree b={b} g={g}")


class MatchEndpoint(unittest.TestCase):
    PERSON = main.MatchBirth(date="1990-01-01", time="12:00:00", latitude=13.08, longitude=80.27, utc_offset_hours=5.5, place_name="Chennai")
    PARTNER = main.MatchBirth(date="1992-05-20", time="08:30:00", latitude=19.08, longitude=72.88, utc_offset_hours=5.5, place_name="Mumbai")

    def test_match_result_is_well_formed(self):
        result = main.compute_match(main.MatchRequest(person=self.PERSON, partner=self.PARTNER))
        self.assertEqual([k["koota"] for k in result["north"]["kootas"]],
                         ["Varna", "Vasya", "Gana", "Tara", "Yoni", "Graha Maitri", "Bhakoot", "Nadi"])
        self.assertTrue(0 <= result["north"]["total"] <= 36)
        self.assertEqual(result["north"]["total"], sum(k["score"] for k in result["north"]["kootas"]))
        self.assertEqual(len(result["south"]["poruthams"]), 10)
        self.assertTrue(0 <= result["south"]["matched_count"] <= 10)
        for side in ("person", "partner"):
            for key in ("rasi", "nakshatra", "pada", "lagna"):
                self.assertIn(key, result[side])
        self.assertIn("both_manglik", result["manglik"])

    def test_role_swap_changes_groom_and_bride(self):
        a = main.compute_match(main.MatchRequest(person=self.PERSON, partner=self.PARTNER, person_is_groom=True))
        b = main.compute_match(main.MatchRequest(person=self.PERSON, partner=self.PARTNER, person_is_groom=False))
        self.assertEqual(a["roles"], {"groom": "person", "bride": "partner"})
        self.assertEqual(b["roles"], {"groom": "partner", "bride": "person"})
        # Asymmetric kootas mean the score can differ by role (sanity: both valid).
        self.assertTrue(0 <= a["north"]["total"] <= 36 and 0 <= b["north"]["total"] <= 36)


if __name__ == "__main__":
    unittest.main(verbosity=2)
