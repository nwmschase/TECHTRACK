"""Fridge rear-wall ice/frost: CCD-0008122 Ice and Moisture p.36, not fuse/12V."""
import unittest

from gd_library_coach import (
    ICE_MOISTURE_PRODUCT_LOCK,
    ICE_MOISTURE_SEARCH_BOOST,
    ICE_MOISTURE_SHOP_LINE,
    coach_library_search_boost,
    ensure_fridge_ice_moisture_path,
    extract_stated_facts,
    ice_moisture_reply_needs_guard,
    ice_moisture_search_symptom,
    is_fcr_e2_fan_fault_context,
    is_fridge_ice_moisture_context,
    is_fridge_no_power_complaint,
    rank_chunks_for_ice_moisture,
    reply_names_ice_moisture_p36,
    reply_opens_fuse_12v_no_power,
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

    def test_stated_facts_boost_is_moisture_not_fuse(self):
        facts = extract_stated_facts(WO_COMPLAINT)
        self.assertEqual(facts.get("ice_moisture"), "rear_wall")
        boost = coach_library_search_boost(facts)
        low = boost.lower()
        self.assertIn("ice and moisture", low)
        self.assertNotIn("no power", low)
        self.assertNotIn("inoperable compressor", low)


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


class TestIceMoistureGuard(unittest.TestCase):
    def test_live_miss_fuse_cite_without_page_is_caught(self):
        self.assertTrue(reply_opens_fuse_12v_no_power(LIVE_FUSE_MISS))
        self.assertFalse(reply_names_ice_moisture_p36(LIVE_FUSE_MISS))
        self.assertTrue(ice_moisture_reply_needs_guard(LIVE_FUSE_MISS))
        self.assertNotIn("page 36", LIVE_FUSE_MISS.lower())
        self.assertIn("fuse location", LIVE_FUSE_MISS.lower())

    def test_ensure_steers_to_p36_and_drops_fuse_12v(self):
        fixed = ensure_fridge_ice_moisture_path(LIVE_FUSE_MISS)
        self.assertTrue(reply_names_ice_moisture_p36(fixed))
        self.assertFalse(reply_opens_fuse_12v_no_power(fixed))
        low = fixed.lower()
        self.assertIn("ice and moisture", low)
        self.assertIn("page 36", low)
        self.assertIn("fig.36", low.replace(" ", "").replace("fig. 36", "fig.36"))
        self.assertIn("gasket", low)
        self.assertNotIn("fuse location", low)
        self.assertIn(ICE_MOISTURE_SHOP_LINE.split("\n")[0][:40], fixed)
        self.assertIn("📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36", fixed)

    def test_good_p36_reply_is_left_alone(self):
        good = (
            "Rear-wall ice about half from the top is Ice and Moisture → "
            "Ice or Moisture in the Fridge. Note the frost pattern, then check "
            "whether the dial is at max, then the door gasket, then verify cooling.\n"
            "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36"
        )
        self.assertTrue(reply_names_ice_moisture_p36(good))
        self.assertFalse(reply_opens_fuse_12v_no_power(good))
        self.assertFalse(ice_moisture_reply_needs_guard(good))
        self.assertEqual(ensure_fridge_ice_moisture_path(good), good)

    def test_product_lock_is_p36_not_fuse_tree(self):
        self.assertFalse(reply_opens_fuse_12v_no_power(ICE_MOISTURE_PRODUCT_LOCK))
        low = ICE_MOISTURE_PRODUCT_LOCK.lower()
        self.assertIn("ice and moisture", low)
        self.assertIn("page 36", low)
        self.assertIn("fig. 36", low)
        self.assertIn("gasket", low)
        self.assertIn("dial max", low)
        self.assertIn("no power", low)
        self.assertIn("fuse location", low)
        self.assertIn("unless", low)
        self.assertFalse(reply_opens_fuse_12v_no_power(ICE_MOISTURE_SHOP_LINE))
        self.assertTrue(reply_names_ice_moisture_p36(ICE_MOISTURE_SHOP_LINE))


if __name__ == "__main__":
    unittest.main()
