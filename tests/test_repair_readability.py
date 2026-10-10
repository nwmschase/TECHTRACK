"""Repair steps stay short enough to finish from the sheet alone."""
import re
import unittest

import manual_figures as mf
from bay_procedure import compose_sheet, compile_bay_procedure, layout_problems, render_bay_procedure_pdf
from gd_library_coach import avoid_duplicate_reply

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


class TestReadability(unittest.TestCase):
    def test_thetford_steps_are_short_and_have_a_yes_no_check(self):
        for kind in ("valve", "breaker"):
            layout = mf.thetford_kit_layout(kind)
            self.assertTrue(layout["removal"])
            self.assertTrue(layout["installation"])
            self.assertIn("BEFORE YOU START".lower(), "before you start")
            self.assertTrue(layout["before"])
            for step in layout["steps"]:
                problems = mf.readability_problems(step)
                self.assertEqual(problems, [], (kind, step["text"], problems))
                joined = " ".join(mf.step_sentences(step))
                for label in mf.STEP_FIELDS:
                    self.assertIn(f"{label}:", joined)
                self.assertIn("On good:", step["fields"]["NEXT"])
                self.assertIn("On bad:", step["fields"]["NEXT"])
                self.assertNotRegex(step["text"], r"\band then\b")
                self.assertLessEqual(mf._word_count(step["text"]), 15, step["text"])
                self.assertNotIn("It looks right", joined)
                if step.get("fig"):
                    self.assertIsNotNone(step.get("figure"), step["text"])
                    label = step["figure"]["label"]
                    number = re.search(r"(\d+)", label).group(1)
                    self.assertIn(number, step["fields"]["FIGURE"])
                else:
                    self.assertIsNone(step.get("figure"))
                    self.assertEqual(step["fields"]["FIGURE"], "UNCONFIRMED")
            blob = " ".join(
                " ".join(step.get("actions") or [step["text"]]).lower()
                for step in layout["steps"]
            )
            source = " ".join(page["text"].lower() for page in mf.index_pdf_bytes(
                (VALVE_PDF if kind == "valve" else BREAKER_PDF).read_bytes()
            )["pages"])
            if kind == "valve":
                for token in ("pedal", "retainer", "pocket a", "pocket b"):
                    self.assertIn(token, blob, token)
                    self.assertIn(token.replace("pocket ", "pocket "), source)
            else:
                self.assertIn("clamp a", blob)
                self.assertIn("clamp a", source)

    def test_steps_come_from_the_sheet_not_a_stored_script(self):
        text = """
        Before Beginning
        Read all instructions completely.
        Remove the lever
        1. Turn off the power.
        2. Pull the lever up and off.
        3. Rotate the lock to the right until it stops (Fig. 1).
        Install the lever
        1. Put the pin in slot A (Fig. 1).
        """
        figures = [{"label": "Fig. 1 LEVER LOCK", "png": b"png", "page": 1}]
        layout = mf.procedure_from_sheet(text, figures, "Widget lever sheet")
        blob = " ".join(
            " ".join(step.get("actions") or [step["text"]]).lower()
            for step in layout["steps"]
        )
        self.assertIn("lever", blob)
        self.assertIn("lock", blob)
        self.assertIn("slot a", blob)
        self.assertNotIn("water valve", blob)
        self.assertNotIn("pocket", blob)
        self.assertNotIn("vacuum breaker", blob)
        pictured = [step for step in layout["steps"] if step.get("figure")]
        self.assertTrue(pictured)
        for step in pictured:
            self.assertIn(
                "1",
                step["text"] + " " + step.get("explain", "") + " " + (step.get("fields") or {}).get("FIGURE", ""),
            )
        for step in layout["steps"]:
            self.assertEqual(mf.readability_problems(step), [])

    def test_bay_pdf_shows_removal_installation_and_no_extra_image(self):
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
        self.assertEqual(len(proc.procedures), 2)
        self.assertTrue(proc.procedures[0]["title"].lower().startswith("water"))
        pages = compose_sheet(proc)
        self.assertEqual(pages[0].images, [])
        images = [image for page in pages for image in page.images]
        pictured = [
            step
            for procedure in proc.procedures
            for step in procedure["steps"]
            if step.get("figure") and step["figure"].get("png")
        ]
        self.assertEqual(len(images), len(pictured))
        self.assertGreater(len(images), 4)
        for image in images:
            self.assertGreaterEqual(image.w, 120.0)
            self.assertFalse(mf.png_is_blank(image.png))
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc).lower()
        doc.close()
        self.assertIn("before you start", text)
        self.assertIn("removal", text)
        self.assertIn("installation", text)
        self.assertIn("where:", text)
        self.assertIn("good vs bad:", text)
        self.assertIn("tools / meter setting:", text)
        self.assertIn("do not make the nuts too tight", text)
        self.assertLess(text.find("removal"), text.find("installation"))
        # A step with no figure is text only. The first water-off step has no picture.
        self.assertIn("turn off the water to the rv", text)


class TestProcedureHandoff(unittest.TestCase):
    def test_gd_waits_for_a_photo_before_the_next_step(self):
        history = [
            {"role": "user", "content": "toilet leaks under the flush lever"},
            {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        ]
        asked = avoid_duplicate_reply(
            "Check whether the vacuum breaker leaks while flushing.",
            history,
            "Supply is tight. The water valve weeps at the pedal.",
            "Plumbing / Toilets",
            "Style II 42070",
        )
        self.assertIn("vacuum breaker", asked.lower())
        self.assertNotIn("Step 1 of", asked)
        self.assertNotIn("42049", asked)
        history = history + [
            {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
            {"role": "assistant", "content": asked},
        ]
        first = avoid_duplicate_reply(
            "",
            history,
            "Vacuum breaker is dry. No leak there.",
            "Plumbing / Toilets",
            "Style II 42070",
        )
        self.assertIn("Here is the repair procedure.", first)
        self.assertIn("Step 1 of", first)
        self.assertIn("Take a photo of this step and send it.", first)
        for label in mf.STEP_FIELDS:
            self.assertIn(f"{label}:", first)
        self.assertNotIn("Step 2 of", first)
        self.assertIn("42109", first)
        self.assertNotIn("It looks right", first)
        for sentence in re.split(r"\n+", first):
            if sentence.startswith("📖"):
                continue
            name = sentence.split(":", 1)[0]
            if name in mf.STEP_FIELDS and name != "HOW":
                continue
            self.assertLessEqual(mf._word_count(sentence), 15, sentence)
        history = history + [
            {"role": "user", "content": "Vacuum breaker is dry. No leak there."},
            {"role": "assistant", "content": first},
        ]
        held = avoid_duplicate_reply(
            "",
            history,
            "Not yet.",
            "Plumbing / Toilets",
            "Style II 42070",
        )
        self.assertIn("Step 1 of", held)
        self.assertIn("Send the photo before the next step.", held)
        self.assertNotIn("Step 2 of", held)
        advanced = avoid_duplicate_reply(
            "",
            history,
            "Photo sent. Yes.",
            "Plumbing / Toilets",
            "Style II 42070",
        )
        self.assertIn("Step 2 of", advanced)
        self.assertNotIn("Step 1 of", advanced)


if __name__ == "__main__":
    unittest.main()
