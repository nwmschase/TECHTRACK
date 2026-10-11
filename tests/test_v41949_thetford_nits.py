"""v4.19.49 Thetford review: leak-test fields, no leaked instructions, one pedal step."""
import io
import unittest

from PIL import Image

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import (
    cited_figure_count,
    clean_ocr_prose,
    compile_bay_procedure,
    render_bay_procedure_pdf,
)
from gd_library_coach import (
    avoid_duplicate_reply,
    ensure_facr_early_pressure_ask,
    repair_glued_sentence,
    strip_leaked_prompt,
)


def _png(width=180, height=140, color=(30, 70, 120)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_pages(pdf: bytes) -> list[str]:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return pages


def _sources_only(page: str) -> bool:
    lines = [line.strip() for line in page.splitlines() if line.strip()]
    body = [
        line for line in lines
        if line not in {"BAY PROCEDURE"}
        and "Tacoma RV Center" not in line
        and line not in {"Repair procedure", "Bay order continued"}
    ]
    if not body:
        return False
    return all(
        line.startswith("SOURCES") or line.startswith("Sources:") or line.startswith("- ")
        for line in body
    )


class TestLeakTestStep(unittest.TestCase):
    def test_water_on_matches_and_the_leak_check_is_complete(self):
        last = mf.thetford_kit_layout("valve")["steps"][-1]
        fields = last["fields"]
        shown = mf.format_one_step(last, 13, 13)
        self.assertIn("Turn the RV water on", fields["HOW"])
        self.assertIn("Turn the RV water on for the leak test.", fields["SAFETY"])
        self.assertNotIn("Turn the RV water off", fields["SAFETY"])
        self.assertIn("pedal", fields["WHERE"].lower())
        self.assertIn("valve", fields["WHERE"].lower())
        good = fields["GOOD vs BAD"]
        self.assertIn("Flush 3 times.", good)
        self.assertIn("dry at the pedal and valve", good)
        self.assertIn("any drip", good)
        self.assertIn("recheck the seal and the nuts", good)
        self.assertIn("Good looks like: Flush 3 times.", shown)
        self.assertIn("At the pedal and the water valve.", shown)

    def test_the_done_line_keeps_look_for_leaks(self):
        layout = mf.thetford_kit_layout("valve")
        total = len(layout["steps"])
        history = [
            {"role": "user", "content": "Style II 42070 leaks under the flush lever"},
            {"role": "assistant", "content": mf.thetford_proving_line("supply")},
            {"role": "user", "content": "Supply is tight. No leak at the connection."},
            {"role": "assistant", "content": mf.thetford_proving_line("vacuum")},
            {"role": "user", "content": "No leak while flushing. The water valve weeps at the pedal."},
        ]
        for number in range(1, total + 1):
            history.append(
                {"role": "assistant", "content": f"Here is the repair procedure.\nStep {number} of {total}.\nHOW: Do this step.\n📖 Source: Thetford Water Valve Kit 42109, page 1"}
            )
            history.append({"role": "user", "content": "Yes."})
        done = avoid_duplicate_reply(
            "draft", history, "The water is on.", "Plumbing / Toilets", "Thetford 42070"
        )
        self.assertIn("The repair procedure is done.", done)
        self.assertIn("Look for leaks.", done)
        self.assertNotIn("Look for leak\n", done)
        self.assertFalse(done.rstrip().endswith("Look for leaks"))


class TestInstructionTextStaysOffTheReply(unittest.TestCase):
    def test_the_page_image_instruction_is_stripped(self):
        leaked = (
            "Turn the RV water on.\n\n"
            "The figure is in the shop Document Library PDF. "
            "If a page image appears below, that is the real shop library page "
            "(not a chat photo embed). If nothing appears below, say so and use Download PDF / meter from the text labels."
        )
        cleaned = strip_leaked_prompt(leaked)
        self.assertIn("Turn the RV water on.", cleaned)
        self.assertNotIn("page image appears", cleaned.lower())
        self.assertNotIn("Download PDF", cleaned)
        self.assertNotIn("chat photo embed", cleaned.lower())
        self.assertEqual(
            strip_leaked_prompt(
                "If a page image appears below, say so and use Download PDF."
            ),
            "",
        )
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        source = root.joinpath("rv_techtrack.py").read_text(encoding="utf-8")
        self.assertNotIn("If a page image appears below", source)
        self.assertNotIn("use Download PDF", source)

    def test_an_empty_library_shows_no_bundled_caption(self):
        offers = fb.offers_for_turn(
            [],
            "Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me the figure",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertEqual(offers, [])
        backfill = __import__("pathlib").Path(__file__).resolve().parents[1].joinpath(
            "library_figure_backfill.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Bundled kit sheet", backfill)


class TestPedalPullIsOneStep(unittest.TestCase):
    def test_the_grab_and_the_pull_share_a_step(self):
        steps = mf.thetford_kit_layout("valve")["steps"]
        self.assertEqual(len(steps), 13)
        hits = [
            step for step in steps
            if "pull the pedal" in " ".join(step.get("actions") or []).lower()
        ]
        self.assertEqual(len(hits), 1)
        actions = " ".join(hits[0].get("actions") or []).lower()
        self.assertIn("grab the front of the pedal", actions)
        self.assertIn("pull the pedal up and off", actions)
        breaker = mf.thetford_kit_layout("breaker")["steps"]
        self.assertEqual(len(breaker), 13)


class TestDiagnosisLines(unittest.TestCase):
    def test_supply_on_bad_tightens_and_the_flange_drops_part_noise(self):
        supply = mf.thetford_proving_body("supply")
        flange = mf.thetford_proving_body("flange")
        self.assertIn("If it fails: fix or tighten the supply connection.", supply)
        self.assertNotIn("replace the water valve", supply.lower())
        self.assertNotIn("33239", flange)
        self.assertNotIn("42067", flange)
        self.assertNotIn("not on this sheet", flange.lower())
        self.assertIn("02125", flange)


class TestHeadingsStayWithTheFirstStep(unittest.TestCase):
    def test_removal_is_not_left_at_the_bottom_of_a_page(self):
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category="Plumbing / Toilets",
            chunks=[
                {
                    "title": "Thetford Style II OM Permanent RV Toilet 42088",
                    "page": 3,
                    "excerpt": "Check the water supply line connection.",
                }
            ],
        )
        pages = _pdf_pages(render_bay_procedure_pdf(proc))
        self.assertFalse(any(_sources_only(page) for page in pages))
        for index, page in enumerate(pages):
            tail = page.strip().splitlines()[-1].strip()
            self.assertNotIn(tail, {"REMOVAL", "INSTALLATION"})
            if "\nREMOVAL\n" in f"\n{page}\n" or page.rstrip().endswith("REMOVAL"):
                self.assertIn("Where:", page)
            if "\nINSTALLATION\n" in f"\n{page}\n" or page.rstrip().endswith("INSTALLATION"):
                self.assertIn("Where:", page)
        joined = "\n".join(pages)
        self.assertIn("Turn the RV water on for the leak test.", joined)
        self.assertIn("Flush 3 times.", joined)
        self.assertIn("dry at the pedal and valve", joined)
        self.assertNotIn("33239", joined)
        self.assertNotIn("42067", joined)


class TestSmallNits(unittest.TestCase):
    def test_s09_puts_a_period_before_next(self):
        raw = "Replace the ceiling thermostat Next check the selector at the rooftop unit."
        self.assertIn("thermostat. Next", clean_ocr_prose(raw))
        self.assertNotIn("thermostat Next", clean_ocr_prose(raw))
        self.assertIn("unit. Next", repair_glued_sentence("bypass at the rooftop unit Next check it."))
        proc = compile_bay_procedure(
            concern="Dometic B57915 rooftop air conditioner is not cooling.",
            brand="Dometic",
            model="B57915",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Dometic Brisk II",
                    "page": 23,
                    "excerpt": raw,
                }
            ],
        )
        text = "\n".join(_pdf_pages(render_bay_procedure_pdf(proc)))
        self.assertIn("thermostat. Next", text)
        self.assertNotIn("thermostat Next", text)

    def test_s06_cited_count_matches_the_drawn_image(self):
        png = _png()
        table = {
            "title": "Lippert Level Up Advantage LCD specification table",
            "label": "Fig. 2 LCD spec table",
            "caption": "LCD specification table",
            "product_line": "Level Up",
        }
        proc = compile_bay_procedure(
            concern="Manual Mode flashes then dumps back to home. Auto Level still works.",
            brand="Lippert",
            model="Level Up Advantage 807662",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert Level Up Advantage LCD specification table",
                    "brand": "Lippert",
                    "product_line": "Level Up",
                    "page": 4,
                    "excerpt": "LCD specification table for the display. " * 8,
                    "figures": [{**table, "png": png, "page": 4}],
                }
            ],
        )
        import pymupdf

        pdf = render_bay_procedure_pdf(proc)
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        images = sum(len(page.get_images()) for page in doc)
        doc.close()
        self.assertEqual(cited_figure_count(proc), images)
        self.assertEqual(images, 0)

    def test_s14_does_not_leave_a_sources_only_page(self):
        proc = compile_bay_procedure(
            concern="Front stabilizer jack. Power works. Manual crank will not operate. Roll pin broken.",
            brand="Lippert",
            model="PSX1",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert PSX1 stabilizer jack",
                    "brand": "Lippert",
                    "product_line": "PSX1",
                    "page": 1,
                    "excerpt": "Replace the roll pin on the manual crank.",
                }
            ],
        )
        pages = _pdf_pages(render_bay_procedure_pdf(proc))
        self.assertLessEqual(len(pages), 3)
        self.assertFalse(any(_sources_only(page) for page in pages))
        self.assertIn("PSX1", "\n".join(pages))


S01_LIVE = [
    "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running, not raining.",
    "Drain is clear, pan is clean and draining, base-pan slope is fine.",
    "Filter is clean.",
    "Evaporator fan spins freely with good airflow.",
    "Freeze sensor reads 2 kΩ at 25°C.",
    "Pressures 68 / 235 psig.",
    "Suction line clear / not iced; still frosting after drain, pan, filter and fan checks.",
]
_AUTH_SENTENCE = "authorize rooftop assembly r&r on the ccd-0007990 condensate and assembly path."


def _s01_walk(turns):
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


class TestS01PressuresBeforeRooftopRr(unittest.TestCase):
    def test_freeze_sensor_before_pressures_asks_then_advances(self):
        replies = _s01_walk(S01_LIVE)
        self.assertIn("refrigerant pressure", replies[0].lower())
        for reply in replies[:5]:
            low = reply.lower()
            self.assertNotIn("replace the rooftop assembly", low)
            self.assertNotIn("authorize rooftop assembly", low)
        sensor = replies[4].lower()
        self.assertIn("read the refrigerant pressures", sensor)
        pressures = replies[5].lower()
        self.assertIn("authorize rooftop assembly", pressures)
        self.assertIn("replace the rooftop assembly", pressures)
        self.assertIn("ccd-0007990", pressures)
        self.assertIn("pressure", pressures)
        later = replies[6].lower()
        self.assertNotEqual(later, pressures)
        self.assertNotIn(_AUTH_SENTENCE, later)
        self.assertIn("suction line is clear", later)
        self.assertIn("still frosting", later)
        self.assertIn("verify", later)
        self.assertIn("rooftop assembly", later)
        self.assertIn("ccd-0007990", later)


if __name__ == "__main__":
    unittest.main()
