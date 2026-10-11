"""Established profiles v1.0: Thetford and S01 PDF and GD outputs."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import manual_figures as mf
import profile_check
from bay_procedure import compile_bay_procedure, render_bay_procedure_pdf
from gd_library_coach import avoid_duplicate_reply
from tests.test_s01_facr_standard import _sheet
from tests.test_thetford_step_template import BREAKER_PDF, VALVE_PDF, _packet


def _thetford():
    return compile_bay_procedure(
        concern="Thetford 42070 leaks under the flush lever",
        brand="Thetford",
        model="42070",
        category="Plumbing / Toilets",
        chunks=[
            _packet("Thetford Water Valve Kit 42109", VALVE_PDF),
            _packet("Thetford Vacuum Breaker Kit 34123/34122", BREAKER_PDF),
        ],
    )


def _failures(rules):
    return [f"{rule.name}: {rule.detail}" for rule in rules if not rule.ok]


def _transcript(turns):
    """turns is (user, assistant) pairs."""
    lines = []
    for user, assistant in turns:
        lines.append(f"USER: {user}\nASSISTANT:\n{assistant}")
    return "\n\n".join(lines)


class TestProfileDocs(unittest.TestCase):
    def test_v1_files_are_the_standard(self):
        readme = (ROOT / "docs" / "profiles" / "README.md").read_text(encoding="utf-8")
        guided = (ROOT / "docs" / "profiles" / "GD-PROFILE.md").read_text(encoding="utf-8")
        pdf = (ROOT / "docs" / "profiles" / "PDF-PROFILE.md").read_text(encoding="utf-8")
        self.assertIn("Before ANY TechTrack change", readme)
        self.assertIn("Established by Chase on 2026-10-11.", guided)
        self.assertIn("No rigid label block. No step counter in the chat.", guided)
        self.assertIn("May ask the tech for a photo when that would really help.", guided)
        self.assertIn("Established by Chase on 2026-10-11.", pdf)
        self.assertIn("Before you start", pdf)
        self.assertIn("Thetford-42070", pdf)
        self.assertIn("Version 1.2", guided)
        self.assertIn("## Performance scorecard (grade every reviewed session, PASS/FAIL per line)", guided)
        self.assertIn("Any FAIL on 1, 8, or 10 is an automatic overall FAIL.", guided)
        self.assertIn("## Performance scorecard (grade every PDF, PASS/FAIL per line)", pdf)
        self.assertIn("Any FAIL on 2, 7, 8, or 9 is an automatic overall FAIL.", pdf)
        log = (ROOT / "docs" / "profiles" / "PROFILE-CHANGE-LOG.md").read_text(encoding="utf-8")
        self.assertIn("| 2026-10-11 10:42 AM | GD + PDF | 1.2 |", log)


class TestPdfProfile(unittest.TestCase):
    def test_thetford_pdf_matches_the_profile(self):
        pdf = render_bay_procedure_pdf(_thetford())
        rules = profile_check.check_pdf_bytes(pdf)
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))

    def test_s01_pdf_matches_the_profile(self):
        pdf = render_bay_procedure_pdf(_sheet())
        rules = profile_check.check_pdf_bytes(pdf)
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))


class TestGdProfile(unittest.TestCase):
    def test_thetford_chat_matches_the_profile(self):
        history = []
        latest = "toilet leaks under the flush lever when flushing"
        turns = []
        for _ in range(4):
            reply = avoid_duplicate_reply(
                "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
                history,
                latest,
                "Plumbing / Toilets",
                "Style II 42070",
            )
            turns.append((latest, reply))
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
            latest = "Not checked yet"
        turns.append(("show me", "The manual shows Fig. 1 on the cited page.\n[figure] 42088 page 3\nWhat do you see?"))
        rules = profile_check.check_transcript(_transcript(turns))
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))
        self.assertFalse(mf.tech_asked_for_manual_figure("Not checked yet"))
        self.assertTrue(mf.tech_asked_for_manual_figure("show me"))
        self.assertTrue(mf.tech_asked_for_manual_figure("where is it"))
        self.assertTrue(mf.tech_asked_for_manual_figure("what does it look like"))

    def test_s01_chat_matches_the_profile(self):
        proving = mf.facr_proving_layout()["steps"]
        repair = mf.facr_rr_layout()["steps"]
        answers = (
            "Water is leaking inside while the unit runs.",
            "The ceiling is dry.",
            "The unit is running in COOL.",
            "The breaker is off.",
        )
        steps = [proving[0], proving[1], proving[3], repair[0]]
        turns = []
        for answer, step, number in zip(answers, steps, range(1, 5)):
            turns.append((answer, mf.format_chat_turn(step, number, len(steps))))
        rules = profile_check.check_transcript(_transcript(turns))
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))

    def test_a_photo_is_not_asked_on_every_proving_step(self):
        lines = [mf.thetford_proving_line(key) for key in ("supply", "vacuum", "valve", "flange")]
        asked = [line for line in lines if mf.PHOTO_VISUAL in line]
        self.assertLess(len(asked), len(lines))
        self.assertNotIn(mf.PHOTO_VISUAL, mf.thetford_proving_line("valve"))
        self.assertIn(mf.PHOTO_VISUAL, mf.thetford_proving_line("vacuum"))

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
        for number in (1, 2, 6, 8, 9):
            self.assertIn(f"{number}. MANUAL", summary)
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
        self.assertIn("Lines 10.", summary)

    def test_a_blame_on_reopen_fails_the_manual_line(self):
        text = _transcript([
            ("It came back. It wasn't the fix.", "This was your fault. What do you see?"),
        ])
        summary = profile_check.gate_summary(profile_check.check_transcript(text))
        self.assertIn("9. FAIL", summary)
        self.assertIn("Automatic FAIL: no.", summary)

    def test_thetford_pdf_scorecard_leaves_human_lines_manual(self):
        rules = profile_check.check_pdf_bytes(render_bay_procedure_pdf(_thetford()))
        self.assertEqual(_failures(rules), [])
        summary = profile_check.gate_summary(rules)
        self.assertTrue(summary.startswith("## Bay PDF scorecard"))
        self.assertIn("2. PASS", summary)
        self.assertIn("7. MANUAL", summary)
        self.assertIn("8. MANUAL", summary)
        self.assertIn("Automatic FAIL: no.", summary)
        self.assertRegex(summary, r"Result: \d+/10\.")
        report = profile_check.format_report(rules)
        self.assertIn("## Bay PDF scorecard", report)
        self.assertTrue(report.endswith("PASS"))


if __name__ == "__main__":
    unittest.main()
