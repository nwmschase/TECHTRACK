"""Every Thetford check and every Thetford repair step uses the shop template.

WHERE, SAFETY, TOOLS / METER SETTING, HOW, GOOD vs BAD, NEXT, FIGURE, and
PHOTO come from the owner manual or the kit sheet. A value those documents
do not state is omitted from the shop text. The internal marker is not printed.
"""
import unittest

import manual_figures as mf
from bay_procedure import compile_bay_procedure, render_bay_procedure_pdf
from gd_library_coach import (
    THETFORD_FLANGE_LINE,
    THETFORD_SUPPLY_LINE,
    THETFORD_VACUUM_LINE,
    THETFORD_VALVE_LINE,
    avoid_duplicate_reply,
)

VALVE_PDF = mf.Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf"
BREAKER_PDF = mf.Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "34123-34122-VacBrkr-1.pdf"


def _packet(title, path):
    indexed = mf.index_pdf_bytes(path.read_bytes())
    text = "\n".join(page["text"] for page in indexed["pages"])
    figures = [
        {"title": title, "page": fig["page"], "label": fig["label"], "png": fig["png"]}
        for fig in indexed["figures"]
    ]
    return {
        "title": title,
        "page": figures[0]["page"] if figures else 1,
        "excerpt": text,
        "figures": figures,
    }


def _assert_fields(case, text):
    """A printed Bay step has a heading and a Do this list. Blanks and the photo script stay off."""
    case.assertRegex(text, r"Step \d+:")
    case.assertIn("Do this:", text)
    case.assertNotIn("HOW:", text)
    case.assertNotIn("PHOTO:", text)
    case.assertNotIn("Yes, go to the next step.", text)
    case.assertNotIn("A photo is optional.", text)
    case.assertNotIn("UNCONFIRMED", text)
    case.assertNotIn("Not stated in this sheet", text)


def _assert_chat(case, text):
    """A Guided Diagnostics reply is sentences. The label block and the counter stay off."""
    case.assertNotIn("Where:", text)
    case.assertNotIn("Do this:", text)
    case.assertNotIn("Good looks like:", text)
    case.assertNotIn("Bad looks like:", text)
    case.assertNotIn("Next:", text)
    case.assertNotRegex(text, r"Step \d+ of")
    case.assertNotIn("**Step ", text)
    case.assertNotIn("HOW:", text)
    case.assertNotIn("PHOTO:", text)
    case.assertNotIn("Yes, go to the next step.", text)
    case.assertNotIn("A photo is optional.", text)
    case.assertNotIn("UNCONFIRMED", text)
    case.assertNotIn("Not stated in this sheet", text)
    case.assertIn("What do you see?", text)


class TestThetfordStepTemplate(unittest.TestCase):
    def test_every_proving_line_has_the_eight_fields(self):
        for key, line in (
            ("supply", THETFORD_SUPPLY_LINE),
            ("vacuum", THETFORD_VACUUM_LINE),
            ("valve", THETFORD_VALVE_LINE),
            ("flange", THETFORD_FLANGE_LINE),
        ):
            _assert_chat(self, line)
            self.assertNotIn("SAFETY:", line)
            self.assertNotIn("Safety:", line)
            self.assertNotIn("TOOLS / METER SETTING:", line)
            step = {"fields": mf._THETFORD_PROVING[key], "actions": [], "text": ""}
            if mf.step_needs_photo(step):
                self.assertEqual(line.count(mf.PHOTO_VISUAL), 1, key)
            else:
                self.assertNotIn(mf.PHOTO_VISUAL, line, key)

    def test_gd_walk_keeps_the_fields_on_every_check(self):
        history = []
        latest = "toilet leaks under the flush lever when flushing"
        draft = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
        for _ in range(4):
            reply = avoid_duplicate_reply(
                draft, history, latest, "Plumbing / Toilets", "Style II 42070"
            )
            _assert_chat(self, reply)
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
            latest = "Not checked yet"

    def test_bay_checks_and_repair_steps_have_the_fields(self):
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category="Plumbing / Toilets",
            chunks=[
                _packet("Thetford Water Valve Kit 42109", VALVE_PDF),
                _packet("Thetford Vacuum Breaker Kit 34123/34122", BREAKER_PDF),
            ],
        )
        self.assertGreaterEqual(len(proc.bay_order), 4)
        for step in proc.bay_order:
            _assert_fields(self, step)
        shown = []
        for procedure in proc.procedures:
            self.assertTrue(procedure["steps"])
            for step in procedure["steps"]:
                text = "\n".join(mf.step_sentences(step))
                _assert_fields(self, text)
                shown.append(mf.format_one_step(step, 1, len(procedure["steps"])))
                self.assertLessEqual(mf._word_count(step["fields"]["HOW"]), 15, step["text"])
                self.assertNotIn("It looks right", text)
        leak = next(
            step
            for procedure in proc.procedures
            for step in procedure["steps"]
            if "turn the rv water on" in " ".join(step.get("actions") or []).lower()
        )
        self.assertIn("pedal", leak["fields"]["WHERE"].lower())
        self.assertNotIn("Turn the RV water off", leak["fields"]["SAFETY"])
        self.assertTrue(any("until" in (step.get("source") or "").lower() and "Good: Not stated in this sheet." not in step["fields"]["GOOD vs BAD"] for procedure in proc.procedures for step in procedure["steps"]))
        self.assertNotIn("UNCONFIRMED", " ".join(proc.bay_order))
        self.assertNotIn("UNCONFIRMED", " ".join(proc.do_not))
        import pymupdf

        doc = pymupdf.open(stream=render_bay_procedure_pdf(proc), filetype="pdf")
        pdf = "\n".join(page.get_text() for page in doc).lower()
        doc.close()
        self.assertIn("do this:", pdf)
        self.assertIn("step 1:", pdf)
        self.assertNotIn("photo:", pdf)
        self.assertNotIn("a photo is optional", pdf)
        self.assertNotIn("yes, go to the next step", pdf)
        self.assertNotIn("unconfirmed", pdf)


if __name__ == "__main__":
    unittest.main()
