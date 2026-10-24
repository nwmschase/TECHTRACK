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


