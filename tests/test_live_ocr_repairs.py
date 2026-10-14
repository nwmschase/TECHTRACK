"""v4.19.58: live-library OCR and figure repairs (generic, code only)."""
import io

from PIL import Image, ImageDraw

import bay_procedure as bp
import library_figure_backfill as fb
import manual_figures as mf


def test_line_break_hyphen_rejoins_only_known_words():
    assert mf.rejoin_line_break_hyphen("Remove Bolt Cov-", "ers (if present).") == "Remove Bolt Covers (if present)."
    assert mf.rejoin_line_break_hyphen("Uncover holding tank open-", "ing and remove towel(s).").endswith("opening and remove towel(s).")
    # A real hyphenated term keeps its hyphen.
    assert mf.rejoin_line_break_hyphen("attach two o-", "rings on the hooks") == "attach two o- rings on the hooks"


def test_english_body_joins_ascii_hyphen_breaks():
    text = "5. Replace Bolt Covers (if pres-\nent).\n2. Uncover holding tank open-\ning and remove towel(s)."
    body = mf._english_body(text)
    assert "present" in body and "opening" in body
    assert "pres ent" not in body and "open ing" not in body


def test_space_split_rejoin_is_conservative():
    assert mf.rejoin_space_splits("Take off the bolt cov ers now") == "Take off the bolt covers now"
    assert mf.rejoin_space_splits("Uncover the open ing") == "Uncover the opening"
    assert mf.rejoin_space_splits("if pres ent") == "if present"
    # Two real words stay apart.
    for phrase in ("set it in to place", "pull a part out", "turn the water on", "the old seal"):
        assert mf.rejoin_space_splits(phrase) == phrase


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


def test_dedupe_source_rows_same_quote():
    rows = [
        {"title": "Manual A", "page": 3, "excerpt": "Check the supply line."},
        {"title": "Manual A", "page": 6, "excerpt": "Check the  supply line."},
        {"title": "Manual A", "page": 7, "excerpt": "Different quote."},
        {"title": "Manual B", "page": 1, "excerpt": "Check the supply line."},
    ]
    kept = bp._dedupe_source_rows(rows)
    assert [(r["title"], r["page"]) for r in kept] == [("Manual A", 3), ("Manual A", 7), ("Manual B", 1)]


def test_doc_part_numbers_from_file_name():
    assert bp._doc_part_numbers({"file_path": "documents/13_2026_42109_SK_WaterValve_Res_42049C-1.pdf"}).split() == ["42109", "42049"]
    assert bp._doc_part_numbers({"file_path": "docs/GDS.JACKS.002.pdf"}) == ""


def test_display_title_uses_doc_text_numbers():
    layout_title = mf._display_title("Water Valve Kit 42109", "water valve steps\n42109 42049")
    assert layout_title == "Water valve 42049 / kit 42109"
