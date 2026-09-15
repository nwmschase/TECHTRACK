"""Furrion FCR E2 / Fan Fault Current: Fan Replacement must outrank board-only R&R."""
import unittest

from gd_library_coach import (
    FAN_FAULT_SEARCH_BOOST,
    FCR_E2_FAN_FAULT_PRODUCT_LOCK,
    FURRION_FCR_FAN_FAULT_PAGES,
    claims_fcr_e2_board_only_cage,
    fcr_e2_search_symptom,
    is_air_conditioning_context,
    is_fcr_e2_fan_fault_context,
    rank_chunks_for_fcr_fan_fault,
    score_fcr_fan_fault_chunk,
)

FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"
WO_MODEL = "Furrion FCR10DCGTA-BG-PWH"
WO_COMPLAINT = (
    "Freezes contents; intermittent blinking 2 / E2; temp control intermittent"
)
WO_READINGS = (
    "fan V 14.28-10.37 V; fan amps 0.383-0.442 A; supply 13.37 V shore / "
    "12.70 V battery; E2 returned about 1.5 hr after thaw"
)

# Shop-typical CCD-0008122 index text already used in this repo (p.27 fixture + leftover tree).
FAN_FAULT_DIAG = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 27,
    "excerpt": (
        "Error Code — Fan Fault Diagnostics\n"
        "Fig. 21 Locate the inverter PCB. "
        "Measure voltage at the F+ and F− terminals.\n"
        "If the error code remains after checking connections, "
        "replace the inverter PCB and fan. Fan Replacement in Repair Section 2."
    ),
}
FAN_REPLACEMENT = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 33,
    "excerpt": (
        "Potential air blockage or bad fan. Proceed to Fan Replacement in "
        "Repair Section 2 for further information."
    ),
}
FAN_FAULT_CURRENT_SPEC = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 18,
    "excerpt": (
        "Fan Fault Current 1 A peak. Inverter-board fan driver overcurrent spec."
    ),
}
BOARD_ONLY_RR = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 48,
    "excerpt": (
        "Compressor Inverter PCB Replacement. Replace the driver board / "
        "rear inverter. No fan procedure on this page."
    ),
}
AC_E2 = {
    "title": "Furrion FACT12SA2 Rooftop Air Conditioner SM",
    "category": "Air Conditioning",
    "page": 15,
    "excerpt": "E2 freeze / evaporator sensor on the rooftop AC. Not a fridge fan code.",
}

LIBRARY = [FAN_FAULT_CURRENT_SPEC, BOARD_ONLY_RR, FAN_FAULT_DIAG, FAN_REPLACEMENT, AC_E2]


class TestFcrE2Detect(unittest.TestCase):
    def test_wo_complaint_is_fridge_e2_not_ac(self):
        self.assertTrue(
            is_fcr_e2_fan_fault_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_air_conditioning_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )

    def test_fan_readings_keep_the_path(self):
        self.assertTrue(
            is_fcr_e2_fan_fault_context(
                "Refrigerators", WO_MODEL, f"{WO_COMPLAINT} {WO_READINGS}"
            )
        )

    def test_ac_e2_is_not_fridge_fan_fault(self):
        self.assertFalse(
            is_fcr_e2_fan_fault_context("Air Conditioning", "Furrion FACT12SA2", "E2 on the CCC")
        )
        self.assertTrue(
            is_air_conditioning_context("Air Conditioning", "Furrion FACT12SA2", "E2 on the CCC")
        )

    def test_powered_not_cooling_without_e2_is_not_fan_fault(self):
        self.assertFalse(
            is_fcr_e2_fan_fault_context(
                "Refrigerators",
                "Furrion FCR10",
                "found fuse blown and replaced, fridge light comes on, fridge is not cooling",
            )
        )


class TestFcrE2QueryRewrite(unittest.TestCase):
    def test_boost_prefers_fan_fault_and_fan_replacement(self):
        q = fcr_e2_search_symptom("Refrigerators", WO_MODEL, WO_COMPLAINT)
        low = q.lower()
        self.assertIn("fan fault", low)
        self.assertIn("fan replacement", low)
        self.assertIn("f+", low)
        self.assertNotIn("unity", low)
        self.assertIn("fan replacement", FAN_FAULT_SEARCH_BOOST.lower())

    def test_non_e2_fridge_unchanged(self):
        raw = "fridge not cooling cavity light on"
        self.assertEqual(fcr_e2_search_symptom("Refrigerators", "FCR10", raw), raw)


class TestFcrE2Ranking(unittest.TestCase):
    def test_fan_pages_outrank_board_only_and_spec(self):
        query = f"{WO_MODEL} {WO_COMPLAINT} {WO_READINGS}"
        ranked = rank_chunks_for_fcr_fan_fault(LIBRARY, query, limit=4)
        pages = [int(r["page"]) for r in ranked]
        self.assertIn(27, pages[:2])
        self.assertTrue(any(p in FURRION_FCR_FAN_FAULT_PAGES for p in pages[:2]))
        self.assertGreater(
            score_fcr_fan_fault_chunk(FAN_FAULT_DIAG, query),
            score_fcr_fan_fault_chunk(BOARD_ONLY_RR, query),
        )
        self.assertGreater(
            score_fcr_fan_fault_chunk(FAN_REPLACEMENT, query),
            score_fcr_fan_fault_chunk(FAN_FAULT_CURRENT_SPEC, query),
        )
        self.assertGreater(
            score_fcr_fan_fault_chunk(FAN_FAULT_DIAG, query),
            score_fcr_fan_fault_chunk(AC_E2, query),
        )


class TestFcrE2CageDetect(unittest.TestCase):
    def test_live_miss_board_only_is_a_cage(self):
        live = (
            "CCD-0008122 does not list a separate freezer evaporator fan. "
            "E2 repair is board only. Replace the rear inverter/control board."
        )
        self.assertTrue(claims_fcr_e2_board_only_cage(live))

    def test_board_and_fan_recommendation_is_not_a_cage(self):
        good = (
            "Fan volts and amps are present and E2 returned after thaw. "
            "CCD-0008122 Fan Fault Diagnostics: replace the inverter PCB and fan. "
            "Recommend freezer evaporator fan R&R and the rear inverter/control board.\n"
            "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 27"
        )
        self.assertFalse(claims_fcr_e2_board_only_cage(good))
        self.assertIn("freezer evaporator fan", good.lower())

    def test_product_lock_is_not_flagged_as_a_cage(self):
        self.assertFalse(claims_fcr_e2_board_only_cage(FCR_E2_FAN_FAULT_PRODUCT_LOCK))
        self.assertIn("Fan Replacement", FCR_E2_FAN_FAULT_PRODUCT_LOCK)
        self.assertIn("27", str(FURRION_FCR_FAN_FAULT_PAGES))
        self.assertIn("33", str(FURRION_FCR_FAN_FAULT_PAGES))


if __name__ == "__main__":
    unittest.main()
