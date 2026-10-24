"""Live v4.19.40 misses: figures, the full Bay procedure, an optional photo, the procedure list, and the freeze-sensor shorthand."""
import unittest

from pathlib import Path

import manual_figures as mf
from gd_library_coach import (
    figure_render_honesty_note,
)

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
CITE = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"


def _procedure_history(first_step):
    return [
        {"role": "user", "content": "toilet leaks under the flush lever"},
        {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
        {"role": "assistant", "content": "Check whether the vacuum breaker leaks while flushing."},
        {"role": "user", "content": "Vacuum breaker is dry. No leak there."},
        {"role": "assistant", "content": first_step},
    ]


class TestBundledThetfordFigures(unittest.TestCase):
    def test_show_me_and_a_physical_step_get_a_real_crop(self):
        show = mf.bundled_thetford_offers(
            "Check the water supply line connection at the water valve.",
            "show me the figure",
            CAT,
            MODEL,
        )
        self.assertTrue(show)
        self.assertTrue(show[0]["png"])
        self.assertFalse(mf.png_is_blank(show[0]["png"]))
        self.assertIn("png", show[0])
        valve = mf.bundled_thetford_offers(
            "Fig. 1 PEDAL REMOVED. Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me",
            CAT,
            MODEL,
        )
        labels = " ".join(item["label"] for item in valve).lower()
        self.assertIn("pedal", labels)
        self.assertTrue(any(item["label"] == "page" for item in valve))
        other = mf.bundled_thetford_offers("Read the freeze sensor.", "show me", "Air Conditioning", "FACR08")
        self.assertEqual(other, [])

    def test_empty_library_labels_the_bundled_page_as_a_last_resort(self):
        import library_figure_backfill as fb

        offers = fb.offers_for_turn(
            [],
            "Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me the figure",
            CAT,
            MODEL,
        )
        self.assertTrue(offers)
        self.assertTrue(offers[0].get("png"))
        self.assertNotIn("will display the shop", " ".join(item.get("caption") or "" for item in offers).lower())
        note = figure_render_honesty_note("Thetford Water Valve Kit 42109", True)
        self.assertIn("could not load", note.lower())
        miss = fb.offers_for_turn(
            [],
            "No document in the shop library for this unit.",
            "show me",
            CAT,
            MODEL,
        )
        self.assertEqual(miss, [])
        other = fb.offers_for_turn([], "Read the freeze sensor.", "show me", "Air Conditioning", "FACR08")
        self.assertEqual(other, [])
        root = Path(__file__).resolve().parents[1]
        source = root.joinpath("rv_techtrack.py").read_text(encoding="utf-8")
        backfill = root.joinpath("library_figure_backfill.py").read_text(encoding="utf-8")
        self.assertIn("offers_for_turn", source)
        self.assertIn("Backfill selected manuals", source)
        self.assertNotIn("Backfill page images and figures", source)
        self.assertNotIn('st.button("Backfill page images")', source)
        self.assertIn("st.file_uploader(", source)
        self.assertIn("Photo (optional)", source)
        self.assertNotIn("Bundled kit sheet", backfill)


if __name__ == "__main__":
    unittest.main()
