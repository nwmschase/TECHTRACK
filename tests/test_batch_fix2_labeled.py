"""Batch fix 2 (Leader 2026-10-14 8:57 PM): raw manual steps become labeled checks."""
import re
import unittest

from bay_procedure import _labeled_generic_steps

PG = [
    "onnector: Check for voltage at pin #6.",
    "Check for +12V DC at the large battery terminal of the motor solenoid.",
    "If no voltage or if voltage is less than +12V DC, recharge battery or replace power cable.",
    "Air Distribution Box (ADB) Shroudx 1 ?",
    "If this check fails, stay on it.",
    "Check for continuity between pin #1 of the 6-pin connector and ground.",
    "If there is no continuity, the switch is bad.",
]


class TestLabeledGenericSteps(unittest.TestCase):
    def setUp(self):
        self.steps = _labeled_generic_steps(PG)

    def test_each_step_is_an_action_with_labels(self):
        self.assertEqual(len(self.steps), 2)
        for step in self.steps:
            self.assertRegex(step, r"^Step \d+: (?:Check|Test|Measure)\b")
            for label in ("Where:", "Do this:", "Bad looks like:", "Next:"):
                self.assertIn(label, step)

    def test_labels_come_from_the_manual(self):
        self.assertIn("Where: At the large battery terminal of the motor solenoid.", self.steps[0])
        self.assertIn("If it fails: Recharge battery or replace power cable.", self.steps[0])
        self.assertIn("Good looks like: Continuity is present.", self.steps[1])
        self.assertIn("confirmed correction", self.steps[-1])

    def test_parts_dump_and_filler_are_dropped(self):
        blob = " ".join(self.steps)
        self.assertNotIn("Shroudx", blob)
        self.assertNotIn("stay on it", blob)

    def test_headings_are_short(self):
        for step in self.steps:
            head = re.match(r"^Step \d+: ([^.]+)\.", step).group(1)
            self.assertLessEqual(len(head.split()), 12)

    def test_no_if_lines_means_no_labeled_steps(self):
        self.assertEqual(_labeled_generic_steps(["Check the fuse at the panel."]), [])


if __name__ == "__main__":
    unittest.main()
