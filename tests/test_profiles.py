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


def _past_fails(rules):
    return {rule.name: rule for rule in rules if rule.name.startswith("PF-")}


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
        self.assertIn("Version 1.4", pdf)
        self.assertIn("PDF-PAST-FAILS.md", pdf)
        self.assertIn("## Performance scorecard (grade every reviewed session, PASS/FAIL per line)", guided)
        self.assertIn("Any FAIL on 1, 8, or 10 is an automatic overall FAIL.", guided)
        self.assertIn("## Performance scorecard (grade every PDF, PASS/FAIL per line)", pdf)
        self.assertIn("Any FAIL on 2, 7, 8, or 9 is an automatic overall FAIL.", pdf)
        log = (ROOT / "docs" / "profiles" / "PROFILE-CHANGE-LOG.md").read_text(encoding="utf-8")
        self.assertIn("| 2026-10-11 10:42 AM | GD + PDF | 1.2 |", log)
        self.assertIn("| 2026-10-11 10:50 AM | PDF | 1.3 |", log)
        self.assertIn("| 2026-10-11 12:11 PM | PDF | 1.4 |", log)


class TestPdfProfile(unittest.TestCase):
    def test_thetford_pdf_matches_the_profile(self):
        pdf = render_bay_procedure_pdf(_thetford())
        rules = profile_check.check_pdf_bytes(pdf)
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))
        self._past_fails_pass(rules)

    def test_s01_pdf_matches_the_profile(self):
        pdf = render_bay_procedure_pdf(_sheet())
        rules = profile_check.check_pdf_bytes(pdf)
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))
        self._past_fails_pass(rules)

    def _past_fails_pass(self, rules):
        pf = _past_fails(rules)
        self.assertEqual(len(pf), 33)
        failed = [f"{name} {rule.detail}" for name, rule in pf.items() if rule.status == "FAIL"]
        self.assertEqual(failed, [])
        self.assertEqual(pf["PF-10"].status, "PASS")
        self.assertIn("once per section", pf["PF-10"].detail)
        self.assertEqual(pf["PF-13"].status, "PASS")
        self.assertIn("page", pf["PF-13"].detail)
        report = profile_check.format_report(rules)
        self.assertIn("PF-01 PASS", report)
        self.assertIn("PF-33 PASS", report)
        self.assertIn("## Bay PDF scorecard", report)
        self.assertTrue(report.endswith("PASS"))


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
            turns.append((answer, mf.strip_html_comments(mf.format_chat_turn(step, number, len(steps)))))
        rules = profile_check.check_transcript(_transcript(turns))
        self.assertEqual(_failures(rules), [], "\n".join(profile_check.format_report(rules).splitlines()))

    def test_a_photo_is_not_asked_on_every_proving_step(self):
        lines = [mf.thetford_proving_line(key) for key in ("supply", "vacuum", "valve", "flange")]
        asked = [line for line in lines if mf.PHOTO_VISUAL in line]
        self.assertLess(len(asked), len(lines))
        # v4.19.59: the valve check now looks for a weep (Leader: diagnosis is a check), so it may ask once.
        self.assertLessEqual(mf.thetford_proving_line("valve").count(mf.PHOTO_VISUAL), 1)
        self.assertNotIn(mf.PHOTO_VISUAL, mf.thetford_proving_line("vacuum"))
        self.assertIn("Tell me what you see.", mf.thetford_proving_line("vacuum"))

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

    def test_thetford_pdf_scorecard_is_ten_of_ten(self):
        rules = profile_check.check_pdf_bytes(render_bay_procedure_pdf(_thetford()))
        self.assertEqual(_failures(rules), [])
        summary = profile_check.gate_summary(rules)
        self.assertTrue(summary.startswith("## Bay PDF scorecard"))
        self.assertIn("2. PASS", summary)
        self.assertIn("7. PASS", summary)
        self.assertIn("8. PASS", summary)
        self.assertIn("Result: 10/10.", summary)
        self.assertIn("Automatic FAIL: no.", summary)
        report = profile_check.format_report(rules)
        self.assertIn("## Bay PDF scorecard", report)
        self.assertTrue(report.endswith("PASS"))
        pf = _past_fails(rules)
        manual = [name for name, rule in pf.items() if rule.status == "MANUAL"]
        self.assertEqual(manual, ["PF-32"])

    def test_an_invented_caption_fails_line_7(self):
        text = "\n".join([
            "CONCERN\nleak\nMODEL\n42070\nPRIMARY\nThetford\nDIAGNOSIS\nYES\nNO\n",
            "REMOVAL\nStep 1: Pull\nDo this:\n1. Pull.\nGood looks like: It is off.\nNext: Stop.",
            "DO NOT\n- Stop.\nSOURCES\n- Thetford 42088 page 3",
            "Fig. sketch of a Norcold board",
        ])
        sheet = profile_check.check_sheet_text(text)
        summary = profile_check.gate_summary(sheet + profile_check.grade_pdf(text, sheet))
        self.assertIn("7. FAIL", summary)

    def test_a_safety_contradiction_fails_line_8(self):
        text = "\n".join([
            "REPAIR PROCEDURE",
            "Step 14: Open the valve",
            "Safety: Turn the RV water off.",
            "Do this:",
            "1. Turn the RV water on.",
            "Good looks like: Water is on.",
            "Next: Stop.",
        ])
        rules = profile_check.check_sheet_text(text)
        summary = profile_check.gate_summary(rules + profile_check.grade_pdf(text, rules))
        self.assertIn("8. FAIL", summary)

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


class TestPastFails(unittest.TestCase):
    def _pf(self, text):
        return _past_fails(profile_check.grade_past_fails(None, text))

    def test_placeholders_and_a_blank_model_fail(self):
        rules = self._pf("UNCONFIRMED\nNot stated in this sheet\nSee doc.\nMODEL\n-\n")
        self.assertEqual(rules["PF-03"].status, "FAIL")
        self.assertEqual(rules["PF-31"].status, "FAIL")
        self.assertFalse(rules["PF-03"].ok)

    def test_an_internal_note_and_a_doubled_yes_fail(self):
        rules = self._pf("YES\nNO\nYES YES\n(FACR08 manual, closest reference)\n")
        self.assertEqual(rules["PF-11"].status, "FAIL")
        self.assertEqual(rules["PF-25"].status, "FAIL")

    def test_a_step_without_a_safety_line_still_passes(self):
        text = "\n".join([
            "REPAIR PROCEDURE",
            "Step 1: Pull the pedal",
            "Where: At the pedal.",
            "Do this:",
            "1. Pull the pedal.",
            "Good looks like: The pedal is off.",
            "Next: Stop here.",
            "SOURCES (SHOP DOCUMENT LIBRARY)",
            "- Thetford Water Valve Kit 42109 page 1",
        ])
        rules = self._pf(text)
        self.assertEqual(rules["PF-10"].status, "PASS")
        self.assertIn("once per section", rules["PF-10"].detail)
        self.assertEqual(rules["PF-13"].status, "PASS")

    def test_water_off_and_water_on_in_one_step_fail(self):
        text = "\n".join([
            "REPAIR PROCEDURE",
            "Step 14: Open the valve",
            "Safety: Turn the RV water off.",
            "Do this:",
            "1. Turn the RV water on.",
            "Good looks like: Water is on.",
            "Next: Stop.",
        ])
        rules = self._pf(text)
        self.assertEqual(rules["PF-10"].status, "FAIL")
        self.assertEqual(rules["PF-33"].status, "FAIL")

    def test_a_cut_off_quote_fails(self):
        rules = self._pf("Straighten the temperature probe (Fig .\n")
        self.assertEqual(rules["PF-01"].status, "FAIL")

    def test_a_source_without_a_page_fails(self):
        text = "SOURCES (SHOP DOCUMENT LIBRARY)\n- Lippert Level Up owner's manual, hose diagram\n"
        rules = self._pf(text)
        self.assertEqual(rules["PF-13"].status, "FAIL")


if __name__ == "__main__":
    unittest.main()
