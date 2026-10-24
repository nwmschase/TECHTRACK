"""v4.19.58: live-library OCR and figure repairs (generic, code only)."""
import io

from PIL import Image, ImageDraw

import library_figure_backfill as fb
import manual_figures as mf


def test_full_figure_label_from_wrapped_caption():
    page = "FIGURE 2 - INSERTING WATER INLET SEAL ASSEMBLY\nFIGURE 3 - WATER \nVALVE CLOSED \nPOSITION\nWater Inlet \nopening"
    assert fb.full_figure_label("Fig. 3 WATER", page) == "Fig. 3 WATER VALVE CLOSED POSITION"
    assert fb.full_figure_label("Fig. 2 INSERTING WATER INLET SEAL ASSEMBLY", page) == ""
    assert fb.full_figure_label("Step 1", page) == ""


def _crop_with_caption() -> bytes:
    image = Image.new("RGB", (200, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 195, 200), outline="black", width=3)
    draw.text((10, 225), "FIGURE 3 - WATER", fill="black")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_trim_caption_from_crop_keeps_the_drawing():
    trimmed = fb.trim_caption_from_crop(_crop_with_caption())
    assert trimmed
    height = Image.open(io.BytesIO(trimmed)).height
    assert 200 <= height < 225


def test_complete_figure_rows_updates_label_and_crop_in_memory():
    rows = [{"kind": "figure", "document_id": 9, "page": 1, "label": "Fig. 3 WATER", "png": _crop_with_caption(),
             "caption": "Kit / page 1 / Fig. 3"}]
    chunks = [{"document_id": 9, "page": 1, "chunk_text": "FIGURE 3 - WATER\nVALVE CLOSED\nPOSITION\nPedal Pivot"}]
    fb.complete_figure_rows(rows, chunks)
    assert rows[0]["label"] == "Fig. 3 WATER VALVE CLOSED POSITION"
    assert Image.open(io.BytesIO(rows[0]["png"])).height < 225


def test_clean_asset_caption_drops_trailing_kind_word():
    assert fb.clean_asset_caption("Manual 42088 / page 3 / page") == "Manual 42088 / page 3"
    assert fb.clean_asset_caption("Kit 42109 / page 1 / Fig. 3") == "Kit 42109 / page 1 / Fig. 3"


def test_attach_pngs_cleans_caption():
    offers = [{"png": b"x", "caption": "Owner Manual / page 2 / page"}]
    fb.attach_pngs(None, offers)
    assert offers[0]["caption"] == "Owner Manual / page 2"


