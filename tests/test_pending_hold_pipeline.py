"""Leader 11:25 PM checker items (RC20 e77941b shape), end to end through official_turn with a stubborn model:
(a1) the pending hold does not drop after the tech reports an unauthorized swap ("Replaced X ... still pending");
(a2) NO-REPEAT ("anything else to check?" asked again and again) never turns into a GD-directed replace while a test is pending.
Generic hydraulic-leveling text; no case keys in GD code."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402
from tests.test_selector_root_fix import Lib  # noqa: E402

DOC = {"id": 7, "title": "Hydraulic Leveling Shop Writeup", "brand": "Generic", "models": "HL1", "doc_number": "H1"}
TEXT = {7: "Jacks drift when other circuits pressurize. Unplug the coils and watch the jacks. Cap the manifold ports. "
           "Replaceable parts: holding-valve cartridges, power unit, jacks, hoses."}
PEND = "Plumbing check and gray-coil unplug are still pending."
SWAP = ("Replaced both front holding-valve cartridges, bled, and resynced; front jacks still drift when other circuits "
        "pressurize. Plumbing check and gray-coil unplug remain pending.")
ASK_AGAIN = "Before I replace that - anything else to check?"
# GD lines that slipped on e77941b (turns 5-12), replayed as a stubborn model
SLIPPED = [
    "Back-probe both front coils with a slide running and report volts. [General trade knowledge]\n"
    "Did both front cartridges get replaced, and did the fronts stay put on the verify cycles?",
    "Requested authorization: replace complete hydraulic power unit / manifold assembly, then bleed, resync, and cycle-verify.",
    "Nothing else to check: coils stayed ~0 V, cartridges already failed verify. Replace both front jack assemblies as a matched set. "
    "[General trade knowledge]\nVERIFY: run slides 2-3 full cycles and confirm both front jacks stay put. [General trade knowledge]",
    "Recorded path (cartridges, power unit and both jacks already failed verify): replace the remaining front-jack hoses as a matched "
    "pair, then bleed and resync. [General trade knowledge]",
    "If the front jacks still move with no voltage on the coils: replace both front holding-valve cartridges as a matched pair.",
]


def _replace_lines(reply):
    reply = re.sub(r'"[^"\n]*"', '""', reply)  # quoted tech words are not GD directives
    return [ln for ln in reply.splitlines() if not ln.startswith("Hold all part replacement")
            and ((go.unnegated_condemn(ln) and not go._follow_up_line(ln)) or go.PRESUMED_REPLACE_RE.search(ln))]


def _walk(answers, replies):
    hist, pin, outs = [], {}, []
    for a, r in zip(answers, replies):
        out = go.official_turn(a, "Leveling", "Generic HL1", hist, library=Lib([DOC], TEXT),
                               chat_fn=lambda m, t, e, r=r: r, pin_store=pin)
        outs.append(out["reply"])
        hist += [{"role": "user", "content": a}, {"role": "assistant", "content": out["reply"]}]
    return outs, pin


class TestHoldSurvivesTechSwap(unittest.TestCase):
    def test_hold_stays_after_unauthorized_swap(self):
        answers = ["Front jacks drift on their own when the slides run.", PEND, SWAP, ASK_AGAIN,
                   "Replaced the power unit; front jacks still drift. Plumbing check and gray-coil unplug remain pending.",
                   ASK_AGAIN, ASK_AGAIN]
        replies = ["Run the slides and watch both front jacks; report which moves. [General trade knowledge]"] + \
                  [SLIPPED[i % len(SLIPPED)] for i in range(len(answers) - 1)]
        outs, pin = _walk(answers, replies)
        for i, o in enumerate(outs[1:], 2):
            self.assertEqual(_replace_lines(o), [], f"turn {i}: {o}")
        held = ("Hold all part replacement", "Before condemning", "No part is replaced")
        self.assertTrue(all(any(h in o for h in held) for o in outs[2:6]), outs)  # held, not silently obeyed, through the swap


class TestNoRepeatNeverBecomesACondemn(unittest.TestCase):
    def test_property_every_slipped_line_x_repeated_question(self):
        for line in SLIPPED:
            answers = ["Front jacks drift on their own when the slides run.", PEND, SWAP] + [ASK_AGAIN] * 4
            replies = ["Run the slides and watch both front jacks; report which moves. [General trade knowledge]"] + [line] * 6
            outs, pin = _walk(answers, replies)
            for i, o in enumerate(outs[1:], 2):
                self.assertEqual(_replace_lines(o), [], f"{line[:50]} turn {i}: {o}")

    def test_recorded_result_releases_the_hold(self):
        # Root rule (Leader 2026-10-17 1:45 AM): recording the pending results ends the STRUCTURAL hold; the cartridge replace then
        # still needs the cartridge's OWN decisive result (a coil-unplug observation is not a cartridge result), and passes once it has one.
        answers = ["Front jacks drift on their own when the slides run.", PEND,
                   "Plumbing check done: no leaks at the manifold. Gray-coil unplug test done: jacks still drift with coils unplugged.",
                   "Front holding-valve cartridges: both bypass fluid on the manual leak-down check with the coils unplugged "
                   "(jacks drop 2 in. in 5 min)."]
        replace = "Replace both front holding-valve cartridges as a matched pair. [General trade knowledge]"
        replies = ["Run the slides and watch both front jacks; report which moves. [General trade knowledge]",
                   SLIPPED[4], replace, replace]
        outs, _ = _walk(answers, replies)
        self.assertEqual(_replace_lines(outs[1]), [], outs[1])
        self.assertIn("isolation test is still pending", outs[1])
        self.assertNotIn("isolation test is still pending", outs[2])
        self.assertEqual(_replace_lines(outs[2]), [], outs[2])
        self.assertTrue(re.search(r"Replace both front holding-valve cartridges", outs[3]), outs[3])
        self.assertNotIn("Hold all part replacement", outs[3])


class TestNoRepeatAcceptsOnlyResults(unittest.TestCase):
    def test_question_or_pending_is_not_accepted(self):
        for ans in (ASK_AGAIN, PEND, "Not done yet.", "What else should I check?"):
            self.assertFalse(go.answer_has_result(ans), ans)
        for ans in ("Winding and ground checks look normal/OK.", "Coil reads 32 ohms.", "14.2 V idle, 5-10 V during the try."):
            self.assertTrue(go.answer_has_result(ans), ans)

    def test_capped_question_routes_to_record_or_tech_line(self):
        pin = {}
        ask = "Unplug both front coils, run the slides, and report whether the jacks move. [General trade knowledge]"
        for _ in range(2):
            go.cap_repeats(ask, pin, "x")
        out = go.cap_repeats(ask, pin, ASK_AGAIN)
        self.assertNotIn("Accepted as reported", out)
        self.assertIn("shop/OEM tech line", out)
        self.assertNotIn(ask, out)


class TestHoldLineNeverCappedAndNoOrphanInstallSteps(unittest.TestCase):
    """642b658 RC20 turns 9-12: NO-REPEAT capped the hold line on its third turn, and 'After install: bleed ...' survived its held
    replace; the tech replaced twice."""
    HOLD = ('Hold all part replacement: an isolation test is still pending ("Plumbing check is still pending."). No part is replaced '
            'or submitted for replacement until that result is recorded. Do that test, or call the shop/OEM tech line with the findings '
            'so far. [General trade knowledge]')

    def test_property_guard_lines_survive_any_number_of_repeats(self):
        for g in (self.HOLD, "Before condemning the cartridges, record its isolation reading and send it. [General trade knowledge]",
                  "That test has been asked twice and will not be asked again. No result is recorded for it yet. [General trade knowledge]"):
            pin = {}
            for i in range(6):
                out = go.cap_repeats("Bleed the front circuit. [General trade knowledge]\n" + g, pin, ASK_AGAIN)
                self.assertIn(g, out, f"repeat {i}")

    def test_orphan_after_install_dropped_only_when_a_replace_was_held(self):
        pend = [PEND]
        for after in ("After install: bleed the front circuit, then Zero Point.", "After replacing both cartridges, bleed and resync.",
                      "After the new power unit is in: bleed, resync both front jacks.", "After the cartridge (or jack) repair: run slides again."):
            out = go.drop_orphan_install_steps(go.hold_while_pending("Replace both front cartridges as a matched pair.\n" + after +
                                                                     "\nVERIFY: run slides 2-3 times.", pend))
            self.assertNotIn(after, out)
            self.assertIn("VERIFY: run slides 2-3 times.", out)
            self.assertEqual(go.drop_orphan_install_steps(go.hold_while_pending(after, pend)), after)  # nothing held: left alone
            live = "Replace both front cartridges as a matched pair.\n" + after
            self.assertEqual(go.drop_orphan_install_steps(live), live)  # no hold, live replace: its install step stays

    def test_end_to_end_hold_present_on_every_replace_turn(self):
        answers = ["Front jacks drift on their own when the slides run.", PEND] + [ASK_AGAIN, PEND] * 4
        replies = ["Run the slides and watch both front jacks; report which moves. [General trade knowledge]"] + \
                  ["Coils not commanded, so this is leak-by on the front pair. Replace both front cartridges as a matched pair.\n"
                   "After install: bleed the front circuit, then Zero Point.\nVERIFY: run slides 2-3 full cycles."] * 9
        outs, _ = _walk(answers, replies)
        for i, o in enumerate(outs[1:], 2):
            self.assertEqual(_replace_lines(o), [], f"turn {i}: {o}")
            self.assertNotIn("After install", o, f"turn {i}")
            self.assertTrue(any(h in o for h in ("Hold all part replacement", "Before condemning")), f"turn {i}: {o}")
