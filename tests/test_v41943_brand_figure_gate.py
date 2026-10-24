"""Lippert Power Gear pages must not illustrate a Thetford, Dometic, or other Lippert line.

The live library gained Power Gear tip sheets. A missing brand was treated as
a match, so How blocks and figures from those sheets landed on other cases.
The step cursor reads the stored chat text, and that appended How block
changed which Thetford check a real answer closed.
"""
import io
import unittest

from PIL import Image

import library_figure_backfill as fb
import manual_figures as mf

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
HOW = (
    "\n\nHow (Tip Sheet #216, page 4): Tools: wrench. "
    "Meter setting: not stated in Tip Sheet #216. "
    "Connector or pin: not stated in Tip Sheet #216. "
    "Expected reading: not stated in Tip Sheet #216. "
    "Order: 1. Remove the pump seal at the closet flange. "
    "2. Replace the motor brake. Step 1 of 14. "
    "Torque or spec: not stated in Tip Sheet #216\n"
    "Power Gear pump replacement / page 2 / Fig. 3 motor brake"
)


def _png() -> bytes:
    image = Image.new("RGB", (32, 32), (20, 40, 80))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


TINY = _png()


def _row(
    doc_id,
    title,
    brand,
    label,
    caption,
    product_line="",
    category_name="",
    models="",
    width=0,
    height=0,
):
    return {
        "id": doc_id,
        "document_id": doc_id,
        "kind": "figure",
        "title": title,
        "brand": brand,
        "product_line": product_line,
        "category_name": category_name,
        "models": models,
        "page": 1,
        "label": label,
        "caption": caption,
        "png": TINY,
        "width": width,
        "height": height,
    }


def _library():
    return [
        _row(
            1,
            "Tip Sheet #216",
            "Lippert",
            "Fig. 4 pump seal",
            "Power Gear pump seal",
            product_line="Power Gear",
            category_name="Leveling",
        ),
        _row(
            2,
            "Power Gear motor brake",
            "Power Gear",
            "Fig. 2 motor brake",
            "Motor brake assembly",
            product_line="Power Gear",
            category_name="Leveling",
        ),
        _row(
            3,
            "Power Gear pump replacement",
            "Power Gear",
            "Fig. 1 pump replacement",
            "Hydraulic pump replacement",
            product_line="Power Gear",
            category_name="Leveling",
        ),
        _row(
            4,
            "Thetford Water Valve Kit 42109",
            "Thetford",
            "Fig. 1 PEDAL REMOVED",
            "Water valve kit 42109 pedal",
            category_name="Plumbing / Toilets",
        ),
        _row(
            5,
            "Thetford Vacuum Breaker Kit 34123/34122",
            "Thetford",
            "Fig. 1 vacuum breaker",
            "Vacuum breaker kit 34122",
            category_name="Plumbing / Toilets",
        ),
        _row(
            6,
            "Dometic Brisk II diagnostic 3311071",
            "Dometic",
            "Fig. 2 ceiling thermostat",
            "B57915 ceiling selector",
            category_name="Air Conditioning",
        ),
        _row(
            7,
            "Lippert Level Up Towable Owner's Manual",
            "Lippert",
            "Fig. 1 CARTRIDGE VALVE",
            "Cartridge valve 177094",
            product_line="Level Up",
            category_name="Leveling",
            models="807662",
        ),
        _row(
            8,
            "Lippert PSX1 stabilizer jack",
            "Lippert",
            "Fig. 2 roll pin",
            "PSX1 manual crank roll pin",
            product_line="PSX1",
            category_name="Leveling",
            models="PSX1",
        ),
        _row(
            9,
            "Thetford Plastic Tank",
            "Thetford",
            "Fig. 1 plastic tank",
            "Plastic tank waste",
            category_name="Plumbing / Toilets",
        ),
        _row(
            11,
            "(Discontinued) Atwood Manual Tongue Jack Bevel Gear",
            "Atwood",
            "Fig. 1 bevel gear",
            "SAMPLE watermark",
            product_line="Tongue Jack",
            category_name="Leveling",
        ),
        _row(
            12,
            "Lippert TI-143",
            "Lippert",
            "port header",
            "TI-143 port header strip",
            product_line="Leveling",
            category_name="Leveling",
            width=960,
            height=36,
        ),
        _row(
            13,
            "Lippert TI-489 Titan Electric Bracket",
            "Lippert",
            "Fig. 1 Titan bracket",
            "TI-489 Titan bracket",
            product_line="Titan",
            category_name="Leveling",
        ),
    ]


def _blob(offers) -> str:
    return " ".join(
        f"{item.get('title') or ''} {item.get('label') or ''} {item.get('caption') or ''}"
        for item in offers
    ).lower()


class TestOffBrandFiguresStayOff(unittest.TestCase):
    def setUp(self):
        self.rows = _library()

    def test_dometic_ac_does_not_take_the_pump_seal_sheet(self):
        offers = fb.offers_for_turn(
            self.rows,
            "Replace the ceiling thermostat.",
            "The fan runs and the air is not cold. Show me the figure.",
            "Air Conditioning",
            "Dometic B57915E711J0EMX",
        )
        blob = _blob(offers)
        self.assertIn("dometic", blob)
        self.assertIn("thermostat", blob)
        bare = fb.offers_for_turn(
            self.rows,
            "Replace the ceiling thermostat.",
            "The fan runs and the air is not cold.",
            "Air Conditioning",
            "B57915E711J0EMX",
        )
        bare_blob = _blob(bare)
        self.assertIn("dometic", bare_blob)
        self.assertNotIn("tip sheet", bare_blob)
        self.assertNotIn("power gear", bare_blob)
        self.assertNotIn("tip sheet", blob)
        self.assertNotIn("216", blob)
        self.assertNotIn("power gear", blob)
        self.assertNotIn("pump seal", blob)
        self.assertNotIn("thetford", blob)


    def test_level_up_ground_control_and_psx1_do_not_share_power_gear_figures(self):
        cases = (
            (
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes then dumps back to home. Loose cartridge 177094.",
                "177094",
            ),
            (
                "Leveling",
                "Lippert Ground Control 343633",
                "Auto-level lifts the driver side. Zero-point calibration is the repair.",
                "",
            ),
            (
                "Leveling",
                "Lippert PSX1",
                "Front stabilizer jack. The roll pin is broken.",
                "roll pin",
            ),
        )
        for category, model, reply, expect in cases:
            offers = fb.offers_for_turn(self.rows, reply, "show me the figure", category, model)
            blob = _blob(offers)
            self.assertNotIn("tip sheet", blob, model)
            self.assertNotIn("power gear", blob, model)
            self.assertNotIn("motor brake", blob, model)
            self.assertNotIn("pump seal", blob, model)
            self.assertNotIn("thetford", blob, model)
            if expect:
                self.assertIn(expect, blob, model)

    def test_packets_keep_the_case_document_only(self):
        chunks = [
            {"document_id": 1, "title": "Tip Sheet #216", "page": 1, "excerpt": "Remove the pump seal."},
            {"document_id": 4, "title": "Thetford Water Valve Kit 42109", "page": 1, "excerpt": "Pull the pedal."},
            {"document_id": 2, "title": "Power Gear motor brake", "page": 1, "excerpt": "Release the motor brake."},
        ]
        packets = fb.figure_packets(
            self.rows,
            chunks,
            "Plumbing / Toilets Thetford Style II 42070 pedal 42109",
        )
        titles = " ".join(packet["title"] for packet in packets).lower()
        self.assertIn("42109", titles)
        self.assertNotIn("tip sheet", titles)
        self.assertNotIn("power gear", titles)
        self.assertNotIn("motor brake", titles)


def _tip_chunk():
    excerpt = (
        "Needed: wrench. Remove the pump seal. Install the motor brake. "
        "Figure 4 shows the pump seal on the Power Gear motor. "
    ) * 4
    return {
        "title": "Tip Sheet #216",
        "brand": "Lippert",
        "product_line": "Power Gear",
        "category_name": "Leveling",
        "page": 4,
        "excerpt": excerpt,
        "figures": [
            {
                "png": TINY,
                "label": "Fig. 4 pump seal",
                "caption": "Power Gear pump seal",
                "title": "Tip Sheet #216",
                "page": 4,
            }
        ],
    }


_OFF_BRAND = ("tip sheet", "power gear", "pump seal", "motor brake", "216")


def _assert_clean(case, proc):
    sheet = " ".join(proc.bay_order)
    lowered = sheet.lower()
    case.assertNotIn("How (Tip Sheet", sheet)
    for banned in _OFF_BRAND:
        case.assertNotIn(banned, lowered, proc.model)
    placed = " ".join(
        f"{fig.title} {fig.caption}"
        for group in (proc.step_figures or [])
        for fig in group
    )
    placed += " " + " ".join(
        f"{fig.title} {fig.caption}" for fig in (proc.figures or [])
    )
    for banned in _OFF_BRAND:
        case.assertNotIn(banned, placed.lower(), proc.model)


class TestEveryCaseBlocksOffBrand(unittest.TestCase):
    def test_a_document_with_no_system_does_not_fill_a_named_system(self):
        blank = _row(9, "Lippert service bulletin", "Lippert", "Fig. 1", "hydraulic pump")
        self.assertFalse(
            fb.fits_case(
                blank,
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes then dumps home.",
                "",
            )
        )
        self.assertFalse(
            fb.fits_case(
                blank,
                "Air Conditioning",
                "B57915E711J0EMX",
                "The air is not cold.",
                "Replace the ceiling thermostat.",
            )
        )


def _stored_live_step(step: str, how: str, figure: str) -> str:
    """One stored turn: flattened eight fields, the live How block, then the caption.

    Live joins the shop lines onto one line and appends How (title): plus
    "Title / page N / Fig. ...". The title's ")" must not hide the step number.
    """
    return (
        " ".join(step.splitlines())
        + how
        + f" Thetford Water Valve Kit 42109 / page 1 / {figure}"
    )


def _live_how(title="(Discontinued) Atwood Manual Tongue Jack Bevel Gear"):
    """The block live appends: a How title that contains ")", then a caption."""
    return (
        f"\n\nHow ({title}, page 1): Tools: wrench. "
        "Meter setting: not stated in the manual. "
        "Order: 1. Remove the pump seal at the closet flange. "
        "Step 1 of 14. "
        f"{title} / page 1 / Fig. 1 bevel gear"
    )


class TestMissingStorageUsesTheBundledCrop(unittest.TestCase):
    def test_a_thetford_offer_without_an_r2_object_still_has_a_crop(self):
        png = mf.png_for_library_offer(
            {
                "title": "Thetford Water Valve Kit 42109",
                "label": "Fig. 1 PEDAL REMOVED",
                "caption": "Thetford Water Valve Kit 42109 / page 1 / Fig. 1 PEDAL REMOVED",
                "page": 1,
                "file_path": "documents/9_missing_thetford.pdf",
                "image_path": "library-pages/9/p1-fig-1.png",
                "bundled": True,
            }
        )
        self.assertTrue(png)
        self.assertFalse(mf.png_is_blank(png))
        other = mf.png_for_library_offer(
            {
                "title": "Dometic Brisk II",
                "label": "Fig. 2 ceiling thermostat",
                "file_path": "documents/missing.pdf",
                "image_path": "library-pages/6/p1-fig.png",
            }
        )
        self.assertEqual(other, b"")


