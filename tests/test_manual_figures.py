"""Manual page images and figure crops stay with the cited step.

The Thetford water-valve and vacuum-breaker sheets are vector drawings.
Crops come from the rendered page, not from an embedded-image extract.
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pymupdf

import manual_figures as mf
from gd_library_coach import PLUMBING_TOILETS_CATEGORY

ROOT = Path(__file__).resolve().parents[1]
VALVE_PDF = ROOT / "tests" / "fixtures" / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf"
BREAKER_PDF = ROOT / "tests" / "fixtures" / "34123-34122-VacBrkr-1.pdf"
VALVE_TITLE = "Thetford Water Valve Kit 42109"
BREAKER_TITLE = "Thetford Vacuum Breaker Kit 34123/34122"
CONCERN = "Thetford 42070 leaks under the flush lever"


def _packet(title, pdf_path):
    indexed = mf.index_pdf_bytes(pdf_path.read_bytes())
    text = "\n".join(page["text"] for page in indexed["pages"])
    figures = [
        {
            "title": title,
            "page": fig["page"],
            "label": fig["label"],
            "png": fig["png"],
        }
        for fig in indexed["figures"]
    ]
    return {
        "title": title,
        "page": indexed["figures"][0]["page"] if indexed["figures"] else 1,
        "excerpt": text,
        "figures": figures,
    }, indexed


class TestManualFigureIndex(unittest.TestCase):
    def test_vector_sheets_crop_real_figures(self):
        for path, title, minimum in (
            (VALVE_PDF, VALVE_TITLE, 4),
            (BREAKER_PDF, BREAKER_TITLE, 1),
        ):
            indexed = mf.index_pdf_bytes(path.read_bytes())
            self.assertFalse(indexed["scanned"], title)
            self.assertGreaterEqual(len(indexed["pages"]), 1)
            self.assertGreaterEqual(len(indexed["figures"]), minimum, title)
            for page in indexed["pages"]:
                self.assertGreaterEqual(page["width"], 1000, title)
                self.assertFalse(mf.png_is_blank(page["png"]), title)
            labels = " ".join(fig["label"] for fig in indexed["figures"])
            self.assertIn("Fig. 1", labels, title)
            for fig in indexed["figures"]:
                self.assertGreaterEqual(fig["width"], 250, fig["label"])
                self.assertFalse(mf.png_is_blank(fig["png"]), fig["label"])
                self.assertIn(title.split()[0], title)

    def test_scanned_pdf_keeps_the_page_and_skips_figures(self):
        doc = pymupdf.open()
        page = doc.new_page()
        page.draw_rect(pymupdf.Rect(40, 40, 400, 500), color=(0, 0, 0), fill=(0, 0, 0), width=2)
        raw = doc.tobytes()
        doc.close()
        indexed = mf.index_pdf_bytes(raw)
        self.assertTrue(indexed["scanned"])
        self.assertEqual(len(indexed["pages"]), 1)
        self.assertEqual(indexed["figures"], [])
        self.assertFalse(mf.png_is_blank(indexed["pages"][0]["png"]))

    def test_howto_quotes_the_sheet_and_does_not_invent(self):
        indexed = mf.index_pdf_bytes(VALVE_PDF.read_bytes())
        text = "\n".join(page["text"] for page in indexed["pages"])
        detail = mf.procedure_detail(text, VALVE_TITLE, 1)
        self.assertIn(VALVE_TITLE, detail)
        self.assertIn("page 1", detail)
        self.assertIn("Pliers", detail)
        self.assertIn(f"not stated in {VALVE_TITLE}", detail)
        self.assertNotIn("12 V", detail)
        self.assertNotIn("120", detail)
        self.assertNotRegex(detail, r"disconnect rv water supply")
        self.assertNotRegex(detail, r"connect rv water supply")
        self.assertEqual(mf.procedure_detail("Disconnect RV water supply from toilet.", VALVE_TITLE, 1), "")

    def test_assets_round_trip_in_sqlite(self):
        indexed = mf.index_pdf_bytes(VALVE_PDF.read_bytes())
        assets = mf.assets_from_index(indexed, 7)
        tmp = tempfile.mkdtemp()
        try:
            root = Path(tmp)
            mf.write_asset_files(7, assets, root)
            db = str(root / "library.db")
            count = mf.save_assets_sqlite(db, 7, assets)
            self.assertEqual(count, len(assets))
            conn = sqlite3.connect(db)
            rows = conn.execute(
                "SELECT document_id, page, kind, label, image_path, width, png_blob, bbox FROM doc_assets"
            ).fetchall()
            conn.close()
            pages = [row for row in rows if row[2] == "page"]
            figures = [row for row in rows if row[2] == "figure"]
            self.assertTrue(pages)
            self.assertGreaterEqual(len(figures), 4)
            for row in rows:
                self.assertEqual(row[0], 7)
                self.assertGreater(row[1], 0)
                self.assertTrue(row[4])
                self.assertGreaterEqual(row[5], 250)
                self.assertFalse(row[6])
                png = (root / row[4]).read_bytes()
                self.assertFalse(mf.png_is_blank(png))
            for row in figures:
                self.assertIn(",", row[7] or "")
        finally:
            shutil.rmtree(tmp)

    def test_other_brand_image_is_refused(self):
        self.assertTrue(mf.brands_conflict("Thetford 42070", "Coleman-Mach 2111 service manual"))
        self.assertFalse(mf.brands_conflict("Thetford 42070", VALVE_TITLE))


class TestFigureCaption(unittest.TestCase):
    def test_caption_is_doc_page_fig(self):
        caption = mf.display_caption(VALVE_TITLE, 1, "Fig. 1 PEDAL REMOVED")
        self.assertEqual(caption, f"{VALVE_TITLE} / page 1 / Fig. 1")
        self.assertTrue(mf.wants_manual_image("show me the photo of the source"))
        self.assertFalse(mf.wants_manual_image("Not checked yet"))


if __name__ == "__main__":
    unittest.main()
