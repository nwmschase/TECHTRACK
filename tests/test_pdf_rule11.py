"""Rule 11: the PDF builder uses GD's pipeline and refuses filler sheets."""
import io
import os
import tempfile
import unittest

import gd_official as go
import pdf_rule11 as r11


def _png():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(b, "PNG")
    return b.getvalue()


FIG = {"p5-Fig-3": {"png": _png(), "page": 5, "label": "Fig. 3", "width": 400, "height": 300}}
MAN = {"origin": "library", "title": "Acme RX100 Service Manual", "label": go.LABEL_LIBRARY, "url": ""}


def good_step(**kw):
    d = dict(action="Measure DC volts at Plug 3.", probe="Plug 3, pin 1 white (-) to pin 2 yellow (+)",
             state="Switch ON, LP mode, during the 45 s trial", good="12 V DC or more", bad="0 V DC",
             next="Good: step 2. Bad: branch A.", page=5)
    d.update(kw)
    return r11.Step(**d)


def sheet(steps, figures=FIG):
    return r11.Sheet(case="T", concern="no gas", unit={"model": "Acme RX100"}, manual=MAN,
                     diagnosis=steps, branches=[], do_not=["Do not jumper the board."],
                     flow=[{"q": "12 V at Plug 3?", "yes": "Step 2.", "no": "Branch A."}], figures=figures)


class FakeLib:
    def __init__(self, docs):
        self.docs = docs

    def documents(self):
        return self.docs

    def chunks(self, doc_id):
        return [{"page": 5, "text": "TROUBLESHOOTING\nCheck voltage at Plug 3."}]


class Rule11(unittest.TestCase):
    def test_zero_figures_blocks_sheet(self):
        sh = sheet([good_step()])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x.pdf")
            with self.assertRaises(r11.NoFigures):
                r11.render_pdf(sh, out)
            self.assertFalse(os.path.exists(out))

    def test_sheet_with_figure_renders(self):
        sh = sheet([good_step(figure="p5-Fig-3")])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x.pdf")
            st = r11.render_pdf(sh, out, os.path.join(d, "x.md"))
            self.assertEqual(st["figures"], 1)
            self.assertTrue(os.path.getsize(out) > 1000)
            md = open(os.path.join(d, "x.md")).read()
            self.assertIn("[Library: Acme RX100 Service Manual, page 5]", md)

    def test_unknown_figure_id_rejected(self):
        with self.assertRaises(r11.StepRuleError):
            r11.validate_sheet(sheet([good_step(figure="p9-Fig-99")]))

    def test_no_manual_stops(self):
        lib = FakeLib([{"id": 1, "title": "Other Brand RX100 Manual", "brand": "Furrion", "models": "", "product_line": "",
                        "clean_title": "", "doc_number": "", "keywords": "", "revision_date": ""}])
        with self.assertRaises(r11.NoManual):
            r11.find_manual("Dometic RM1350", "no LP", "Refrigerators", lib, pdf_for_doc=lambda d: b"%PDF-", api_key="", web=False)

    def test_unit_not_identified_stops(self):
        with self.assertRaises(r11.NoManual) as cm:
            r11.find_manual("Dometic DFS", "shuts off", "Furnaces", FakeLib([]), api_key="", web=False)
        self.assertIn("Exact unit not identified", str(cm.exception))

    def test_library_pin_without_file_is_skipped(self):
        doc = {"id": 7, "title": "Dometic RM1350 Diagnostic Service Manual", "brand": "", "models": "", "product_line": "",
               "clean_title": "", "doc_number": "", "keywords": "", "revision_date": ""}
        with self.assertRaises(r11.NoManual):
            r11.find_manual("Dometic RM1350", "no LP", "Refrigerators", FakeLib([doc]), pdf_for_doc=lambda d: None, api_key="", web=False)
        m = r11.find_manual("Dometic RM1350", "no LP", "Refrigerators", FakeLib([doc]), pdf_for_doc=lambda d: b"%PDF-x", web=False)
        self.assertEqual(m["label"], go.LABEL_LIBRARY)

    def test_uses_gd_functions_not_forks(self):
        import inspect
        src = inspect.getsource(r11)
        for name in ("identify_unit", "pin_document", "load_section", "fetch_official_manual"):
            self.assertIn(f"go.{name}(", src)
            self.assertNotIn(f"def {name}(", src)

    def test_filler_string_rejected(self):
        for filler in ("At the part named in this step.", "The step is done as the cited page says."):
            with self.assertRaises(r11.StepRuleError):
                r11.validate_sheet(sheet([good_step(probe=filler, figure="p5-Fig-3")]))
        with self.assertRaises(r11.StepRuleError):
            r11.validate_sheet(sheet([good_step(next="If it is bad, stay on this step until it passes.", figure="p5-Fig-3")]))

    def test_generic_flowchart_rejected(self):
        sh = sheet([good_step(figure="p5-Fig-3")])
        sh.flow = [{"q": "Did the first check pass?", "yes": "Go on.", "no": "Stay on that check until it passes."}]
        with self.assertRaises(r11.StepRuleError):
            r11.validate_sheet(sh)

    def test_one_action_per_step(self):
        for bad in ("Remove the 3 screws and lower the housing.", "Pull the probe out, then straighten it.",
                    "Pull the blue wire; pull the black wire.", "Turn the dial to OFF. Close both doors.",
                    "Remove the screws, pull the housing down."):
            self.assertTrue(r11.check_action(bad), bad)
            with self.assertRaises(r11.StepRuleError):
                r11.validate_sheet(sheet([good_step(action=bad, figure="p5-Fig-3")]))
        for ok in ("Turn the dial fully to OFF.", "Measure DC volts at Plug 3.", "Pull the blue and black wires off."):
            self.assertEqual(r11.check_action(ok), [], ok)

    def test_every_step_has_probe_state_reading(self):
        for missing in ("probe", "state", "good", "bad"):
            with self.assertRaises(r11.StepRuleError) as cm:
                r11.validate_sheet(sheet([good_step(**{missing: "", "figure": "p5-Fig-3"})]))
            self.assertIn(f"missing {missing}", str(cm.exception))

    def test_notes_are_not_numbered_steps(self):
        note = r11.Step(action="Housing already down from diagnosis? Skip to step 2.", kind="note")
        sh = sheet([note, good_step(figure="p5-Fig-3")])
        r11.validate_sheet(sh)
        with tempfile.TemporaryDirectory() as d:
            st = r11.render_pdf(sh, os.path.join(d, "x.pdf"), os.path.join(d, "x.md"))
            md = open(os.path.join(d, "x.md")).read()
        self.assertEqual((st["steps"], st["notes"]), (1, 1))
        self.assertIn("*Note: Housing already down", md)
        self.assertIn("**Step 1: Measure DC volts at Plug 3**", md)

    def test_figure_must_be_on_the_step_page(self):
        with self.assertRaises(r11.StepRuleError):
            r11.validate_sheet(sheet([good_step(page=14, figure="p5-Fig-3")]))
        r11.validate_sheet(sheet([good_step(page=6, figure="p5-Fig-3")]))

    def test_manual_step_needs_page(self):
        with self.assertRaises(r11.StepRuleError):
            r11.validate_sheet(sheet([good_step(page=None, figure="p5-Fig-3")]))


if __name__ == "__main__":
    unittest.main()
