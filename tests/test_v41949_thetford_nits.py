"""v4.19.49 Thetford review: leak-test fields, no leaked instructions, one pedal step."""
import io
import unittest

from PIL import Image

import library_figure_backfill as fb
import manual_figures as mf


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


class TestInstructionTextStaysOffTheReply(unittest.TestCase):

    def test_an_empty_library_shows_no_bundled_caption(self):
        offers = fb.offers_for_turn(
            [],
            "Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me the figure",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertTrue(offers)
        self.assertTrue(offers[0].get("png"))
        self.assertNotIn("will display the shop", (offers[0].get("caption") or "").lower())
        backfill = __import__("pathlib").Path(__file__).resolve().parents[1].joinpath(
            "library_figure_backfill.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Bundled kit sheet", backfill)


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


if __name__ == "__main__":
    unittest.main()
