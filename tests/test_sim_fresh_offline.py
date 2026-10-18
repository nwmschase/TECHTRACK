"""Offline proof of the new harness wiring (no LLM: every role is a scripted fake)."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import gd_sim_fresh as sim  # noqa: E402
from gd_pages import Page, StubPageFinder  # noqa: E402

CASE = """# RC99 - test case
Unit: Acme fridge X1
Complaint (customer): freezes contents; E2 blinking.
Found on arrival: ice in drain.
Tech readings: fan 10.4 V.
Cause: freezer fan fault.
Fix: replace freezer fan; cools OK.
Status: KNOWN FIX
PASS criteria: fan tested before replacement.
## Live GD run
1. App: replace the board."""


class TestSimHarness(unittest.TestCase):
    def test_tech_never_sees_the_answer(self):
        notes, key = sim.split_case(CASE)
        for hidden in ("freezer fan fault", "replace freezer fan", "KNOWN FIX", "PASS criteria", "replace the board"):
            self.assertNotIn(hidden, notes)
            self.assertIn(hidden, key)
        for shown in ("Acme fridge X1", "freezes contents", "ice in drain", "fan 10.4 V"):
            self.assertIn(shown, notes)
        self.assertNotIn("looks normal/OK", sim.TECH_SYS.replace('"OK"', ""))
        self.assertIn("not measured", sim.TECH_SYS)

    def test_session_flow_with_fakes(self):
        st = lambda **k: "<state>" + json.dumps(k) + "</state>"
        gd = iter(["Did you see it freeze?\n" + st(summary="a"),
                   "Replace the freezer fan [Acme p.29]. Run it after.\n" + st(summary="b"),
                   "Job closed.\n" + st(closed=True, summary="c", repair={"done": True, "verified": True, "what": "fan", "quote": "cools"})])
        tech = iter(["It freezes stuff and blinks E2.", "Yes, saw it.", "Done, it cools now."])
        seen_by_tech = []

        def tech_chat(msgs):
            seen_by_tech.append(json.dumps(msgs))
            return next(tech)
        refs = iter(['{"repair_directed": false}', '{"repair_directed": true, "what": "fan", "matches_fix": true}'])
        finder = StubPageFinder(manuals=[{"doc_id": "L1", "title": "Acme"}],
                                pages=[Page("L1", "Acme", "29", 29, "fan test 2021128850", "entry")])
        v, hist, store = sim.run_case(CASE, "Refrigerators", "Acme X1", finder=finder, gd_chat=lambda m, t, e: next(gd),
                                      tech_chat=tech_chat, referee_chat=lambda m: next(refs),
                                      judge_chat=lambda m: '{"ending": "closed", "fix_reached": true}')
        self.assertEqual(v["harness_ending"], "closed")
        self.assertTrue(v["pass_eligible"])
        self.assertEqual(v["gd_turns"], 3)
        self.assertTrue(all("replace freezer fan" not in s for s in seen_by_tech))
        self.assertIn("complaint is gone", seen_by_tech[-1])

    def test_cap_is_not_a_pass_and_invented_numbers_listed(self):
        st = "<state>{\"summary\": \"s\"}</state>"
        finder = StubPageFinder(manuals=[{"doc_id": "L1", "title": "Acme"}], pages=[Page("L1", "Acme", "2", 2, "call 574-825-4600", "entry")])
        v, _, _ = sim.run_case(CASE, "Refrigerators", "Acme X1", finder=finder, max_turns=2,
                               gd_chat=lambda m, t, e: "Call 574-825-4600 or 800-555-1212, order part 99887766.\n" + st,
                               tech_chat=lambda m: "ok", referee_chat=lambda m: "{}", judge_chat=lambda m: "garbage")
        self.assertEqual(v["harness_ending"], "capped")
        self.assertFalse(v["pass_eligible"])
        self.assertTrue(v["judge_error"])
        self.assertEqual(v["invented_numbers"], ["800-555-1212", "99887766"])

    def test_cli_refuses_without_ok(self):
        sys.argv = ["x", "--case", "RC12", "--out", "/tmp/x", "--max-usd", "1"]
        with self.assertRaises(SystemExit) as e:
            sim.main()
        self.assertIn("Refusing", str(e.exception))


if __name__ == "__main__":
    unittest.main()
