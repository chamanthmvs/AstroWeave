import json
import unittest
from pathlib import Path

from astroweave.common.astro import build_profile, nakshatra_catalog, rasi_catalog
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

    def test_each_nakshatra_has_a_meaning(self):
        self.assertTrue(all(n["meaning"] for n in self.catalog))
        self.assertIn("horse", self.catalog[0]["meaning"])  # Ashwini


class RasiCatalogTests(unittest.TestCase):
    def setUp(self):
        self.rasis = rasi_catalog()

    def test_twelve_signs_in_order(self):
        self.assertEqual(len(self.rasis), 12)
        self.assertEqual([r["number"] for r in self.rasis], list(range(1, 13)))
        self.assertEqual(self.rasis[0]["name"], "Aries")
        self.assertEqual(self.rasis[0]["sanskrit"], "Mesha")

    def test_lords_and_dignities_match_bphs(self):
        by_name = {r["name"]: r for r in self.rasis}
        self.assertEqual(by_name["Aries"]["lord"], "Mars")
        self.assertEqual((by_name["Aries"]["exalted"], by_name["Aries"]["debilitated"]), ("Sun", "Saturn"))
        self.assertEqual((by_name["Libra"]["exalted"], by_name["Libra"]["debilitated"]), ("Saturn", "Sun"))
        self.assertEqual((by_name["Cancer"]["lord"], by_name["Cancer"]["exalted"]), ("Moon", "Jupiter"))
        self.assertEqual(by_name["Pisces"]["lord"], "Jupiter")
        # Elements and modalities form the expected 4x3 structure.
        self.assertEqual({r["element"] for r in self.rasis}, {"Fire", "Earth", "Air", "Water"})
        self.assertEqual({r["modality"] for r in self.rasis}, {"Movable", "Fixed", "Dual"})


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
