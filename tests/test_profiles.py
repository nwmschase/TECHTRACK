"""Established profiles: the GD profile doc and GD transcript checks (the Bay PDF profile is retired)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import manual_figures as mf
import profile_check


def _failures(rules):
    return [f"{rule.name}: {rule.detail}" for rule in rules if not rule.ok]


def _transcript(turns):
    """turns is (user, assistant) pairs."""
    lines = []
    for user, assistant in turns:
        lines.append(f"USER: {user}\nASSISTANT:\n{assistant}")
    return "\n\n".join(lines)


class TestProfileDocs(unittest.TestCase):
    def test_profiles_are_short_descriptions_after_the_2026_10_23_order(self):
        readme = (ROOT / "docs" / "profiles" / "README.md").read_text(encoding="utf-8")
        guided = (ROOT / "docs" / "profiles" / "GD-PROFILE.md").read_text(encoding="utf-8")
        self.assertIn("Version 2.0", guided)
        self.assertIn("Chase", guided)
        self.assertLess(len(guided.split()), 400)          # a short statement, not a rule list
        self.assertNotIn("Performance scorecard", guided)
        self.assertNotIn("automatic overall FAIL", guided)
        self.assertIn("REMOVED-RULES-2026-10-23", guided + readme)
        # The Bay PDF builder is retired (Chase 2026-10-24): GD-PROFILE.md is the only profile.
        self.assertEqual(sorted(p.name for p in (ROOT / "docs" / "profiles").glob("*-PROFILE.md")), ["GD-PROFILE.md"])
        self.assertFalse((ROOT / "docs" / "profiles" / "PDF-PAST-FAILS.md").exists())
        log = (ROOT / "docs" / "profiles" / "PROFILE-CHANGE-LOG.md").read_text(encoding="utf-8")
        self.assertIn("| 2026-10-11 10:42 AM | GD + PDF | 1.2 |", log)      # earlier rows kept as history
        self.assertIn("| 2026-10-16 9:40 PM | PDF | 1.5 |", log)
        self.assertIn("2026-10-23 8:34 AM", log)
        self.assertIn("Approved by Chase in chat 2026-10-23 8:34 AM", log)


class TestGdProfile(unittest.TestCase):


    def test_the_checker_rejects_a_form_and_an_unasked_figure(self):
        form = _transcript([
            ("the pedal is off", "Where: At the pedal.\nDo this:\n1. Pull the pedal.\n"),
        ])
        rules = {rule.name: rule for rule in profile_check.check_transcript(form)}
        self.assertFalse(rules["no_label_block"].ok)
        figure = _transcript([
            ("yes", "[figure] 42109 Fig. 1"),
        ])
        rules = {rule.name: rule for rule in profile_check.check_transcript(figure)}
        self.assertFalse(rules["no_figure_without_ask"].ok)
        repeat = _transcript([
            ("leak", "Check the supply. What do you see?"),
            ("still leaking", "Check the supply. What do you see?"),
        ])
        rules = {rule.name: rule for rule in profile_check.check_transcript(repeat)}
        self.assertFalse(rules["no_repeats"].ok)


class TestScorecard(unittest.TestCase):
    def test_gd_scorecard_prints_manual_lines_and_a_gate_block(self):
        text = _transcript([
            ("The supply connection is tight and dry.", "The supply connection is dry.\nWhat do you see?"),
            ("show me", "The manual shows Fig. 1.\n[figure]\nWhat do you see?"),
        ])
        rules = profile_check.check_transcript(text)
        summary = profile_check.gate_summary(rules)
        for number in (1, 2):
            self.assertIn(f"{number}. MANUAL", summary)
        for number in (6, 8, 9):
            self.assertIn(f"{number}. PASS", summary)
        self.assertIn("Result: ", summary)
        self.assertIn("/10.", summary)
        self.assertIn("Automatic FAIL: no.", summary)
        self.assertIn("Stayed on the shop manual pathways", summary)
        self.assertTrue(summary.startswith("## Guided Diagnostics scorecard"))
        failed = [rule for rule in rules if rule.scorecard and rule.status == "FAIL"]
        self.assertEqual(failed, [])

    def test_a_filler_line_fails_gd_line_10_automatically(self):
        text = _transcript([
            ("leak", "Not stated in this sheet. What do you see?"),
        ])
        summary = profile_check.gate_summary(profile_check.check_transcript(text))
        self.assertIn("10. FAIL", summary)
        self.assertIn("Automatic FAIL: yes.", summary)
        self.assertRegex(summary, r"Lines .*\b10\b")

    def test_a_blame_on_reopen_fails_the_manual_line(self):
        text = _transcript([
            ("It came back. It wasn't the fix.", "This was your fault. What do you see?"),
        ])
        summary = profile_check.gate_summary(profile_check.check_transcript(text))
        self.assertIn("9. FAIL", summary)
        self.assertIn("Automatic FAIL: no.", summary)


    def test_a_how_block_fails_the_how_line(self):
        text = _transcript([
            ("show me", "How (Thetford, page 7): Tools: not stated.\nWhat do you see?"),
        ])
        summary = profile_check.gate_summary(profile_check.check_transcript(text))
        self.assertIn("2. FAIL", summary)
        self.assertIn("10. FAIL", summary)

    def test_a_photo_on_a_plain_step_fails_line_6(self):
        text = _transcript([
            ("yes", "Set the clock.\nSend a photo of what you see.\nWhat do you see?"),
        ])
        summary = profile_check.gate_summary(profile_check.check_transcript(text))
        self.assertIn("6. FAIL", summary)

    def test_a_repair_without_safety_fails_line_8(self):
        text = _transcript([
            ("leak", "Remove the water valve.\nA good result is the valve is out.\nA bad result is it stays in.\nWhat do you see?\n📖 Source: Thetford 42109, page 1"),
        ])
        summary = profile_check.gate_summary(profile_check.check_transcript(text))
        self.assertIn("8. FAIL", summary)


if __name__ == "__main__":
    unittest.main()
