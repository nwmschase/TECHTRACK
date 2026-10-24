"""Fridge rear-wall ice/frost: CCD-0008122 Ice and Moisture p.36, not fuse/12V."""
import unittest

from gd_library_coach import (
    ICE_MOISTURE_PRODUCT_LOCK,
    ICE_MOISTURE_SEARCH_BOOST,
    coach_library_search_boost,
    ice_moisture_search_symptom,
    is_fcr_e2_fan_fault_context,
    is_fridge_ice_moisture_context,
    is_fridge_no_power_complaint,
    rank_chunks_for_ice_moisture,
    score_ice_moisture_chunk,
)

FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"
WO_MODEL = "Furrion FCR10DCGTA-BG-PWH"
WO_COMPLAINT = (
    "icing up on rear wall — only about half from the top down"
)

ICE_MOISTURE_P36 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 36,
    "excerpt": (
        "Ice and Moisture\n"
        "Ice or Moisture in the Fridge\n"
        "Fig. 36 rear wall frost pattern. Check whether the dial is at max, "
        "then the door gasket, then verify cooling. Watch/replace from this section."
    ),
}
FUSE_P19 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 19,
    "excerpt": (
        "Section 1 Fuse. Locate the fuse in the front vent cavity. "
        "15A ATC blade / cartridge. Fuse location. No Ice and Moisture on this page."
    ),
}
INVERTER_12V = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 12,
    "excerpt": (
        "No power. Check 12V inverter supply and battery. "
        "Inverter PCB voltage. Not a moisture page."
    ),
}
FAN_FAULT = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 27,
    "excerpt": (
        "Error Code — Fan Fault Diagnostics. Measure voltage at F+ and F−. "
        "Fan Replacement in Repair Section 2."
    ),
}

LIBRARY = [FUSE_P19, INVERTER_12V, FAN_FAULT, ICE_MOISTURE_P36]

LIVE_FUSE_MISS = (
    "Check the 15A fuse in the front vent cavity. Locate the fuse and "
    "confirm 12V inverter supply.\n"
    "📖 Source: Fuse location"
)


class TestIceMoistureDetect(unittest.TestCase):
    def test_live_rear_wall_icing_is_ice_moisture_not_no_power(self):
        self.assertTrue(
            is_fridge_ice_moisture_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_fridge_no_power_complaint("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_fcr_e2_fan_fault_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )

    def test_arctic_and_moisture_cavity_match(self):
        self.assertTrue(
            is_fridge_ice_moisture_context(
                "Refrigerators",
                "Arctic",
                "frost on the back wall, moisture in fridge cavity",
            )
        )

    def test_no_power_complaint_is_not_ice_path(self):
        for complaint in (
            "no power",
            "dead, won't run, no light",
            "fridge is dead, won't turn on",
        ):
            self.assertTrue(
                is_fridge_no_power_complaint("Refrigerators", WO_MODEL, complaint),
                complaint,
            )
            self.assertFalse(
                is_fridge_ice_moisture_context("Refrigerators", WO_MODEL, complaint),
                complaint,
            )

    def test_ice_plus_no_power_lets_fuse_path_win(self):
        both = f"{WO_COMPLAINT}; no power, no light"
        self.assertTrue(
            is_fridge_no_power_complaint("Refrigerators", WO_MODEL, both)
        )
        self.assertFalse(
            is_fridge_ice_moisture_context("Refrigerators", WO_MODEL, both)
        )

    def test_e2_and_cooktop_are_not_ice_path(self):
        self.assertFalse(
            is_fridge_ice_moisture_context(
                "Refrigerators",
                WO_MODEL,
                "Freezes contents; intermittent blinking 2 / E2",
            )
        )
        self.assertFalse(
            is_fridge_ice_moisture_context(
                "Range & Cooktops",
                "Suburban cooktop",
                "Burner lights, then goes out when a pan is placed",
            )
        )


class TestIceMoistureQueryRewrite(unittest.TestCase):
    def test_boost_prefers_ice_moisture_p36_not_fuse(self):
        q = ice_moisture_search_symptom("Refrigerators", WO_MODEL, WO_COMPLAINT)
        low = q.lower()
        self.assertIn("ice and moisture", low)
        self.assertIn("ice or moisture", low)
        self.assertIn("fig. 36", low)
        self.assertIn("gasket", low)
        self.assertNotIn("no power", low)
        self.assertNotIn("fuse", ICE_MOISTURE_SEARCH_BOOST.lower())
        self.assertNotIn("no power", ICE_MOISTURE_SEARCH_BOOST.lower())

    def test_non_ice_unchanged(self):
        raw = "no power, no light"
        self.assertEqual(
            ice_moisture_search_symptom("Refrigerators", WO_MODEL, raw), raw
        )


class TestIceMoistureRanking(unittest.TestCase):
    def test_p36_outranks_fuse_and_12v_inverter(self):
        query = f"{WO_MODEL} {WO_COMPLAINT}"
        ranked = rank_chunks_for_ice_moisture(LIBRARY, query, limit=4)
        titles_pages = [(r["title"], r["page"]) for r in ranked]
        self.assertEqual(titles_pages[0], (FURRION, 36))
        self.assertGreater(
            score_ice_moisture_chunk(ICE_MOISTURE_P36, query),
            score_ice_moisture_chunk(FUSE_P19, query),
        )
        self.assertGreater(
            score_ice_moisture_chunk(ICE_MOISTURE_P36, query),
            score_ice_moisture_chunk(INVERTER_12V, query),
        )
        self.assertGreater(
            score_ice_moisture_chunk(ICE_MOISTURE_P36, query),
            score_ice_moisture_chunk(FAN_FAULT, query),
        )


if __name__ == "__main__":
    unittest.main()
