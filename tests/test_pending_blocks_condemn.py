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
        self.assertIn("If the coil unplug stops the drift, replace the coil.", out)  # repair decision kept
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
