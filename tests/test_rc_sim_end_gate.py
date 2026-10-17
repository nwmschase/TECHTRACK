"""Sim harness: an early sim-tech [END] cannot end a run (Leader 7:32 PM). General, no case ids."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import gd_rc_sim as sim  # noqa: E402


class TestEarlyEnd(unittest.TestCase):
    def test_end_before_any_gd_reply_is_ignored(self):
        self.assertFalse(sim.end_accepted("Customer says the AC won't cool. [END]", []))

    def test_end_after_only_test_requests_is_ignored(self):
        gd = ["Verify the complaint: run COOL, report supply air temp.", "Meter on VAC, probe L1-N at the unit. Report volts."]
        self.assertFalse(sim.end_accepted("Unit stays dead. [END]", gd))

    def test_held_condemn_is_not_terminal(self):
        gd = ["Before condemning the control board, record its isolation reading and send it. [General trade knowledge]"]
        self.assertFalse(sim.end_accepted("ok [END]", gd))

    def test_end_after_repair_npf_or_oem_is_accepted(self):
        for g in ["Replace the 15A fuse in the front holder.", "No Problem Found: document and release.",
                  "Document the findings and submit them to the OEM for authorization."]:
            self.assertTrue(sim.end_accepted("Replaced, works. [END]", ["Report volts.", g]), g)

    def test_end_after_an_adjustment_repair_with_verify_is_accepted(self):
        self.assertTrue(sim.end_accepted("Fixed. [END]", ["Loosen the nut, reorient the petit tube away from the wheel, snug it, then retest for E8."]))
        self.assertTrue(sim.end_accepted("Fixed. [END]", ["Reseat the plug.\nVERIFY: run 3 cycles and confirm."]))

    def test_end_after_gd_asks_to_confirm_the_fix_is_accepted(self):
        self.assertTrue(sim.end_accepted("No E8. [END]", ["Report that result. If it completes with no E8, the petit-tube orientation fix is verified."]))

    def test_pending_report_is_not_an_outcome(self):
        gd = ["If jumper holds voltage and it lights, repair the coach 12 V feed.\nVERIFY: run the function again."]
        self.assertFalse(sim.end_accepted("Battery-jump test isn't done yet, still pending with tech line. [END]", gd))

    def test_conditional_repair_with_verify_is_not_terminal(self):
        self.assertFalse(sim.gd_terminal("If jumper holds voltage, repair the 12 V feed.\nVERIFY: run the function again."))

    def test_no_end_marker_never_ends(self):
        self.assertFalse(sim.end_accepted("Replaced, works.", ["Replace the fuse."]))


if __name__ == "__main__":
    unittest.main()
