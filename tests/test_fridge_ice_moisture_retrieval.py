"""Fridge rear-wall ice/frost: CCD-0008122 Ice and Moisture p.36, not fuse/12V."""
import unittest

from gd_library_coach import (
    ICE_MOISTURE_PRODUCT_LOCK,
    ICE_MOISTURE_SEARCH_BOOST,
    coach_library_search_boost,
    is_fcr_e2_fan_fault_context,
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
