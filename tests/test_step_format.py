"""Every Bay PDF and every GD step uses the same heading and labels.

The canned photo script stays out of the PDF. Safety is printed once per
section, and again only when that step's safety text changes.
"""
import re
import unittest

import manual_figures as mf
from bay_procedure import compose_sheet, compile_bay_procedure, layout_problems, render_bay_procedure_pdf
from tests.test_s01_facr_standard import _sheet
from tests.test_thetford_step_template import BREAKER_PDF, VALVE_PDF, _packet

_PHOTO_BLOCK = (
    "a photo is optional",
    "you can type what you see",
    "yes, go to the next step",
    "no, do this step again",
    "take a photo of this step",
    "photo:",
)


def _pdf_text(proc) -> str:
    import pymupdf

    trace = []
    pdf = render_bay_procedure_pdf(proc, trace=trace)
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text, trace


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


def _emitted_safety(steps) -> list[str]:
    return [
        mf.step_safety_text(step)
        for index, step in enumerate(steps, 1)
        if mf.show_safety_for(steps, index)
    ]


class TestSharedStepStructure(unittest.TestCase):
    def test_pdf_has_a_heading_per_step_and_no_photo_block(self):
        for name, proc in (("thetford", _thetford()), ("facr", _sheet())):
            text, trace = _pdf_text(proc)
            low = text.lower()
            steps = [step for item in proc.procedures for step in item.get("steps") or []]
            headings = re.findall(r"Step \d+:", text)
            import bay_procedure as bp
            import bay_profile_lines as bpl
            import manual_figures as mf2

            def _painted(item):
                kept = bpl.drop_duplicate_removals(list(item.get("steps") or []), bp._step_good_text)
                return bpl.repair_branch(
                    kept,
                    lambda s: mf2.step_heading(s, 1).split(": ", 1)[-1],
                    lambda s: mf2._good_bad_bits(((s or {}).get("fields") or {}).get("GOOD vs BAD") or ""),
                    bp._branch_step,
                    secure_step=bp._manual_secure_step(proc.procedures),
                )

            painted = sum(len(_painted(item)) for item in proc.procedures)
            diag = len(proc.bay_order) if proc.procedures else 0
            self.assertEqual(len(headings), painted + diag, name)
            for item in proc.procedures:
                import bay_procedure as bp
                import bay_profile_lines as bpl

                kept = _painted(item)
                for step_index, step in enumerate(kept, 1):
                    self.assertIn(f"Step {step_index}:", text, (name, step.get("text")))
            self.assertIn("Do this:", text, name)
            self.assertIn("Where:", text, name)
            for banned in _PHOTO_BLOCK:
                self.assertNotIn(banned, low, (name, banned))
            self.assertEqual(layout_problems(trace), [], name)
        pages = compose_sheet(_thetford())
        images = [image for page in pages for image in page.images]
        pictured = [
            step
            for item in _thetford().procedures
            for step in item.get("steps") or []
            if isinstance(step.get("figure"), dict) and step["figure"].get("png")
        ]
        self.assertGreaterEqual(len(images), 4)
        self.assertEqual(len(images), len(pictured))
        for image in images:
            self.assertGreaterEqual(image.w, 120.0)

    def test_safety_prints_once_per_section_unless_it_changes(self):
        steps = mf.thetford_kit_layout("valve")["steps"]
        emitted = _emitted_safety(steps)
        self.assertLess(len(emitted), len(steps))
        self.assertEqual(emitted.count("Turn the RV water off before this work. Put on gloves and glasses."), 2)
        self.assertEqual(emitted.count("Turn the RV water on for the leak test. Put on gloves and glasses."), 1)
        proc = _thetford()
        text, _trace = _pdf_text(proc)
        low = text.lower()
        off = 0
        on = 0
        for procedure in proc.procedures:
            shown = _emitted_safety(procedure.get("steps") or [])
            off += shown.count("Turn the RV water off before this work. Put on gloves and glasses.")
            on += shown.count("Turn the RV water on for the leak test. Put on gloves and glasses.")
        self.assertGreaterEqual(off, 2)
        self.assertEqual(low.count("turn the rv water off before this work"), off)
        # v4.19.59: every step that carries "Turn the RV water on for the leak test" is itself the
        # "Turn the RV water on" step, so the Safety line only restates the action and is never printed.
        self.assertGreater(on, 0)
        self.assertEqual(low.count("turn the rv water on for the leak test"), 0)
        self.assertLess(off, sum(len(procedure.get("steps") or []) for procedure in proc.procedures))
        rr = mf.facr_rr_layout()["steps"]
        rr_safety = _emitted_safety(rr)
        self.assertLess(len(rr_safety), len(rr))
        self.assertEqual(rr_safety[0], "Keep both supplies off.")
        self.assertNotEqual(rr_safety[1], rr_safety[0])
        facr = _sheet()
        facr_text, _facr_trace = _pdf_text(facr)
        carried = emitted = 0
        for item in facr.procedures:
            for index, step in enumerate(item.get("steps") or [], 1):
                if "keep both supplies off" in mf.step_safety_text(step).lower():
                    carried += 1
                    if mf.show_safety_for(item["steps"], index):
                        emitted += 1
        self.assertGreater(carried, emitted)
        shown = facr_text.lower().count("keep both supplies off")
        self.assertGreaterEqual(shown, 1)
        self.assertLess(shown, carried)
        self.assertLessEqual(shown, 2)

    def test_gd_uses_the_same_markdown_structure(self):
        valve = mf.thetford_kit_layout("valve")["steps"]
        shown = mf.format_one_step(valve[3], 4, len(valve), show_safety=mf.show_safety_for(valve, 4))
        self.assertIn("Here is the repair procedure.", shown)
        self.assertRegex(shown, r"\*\*Step 4: .+\*\*")
        self.assertIn("\n\nDo this:\n1. ", shown)
        located = next(
            step for step in valve
            if any(line.startswith("Where:") for line in mf.step_body_lines(step))
        )
        self.assertIn("Where:", mf.format_one_step(located, 1, len(valve)))
        self.assertNotIn("Yes, go to the next step.", shown)
        self.assertNotIn("A photo is optional.", shown)
        self.assertNotIn("PHOTO:", shown)
        off = mf.facr_rr_layout()["steps"][0]
        quiet = mf.format_one_step(off, 1, 20, show_safety=True)
        self.assertIn("**Step 1: Turn the 115VAC breaker off**", quiet)
        self.assertIn("Safety:", quiet)
        self.assertNotIn(mf.PHOTO_VISUAL, quiet)
        look = next(
            step
            for step in mf.facr_proving_layout()["steps"]
            if step["text"].lower().startswith("look for drip")
        )
        visual = mf.format_one_step(look, 4, 32)
        self.assertEqual(visual.count(mf.PHOTO_VISUAL), 1)
        self.assertIn("\n\nDo this:\n1. Look for drip on the coil.", visual)
        first = valve[0]
        shown_first = mf.format_one_step(first, 1, len(valve), show_safety=True)
        self.assertIn("Good looks like:", shown_first)
        self.assertIn("Bad looks like:", shown_first)
        self.assertEqual(shown_first.count("\n1. "), 1)
        self.assertNotIn("\n2. ", shown_first)
        vacuum = mf.thetford_proving_line("vacuum")
        import library_figure_backfill as fb
        offers = fb.offers_for_turn([], vacuum, "show me", "Plumbing / Toilets", "Thetford 42070")
        self.assertTrue(offers and offers[0].get("png"))
        leaked = __import__("gd_library_coach").strip_leaked_prompt(
            "TechTrack will display the shop Document Library PDF page below.\n\n"
            "Check the vacuum breaker."
        )
        self.assertNotIn("will display the shop", leaked.lower())
        self.assertIn("vacuum breaker", leaked.lower())
        self.assertNotIn(
            "ohms spec",
            __import__("gd_library_coach").strip_leaked_prompt(
                "The ohms spec and the pressure spec are absent from the docs."
            ).lower(),
        )

    def test_other_bay_order_steps_use_the_same_heading(self):
        proc = compile_bay_procedure(
            concern="icing up on rear wall — only about half from the top down",
            brand="Dometic",
            model="DM2652",
            category="Refrigerators",
        )
        text, trace = _pdf_text(proc)
        self.assertRegex(text, r"Step 1:")
        self.assertIn("Do this:", text)
        low = text.lower()
        for banned in _PHOTO_BLOCK:
            self.assertNotIn(banned, low)
        self.assertEqual(layout_problems(trace), [])


if __name__ == "__main__":
    unittest.main()
