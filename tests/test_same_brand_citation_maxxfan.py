"""Same-brand citation guard: MaxxFan 4501K must never cite Furrion/Coleman pages,
and a turn that retrieved the unit's own manual must not say 'No {brand} document'."""
import unittest

import gd_library_coach as g

M = "MaxxAir MaxxFan 4501K"
S = "remote won't turn fan on, controls at fan work"
FURRION = {"title": "Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990", "excerpt": "Fig 2 wall thermostat fan"}
COLEMAN = {"title": "Coleman-Mach Mechanical Controls Service Manual", "excerpt": "fan/low fan/high nothing happens"}
MAXX = {"title": "MaxxAir MAXXFAN / MAXXFAN Plus / Mini Installation Instructions and Operating Guide 11F90000K",
        "excerpt": "REMOTE CONTROL OPERATING GUIDE ... MODELS 4501K, 4541K", "brand": "MaxxAir"}
THET = {"title": "Thetford Style II OM Permanent RV Toilet 42088", "excerpt": "water valve pedal"}


class TestMaxxAirBrand(unittest.TestCase):
    def test_maxxfan_is_its_own_brand(self):
        self.assertEqual(g.asked_brands_for_lookup("", M, S), {"maxxair"})
        self.assertEqual(g.library_miss_brand_label("", M, S), "MaxxAir")

    def test_airxcel_on_maxxair_page_is_not_coleman(self):
        self.assertEqual(g.canonical_shop_brands("Airxcel MaxxFan Plus"), {"maxxair"})
        self.assertEqual(g.canonical_shop_brands("Coleman-Mach Airxcel 2111"), {"coleman"})

    def test_other_brands_rejected_for_maxxfan(self):
        asked = g.asked_brands_for_lookup("", M, S)
        self.assertFalse(g.chunk_matches_asked_brand(FURRION["title"], "", FURRION["excerpt"], asked))
        self.assertFalse(g.chunk_matches_asked_brand(COLEMAN["title"], "", COLEMAN["excerpt"], asked))
        self.assertTrue(g.chunk_matches_asked_brand(MAXX["title"], "", MAXX["excerpt"], asked, brand="MaxxAir"))

    def test_miss_line_when_only_other_brands(self):
        line = g.library_miss_reply_for_turn([], S, "", M, S, [FURRION, COLEMAN])
        self.assertIn("No MaxxAir document", line)


class TestUnknownBrandGuard(unittest.TestCase):
    def test_unknown_brand_unit_drops_branded_foreign_pages(self):
        self.assertFalse(g.unnamed_unit_page_allowed("Truma AquaGo", FURRION["title"]))
        self.assertTrue(g.unnamed_unit_page_allowed("Truma AquaGo", "Truma AquaGo Service Manual"))

    def test_unbranded_page_and_empty_unit_keep_old_behaviour(self):
        self.assertTrue(g.unnamed_unit_page_allowed("", FURRION["title"]))
        self.assertTrue(g.unnamed_unit_page_allowed("Truma AquaGo", "Generic 12V wiring primer"))


class TestMissLineVsSameBrandPage(unittest.TestCase):
    def test_retrieved_thetford_page_is_not_a_miss(self):
        out = g._unmatched_unit_line([], "toilet leaks under the flush lever", "Plumbing / Toilets",
                                     "Thetford Style II 42070", current="Check the water valve at the pedal.",
                                     chunks=[THET])
        self.assertEqual(out, "")

    def test_retrieved_maxxair_page_is_not_a_miss(self):
        out = g._unmatched_unit_line([], S, "", M, current="", chunks=[MAXX])
        self.assertEqual(out, "")

    def test_foreign_page_still_a_miss(self):
        out = g._unmatched_unit_line([], S, "", M, current="", chunks=[FURRION])
        self.assertIn("No MaxxAir document", out)


if __name__ == "__main__":
    unittest.main()
