"""v4.19.41 live misses: Thetford repeats, the hidden marker, Bay figures, S13, S10, and S01."""
import io
import unittest
from pathlib import Path

from PIL import Image

import manual_figures as mf
from bay_procedure import compile_bay_procedure, paint_library_step_figures, render_bay_procedure_pdf
from gd_library_coach import (
    GROUND_CONTROL_LEVEL_LINE,
    avoid_duplicate_reply,
    ensure_ground_control_level_path,
)
import library_figure_backfill as fb

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
def _png() -> bytes:
    image = Image.new("RGB", (32, 32), (20, 40, 80))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


TINY_PNG = _png()


def _walk(turns, category, model, draft=""):
    history = []
    replies = []
    for latest in turns:
        reply = avoid_duplicate_reply(draft, history, latest, category, model)
        replies.append(reply)
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": reply})
    return replies


class TestThetfordAdvance(unittest.TestCase):
    def test_vacuum_answers_do_not_repeat_the_same_step(self):
        replies = _walk(
            [
                "Thetford 42070 leaks under the flush lever when flushing",
                "Supply connection is tight.",
                "I flushed it.",
                "Still see water.",
                "Checked again.",
                "No leak while flushing.",
                "Looks the same.",
            ],
            CAT,
            MODEL,
            draft="Check whether the vacuum breaker leaks while flushing.",
        )
        self.assertIn("vacuum breaker", replies[1].lower())
        vacuum = replies[1].strip()
        self.assertNotEqual(replies[2].strip(), vacuum)
        for index in (3, 4, 6):
            self.assertNotEqual(replies[index].strip(), vacuum, index)
            self.assertNotIn("UNCONFIRMED", replies[index])
        self.assertNotIn("UNCONFIRMED", "\n".join(replies))

    def test_a_weep_still_does_not_skip_the_vacuum_breaker(self):
        replies = _walk(
            [
                "toilet leaks under the flush lever when flushing",
                "Supply is tight. The water valve weeps at the pedal.",
            ],
            CAT,
            MODEL,
            draft="Check the water supply line.",
        )
        self.assertIn("vacuum breaker", replies[1].lower())
        self.assertNotIn("42109", replies[1])


class TestFigureMatchesTheStep(unittest.TestCase):
    def test_vacuum_reply_does_not_show_the_water_valve_kit(self):
        reply = (
            "Check whether the vacuum breaker leaks while flushing.\n"
            "Fig. 1, Thetford Vacuum Breaker Kit 34123/34122, page 1."
        )
        user = "Supply is tight. The water valve weeps at the pedal."
        offers = mf.bundled_thetford_offers(reply, user, CAT, MODEL)
        self.assertTrue(offers)
        blob = " ".join(f"{item['title']} {item['label']}" for item in offers).lower()
        self.assertIn("3412", blob)
        self.assertNotIn("42109", blob)
        rows = [
            {
                "id": 1,
                "document_id": 9,
                "kind": "figure",
                "title": "Thetford Water Valve Kit 42109",
                "brand": "Thetford",
                "page": 1,
                "label": "Fig. 1 PEDAL REMOVED",
                "caption": "Water valve kit 42109",
                "png": TINY_PNG,
            },
            {
                "id": 2,
                "document_id": 10,
                "kind": "figure",
                "title": "Thetford Vacuum Breaker Kit 34123/34122",
                "brand": "Thetford",
                "page": 1,
                "label": "Fig. 1 vacuum breaker",
                "caption": "Vacuum breaker kit 34123",
                "png": TINY_PNG,
            },
        ]
        chosen = fb.select_library_figures(rows, reply, user, CAT, MODEL)
        self.assertTrue(chosen)
        self.assertIn("3412", chosen[0]["title"])
        self.assertNotIn("42109", chosen[0]["title"])


class TestBayUsesLibraryFigures(unittest.TestCase):
    def test_library_rows_land_beside_the_matching_step(self):
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category=CAT,
            chunks=[
                {
                    "title": "Thetford Style II OM Permanent RV Toilet 42088",
                    "page": 3,
                    "excerpt": "Check the water supply line connection.",
                }
            ],
        )
        rows = [
            {
                "id": 2,
                "document_id": 10,
                "kind": "figure",
                "title": "Thetford Vacuum Breaker Kit 34123/34122",
                "brand": "Thetford",
                "page": 1,
                "label": "Fig. 1 vacuum breaker",
                "caption": "Vacuum breaker 34123",
                "png": TINY_PNG,
            },
            {
                "id": 1,
                "document_id": 9,
                "kind": "figure",
                "title": "Thetford Water Valve Kit 42109",
                "brand": "Thetford",
                "page": 1,
                "label": "Fig. 1 PEDAL",
                "caption": "Water valve 42109",
                "png": TINY_PNG,
            },
        ]
        proc = paint_library_step_figures(proc, rows)
        vacuum = next(i for i, step in enumerate(proc.bay_order) if "vacuum" in step.lower())
        valve = next(i for i, step in enumerate(proc.bay_order) if "42109" in step or "weep" in step.lower())
        self.assertIn("3412", proc.step_figures[vacuum][0].title)
        self.assertIn("42109", proc.step_figures[valve][0].title)
        self.assertNotIn("UNCONFIRMED", " ".join(proc.bay_order))
        self.assertNotIn("UNCONFIRMED", " ".join(proc.do_not))
        import pymupdf

        doc = pymupdf.open(stream=render_bay_procedure_pdf(proc), filetype="pdf")
        images = sum(len(page.get_images()) for page in doc)
        text = "\n".join(page.get_text() for page in doc).lower()
        doc.close()
        self.assertGreater(images, 0)
        self.assertNotIn("unconfirmed", text)


class TestLoadedFigureCaption(unittest.TestCase):
    def test_a_rendered_figure_does_not_caption_a_failed_pdf_download(self):
        source = (Path(__file__).resolve().parents[1] / "rv_techtrack.py").read_text(encoding="utf-8")
        start = source.index("def render_on_demand_library_pages")
        body = source[start:source.index("\ndef ", start + 1)]
        caption_at = body.index('st.caption("Storage not configured"')
        guard_at = body.rindex("elif not rendered:", 0, caption_at)
        self.assertLess(guard_at, caption_at)
        self.assertNotIn("Could not download file", body[:guard_at])


class TestGirardHoseQuote(unittest.TestCase):
    def test_hose_sentence_survives_a_blower_line(self):
        proc = compile_bay_procedure(
            "Girard GSWH-2 gives E8 error code.",
            "Girard",
            "GSWH-2",
            "Water Heaters",
            chunks=[
                {
                    "title": "Girard Tankless Water Heater GSWH-2 Troubleshooting and Service Manual CCD-0009390",
                    "page": 23,
                    "excerpt": (
                        "The sensing tube is at the blower. "
                        "Check for integrity and connections of the pressure switch hose at the blower."
                    ),
                }
            ],
        )
        hay = " ".join(src.get("excerpt") or "" for src in proc.sources)
        self.assertIn("Check for integrity and connections of the pressure switch hose.", hay)


class TestGroundRepairPhrase(unittest.TestCase):
    def test_the_shipped_level_reply_names_the_repair(self):
        self.assertIn("zero-point calibration is the repair", GROUND_CONTROL_LEVEL_LINE.lower())
        history = [
            {"role": "user", "content": "Auto-level lifts driver-side tires though nearly level."},
            {
                "role": "assistant",
                "content": "Confirm the controller, jack, and touch pad plugs are seated.",
            },
        ]
        reply = ensure_ground_control_level_path("Check the harness.", history)
        self.assertIn("zero-point calibration is the repair", reply.lower())


class TestFreezeSensorGate(unittest.TestCase):
    def test_gate_words_authorize_by_turn_five(self):
        replies = _walk(
            [
                "Furrion FACR08HESA2-PS rooftop AC. Water leaking inside while running.",
                "drain",
                "pan",
                "fan",
                "pressures. freeze sensor 2k at 25C",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
            draft="Read the freeze sensor.",
        )
        last = replies[4].lower()
        self.assertIn("authorize rooftop assembly", last)
        self.assertIn("replace the rooftop assembly", last)
        self.assertIn("ccd-0007990", last)
        self.assertNotIn("read the freeze sensor", last)
        self.assertNotIn("replace the rooftop assembly", replies[3].lower())

    def test_no_pressure_walk_still_does_not_authorize(self):
        replies = _walk(
            [
                "Furrion FACR08 rooftop AC. Water leaking inside.",
                "Drain is clear. Pan is clean and draining. Base-pan slope is fine.",
                "Filter is clean. Fan spins freely.",
                "Freeze sensor 2k at 25C.",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
            draft="Read the freeze sensor.",
        )
        last = replies[-1].lower()
        self.assertNotIn("replace the rooftop assembly", last)
        self.assertNotIn("authorize rooftop assembly", last)


if __name__ == "__main__":
    unittest.main()
