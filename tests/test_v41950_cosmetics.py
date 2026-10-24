"""v4.19.50 cosmetics: leak period, one DO NOT page, kit caption, cited count, crop, Fpart, S02."""
import unittest
from pathlib import Path

import library_figure_backfill as fb
import manual_figures as mf


def _pdf_text(pdf: bytes) -> list[str]:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return pages


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


