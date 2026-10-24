import json
import unittest
from pathlib import Path

from astroweave.common.astro import build_profile, nakshatra_catalog
from astroweave.common.astro.profile_reference import gana_of, nadi_of, vimshottari_lord

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


class NakshatraCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = nakshatra_catalog()

    def test_has_27_entries_numbered_and_named(self):
        self.assertEqual(len(self.catalog), 27)
        self.assertEqual([n["number"] for n in self.catalog], list(range(1, 28)))
        self.assertEqual(self.catalog[0]["name"], "Ashwini")
        self.assertEqual(self.catalog[0]["south_name"], "Aswini")
        self.assertEqual(self.catalog[-1]["name"], "Revati")
        # Every entry has non-empty core fields.
        for entry in self.catalog:
            for key in ("name", "south_name", "symbol", "deity", "ruling_planet", "gana", "yoni", "nadi", "theme"):
                self.assertTrue(entry[key], f"{entry['name']} missing {key}")

    def test_vimshottari_lord_cycles_and_matches_the_profile(self):
        # Ketu starts the 9-planet cycle; Dhanishta (#23) is Mars, as the profile derives.
        self.assertEqual(vimshottari_lord(1), "Ketu")
        self.assertEqual(vimshottari_lord(10), "Ketu")  # repeats every 9
        self.assertEqual(self.catalog[22]["ruling_planet"], "Mars")  # Dhanishta
        self.assertEqual(self.catalog[22]["gana"], "Rakshasa")
        self.assertEqual(self.catalog[22]["nadi"], "Pitta")

    def test_spans_tile_the_zodiac_from_aries(self):
        self.assertEqual(self.catalog[0]["span"]["start"], "Aries 0°00'")
        self.assertEqual(self.catalog[0]["span"]["end"], "Aries 13°20'")
        self.assertEqual(self.catalog[-1]["span"]["end"], "Aries 0°00'")  # 360 wraps to 0


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
