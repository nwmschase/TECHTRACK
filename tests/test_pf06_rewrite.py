import unittest

import pf06_rewrite as r


class FidelityCheckTests(unittest.TestCase):
    def test_lost_number_fails(self):
        ok, why = r.fidelity_ok("Torque the bolt to 25 ft-lb.", ["Torque the bolt."])
        self.assertFalse(ok)
        self.assertIn("25", why)

    def test_lost_unit_fails(self):
        self.assertFalse(r.fidelity_ok("Check for 12 V at pin 3.", ["Check for 12 at pin 3."])[0])

    def test_lost_part_number_fails(self):
        self.assertFalse(r.fidelity_ok("Install kit 34122 on the valve.", ["Install the kit on the valve."])[0])

    def test_lost_part_name_fails(self):
        self.assertFalse(r.fidelity_ok("Open the REMOTE cover now.", ["Open the cover now."])[0])

    def test_lost_warning_word_fails(self):
        self.assertFalse(r.fidelity_ok("Do not open the valve under pressure.", ["Open the valve under pressure."])[0])

    def test_lost_content_word_fails(self):
        self.assertFalse(r.fidelity_ok("Clean the filter every four weeks.", ["Clean the filter."])[0])

    def test_lost_quote_and_paren_fail(self):
        self.assertFalse(r.fidelity_ok('Read the "WARNING" label (red).', ["Read the label (red)."])[0])
        self.assertFalse(r.fidelity_ok("Test the coil (not polarity sensitive).", ["Test the coil."])[0])

    def test_faithful_rewrite_passes(self):
        ok, _ = r.fidelity_ok(
            "Remove the dump valve assembly and bench test it by applying power and ground to the coil (not polarity sensitive).",
            ["Remove the dump valve assembly.", "Bench test it by applying power and ground to the coil.", "Note that the coil is not polarity sensitive."],
        )
        self.assertTrue(ok)


class RewriteTests(unittest.TestCase):
    def test_parenthetical_note_stays_an_action_line(self):
        out = r.rewrite_line("Remove the dump valve assembly and bench test it by applying power and ground to the coil (not polarity sensitive).")
        self.assertEqual(out[-1], "Note that the coil is not polarity sensitive.")

    def test_short_line_unchanged(self):
        self.assertEqual(r.rewrite_line("Check the fuse."), ["Check the fuse."])

    def test_passive_becomes_imperative(self):
        self.assertEqual(
            r.rewrite_line("T o Clean the filter should be cleaned every four weeks or more when in use."),
            ["Clean the filter every four weeks or more when in use."],
        )

    def test_condition_then_actions_keep_step_numbers(self):
        out = r.rewrite_line("If the catch pawl is damaged or otherwise cannot be pulled up, proceed to step 10, remove catch pawl, and return to step 6.")
        self.assertEqual(out[1:], ["Proceed to step 10.", "Remove catch pawl.", "Return to step 6."])
        self.assertTrue(all(len(x.split()) <= 12 for x in out))

    def test_warning_text_survives(self):
        src = ('Safety The "WARNING" symbol above is a sign that an installation procedure has a safety risk involved '
               "and may cause death or serious injury if not performed safely and within the parameters set forth in this manual.")
        out = r.rewrite_line(src)
        self.assertGreater(len(out), 1)
        self.assertTrue(r.fidelity_ok(src, out)[0])
        self.assertIn("death or serious injury if not performed safely", " ".join(out))

    def test_unfaithful_or_still_long_falls_back_to_original(self):
        src = "Replace the AA battery inside or plug in coiled cord between REMOTE and RECEIVER to operate in CORDED mode."
        self.assertEqual(r.rewrite_line(src), [src])

    def test_deterministic(self):
        src = "When running all four jacks, stop often to check level and ensure that all 4 jacks are on the ground."
        self.assertEqual(r.rewrite_line(src), r.rewrite_line(src))
        self.assertTrue(all(len(x.split()) <= 12 for x in r.rewrite_line(src)))


if __name__ == "__main__":
    unittest.main()
