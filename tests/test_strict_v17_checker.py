"""Leader rev5 page review (rev6): cited pages, one number per figure, Where and term fixes."""
import io
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bay_procedure as bp  # noqa: E402
import profile_check as pc  # noqa: E402

LIB = [
    {"title": "Thetford Vacuum Breaker 34123 / 34122", "page": 1, "chunk_text": "Refer to Figure 1 for component locations."},
    {"title": "Thetford Vacuum Breaker 34123 / 34122", "page": 2,
     "chunk_text": "1. With pliers, slide clamp A down inlet tube, then remove inlet tube from vacuum breaker.\n"
                   "4. Install new flush hose on nozzle, then secure with new clamp C."},
]


def _sources(page_a: int) -> str:
    return (
        "SOURCES (SHOP DOCUMENT LIBRARY)\n"
        f"- Thetford Vacuum Breaker Kit 34123/34122 page {page_a}\n"
        "With pliers, slide clamp A down inlet tube, then remove inlet tube from vacuum breaker.\n"
        "- Thetford Vacuum Breaker Kit 34123/34122 page 2\n"
        "Install new flush hose on nozzle, then secure with new clamp C.\n"
    )


def test_source_page_rule_catches_a_wrong_page():
    assert not pc.source_page_rule(_sources(1), LIB).ok
    assert pc.source_page_rule(_sources(2), LIB).ok


def test_source_page_rule_catches_a_quote_not_in_the_manual():
    text = "SOURCES (SHOP DOCUMENT LIBRARY)\n- Thetford Vacuum Breaker Kit 34123/34122 page 2\nTighten the clamp until it clicks twice.\n"
    assert not pc.source_page_rule(text, LIB).ok


def test_builder_moves_a_quote_to_its_page():
    rows = [{"title": "Thetford Vacuum Breaker Kit 34123/34122", "page": 1,
             "excerpt": "With pliers, slide clamp A down inlet tube, then remove inlet tube from vacuum breaker."}]
    assert bp._verify_source_pages(rows, LIB)[0]["page"] == 2


def _png(with_label: bool, size=(300, 220), font_px=None) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    w, h = size
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    box_bottom = int(h * 0.82)
    d.rectangle((5, 5, w - 5, box_bottom), outline="black", width=3)
    d.line((20, 20, w - 20, box_bottom - 10), fill="black", width=2)
    if with_label:
        font = ImageFont.load_default()
        if font_px:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_px)
            except OSError:
                pass
        d.text((10, box_bottom + 12), "FIGURE 1 - PEDAL REMOVED", fill="black", font=font)
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def test_crop_cuts_the_printed_kit_label_only():
    from PIL import Image

    cut = Image.open(io.BytesIO(bp.crop_printed_figure_label(_png(True))))
    assert 180 <= cut.size[1] < 195  # label gone, the drawing's border stays
    plain = _png(False)
    assert bp.crop_printed_figure_label(plain) == plain


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_printed_number_rule_catches_a_second_number():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(50, 50, 500, 380), stream=_png(True, (900, 660), 40))
    page.insert_text((60, 400), "Fig. 2 PEDAL REMOVED, Kit 42109, page 1")
    assert not pc.printed_figure_number_rule(doc).ok


def test_flange_spacer_step_is_conditional_and_hose_term_is_one_word():
    import inspect

    src = inspect.getsource(bp)
    assert "If the flange is low, add Thetford spacers to bring it to 7/16 inch." in src
    assert "The supply line is on the water valve fitting." not in src
    assert "The water hose is on the water valve fitting." in src


def test_trash_bag_where_is_a_place():
    import manual_figures as mf

    assert mf._where_field("Remove toilet from floor and place on plastic trash bag.").startswith("On the trash bag")
