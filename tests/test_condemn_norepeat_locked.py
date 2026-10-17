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
