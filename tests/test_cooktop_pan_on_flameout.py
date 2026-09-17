"""Suburban / gas cooktop pan-on flame-out: tip position with pan before parts R&R."""
import unittest

from gd_library_coach import (
    COOKTOP_PRODUCT_LOCK,
    COOKTOP_SEARCH_BOOST,
    COOKTOP_TIP_PAN_SHOP_LINE,
    cooktop_reply_needs_tip_pan,
    cooktop_search_symptom,
    ensure_cooktop_tip_pan_check,
    is_cooktop_pan_on_flameout_context,
    is_cooktop_range_context,
    is_fcr_e2_fan_fault_context,
    is_water_heater_context,
    rank_chunks_for_cooktop_pan_on,
    reply_has_tip_pan_before_parts,
    reply_names_cooktop_tip_pan_check,
    score_cooktop_pan_on_chunk,
)

WO_MODEL = "Suburban cooktop"
WO_COMPLAINT = (
    "Burner lights, then goes out when a pan is placed (either burner)"
)

SUBURBAN_RANGE = {
    "title": "Suburban Range/Cooktops SM",
    "category": "Range & Cooktops",
    "page": 12,
    "excerpt": (
        "Suburban range / cooktop burner. Thermocouple / flame sensor at the burner head. "
        "Tip position in the flame with cookware on."
    ),
}
FURNACE_SAIL = {
    "title": "Suburban Furnace Service Manual",
    "category": "Furnaces",
    "page": 8,
    "excerpt": "Sail switch IN/OUT. Blower running. Draft and igniter path. No cooktop.",
}
IGNITER_FIRST = {
    "title": "Generic LP igniter notes",
    "category": "Furnaces",
    "page": 3,
    "excerpt": "Check igniter, draft, regulator, orifice. Replace safety valve.",
}
THERMOCOUPLE_RR = {
    "title": "Suburban Range/Cooktops SM",
    "category": "Range & Cooktops",
    "page": 20,
    "excerpt": "Replace the thermocouple. Safety valve R&R. No tip or pan check on this page.",
}

LIBRARY = [FURNACE_SAIL, IGNITER_FIRST, THERMOCOUPLE_RR, SUBURBAN_RANGE]


class TestCooktopDetect(unittest.TestCase):
    def test_pan_on_shutoff_is_cooktop_not_furnace_marker(self):
        self.assertTrue(is_cooktop_range_context("", WO_MODEL, WO_COMPLAINT))
        self.assertTrue(
            is_cooktop_pan_on_flameout_context("", WO_MODEL, WO_COMPLAINT)
        )
        self.assertTrue(
            is_cooktop_pan_on_flameout_context(
                "Range & Cooktops", WO_MODEL, WO_COMPLAINT
            )
        )

    def test_suburban_furnace_is_not_cooktop(self):
        self.assertFalse(
            is_cooktop_pan_on_flameout_context(
                "Furnaces", "Suburban SF-42", "furnace won't light sail switch"
            )
        )
        self.assertFalse(
            is_cooktop_range_context("Furnaces", "Suburban SF-42", "no heat blower runs")
        )

    def test_cooktop_wont_spark_without_pan_is_not_flameout_path(self):
        self.assertTrue(is_cooktop_range_context("", "Suburban cooktop", "won't spark"))
        self.assertFalse(
            is_cooktop_pan_on_flameout_context("", "Suburban cooktop", "won't spark")
        )

    def test_fridge_and_water_heater_lose(self):
        self.assertFalse(
            is_cooktop_pan_on_flameout_context(
                "Refrigerators", "Furrion FCR10", "not cooling"
            )
        )
        self.assertFalse(is_fcr_e2_fan_fault_context("", WO_MODEL, WO_COMPLAINT))
        self.assertFalse(is_water_heater_context("", WO_MODEL, WO_COMPLAINT))


class TestCooktopQueryRewrite(unittest.TestCase):
    def test_boost_prefers_tip_pan_and_suburban_range(self):
        q = cooktop_search_symptom("", WO_MODEL, WO_COMPLAINT)
        low = q.lower()
        self.assertIn("tip", low)
        self.assertIn("position", low)
        self.assertIn("cookware", low)
        self.assertIn("thermocouple", low)
        self.assertIn("suburban", low)
        self.assertIn("tip position", COOKTOP_SEARCH_BOOST.lower())

    def test_non_cooktop_unchanged(self):
        raw = "furnace won't light sail switch"
        self.assertEqual(cooktop_search_symptom("Furnaces", "Suburban SF-42", raw), raw)


class TestCooktopRanking(unittest.TestCase):
    def test_range_cooktop_outranks_furnace_and_igniter(self):
        query = f"{WO_MODEL} {WO_COMPLAINT}"
        ranked = rank_chunks_for_cooktop_pan_on(LIBRARY, query, limit=4)
        titles = [r["title"] for r in ranked]
        self.assertEqual(titles[0], "Suburban Range/Cooktops SM")
        self.assertGreater(
            score_cooktop_pan_on_chunk(SUBURBAN_RANGE, query),
            score_cooktop_pan_on_chunk(FURNACE_SAIL, query),
        )
        self.assertGreater(
            score_cooktop_pan_on_chunk(SUBURBAN_RANGE, query),
            score_cooktop_pan_on_chunk(IGNITER_FIRST, query),
        )


class TestCooktopTipPanGuard(unittest.TestCase):
    def test_live_miss_jumps_to_parts_without_tip_pan(self):
        live = (
            "Flame sensor / thermocouple path. Replace the thermocouple and "
            "check the safety valve, orifice, and regulator. Igniter next if needed."
        )
        self.assertFalse(reply_names_cooktop_tip_pan_check(live))
        self.assertTrue(cooktop_reply_needs_tip_pan(live))
        self.assertFalse(reply_has_tip_pan_before_parts(live))

    def test_ensure_puts_tip_pan_before_parts_rr(self):
        live = (
            "Replace the thermocouple. Then check the safety valve and regulator."
        )
        fixed = ensure_cooktop_tip_pan_check(live)
        self.assertTrue(reply_names_cooktop_tip_pan_check(fixed))
        self.assertTrue(reply_has_tip_pan_before_parts(fixed))
        self.assertIn("tip", fixed.lower())
        self.assertIn("position", fixed.lower())
        self.assertTrue(any(k in fixed.lower() for k in ("pan", "cookware")))
        tip_at = fixed.lower().find("tip")
        parts_at = fixed.lower().find("replace the thermocouple")
        self.assertGreaterEqual(tip_at, 0)
        self.assertGreater(parts_at, tip_at)
        self.assertIn(COOKTOP_TIP_PAN_SHOP_LINE.split("\n")[0][:40], fixed)

    def test_good_tip_pan_reply_is_left_alone(self):
        good = (
            "Verify the thermocouple tip position in the burner flame with cookware on. "
            "Only if the tip geometry is correct and the flame still drops out, "
            "replace the thermocouple.\n"
            "📖 Source: Suburban Range/Cooktops SM"
        )
        self.assertTrue(reply_names_cooktop_tip_pan_check(good))
        self.assertTrue(reply_has_tip_pan_before_parts(good))
        self.assertFalse(cooktop_reply_needs_tip_pan(good))
        self.assertEqual(ensure_cooktop_tip_pan_check(good), good)

    def test_product_lock_requires_tip_pan_before_parts(self):
        low = COOKTOP_PRODUCT_LOCK.lower()
        self.assertIn("tip", low)
        self.assertIn("position", low)
        self.assertIn("cookware", low)
        self.assertIn("before", low)
        self.assertIn("thermocouple", low)
        self.assertNotIn("10.5", COOKTOP_PRODUCT_LOCK)
        self.assertNotIn("page 12", COOKTOP_PRODUCT_LOCK)


if __name__ == "__main__":
    unittest.main()
