"""LOCKED (Leader 2026-10-16 6:23 PM, RCA-RC29-REPEAT-LOOP): condemn guard reads the whole session; a normal/OK test result given in
answer to a GD request counts as recorded; GD never asks the same test a third time. Do not edit without Leader clearance."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402
from tests.test_selector_root_fix import Lib  # noqa: E402

DOC = {"id": 1, "title": "Chill 15K Low Profile Air Conditioner (R32) Troubleshooting and Service Manual", "brand": "Chill",
       "models": "FACR15LPSA2", "doc_number": "C1"}
TEXT = {1: "Troubleshooting. Compressor noise. Check capacitor. Measure compressor winding resistance. Replaceable parts list A-K."}
WINDING_ASK = ("Meter on ohms, low range. Probe compressor Common-to-Run, Common-to-Start and Run-to-Start. Report the three ohm readings. "
               "[General trade knowledge]")
OK = "Winding and ground checks look normal/OK."


def _walk(replies, answers, model="Chill FACR15LPSA2"):
    hist, pin, outs = [], {}, []
    for i, a in enumerate(answers):
        r = replies[i]
        # a stubborn model: the repeat-retry gets the same text back
        out = go.official_turn(a, "Air Conditioners", model, hist, library=Lib([DOC], TEXT), chat_fn=lambda m, t, e, r=r: r,
                               pin_store=pin)
        outs.append(out["reply"])
        hist += [{"role": "user", "content": a}, {"role": "assistant", "content": out["reply"]}]
    return outs, pin


class TestRC29Shape(unittest.TestCase):
    def test_normal_ok_answer_to_the_request_counts_as_recorded(self):
        self.assertEqual(go.unproven_condemns("Replace the compressor.", [OK], [WINDING_ASK]), [])

    def test_visual_ok_is_not_a_test_result(self):
        self.assertEqual(go.unproven_condemns("Replace inverter PCB.", ["Inverter PCB plugs look seated/OK."], ["Check the plugs."]),
                         ["inverter pcb"])

    def test_rc29_reaches_the_whole_unit_oem_call_without_looping(self):
        oem = ("Compressor-tracked noise with windings OK points to the sealed system. Document and submit to the OEM for authorization.\n"
               "Requested authorization: Replace complete rooftop unit (FACR15LPSA2). [General trade knowledge]")
        answers = ["Customer says the A/C grinds while running.", "Verified: grinding with compressor running, fan-only quiet.",
                   "Compressor 7.27 A @117 VAC, noise inside the compressor shell.", OK, OK, OK]
        replies = ["Run it on COOL and report the noise. [General trade knowledge]", "Clamp compressor common, report amps. [General trade knowledge]",
                   WINDING_ASK, WINDING_ASK, WINDING_ASK, oem]
        outs, pin = _walk(replies, answers)
        asks = sum("common-to-run" in o.lower() for o in outs)
        self.assertLessEqual(asks, 2)
        self.assertIn("Accepted as reported", outs[4])
        self.assertIn("replace complete rooftop unit", outs[5].lower())
        self.assertNotIn("before condemning", outs[5].lower())


class TestRewordedThirdAsk(unittest.TestCase):
    """RC22 shape: the same test re-worded each time; similarity is not transitive, so a group must keep every wording."""

    def test_reworded_third_ask_is_capped(self):
        asks = ["If harness-to-ground is open, plug the valve back in. Meter DC volts, 20 V range, on the brown wire at the valve vs chassis ground. Gas switch ON during a try. Report volts during TFI.",
                "Plug the gas-valve brown connector back in. Meter DC volts, 20 V range. Probe brown wire at the valve vs heater chassis ground. Gas switch ON during a try. Report volts during TFI.",
                "Plug the brown connector fully onto the gas valve. Meter DC volts, 20 V range. Probe the brown wire at the valve (valve side of the plug) vs heater chassis ground. Gas switch ON during a try. Report volts during TFI."]
        pin = {}
        outs = [go.cap_repeats(a, pin, "Brown at the valve looks normal/OK.") for a in asks]
        self.assertEqual(outs[:2], asks[:2])
        self.assertIn("Accepted as reported", outs[2])


class TestRepairLinesAreNotRequests(unittest.TestCase):
    """RC12 shape: the tech keeps asking 'anything else?'; the repair and its VERIFY are restated, never capped."""

    def test_repair_and_verify_survive_repeats(self):
        r = ("Replace inverter PCB (Part AL) and cooling fan (Part AB) together. [General trade knowledge]\n"
             "Reconnect 12 V, knob at 4-5. Report whether compressor/fan run and whether E2 returns.\n"
             "VERIFY: run 2 hours and confirm E2 stays off. [General trade knowledge]")
        pin = {}
        for _ in range(5):
            out = go.cap_repeats(r, pin, "Before I replace that - anything else to check?")
        self.assertEqual(out, r)


class TestNoRepeatProperty(unittest.TestCase):
    """PROPERTY: whatever the model emits, no session ever carries the same test request more than twice."""

    POOL = [WINDING_ASK, "Clamp the ammeter on compressor common. Report running amps. [General trade knowledge]",
            "Probe C, R and S to the compressor case on high ohms. Report each reading. [General trade knowledge]",
            "Check the run capacitor terminals and report what you see. [General trade knowledge]",
            "Read the nameplate RLA and LRA and report both numbers. [General trade knowledge]"]

    def test_no_request_more_than_twice(self):
        rng = random.Random(629)
        for trial in range(60):
            n = rng.randint(4, 12)
            replies = ["\n".join(rng.sample(self.POOL, rng.randint(1, 3))) for _ in range(n)]
            answers = ["Verified: noise with compressor running."] + [rng.choice([OK, "Looks normal/OK.", "7.2 A steady."]) for _ in range(n - 1)]
            outs, _ = _walk(replies, answers)
            for ask in self.POOL:
                sig = go._ask_sig(ask)
                count = sum(any(go._same_ask(sig, go._ask_sig(l)) for l in o.splitlines()) for o in outs)
                self.assertLessEqual(count, 2, (trial, ask))


if __name__ == "__main__":
    unittest.main()


class TestMechanicalObservationRule(unittest.TestCase):
    """Leader 8:23 PM (c): observation counts as isolation for a MECHANICAL failure when recorded against the part's own noun AND
    the pinned manual gives no electrical test for it."""
    SEC = "Inspect both motor/sprocket areas for flex. Check standoffs and cables vs the pre-punched holes."

    def test_observation_on_the_part_counts_without_an_electrical_test(self):
        self.assertEqual(go.unproven_condemns("Replace both motor assemblies.", ["Both motor/sprocket areas flex under load."],
                                              ["Inspect both motor areas."], self.SEC), [])

    def test_observation_does_not_count_when_the_manual_has_an_electrical_test(self):
        self.assertEqual(go.unproven_condemns("Replace both motor assemblies.", ["Both motor areas flex under load."], ["Inspect."],
                                              self.SEC + " Measure motor volts at the plug."), ["both motor assemblies"])

    def test_observation_on_the_system_is_not_the_part(self):
        self.assertEqual(go.unproven_condemns("Replace the front lead-jack cartridge valve.", ["The front jacks drift on their own."],
                                              [""], ""), ["front lead-jack cartridge valve"])


class TestAdjustBeforeCondemn(unittest.TestCase):
    """When the pinned manual has adjustment/synchronization steps, one is recorded before any condemn (RC28 class)."""
    SEC = "Cable adjustment: with the room all the way in, take slack out of both bottom cables, then both top cables."

    def test_condemn_held_until_the_adjustment_is_recorded(self):
        self.assertEqual(go.unadjusted_condemns("Replace both motor assemblies.", ["Motors flex."], ["Inspect motors."], self.SEC),
                         ["both motor assemblies"])
        out = go.hold_for_adjustment("Replace both motor assemblies.", ["both motor assemblies"], self.SEC)
        self.assertIn("adjustment/synchronization step", out)
        self.assertIn("take slack out", out)

    def test_recorded_adjustment_releases_the_condemn(self):
        self.assertEqual(go.unadjusted_condemns("Replace both motor assemblies.", ["Bottom and top cables went snug evenly; still crooked."],
                                                ["Take slack out of both bottom cables, then top."], self.SEC), [])

    def test_no_adjustment_in_the_manual_no_hold(self):
        self.assertEqual(go.unadjusted_condemns("Replace the fuse.", ["fuse reads open"], [""], "Check the 15A fuse."), [])


class TestNpfAndSplit(unittest.TestCase):
    """NPF never while the complaint is still present; a bypass/alternate-path result is the split isolation (RC14 class)."""

    def test_npf_held_while_complaint_present(self):
        ev = go.npf_blocked("No Problem Found - operating as designed.", ["Amps normal; with the ceiling controls it still isn't blowing cold."])
        self.assertTrue(ev)
        self.assertIn("Not No Problem Found", go.hold_npf("No Problem Found - operating as designed.", ev))

    def test_npf_allowed_when_not_reproduced(self):
        self.assertEqual(go.npf_blocked("No Problem Found - operating as designed.", ["Ran 30 min, cools to 58F supply, complaint not reproduced."]), "")

    def test_split_result_isolates_the_failing_path_part(self):
        msgs = ["With ceiling controls on high cool the air is not cold. Control bypass cools."]
        self.assertEqual(go.unproven_condemns("Replace the ceiling thermostat/selector.", msgs, [""], ""), [])


class TestPendingDecisiveTest(unittest.TestCase):
    def test_pending_is_unavailable(self):
        self.assertTrue(go.UNAVAILABLE_RE.search("Battery-jump test is still pending with tech line."))
        self.assertIn("REPAIR DECISION", go.PENDING_RULE)
