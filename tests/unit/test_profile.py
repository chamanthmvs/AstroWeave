import json
import unittest
from pathlib import Path

from astroweave.common.astro import build_profile
from astroweave.common.astro.profile_reference import gana_of, nadi_of

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "chart_1990-01-01_chennai.json"
CHART = json.loads(_FIXTURE.read_text())


class ReferenceTableTests(unittest.TestCase):
    def test_gana_and_nadi_cover_all_27_and_match_classical(self):
        self.assertEqual(gana_of(1), "Deva")       # Ashwini
        self.assertEqual(gana_of(23), "Rakshasa")  # Dhanishta
        self.assertEqual(nadi_of(1), "Vata")
        self.assertEqual(nadi_of(23), "Pitta")
        self.assertEqual({gana_of(n) for n in range(1, 28)}, {"Deva", "Manushya", "Rakshasa"})
        self.assertEqual({nadi_of(n) for n in range(1, 28)}, {"Vata", "Pitta", "Kapha"})


class BuildProfileTests(unittest.TestCase):
    def setUp(self):
        self.p = build_profile(CHART)

    def test_summary_matches_the_fixture_chart(self):
        # Fixture: Moon Aquarius 6.47 -> Dhanishta pada 4; Lagna Pisces.
        self.assertEqual(self.p["summary"], {
            "rasi": "Aquarius", "nakshatra": "Dhanishta (pada 4)", "lagna": "Pisces"})

    def test_nakshatra_attributes_are_canonical(self):
        nak = self.p["nakshatra"]
        self.assertEqual(nak["ruling_planet"], "Mars")
        self.assertEqual(nak["gana"], "Rakshasa")
        self.assertEqual(nak["nadi"], "Pitta")
        self.assertEqual(nak["yoni"], "Lion")
        self.assertEqual(nak["deity"], "The Vasus")

    def test_rasi_and_lagna_elements(self):
        self.assertEqual((self.p["rasi"]["element"], self.p["rasi"]["varna"]), ("air", "Shudra"))
        self.assertEqual(self.p["lagna"], {"sign": "Pisces", "lord": "Jupiter", "element": "water", "modality": "dual"})

    def test_plain_language_and_caveat_present(self):
        self.assertTrue(self.p["in_simple_terms"])
        self.assertTrue(all(isinstance(line, str) and line for line in self.p["in_simple_terms"]))
        self.assertIn("birth chart", self.p["note"])
        # Every plain-language line is grounded in a real attribute (no empty templating).
        self.assertTrue(any("Dhanishta" in line for line in self.p["in_simple_terms"]))

    def test_missing_moon_is_reported_not_guessed(self):
        self.assertIn("unavailable", build_profile({"d1": {"ascendant": {"sign": "Pisces"}}}))
        self.assertIn("unavailable", build_profile(None))


if __name__ == "__main__":
    unittest.main()
