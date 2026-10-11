"""v4.19.50 cosmetics: leak period, one DO NOT page, kit caption, cited count, crop, Fpart, S02."""
import unittest
from pathlib import Path

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import (
    cited_figure_count,
    clean_ocr_prose,
    compile_bay_procedure,
    compose_sheet,
    render_bay_procedure_pdf,
)
from gd_library_coach import avoid_duplicate_reply, without_reading_filler


def _thetford():
    return compile_bay_procedure(
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


def _pdf_text(pdf: bytes) -> list[str]:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return pages


class TestLookForLeaksPeriod(unittest.TestCase):
    def test_the_send_path_keeps_the_period(self):
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
                {
                    "role": "assistant",
                    "content": (
                        f"Here is the repair procedure.\nStep {number} of {total}.\n"
                        "HOW: Do this step.\n📖 Source: Thetford Water Valve Kit 42109, page 1"
                    ),
                }
            )
            history.append({"role": "user", "content": "Yes."})
        done = avoid_duplicate_reply(
            "draft", history, "The water is on.", "Plumbing / Toilets", "Thetford 42070"
        )
        live = without_reading_filler(
            done, history, "The water is on.", "Plumbing / Toilets", "Thetford 42070"
        )
        self.assertIn("Look for leaks.", live)
        self.assertTrue(live.rstrip().endswith("Look for leaks."))


class TestDoNotStaysTogether(unittest.TestCase):
    def test_the_list_is_one_page_and_the_generic_line_is_gone(self):
        proc = _thetford()
        self.assertNotIn("Do not order a part number that is not on the sheet.", proc.do_not)
        pages = _pdf_text(render_bay_procedure_pdf(proc))
        blob = "\n".join(pages)
        self.assertNotIn("Do not order a part number that is not on the sheet.", blob)
        homes = [
            index
            for index, page in enumerate(pages)
            if "DO NOT" in page or "Do not replace the water valve" in page
        ]
        self.assertEqual(len(homes), 1)
        page = pages[homes[0]]
        self.assertIn("DO NOT", page)
        self.assertIn("Do not replace the water valve", page)
        self.assertIn("Do not use scouring powders", page)
        self.assertNotIn("Never use automotive antifreeze", page)
        self.assertNotIn("do not flush until the ice thaws", page)
        self.assertNotIn("the toilet valve must be open", page)


class TestStepFourShowCaption(unittest.TestCase):
    def test_show_me_uses_the_kit_label(self):
        layout = mf.thetford_kit_layout("valve")
        step = next(
            item for item in layout["steps"]
            if "fig. 1" in ((item.get("figure") or {}).get("label") or "").lower()
        )
        reply = mf.format_one_step(step, 4, len(layout["steps"]))
        self.assertEqual(mf.thetford_procedure_show_caption(reply), "42109 Fig. 1")
        self.assertEqual(mf.thetford_procedure_show_caption(mf.thetford_proving_line("valve")), "")
        om = {
            "id": 11,
            "document_id": 11,
            "kind": "page",
            "title": "Thetford Style II OM Permanent RV Toilet 42088",
            "brand": "Thetford",
            "page": 3,
            "label": "page",
            "caption": "Thetford Style II OM Permanent RV Toilet 42088 / page 3 / page",
            "category_name": "Plumbing / Toilets",
            "png": b"page",
        }
        offers = fb.offers_for_turn(
            [om], reply, "show me", "Plumbing / Toilets", "Thetford 42070"
        )
        self.assertTrue(offers)
        blob = " ".join(
            f"{item.get('caption') or ''} {item.get('label') or ''}" for item in offers
        )
        self.assertIn("42109 Fig. 1", blob)
        self.assertNotIn("42088", blob)
        self.assertNotIn("/ page", blob.lower())
        empty = fb.offers_for_turn(
            [],
            "Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me the figure",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertTrue(empty)
        self.assertTrue(empty[0].get("png"))
        self.assertNotIn("will display the shop", (empty[0].get("caption") or "").lower())


class TestCitedCountMatchesDrawn(unittest.TestCase):
    def test_thetford_valve_sheet_counts_the_drawn_figures(self):
        proc = _thetford()
        pages = compose_sheet(proc)
        images = [image for page in pages for image in page.images]
        self.assertEqual(cited_figure_count(proc), len(images))
        self.assertGreaterEqual(len(images), 4)


class TestKitCropKeepsTheCaption(unittest.TestCase):
    def test_the_figure_crop_includes_its_caption_line(self):
        import pymupdf

        path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf"
        doc = pymupdf.open(path)
        page = doc[0]
        png = mf.render_page_png(page)
        figures = mf.detect_page_figures(page, png)
        labels = " ".join(fig["label"] for fig in figures)
        self.assertIn("Fig. 1", labels)
        self.assertIn("Fig. 2", labels)
        self.assertIn("Fig. 3", labels)
        self.assertIn("Fig. 4", labels)
        pedal = next(fig for fig in figures if "PEDAL REMOVED" in fig["label"].upper())
        caption = next(rect for text, rect in mf._text_lines(page) if text.startswith("FIGURE 1"))
        box = mf._figure_above_caption(page, caption)
        need = int((caption.y1 - box.y0) * mf._ZOOM)
        self.assertGreaterEqual(pedal["height"], need - 2)
        doc.close()


class TestItemFPart(unittest.TestCase):
    def test_item_f_stays_separate_from_part(self):
        cleaned = clean_ocr_prose("Cartridge Valve, item F, part 177094.")
        self.assertNotIn("Fpart", cleaned)
        self.assertIn("item F, part 177094", cleaned)
        self.assertIn("black", clean_ocr_prose("The wire is b lack at the plug.").lower())


class TestS02DoesNotReaskPeacemaker(unittest.TestCase):
    def test_turn_three_moves_past_the_bypass(self):
        history = []
        turns = [
            (
                "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead.",
                "Do the Peacemaker bypass at the rooftop unit and report whether the compressor runs while the fan stays still.",
            ),
            (
                "122 VAC at the control box. Fan High is dead.",
                "Do the Peacemaker bypass at the rooftop unit.",
            ),
        ]
        for latest, draft in turns:
            reply = avoid_duplicate_reply(
                draft, history, latest, "Air Conditioning", "Coleman-Mach 2111-0001"
            )
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        latest = "Peacemaker bypass: compressor runs, fan does not rotate. About 1.91 A, shaft locked."
        for draft in (
            "Do the Peacemaker bypass at the rooftop unit.",
            "Next: do the Peacemaker bypass again at the rooftop unit.",
            "Run a Peacemaker bypass of the thermostat and control box. Report whether the compressor runs.",
            "Please repeat the Peacemaker bypass and report compressor and fan.",
        ):
            reply = avoid_duplicate_reply(
                draft, history, latest, "Air Conditioning", "Coleman-Mach 2111-0001"
            )
            low = reply.lower()
            self.assertNotRegex(low, r"\b(?:do|run|repeat|perform)\b.{0,48}\bpeacemaker\b")
            self.assertRegex(low, r"capacitor|microfarad")
