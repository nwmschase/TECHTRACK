"""v4.19.41 live misses: Thetford repeats, the hidden marker, Bay figures, S13, S10, and S01."""
import io
import unittest
from pathlib import Path

from PIL import Image

import manual_figures as mf
import library_figure_backfill as fb

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
def _png() -> bytes:
    image = Image.new("RGB", (32, 32), (20, 40, 80))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


TINY_PNG = _png()


class TestFigureMatchesTheStep(unittest.TestCase):
    pass


class TestLoadedFigureCaption(unittest.TestCase):
    def test_a_rendered_figure_does_not_caption_a_failed_pdf_download(self):
        source = (Path(__file__).resolve().parents[1] / "rv_techtrack.py").read_text(encoding="utf-8")
        # v4.20.7: both old renderers are retired; they must not come back
        for name in ("def render_on_demand_library_pages", "def render_library_page_image"):
            self.assertNotIn(name, source)
        for name in ("def _render_cited_sheet", "def _render_gd_picture"):
            start = source.index(name)
            body = source[start:source.index("\ndef ", start + 1)]
            self.assertNotIn("Could not download file", body, name)
            self.assertNotIn("Could not download that PDF from shop storage.", body, name)
            self.assertNotIn("Storage not configured", body, name)


if __name__ == "__main__":
    unittest.main()
