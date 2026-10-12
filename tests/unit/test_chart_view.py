import json
import unittest
from pathlib import Path

from astroweave.common.astro import build_chart_view, dignity
from astroweave.common.astro.reference import SIGN_INDEX

# Real chart-service output (Lahiri / KP ayanamsa) for 1990-01-01 12:00 IST, Chennai.
# The expected facts below were checked by hand against classical rules.
_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "chart_1990-01-01_chennai.json"
CHART = json.loads(_FIXTURE.read_text())


def _planet(view, name):
    return next(row for row in view["planets"] if row["planet"] == name)


class DignityTests(unittest.TestCase):
    def test_exaltation_debilitation_and_own_sign(self):
        self.assertEqual(dignity("Sun", SIGN_INDEX["Aries"], 10.0), "exalted")
        self.assertEqual(dignity("Sun", SIGN_INDEX["Libra"], 10.0), "debilitated")
        self.assertEqual(dignity("Mars", SIGN_INDEX["Scorpio"], 16.0), "own sign")

    def test_moolatrikona_respects_degree_ranges(self):
        self.assertEqual(dignity("Moon", SIGN_INDEX["Taurus"], 2.0), "exalted")
        self.assertEqual(dignity("Moon", SIGN_INDEX["Taurus"], 10.0), "moolatrikona")
        self.assertEqual(dignity("Mercury", SIGN_INDEX["Virgo"], 10.0), "exalted")
        self.assertEqual(dignity("Mercury", SIGN_INDEX["Virgo"], 17.0), "moolatrikona")
        self.assertEqual(dignity("Mercury", SIGN_INDEX["Virgo"], 25.0), "own sign")
        self.assertEqual(dignity("Sun", SIGN_INDEX["Leo"], 25.0), "own sign")

    def test_natural_relationships_and_nodes(self):
        self.assertEqual(dignity("Jupiter", SIGN_INDEX["Gemini"], 11.0), "enemy sign")
        self.assertEqual(dignity("Venus", SIGN_INDEX["Capricorn"], 12.0), "friendly sign")
        self.assertEqual(dignity("Saturn", SIGN_INDEX["Sagittarius"], 22.0), "neutral sign")
        self.assertEqual(dignity("Rahu", SIGN_INDEX["Capricorn"]), "node (dispositor Saturn)")


class ChartViewTests(unittest.TestCase):
    def setUp(self):
        self.view = build_chart_view(CHART, "career", "both")

    def test_summary_identifies_lagna_moon_and_special_states(self):
        summary = self.view["summary"]
        self.assertEqual(summary["lagna"], "Pisces")
        self.assertEqual(summary["lagna_lord"], "Jupiter")
        self.assertEqual(summary["lagna_lord_house"], 4)
        self.assertEqual(summary["janma_nakshatra"], "Dhanishta pada 4 (lord Mars)")
        self.assertEqual(summary["retrograde"], ["Mercury", "Jupiter", "Venus"])
        self.assertEqual(summary["vargottama"], ["Mars", "Mercury"])

    def test_planet_houses_lordships_and_aspects(self):
        jupiter = _planet(self.view, "Jupiter")
        self.assertEqual(jupiter["house"], 4)
        self.assertEqual(jupiter["rules_houses"], [1, 10])
        self.assertEqual(jupiter["aspects_houses"], [8, 10, 12])
        self.assertEqual(jupiter["aspected_by"], ["Mars", "Saturn", "Sun"])
        self.assertEqual(_planet(self.view, "Moon")["aspected_by"], ["Jupiter", "Mars", "Saturn"])

    def test_combustion_uses_classical_orbs(self):
        # Saturn is 5 degrees from the Sun (orb 15): combust.
        self.assertTrue(_planet(self.view, "Saturn")["combust"])
        # Retrograde Mercury is 15.1 degrees away (orb 12): not combust.
        self.assertFalse(_planet(self.view, "Mercury")["combust"])
        self.assertNotIn("combust", _planet(self.view, "Rahu"))

    def test_house_table_cross_references_lords_and_bindus(self):
        tenth = self.view["houses"][9]
        self.assertEqual(tenth["sign"], "Sagittarius")
        self.assertEqual(tenth["occupants"], ["Sun", "Saturn"])
        self.assertEqual(tenth["lord_in_house"], 4)
        self.assertEqual(tenth["sarvashtakavarga_bindus"], 32)

    def test_kp_uses_placidus_cusps_and_four_level_significators(self):
        kp = self.view["kp"]
        mercury = next(p for p in kp["planets"] if p["planet"] == "Mercury")
        # Whole-sign 11th, but before the 11th cusp (Capricorn 10.9) so KP house 10.
        self.assertEqual(_planet(self.view, "Mercury")["house"], 11)
        self.assertEqual(mercury["kp_house"], 10)
        tenth = kp["house_significators"][9]
        self.assertEqual(tenth["b_occupants"], ["Sun", "Mercury", "Saturn"])
        self.assertEqual(tenth["a_in_star_of_occupants"], ["Mars", "Mercury", "Ketu"])
        self.assertEqual(tenth["d_owner"], "Jupiter")
        cusp10 = kp["cusps"][9]
        self.assertEqual(cusp10["sub_lord"], "Venus")
        self.assertEqual(cusp10["sub_lord_signifies"], {"via_star_lord": [5, 11], "own": [3, 8, 11]})
        rahu = next(p for p in kp["planets"] if p["planet"] == "Rahu")
        # Rahu occupies the 11th and also carries its dispositor Saturn's houses.
        self.assertEqual(rahu["signifies"]["own"], [10, 11, 12])

    def test_dasha_keeps_full_sequence_and_windows_antardashas(self):
        dasha = self.view["dasha"]
        self.assertEqual(
            [md["lord"] for md in dasha["mahadashas"]],
            ["Mars", "Rahu", "Jupiter", "Saturn", "Mercury", "Ketu", "Venus", "Sun", "Moon"],
        )
        self.assertEqual(
            {ad["mahadasha"] for ad in dasha["antardashas"]}, {"Jupiter", "Saturn", "Mercury"}
        )
        current = [md for md in dasha["mahadashas"] if md["status"] == "current"]
        self.assertEqual([md["lord"] for md in current], ["Saturn"])
        self.assertEqual(dasha["current"]["pratyantardasha_lord"], "Jupiter")

    def test_pratyantardashas_give_month_level_timing_within_a_stated_window(self):
        window = self.view["dasha"]["pratyantardashas"]
        self.assertTrue(window["covers"].endswith("2031-10-12"))
        periods = window["periods"]
        # Contiguous: each period ends exactly where the next begins.
        for earlier, later in zip(periods, periods[1:]):
            self.assertEqual(earlier["end"], later["start"])
        current = [p for p in periods if p["status"] == "current"]
        self.assertEqual(
            [(p["antardasha"], p["pratyantardasha"], p["start"], p["end"]) for p in current],
            [("Saturn", "Jupiter", "2026-09-19", "2027-02-12")],
        )
        # The next one starts where the current antardasha ends (Saturn-Mercury-Mercury).
        following = periods[periods.index(current[0]) + 1]
        self.assertEqual(
            (following["antardasha"], following["pratyantardasha"], following["start"], following["end"]),
            ("Mercury", "Mercury", "2027-02-12", "2027-07-01"),
        )
        # KP timing uses the antara level too.
        self.assertIn("pratyantardashas", build_chart_view(CHART, "love", "kp")["dasha"])

    def test_transits_are_read_from_lagna_and_moon(self):
        transits = self.view["transits"]
        saturn = next(p for p in transits["planets"] if p["planet"] == "Saturn")
        self.assertEqual((saturn["sign"], saturn["house_from_lagna"], saturn["house_from_moon"]), ("Pisces", 1, 2))
        self.assertEqual(transits["sade_sati"], {"active": True, "phase": "final phase (2nd from Moon)"})
        self.assertEqual(transits["double_transit_houses"], [1])

    def test_domain_selects_relevant_divisional_charts(self):
        self.assertEqual(list(self.view["divisional_charts"]), ["D9", "D10", "D24"])
        love = build_chart_view(CHART, "love", "vedic")
        self.assertEqual(list(love["divisional_charts"]), ["D9", "D7"])
        self.assertNotIn("D60", love["divisional_charts"])

    def test_element_and_modality_balance_for_whole_person_readings(self):
        # Lagna Pisces + Sun Sag, Moon Aqu, Mars Sco, Mercury Cap, Jupiter Gem, Venus Cap, Saturn Sag.
        summary = self.view["summary"]
        self.assertEqual(summary["element_balance"], {"fire": 2, "earth": 2, "air": 2, "water": 2})
        self.assertEqual(summary["modality_balance"], {"movable": 2, "fixed": 2, "dual": 4})

    def test_general_domain_gets_broad_divisional_charts(self):
        general = build_chart_view(CHART, "general", "vedic")
        self.assertEqual(
            list(general["divisional_charts"]), ["D9", "D3", "D4", "D7", "D10", "D12", "D24"]
        )

    def test_methodology_projection(self):
        vedic = build_chart_view(CHART, "career", "vedic")
        self.assertNotIn("kp", vedic)
        self.assertIn("divisional_charts", vedic)
        kp_only = build_chart_view(CHART, "career", "kp")
        self.assertIn("kp", kp_only)
        for parashari_only in ("divisional_charts", "yogas", "bhinna_ashtakavarga_by_house"):
            self.assertNotIn(parashari_only, kp_only)

    def test_view_never_changes_computed_values(self):
        raw = {p["planet"]: p for p in CHART["d1"]["planets"]}
        for row in self.view["planets"]:
            self.assertEqual(row["sign"], raw[row["planet"]]["sign"])
            self.assertAlmostEqual(row["degree"], raw[row["planet"]]["longitude_in_sign"], places=2)

    def test_missing_chart_is_reported_not_guessed(self):
        self.assertIn("unavailable", build_chart_view({"d1": {}}, "career", "both"))
        self.assertIn("unavailable", build_chart_view(None))


if __name__ == "__main__":
    unittest.main()
