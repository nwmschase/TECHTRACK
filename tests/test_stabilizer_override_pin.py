"""Front stabilizer / PSX1 seized override pin: complete jack assembly, not coupler-only."""
import unittest

from gd_library_coach import (
    PSX1_ASSEMBLY_RR_SHOP_LINE,
    PSX1_PRODUCT_LOCK,
    PSX1_SEARCH_BOOST,
    claims_coupler_only_rr,
    ensure_stabilizer_assembly_rr,
    is_level_up_advantage_context,
    is_stabilizer_override_pin_context,
    rank_chunks_for_stabilizer_override,
    reply_recommends_complete_jack_assembly,
    score_stabilizer_override_chunk,
    stabilizer_reply_needs_assembly_rr,
    stabilizer_search_symptom,
)

WO_MODEL = "Lippert PSX1 front stabilizer"
WO_COMPLAINT = (
    "Power extend/retract works; manual crank/override will not engage. "
    "Roll pin seized at the override coupler."
)

PSX1_OVERRIDE_USAGE = {
    "title": "Lippert PSX1 CCD-0007345",
    "category": "Leveling",
    "page": 7,
    "excerpt": (
        "Override usage. How to use the manual override crank. "
        "Coupler engagement for temporary override. Not an assembly R&R page."
    ),
}
PSX1_ASSEMBLY = {
    "title": "Lippert PSX1 CCD-0007345",
    "category": "Leveling",
    "page": 4,
    "excerpt": (
        "Front stabilizer jack. Replace the complete jack assembly. "
        "Reconnect mount and electrical. Retest power and manual."
    ),
}
COUPLER_ONLY = {
    "title": "Lippert PSX1 CCD-0007345",
    "category": "Leveling",
    "page": 9,
    "excerpt": "Replace the override coupler only. Coupler-only repair. No complete assembly.",
}
REAR_OWNER = {
    "title": "rear stabilizer owner",
    "category": "ID & Reference",
    "page": 1,
    "excerpt": "Rear stabilizer owner identification. Stabilizer jack location.",
}
LEVEL_UP = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "page": 2,
    "excerpt": "Level-Up hydraulic leveling controller 807662 Manual Mode. OCTP.",
}

LIBRARY = [PSX1_OVERRIDE_USAGE, COUPLER_ONLY, LEVEL_UP, REAR_OWNER, PSX1_ASSEMBLY]


class TestStabilizerDetect(unittest.TestCase):
    def test_seized_roll_pin_is_psx1_path(self):
        self.assertTrue(
            is_stabilizer_override_pin_context("Leveling", WO_MODEL, WO_COMPLAINT)
        )
        self.assertTrue(
            is_stabilizer_override_pin_context(
                "",
                "PSX1",
                "manual override will not engage, override pin broken, not field serviceable",
            )
        )

    def test_level_up_advantage_is_not_stabilizer_pin(self):
        self.assertFalse(
            is_stabilizer_override_pin_context(
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes then returns home",
            )
        )
        self.assertTrue(
            is_level_up_advantage_context(
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes then returns home",
            )
        )

    def test_power_only_without_manual_fail_is_not_pin_path(self):
        self.assertFalse(
            is_stabilizer_override_pin_context(
                "Leveling", "front stabilizer jack", "power extend works"
            )
        )


class TestStabilizerQueryRewrite(unittest.TestCase):
    def test_boost_prefers_complete_assembly_and_psx1(self):
        q = stabilizer_search_symptom("Leveling", WO_MODEL, WO_COMPLAINT)
        low = q.lower()
        self.assertIn("psx1", low)
        self.assertIn("ccd-0007345", low)
        self.assertIn("complete", low)
        self.assertIn("assembly", low)
        self.assertIn("complete assembly", PSX1_SEARCH_BOOST.lower())

    def test_non_stab_unchanged(self):
        raw = "Manual Mode flashes then returns home"
        self.assertEqual(
            stabilizer_search_symptom("Leveling", "807662", raw), raw
        )


class TestStabilizerRanking(unittest.TestCase):
    def test_complete_assembly_outranks_coupler_and_override_usage(self):
        query = f"{WO_MODEL} {WO_COMPLAINT}"
        ranked = rank_chunks_for_stabilizer_override(LIBRARY, query, limit=5)
        titles_pages = [(r["title"], r["page"]) for r in ranked]
        self.assertIn(("Lippert PSX1 CCD-0007345", 4), titles_pages[:2])
        self.assertGreater(
            score_stabilizer_override_chunk(PSX1_ASSEMBLY, query),
            score_stabilizer_override_chunk(COUPLER_ONLY, query),
        )
        self.assertGreater(
            score_stabilizer_override_chunk(PSX1_ASSEMBLY, query),
            score_stabilizer_override_chunk(PSX1_OVERRIDE_USAGE, query),
        )
        self.assertGreater(
            score_stabilizer_override_chunk(PSX1_ASSEMBLY, query),
            score_stabilizer_override_chunk(LEVEL_UP, query),
        )


class TestStabilizerAssemblyGuard(unittest.TestCase):
    def test_live_miss_coupler_only_is_caught(self):
        live = (
            "Override will not engage. Roll pin is seized. Replace the coupler only. "
            "See PSX1 CCD-0007345 p.7 override usage."
        )
        self.assertTrue(claims_coupler_only_rr(live))
        self.assertTrue(stabilizer_reply_needs_assembly_rr(live, {"override_pin": "broken_or_seized"}))
        self.assertFalse(reply_recommends_complete_jack_assembly(live))

    def test_ensure_steers_to_complete_assembly_not_coupler_only(self):
        live = (
            "Override pin is seized. Replace the coupler only. "
            "📖 Source: Lippert PSX1 CCD-0007345 - page 7"
        )
        facts = {"override_pin": "broken_or_seized"}
        fixed = ensure_stabilizer_assembly_rr(live, facts)
        self.assertTrue(reply_recommends_complete_jack_assembly(fixed))
        self.assertIn("complete", fixed.lower())
        self.assertIn("assembly", fixed.lower())
        self.assertFalse(claims_coupler_only_rr(fixed))
        self.assertIn(PSX1_ASSEMBLY_RR_SHOP_LINE.split("\n")[0][:40], fixed)

    def test_good_assembly_reply_is_left_alone(self):
        good = (
            "Roll pin is seized and not field-serviceable. "
            "Replace the complete front stabilizer jack assembly. "
            "Reconnect mount and electrical; retest power and manual.\n"
            "📖 Source: Lippert PSX1 CCD-0007345"
        )
        facts = {"override_pin": "broken_or_seized"}
        self.assertTrue(reply_recommends_complete_jack_assembly(good))
        self.assertFalse(claims_coupler_only_rr(good))
        self.assertFalse(stabilizer_reply_needs_assembly_rr(good, facts))
        self.assertEqual(ensure_stabilizer_assembly_rr(good, facts), good)

    def test_product_lock_is_not_coupler_only_and_names_assembly(self):
        self.assertFalse(claims_coupler_only_rr(PSX1_PRODUCT_LOCK))
        low = PSX1_PRODUCT_LOCK.lower()
        self.assertIn("complete", low)
        self.assertIn("assembly", low)
        self.assertIn("coupler only", low)
        self.assertIn("p.7", low)
        self.assertIn("override", low)


if __name__ == "__main__":
    unittest.main()
