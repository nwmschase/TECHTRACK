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
    pass


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
    pass


