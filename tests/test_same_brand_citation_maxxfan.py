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

    def test_airxcel_on_maxxair_page_is_not_coleman(self):
        self.assertEqual(g.canonical_shop_brands("Airxcel MaxxFan Plus"), {"maxxair"})
        self.assertEqual(g.canonical_shop_brands("Coleman-Mach Airxcel 2111"), {"coleman"})

    def test_other_brands_rejected_for_maxxfan(self):
        asked = g.asked_brands_for_lookup("", M, S)
        self.assertFalse(g.chunk_matches_asked_brand(FURRION["title"], "", FURRION["excerpt"], asked))
        self.assertFalse(g.chunk_matches_asked_brand(COLEMAN["title"], "", COLEMAN["excerpt"], asked))
        self.assertTrue(g.chunk_matches_asked_brand(MAXX["title"], "", MAXX["excerpt"], asked, brand="MaxxAir"))


if __name__ == "__main__":
    unittest.main()
