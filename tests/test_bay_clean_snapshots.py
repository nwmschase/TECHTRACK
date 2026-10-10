"""Lock the PDF text of the eight sheets that were clean on the v4.19.10 check."""
import re
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bay_procedure import compile_bay_procedure, render_bay_procedure_pdf

ROOT = Path(__file__).resolve().parent / "fixtures" / "bay_clean_text"
CREATED = datetime(2026, 10, 9, 15, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
GROUNDED = (
    "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
    "tires off the ground even though the coach was nearly level."
)
FACR08_BOOK = {
    "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
    "page": 5,
    "excerpt": (
        "FACR08HESA2 8K rooftop. ? Do not install in an unventilated space. "
        "? Boltx 4 ? Mounting Framex 1 ? Screwx 2"
    ),
}
CASES = (
    (
        "S03",
        "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work.",
        "BAL",
        "Soft-Touch SS 5.1",
        "Leveling",
        None,
    ),
    (
        "S04",
        "temperature dial OFF but compressor still running, freezer frozen solid",
        "Furrion",
        "FCR10",
        "Refrigerators",
        [
            {
                "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                "page": 45,
                "excerpt": "Cand Topen with no jumper on the thermostat (Fig.",
            }
        ],
    ),
    (
        "S05",
        "icing up on rear wall — only about half from the top down",
        "Furrion",
        "FCR10",
        "Refrigerators",
        None,
    ),
    (
        "S07",
        "FCR10 E2 fan fault current on the freezer evaporator fan",
        "Furrion",
        "FCR10",
        "Refrigerators",
        [
            {
                "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                "page": 33,
                "excerpt": "The fan sits in the cavityso the inverter PCB can see it (Fig.",
            }
        ],
    ),
    (
        "S09",
        "Dometic B57915 rooftop air conditioner is not cooling.",
        "Dometic",
        "B57915",
        "Air Conditioning",
        [
            {
                "title": "Dometic B57915 Installation Manual",
                "page": 9,
                "excerpt": "Minor adjustments while pushingup the housing. Installationwe q r 23.",
            }
        ],
    ),
    (
        "S10",
        GROUNDED,
        "Lippert",
        "Ground Control 343633",
        "Leveling",
        [
            {
                "title": "Lippert Ground Control notes",
                "page": 2,
                "excerpt": "-> If the fault reverses when the harness is swapped, replace the sensor.",
            }
        ],
    ),
    (
        "S11",
        "Furrion FACT12SA2 rooftop shows E3",
        "Furrion",
        "FACT12SA2",
        "Air Conditioning",
        [FACR08_BOOK],
    ),
    (
        "S12",
        "Furrion FACT12SA2 rooftop shows E2",
        "Furrion",
        "FACT12SA2",
        "Air Conditioning",
        [FACR08_BOOK],
    ),
)


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class TestCleanSheetSnapshots(unittest.TestCase):
    def test_clean_sheet_text_matches_the_locked_snapshot(self):
        for name, concern, brand, model, category, chunks in CASES:
            proc = compile_bay_procedure(
                concern=concern,
                brand=brand,
                model=model,
                category=category,
                chunks=chunks or [],
                created=CREATED,
            )
            got = _norm(_pdf_text(render_bay_procedure_pdf(proc)))
            locked = (ROOT / f"{name}.txt").read_text(encoding="utf-8").strip()
            self.assertEqual(got, locked, name)


if __name__ == "__main__":
    unittest.main()
