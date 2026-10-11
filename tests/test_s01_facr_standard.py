"""S01 FACR08 sheet under the numbered proving and R&R standard."""
import io
import re
import unittest

import manual_figures as mf
from bay_procedure import (
    compile_bay_procedure,
    compose_sheet,
    layout_problems,
    place_facr_library_figures,
    render_bay_procedure_pdf,
)
from gd_library_coach import avoid_duplicate_reply, ensure_facr_early_pressure_ask

CONCERN = "FACR08 freeze up interior leak condensate"


def _png(color):
    from PIL import Image

    image = Image.new("RGB", (48, 48), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _sheet():
    return compile_bay_procedure(
        concern=CONCERN,
        brand="Furrion",
        model="FACR08HESA2-PS",
        category="Air Conditioning",
    )


def _steps(proc):
    return [step for procedure in proc.procedures for step in procedure["steps"]]


def _walk(turns):
    history = []
    replies = []
    for latest in turns:
        reply = avoid_duplicate_reply(
            "Check the filter and the fan.",
            history,
            latest,
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        reply = ensure_facr_early_pressure_ask(
            reply, history, latest, "Air Conditioning", "FACR08HESA2-PS"
        )
        replies.append(reply or "")
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": reply})
    return replies


S01_LIVE = [
    "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running, not raining.",
    "Drain is clear, pan is clean and draining, base-pan slope is fine.",
    "Filter is clean.",
    "Evaporator fan spins freely with good airflow.",
    "Freeze sensor reads 2 kΩ at 25°C.",
    "Pressures 68 / 235 psig.",
    "Suction line clear / not iced; still frosting after drain, pan, filter and fan checks.",
]


class TestFacrSheet(unittest.TestCase):
    def test_proving_and_rr_are_short_one_action_steps(self):
        proc = _sheet()
        self.assertEqual(len(proc.procedures), 2)
        titles = " ".join(item["title"] for item in proc.procedures)
        self.assertIn("2024006031", titles)
        self.assertIn("proving", titles.lower())
        self.assertIn("removal", titles.lower())
        hows = []
        sheets = []
        for step in _steps(proc):
            how = step["text"]
            hows.append(how.lower())
            sheets.append(" ".join(mf.step_sentences(step)).lower())
            self.assertLessEqual(mf._word_count(how), 12, how)
            self.assertNotRegex(how, r"(?i)\band\b")
            self.assertNotRegex(how, r"(?i)\band then\b")
            joined = " ".join(mf.step_sentences(step))
            self.assertNotIn("UNCONFIRMED", joined.upper())
            self.assertNotIn("not stated", joined.lower())
            for label in ("WHERE", "SAFETY", "HOW", "GOOD vs BAD", "NEXT", "PHOTO"):
                self.assertIn(f"{label}:", joined, how)
            self.assertIn("Yes, go to the next step.", joined)
            self.assertIn("No, do this step again.", joined)
            for line in mf.step_sentences(step):
                body = line.split(":", 1)[-1]
                for sentence in re.split(r"[.]", body):
                    sentence = sentence.strip()
                    if sentence:
                        self.assertLessEqual(mf._word_count(sentence), 12, sentence)
        blob = " ".join(sheets)
        for token in (
            "dry the ceiling",
            "115vac",
            "12vdc",
            "discharge the capacitors",
            "drain openings",
            "pan empties",
            "15 degrees",
            "shim the unit",
            "fig. 2",
            "40 to 50",
            "fig. 28",
            "fig. 29",
            "nozzles",
            "blower",
            "1-3/16",
            "ohms",
            "halide",
            "8.2",
            "hoist",
            "furnace",
            "14-1/4",
            "marked side",
            "foil tape",
            "dip switches",
        ):
            self.assertIn(token, blob, token)
        text = "\n".join(
            " ".join(item.get("before") or [])
            + " "
            + " ".join(" ".join(mf.step_sentences(step)) for step in item["steps"])
            for item in proc.procedures
        )
        low = text.lower()
        self.assertIn("2024006031", text)
        self.assertNotIn("facr13", low)
        self.assertNotIn("facr14", low)
        self.assertNotIn("facr15", low)
        self.assertNotRegex(low, r"\bpsig\b|\bpsi\b")
        self.assertNotRegex(low, r"\b68\b|\b235\b")
        self.assertNotRegex(low, r"\d+\s*(?:ohms|ohm)\b")
        self.assertIn("changes smoothly", low)
        self.assertIn("do not use ccd-0007990 part numbers", low)
        self.assertIn("r32 is flammable", low)
        self.assertIn("do not slide the unit", low)
        numbers = set(re.findall(r"\b\d{10}\b", text))
        self.assertEqual(numbers, {"2024006031"})
        forward = next(step for step in _steps(proc) if "marked side" in step["text"])
        self.assertIsNone(forward["figure"]["page"])
        self.assertNotRegex(forward["fields"]["FIGURE"], r"page\s*\d")
        order = " ".join(proc.bay_order).lower()
        self.assertIn("cool cycle", order)
        self.assertIn("replace the rooftop", order)
        self.assertIn("confirmed correction", order)
        donot = " ".join(proc.do_not).lower()
        self.assertIn("pressures alone", donot)
        self.assertIn("without filters", donot)
        self.assertIn("open flame", donot)
        self.assertIn("do not slide", donot)
        self.assertIn("dip switches", donot)
        self.assertIn("part numbers", donot)
        self.assertNotIn("ccd-0007990", donot)

    def test_library_page_is_drawn_and_a_wrong_page_is_not(self):
        proc = _sheet()
        for step in _steps(proc):
            figure = step.get("figure") or {}
            self.assertFalse((figure or {}).get("png"))
        png20 = _png((10, 10, 10))
        png7 = _png((20, 20, 80))
        png_other = _png((80, 20, 20))
        rows = [
            {"title": "Furrion Chill FACR08 8K manual CCD-0008666", "page": 20, "png": png20},
            {"title": "Furrion Rooftop HVAC Troubleshooting CCD-0007990", "page": 7, "png": png7},
            {"title": "Furrion Chill FACR CCD-0008666", "page": 4, "png": png_other},
            {"title": "Some other book CCD-0008122", "page": 20, "png": _png((1, 80, 1))},
        ]
        placed = place_facr_library_figures(proc, rows)
        water = [
            step
            for step in _steps(placed)
            if (step.get("figure") or {}).get("label") == "Water enters the vehicle"
        ]
        self.assertTrue(water)
        for step in water:
            self.assertEqual(step["figure"]["png"], png20)
        drain = next(step for step in _steps(placed) if step["text"].startswith("Clear the drain"))
        self.assertEqual(drain["figure"]["png"], png7)
        self.assertIn("CCD-0007990", drain["figure"]["title"])
        forward = next(step for step in _steps(placed) if "marked side" in step["text"])
        self.assertFalse(forward["figure"]["png"])
        self.assertIsNone(forward["figure"]["page"])
        level = next(step for step in _steps(placed) if "15 degrees" in step["text"])
        self.assertFalse(level["figure"]["png"])
        pages = compose_sheet(placed)
        images = [image.png for page in pages for image in page.images]
        self.assertIn(png20, images)
        self.assertIn(png7, images)
        self.assertNotIn(png_other, images)

    def test_full_sheet_stays_readable(self):
        proc = _sheet()
        pages = compose_sheet(proc)
        self.assertGreaterEqual(len(pages), 4)
        text = "\n".join(item.text for page in pages for item in page.texts).lower()
        self.assertIn("proving checks", text)
        self.assertIn("removal", text)
        self.assertIn("installation", text)
        self.assertIn("where:", text)
        self.assertIn("good vs bad:", text)
        self.assertIn("2024006031", text)
        self.assertNotIn("unconfirmed", text)
        self.assertNotIn("not stated", text)
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])


class TestFacrRepairWalk(unittest.TestCase):
    def test_rr_starts_after_authorization_and_yes_advances(self):
        replies = _walk(S01_LIVE)
        for reply in replies[:5]:
            self.assertNotIn("Step 1 of", reply)
            self.assertNotIn("authorize rooftop assembly", reply.lower())
        later = replies[6]
        low = later.lower()
        self.assertIn("suction line is clear", low)
        self.assertIn("still frosting", low)
        self.assertIn("verify", low)
        self.assertIn("rooftop assembly", low)
        self.assertIn("ccd-0007990", low)
        self.assertNotIn("authorize rooftop assembly r&r on the ccd-0007990 condensate and assembly path.", low)
        self.assertIn("Here is the repair procedure.", later)
        self.assertIn("Step 1 of", later)
        self.assertIn("Take a photo of this step and send it.", later)
        self.assertIn("Yes, go to the next step.", later)
        self.assertIn("No, do this step again.", later)
        self.assertIn("2024006031", later)
        history = []
        for latest, reply in zip(S01_LIVE, replies):
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        held = avoid_duplicate_reply(
            "",
            history,
            "Not yet.",
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        self.assertIn("Step 1 of", held)
        self.assertIn("Send the photo before the next step.", held)
        self.assertNotIn("Step 2 of", held)
        advanced = avoid_duplicate_reply(
            "",
            history,
            "Yes.",
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        self.assertIn("Step 2 of", advanced)
        self.assertNotIn("Step 1 of", advanced)
        self.assertIn("12VDC", advanced)
        self.assertNotIn("authorize rooftop assembly r&r on the ccd-0007990 condensate and assembly path.", advanced.lower())

    def test_repair_question_before_the_walk_still_authorizes(self):
        replies = _walk(S01_LIVE[:6] + ["What is the repair?"])
        last = replies[-1].lower()
        self.assertIn("authorize rooftop assembly", last)
        self.assertIn("replace the rooftop assembly", last)
        self.assertIn("ccd-0007990", last)
        self.assertNotIn("step 1 of", last)
        self.assertNotIn("read the refrigerant pressures", last)


if __name__ == "__main__":
    unittest.main()
