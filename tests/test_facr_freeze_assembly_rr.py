"""FACR freeze + interior leak continues to rooftop assembly R&R after the three proves."""
import unittest

from gd_library_coach import (
    FACR_ASSEMBLY_RR_SHOP_LINE,
    FACR_FREEZE_ASSEMBLY_LOCK,
    OPEN_LIBRARY_COACH_RULE,
    ensure_facr_freeze_assembly_rr,
    facr_freeze_proves_from_text,
    facr_proves_complete,
    reply_loops_drain_only,
    reply_names_rooftop_assembly_rr,
    reply_stalls_searching_manuals,
)

PROVES = "Drain is clear. Fan-filter OK. Freeze sensor good. Interior leak is still there."
STALL = "Searching the manuals for a condensate procedure. Clear the drain again and retest."
DRAIN_LOOP = (
    "The drain is the whole job. Clear the drain, then check the drain, then clean the drain."
)
GOOD = (
    "Drain, fan/filter, and freeze sensor are already proved. "
    "Continue to rooftop assembly R&R on the CCD-0007990 condensate and assembly path. "
    "Replace the rooftop assembly.\n"
    "?? Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
)


class TestFacrAssemblyClimax(unittest.TestCase):
    def test_three_proves_are_recognized(self):
        facts = facr_freeze_proves_from_text(PROVES)
        self.assertTrue(facr_proves_complete(facts))
        self.assertEqual(facts.get("facr_drain"), "clear")
        self.assertEqual(facts.get("facr_fan_filter"), "ok")
        self.assertEqual(facts.get("facr_freeze_sensor"), "good")
        split = {}
        for line in (
            "condensate drain is clear",
            "fan and filter are good",
            "freeze sensor tests good",
        ):
            split.update(facr_freeze_proves_from_text(line))
        self.assertTrue(facr_proves_complete(split))
        self.assertIn("rooftop assembly", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("CCD-0007990", FACR_FREEZE_ASSEMBLY_LOCK)
        self.assertIn("searching manuals", FACR_FREEZE_ASSEMBLY_LOCK.lower())

    def test_stall_and_drain_loop_continue_to_assembly_rr(self):
        facts = facr_freeze_proves_from_text(PROVES)
        self.assertTrue(reply_stalls_searching_manuals(STALL))
        self.assertTrue(reply_loops_drain_only(DRAIN_LOOP))
        for bad in (STALL, DRAIN_LOOP, "", "Error contacting AI: still searching manuals."):
            fixed = ensure_facr_freeze_assembly_rr(bad, facts)
            self.assertTrue(reply_names_rooftop_assembly_rr(fixed), fixed[:400])
            self.assertIn("CCD-0007990", fixed)
            self.assertIn("condensate", fixed.lower())
            self.assertIn("rooftop assembly", fixed.lower())
            self.assertIn("replace the rooftop assembly", fixed.lower())
            self.assertFalse(reply_stalls_searching_manuals(fixed), fixed[:300])
            self.assertFalse(reply_loops_drain_only(fixed), fixed[:300])
        self.assertIn(FACR_ASSEMBLY_RR_SHOP_LINE.split("\n")[0][:40], ensure_facr_freeze_assembly_rr(STALL, facts))

    def test_complete_reply_is_left_alone(self):
        facts = facr_freeze_proves_from_text(PROVES)
        self.assertTrue(reply_names_rooftop_assembly_rr(GOOD))
        self.assertEqual(ensure_facr_freeze_assembly_rr(GOOD, facts), GOOD)

    def test_searching_manuals_before_proves_does_not_stall(self):
        fixed = ensure_facr_freeze_assembly_rr("Searching manuals. I will look through the manuals.")
        self.assertFalse(reply_stalls_searching_manuals(fixed), fixed[:300])
        self.assertIn("CCD-0007990", fixed)
        self.assertIn("rooftop assembly", fixed.lower())
        self.assertNotIn("searching manuals.", fixed.lower())


if __name__ == "__main__":
    unittest.main()
