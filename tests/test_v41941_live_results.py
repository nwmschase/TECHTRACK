"""v4.19.41 live misses: Thetford repeats, the hidden marker, Bay figures, S13, S10, and S01."""
import io
import unittest
from pathlib import Path

from PIL import Image

import manual_figures as mf
from gd_library_coach import (
    GROUND_CONTROL_LEVEL_LINE,
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


class TestLoadedFigureCaption(unittest.TestCase):
    def test_a_rendered_figure_does_not_caption_a_failed_pdf_download(self):
        source = (Path(__file__).resolve().parents[1] / "rv_techtrack.py").read_text(encoding="utf-8")
        for name in ("def render_on_demand_library_pages", "def render_library_page_image"):
            start = source.index(name)
            body = source[start:source.index("\ndef ", start + 1)]
            self.assertNotIn("Could not download file", body, name)
            self.assertNotIn("Could not download that PDF from shop storage.", body, name)
            self.assertNotIn("Storage not configured", body, name)


if __name__ == "__main__":
    unittest.main()
