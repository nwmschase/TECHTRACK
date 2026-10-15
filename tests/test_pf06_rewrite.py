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

    def test_or_split_keeps_every_word(self):
        src = "Replace the AA battery inside or plug in coiled cord between REMOTE and RECEIVER to operate in CORDED mode."
        out = r.rewrite_line(src)
        self.assertTrue(r.fidelity_ok(src, out)[0] or out == [src])
        self.assertTrue(all(len(x.split()) <= 15 for x in out))

    def test_deterministic(self):
        src = "When running all four jacks, stop often to check level and ensure that all 4 jacks are on the ground."
        self.assertEqual(r.rewrite_line(src), r.rewrite_line(src))
        self.assertTrue(all(len(x.split()) <= 12 for x in r.rewrite_line(src)))


if __name__ == "__main__":
    unittest.main()


class GeneralChunkTests(unittest.TestCase):
    def test_table_rows_keep_every_value(self):
        src = "Terminals Switch Position L-1-3 Lo Heat L-1 Lo Fan L-2 Hi Fan L-1-4 Lo Cool L-2-4 Hi Cool"
        out = r.rewrite_line(src)
        self.assertGreater(len(out), 1)
        for tok in ("L-1-3", "L-1", "L-2", "L-1-4", "L-2-4"):
            self.assertIn(tok, " ".join(out))
        self.assertTrue(all(len(x.split()) <= 12 for x in out))

    def test_prose_chunks_keep_word_order(self):
        src = "Problem 5 The ice maker is not working action 1 Check the 5 amp fuse in the back control unit."
        out = r.rewrite_line(src)
        self.assertEqual(" ".join(out).replace(".", "").lower().split(), src.replace(".", "").lower().split())

    def test_condition_never_cut_from_its_command(self):
        src = "If ignition is not successful, the module board will attempt 2 more trials for ignition, each trail for ignition will be preceded by a 15-18 second purge."
        out = r.rewrite_line(src)
        self.assertFalse(any(x.startswith("If") and "," not in x for x in out if len(out) > 1))

    def test_failed_segment_stays_as_written(self):
        src = "Read the codes L-1 Lo L-2 Hi L-3 Med * If you do not wish to remove the wires from the switch, check them in place."
        out = r.rewrite_line(src)
        self.assertIn("If you do not wish to remove the wires from the switch, check them in place", " ".join(out))


class StatementHeadingTests(unittest.TestCase):
    def test_statement_lines_join_previous_step(self):
        import bay_procedure as bp
        out = bp._label_fallback_steps([
            "Check the fuse in the back control unit.",
            "This will reset power to the unit.",
            "Is heated by the burner flame generating a small current.",
            "Measure the voltage at the board.",
        ])
        heads = [o.split(" Where:")[0].rstrip(".") for o in out]
        self.assertEqual(heads, ["Step 1: Check the fuse in the back control unit", "Step 2: Measure the voltage at the board"])
        self.assertIn("This will reset power to the unit", out[0])
        self.assertIn("Is heated by the burner flame", out[0])


class PlainPathTests(unittest.TestCase):
    def test_shop_line_over_limit_is_left_alone(self):
        src = "Clear the rear drain and trough with a soft plastic probe only so melt water can leave."
        self.assertTrue(r.is_shop_line(src))
        self.assertEqual(r.rewrite_plain_line(src), [src])

    def test_manual_long_line_is_rewritten(self):
        src = "Problem 5 The ice maker is not working action 1 Check the 5 amp fuse in the back control unit."
        out = r.rewrite_plain_line(src)
        self.assertGreater(len(out), 1)
        self.assertTrue(all(len(x.split()) <= 15 for x in out))
        self.assertFalse(any(x.rstrip().endswith(":") and x.split()[0] in ("If", "When") for x in out))

    def test_bare_if_then_split_falls_back(self):
        src = "If the dial is at max and the compressor is still running then open C and T with no jumper and leave them open."
        # Force a rewrite that would produce a bare If:; the plain path must refuse it.
        out = r.rewrite_plain_line(src)
        if any(x.rstrip().endswith(":") for x in out):
            self.fail("plain path emitted a bare If/then line")


class RemainingFailTests(unittest.TestCase):
    def test_leading_ocr_index_stripped(self):
        out = r.rewrite_line("2. Test of the defrost heating element in the fresh food side.")
        self.assertTrue(all(not x.lstrip().startswith("2.") for x in out))
        self.assertIn("defrost", " ".join(out).lower())

    def test_truncated_warning_symbol_rewrites(self):
        src = (
            "Symbol above is a sign that a safety risk is involved and may cause "
            "personal injury and/or product or property damage if not safely adhered "
            "to and within the parameters set forth in this manual."
        )
        out = r.rewrite_line(src)
        self.assertGreater(len(out), 1)
        self.assertTrue(r.fidelity_ok(src, out)[0])
        self.assertTrue(all(len(x.split()) <= 15 for x in out))

    def test_statement_only_manual_becomes_one_labeled_step(self):
        import bay_procedure as bp
        out = bp._label_fallback_steps([
            "Using a DC Voltmeter Check the Converter output as above.",
            "Gel Jumper To set the charger to work with Gel batteries, add a jumper.",
            "This is a standard.100 spacing jumper available from us or computer stores.",
            "If this check fails, stay on it.",
        ])
        self.assertEqual(len(out), 1)
        self.assertIn("Do the cited check", out[0])
        self.assertIn("Gel Jumper", out[0])
        self.assertNotIn("If this check fails, stay on it", out[0].split("Do this:")[0])

    def test_do_this_does_not_double_number(self):
        import bay_procedure as bp
        out = bp._label_fallback_steps(["2. Test of the defrost heating element in the fresh food side."])
        self.assertNotRegex(out[0], r"Do this: \d+\. \d+\.")
