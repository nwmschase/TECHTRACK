"""Repair steps stay short enough to finish from the sheet alone."""
import re
import unittest

import manual_figures as mf

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
                self.assertNotIn("Not stated in this sheet", joined)
                self.assertRegex(joined, r"Step \d+:")
                self.assertIn("Do this:", joined)
                self.assertNotIn("PHOTO:", joined)
                self.assertNotIn("Yes, go to the next step.", joined)
                self.assertNotIn("A photo is optional.", joined)
                if mf.shop_field_value(step["fields"].get("WHERE") or ""):
                    self.assertIn("Where:", joined, step["text"])
                if mf.shop_field_value(step["fields"].get("TOOLS / METER SETTING") or ""):
                    self.assertIn("Tools:", joined, step["text"])
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
                    self.assertEqual(step["fields"]["FIGURE"], "Not stated in this sheet.")
                    self.assertNotIn("UNCONFIRMED", joined)
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


if __name__ == "__main__":
    unittest.main()
