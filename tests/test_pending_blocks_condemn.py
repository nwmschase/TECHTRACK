"""General rule (Leader 10:21 PM): a pending isolation test blocks EVERY condemn/replace, a tech-proposed replacement and an OEM
replacement request included, until its result is recorded. A 'pending ... looks normal/OK' answer is not a result."""
import itertools
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import gd_official as go  # noqa: E402
import gd_rc_sim as sim  # noqa: E402

PENDING_ANSWERS = [
    "Gray-coil unplug isn't in the notes (still pending). Complaint still present.",
    "Plumbing check isn't in the notes (still pending); hoses/fittings/manifold look normal/OK from what's recorded.",
    "Battery-jump test and tech-line call are still pending.",
    "Isolation reading at the remaining part is still pending - it looks normal/OK.",
    "Haven't done the bypass test yet.",
]
CONDEMNS = [
    "Replace both front valves/manifold as a matched set. [Library: M p.3]",
    "Commit to replace the remaining front jack. [Library: M p.3]",
    "Requested authorization: replace the control board as a matched set.",
    "Go ahead and R&R the pump motor. [General trade knowledge]",
    "Install a new gas valve. [Library: M p.17]",
    "The control board is bad. [General trade knowledge]",
]


class TestPendingBlocksCondemn(unittest.TestCase):
    def test_rc20_shape_valve_manifold_then_jack_held(self):
        tech = PENDING_ANSWERS[:2]
        reply = ("Nothing else to check on this path.\n" + CONDEMNS[0] + "\n" + CONDEMNS[2] +
                 "\nIf the coil unplug stops the drift, replace the coil. [Library: M p.3]\nVERIFY: run slides 2-3 times.")
        out = go.hold_while_pending(reply, go.pending_isolation_tests(tech))
        self.assertIn("Hold all part replacement", out)
        self.assertNotIn("Replace both front valves", out)
        self.assertNotIn("Requested authorization: replace", out)
        self.assertNotIn("replace the coil", out)  # Leader 10:21 PM: a pending test blocks EVERY replace, conditional too
        self.assertIn("VERIFY:", out)

    def test_pending_plus_normal_ok_is_not_a_result(self):
        self.assertFalse(go.isolation_recorded("manifold", [PENDING_ANSWERS[1]], ["Inspect hoses, fittings and manifold; report."]))
        self.assertFalse(go._is_result(PENDING_ANSWERS[3].lower()))

    def test_recorded_result_clears_the_pending_test(self):
        tech = [PENDING_ANSWERS[0], "Gray-coil unplugged: the front jacks stop drifting; coil reads 0 V."]
        self.assertEqual(go.pending_isolation_tests(tech), [])
        self.assertEqual(go.hold_while_pending(CONDEMNS[0], go.pending_isolation_tests(tech)), CONDEMNS[0])

    def test_not_in_the_notes_alone_is_the_unrecorded_normal_convention(self):
        # harness convention: a reading the case file doesn't record is reported normal; only explicit pending/not-done holds
        self.assertEqual(go.pending_isolation_tests(["Winding ohms to frame look normal/OK (not in the notes)."]), [])

    def test_generic_not_checked_yet_is_not_a_pending_isolation_test(self):
        self.assertEqual(go.pending_isolation_tests(["Haven't run it or checked anything yet."]), [])

    def test_negated_replacement_is_not_held(self):
        out = go.hold_while_pending("Requested authorization: firmware flash; no board R&R.", ["Battery-jump test still pending."])
        self.assertIn("no board R&R", out)

    def test_no_pending_no_hold(self):
        tech = ["Coil reads 32 ohms, in spec.", "Supply holds 13.1 V during the try."]
        self.assertEqual(go.pending_isolation_tests(tech), [])

    def test_long_part_phrase_is_seen_by_condemn_re(self):
        self.assertEqual(go.condemned_parts(CONDEMNS[0]), ["both front valves/manifold"])

    def test_sim_tech_never_adds_normal_ok_to_pending(self):
        self.assertIn("never add 'looks normal/OK' to a pending test", sim.TECH_SYS)


class TestPendingProperty(unittest.TestCase):
    def test_no_unconditional_replace_survives_any_pending_answer(self):
        """Property: for every pending answer x every condemn wording x position, no unconditional replace line survives."""
        n = 0
        for ans, (c1, c2) in itertools.product(PENDING_ANSWERS, itertools.permutations(CONDEMNS, 2)):
            reply = "Report the reading at the part. [General trade knowledge]\n" + c1 + "\n" + c2 + "\nVERIFY: run it 3 times."
            out = go.hold_while_pending(reply, go.pending_isolation_tests(["Complaint verified.", ans]))
            for line in out.splitlines():
                if line.startswith(("Hold all part replacement", "VERIFY")):
                    continue
                self.assertFalse(go.REPLACE_ANY_RE.search(line) or go.CONDEMN_RE.search(line), (ans, line))
            n += 1
        self.assertEqual(n, len(PENDING_ANSWERS) * 30)


if __name__ == "__main__":
    unittest.main()


class TestMixedLine(unittest.TestCase):
    """e82df6b RC20: 'Replace X. Do not replace Y.' on one line hid the condemn of X from every guard."""

    LINE = ("Replace both front jack solenoid cartridges as a matched pair at the manifold. Do not replace the LCD or control board. "
            "[General trade knowledge]")

    def test_condemn_seen_despite_a_negated_sentence(self):
        self.assertEqual(go.condemned_parts(self.LINE), ["both front jack solenoid cartridges"])

    def test_pending_hold_fires_on_mixed_line(self):
        out = go.hold_while_pending(self.LINE, ["Plumbing check and coil unplug test are still pending."])
        self.assertTrue(out.startswith("Hold all part replacement"))
        self.assertNotIn("Replace both front jack", out)

    def test_negated_only_line_untouched(self):
        line = "Coil is in spec; do not replace the valve. [Library: M p.22]"
        self.assertEqual(go.condemned_parts(line), [])
        self.assertEqual(go.hold_while_pending(line, ["Jump test still pending."]), line)


class TestDisguisedConditionals(unittest.TestCase):
    """750b5cf RC20: a parenthetical negation and a counterfactual 'If they would ... (matches what you already have)' let a swap through."""
    PEND = ["Plumbing check on the hoses at the manifold is still pending."]

    def test_parenthetical_negation_does_not_hide_the_condemn(self):
        line = "Shop path without those tests: replace both valve cartridges as a pair (do not replace the cylinders for this alone)."
        self.assertTrue(go.hold_while_pending(line, self.PEND).startswith("Hold all part replacement"))

    def test_counterfactual_conditional_is_held_while_pending(self):
        line = "If they would still drift with coils unplugged (matches the voltages you already have), replace both valve cartridges."
        self.assertTrue(go.hold_while_pending(line, self.PEND).startswith("Hold all part replacement"))

    def test_conditional_repair_is_held_while_pending(self):
        line = "If they still drift with both coils unplugged, replace both valve cartridges as a pair (not the cylinders)."
        self.assertTrue(go.hold_while_pending(line, self.PEND).startswith("Hold all part replacement"))

    def test_sim_tech_pending_condition_never_met(self):
        self.assertIn("a condition about a test the case file marks pending is NOT met", sim.TECH_SYS)


class TestEveryReplaceHeldWhilePending(unittest.TestCase):
    """215fce8 RC20 turn 6/7: a conditional whose condition was already met ('If ... with no voltage on FL/FR coils: replace both
    front isolation cartridges') and 'commit to the repair' / 'Did both cartridges go in?' got through while two tests were pending."""
    PEND = ["Plumbing check at the manifold is still pending — not done yet.", "Gray-coil unplug test is also still pending."]
    CONDS = ["If the front jacks still move with no voltage on FL/FR coils: replace both front isolation cartridges as a matched pair.",
             "If they still drift after both cartridges: replace both front jacks as a matched set.",
             "When the reading is low, condemn the inverter board.",
             "Once the leak is confirmed, order a new power unit.",
             "Should it still fail, R&R the pump motor."]
    PRESUMED = ["Nothing else to check, so commit to the repair. [General trade knowledge]",
                "Did both cartridges go in, and did the front jacks stay still on verify?",
                "Which repair did you complete, and did the front jacks stay still on verify?",
                "Go ahead and install the new valve."]

    def test_unit_rc20_turn6_conditional_held(self):
        pend = go.pending_isolation_tests(self.PEND)
        self.assertTrue(pend)
        out = go.hold_while_pending(self.CONDS[0] + "\nVERIFY: run slides 2-3 full cycles.", pend)
        self.assertNotIn("replace both front isolation", out)
        self.assertIn("Hold all part replacement", out)
        self.assertIn("VERIFY:", out)

    def test_property_no_replace_or_presumed_line_survives(self):
        pend = go.pending_isolation_tests(self.PEND)
        lead, tail = "Back-probe both coils and report volts. [General trade knowledge]", "VERIFY: run it 2-3 times. [General trade knowledge]"
        for x in self.CONDS + self.PRESUMED:
            for reply in (x, lead + "\n" + x, x + "\n" + tail, lead + "\n" + x + "\n" + tail):
                out = go.hold_while_pending(reply, pend)
                self.assertNotIn(x, out, reply)
                self.assertEqual(out.count("Hold all part replacement"), 1, reply)
                for keep in (lead, tail):
                    if keep in reply:
                        self.assertIn(keep, out)

    def test_no_pending_conditionals_untouched(self):
        for x in self.CONDS + self.PRESUMED:
            self.assertEqual(go.hold_while_pending(x, []), x)


class TestVerifyWordDoesNotExemptAReplace(unittest.TestCase):
    """e77941b RC20: every replace line that slipped the pending hold carried the word 'verify' somewhere, and the follow-up
    exemption matched 'verify' anywhere in the line."""
    PEND = ["Plumbing check and gray-coil unplug are still pending."]
    SLIPPED = ["Did both front cartridges get replaced, and did the fronts stay put on the verify cycles?",
               "Requested authorization: replace complete hydraulic power unit / manifold assembly, then bleed, resync, and cycle-verify.",
               "Nothing else to check: cartridges already failed verify. Replace both front jack assemblies as a matched set.",
               "Recorded path (cartridges already failed verify): replace the remaining front-jack hoses as a matched pair, then bleed and resync.",
               "After that, replace the pump motor and verify."]
    FOLLOW = ["VERIFY: run slides and other circuits 2-3 full cycles and confirm both front jacks stay put.",
              "After install: bleed the front circuit, then resync the front jacks.",
              "After the cartridge (or jack) repair: run slides again, 2-3 full cycles, and confirm the jacks stay put.",
              "Reconnect the brown wire and verify one full try."]

    def test_unit_slipped_lines_are_held(self):
        for x in self.SLIPPED:
            out = go.hold_while_pending(x, self.PEND)
            self.assertNotIn(x, out)
            self.assertTrue(out.startswith("Hold all part replacement"), x)

    def test_property_follow_ups_kept_replaces_held_in_any_mix(self):
        import itertools
        for a, b in itertools.product(self.SLIPPED, self.FOLLOW):
            for reply in (a + "\n" + b, b + "\n" + a):
                out = go.hold_while_pending(reply, self.PEND)
                self.assertNotIn(a, out, reply)
                self.assertIn(b, out, reply)
                self.assertEqual(out.count("Hold all part replacement"), 1, reply)
