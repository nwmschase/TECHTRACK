"""Page images and figure crops for the shop Document Library.

Pages are rendered at about 150 dpi with PyMuPDF. Figures are vector drawings
and embedded images, cropped from the rendered page at the drawing box that
sits under a Fig. / Figure caption or a step number. A scanned page with no
text keeps the page image and does not grow a made-up figure.
"""
from __future__ import annotations

import io
import re
import sqlite3
from pathlib import Path

PAGE_DPI = 150
_ZOOM = PAGE_DPI / 72.0
MIN_CROP_PX = 250

_CAPTION_RE = re.compile(
    r"^(figure|fig\.?)\s*(\d+)\b\s*[-–—:]?\s*(.*)$",
    re.I,
)
_STEP_RE = re.compile(r"^(?:step\s+)?(\d+)[\.\)]\s+\S", re.I)
_INSTALL_BAN_RE = re.compile(
    r"\b(?:disconnect|connect)\b.{0,80}\bwater supply\b",
    re.I,
)
_TOOL_WORD_RE = re.compile(
    r"\b(?:towels?|pliers|phillips(?:-head)? screwdriver|screwdrivers?|"
    r"needle[-\s]?nose(?: pliers)?|wrenches?|\d/\d-inch wrench|"
    r"multimeters?|torque wrench|plastic trash bags?|protective gloves)\b",
    re.I,
)
_METER_RE = re.compile(
    r"\b(?:continuity|ohms?|volts?(?:\s+AC|\s+DC)?|VAC|VDC|kΩ|millivolts?)\b",
    re.I,
)
_PIN_RE = re.compile(
    r"\b(?:clamp\s+[A-C]|pin\s+[A-Z0-9]{1,3}\b|connector\s+[A-Z0-9]{1,4}\b|"
    r"terminal\s+[A-Z0-9]{1,4}\b|drive pin|pocket\s+[A-B])\b",
    re.I,
)
_READING_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:V|VAC|VDC|ohm|ohms|Ω|kΩ|psi|in-?lb|ft-?lb|N·m|Nm)\b",
    re.I,
)
_TORQUE_RE = re.compile(
    r"(?:do not overtighten|torque[^.]{0,60}|in-?lb|ft-?lb|N·m)",
    re.I,
)
_BRANDS = (
    "thetford",
    "coleman",
    "dometic",
    "furrion",
    "suburban",
    "girard",
    "lippert",
    "norcold",
    "bal",
)

ASSET_DDL = """
CREATE TABLE IF NOT EXISTS doc_assets (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    page INTEGER NOT NULL,
    kind VARCHAR(20) NOT NULL,
    label VARCHAR(120) DEFAULT '',
    image_path VARCHAR(400) DEFAULT '',
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    png_blob BLOB,
    caption TEXT DEFAULT '',
    bbox VARCHAR(80) DEFAULT '',
    chunk_id INTEGER
)
"""


def format_bbox(bbox) -> str:
    """Store a figure box as x0,y0,x1,y1 in PDF points."""
    if bbox is None or bbox == "":
        return ""
    if isinstance(bbox, str):
        return bbox[:80]
    try:
        return ",".join(f"{float(part):.2f}" for part in bbox)[:80]
    except (TypeError, ValueError):
        return ""


def ensure_asset_columns(conn) -> None:
    """Add caption, bbox, and chunk_id on a library database that predates them."""
    conn.execute(ASSET_DDL)
    have = {row[1] for row in conn.execute("PRAGMA table_info(doc_assets)").fetchall()}
    alters = (
        ("caption", "ALTER TABLE doc_assets ADD COLUMN caption TEXT DEFAULT ''"),
        ("bbox", "ALTER TABLE doc_assets ADD COLUMN bbox VARCHAR(80) DEFAULT ''"),
        ("chunk_id", "ALTER TABLE doc_assets ADD COLUMN chunk_id INTEGER"),
    )
    for name, ddl in alters:
        if name not in have:
            conn.execute(ddl)


def _fitz():
    import pymupdf

    return pymupdf


def render_page_png(page, zoom: float = _ZOOM) -> bytes:
    """Rasterize one PyMuPDF page. Vector drawings become pixels here."""
    fitz = _fitz()
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def _png_size(png: bytes) -> tuple[int, int]:
    from PIL import Image

    image = Image.open(io.BytesIO(png))
    return image.size


def png_is_blank(png: bytes) -> bool:
    """True when the crop is empty or nearly all white."""
    if not png:
        return True
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("L")
    width, height = image.size
    if width < 8 or height < 8:
        return True
    hist = image.histogram()
    dark = sum(hist[:210])
    return dark < (width * height * 0.008)


def _upscale_min_width(png: bytes, min_px: int = MIN_CROP_PX) -> bytes:
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    width, height = image.size
    if width >= min_px and max(width, height) >= 300:
        return png
    scale = max(min_px / max(width, 1), 300 / max(width, height, 1))
    if scale <= 1.01:
        return png
    resized = image.resize(
        (max(min_px, int(width * scale)), max(1, int(height * scale))),
        Image.Resampling.LANCZOS,
    )
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()


def _crop_rendered(png: bytes, page_rect, box, zoom: float) -> bytes:
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    pad = 4
    x0 = max(0, int(box.x0 * zoom) - pad)
    y0 = max(0, int(box.y0 * zoom) - pad)
    x1 = min(image.width, int(box.x1 * zoom) + pad)
    y1 = min(image.height, int(box.y1 * zoom) + pad)
    if x1 - x0 < 12 or y1 - y0 < 12:
        return b""
    cropped = image.crop((x0, y0, x1, y1))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return _upscale_min_width(buf.getvalue())


def _text_lines(page) -> list[tuple[str, object]]:
    fitz = _fitz()
    rows = []
    data = page.get_text("dict")
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            text = "".join(span.get("text") or "" for span in line.get("spans") or []).strip()
            if text:
                rows.append((text, fitz.Rect(line["bbox"])))
    return rows


def _ink_rects(page) -> list:
    rects = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        if rect.width < 28 or rect.height < 28:
            continue
        if rect.width > page.rect.width * 0.96 and rect.height > page.rect.height * 0.45:
            continue
        rects.append(rect)
    try:
        for info in page.get_image_info() or []:
            fitz = _fitz()
            rect = fitz.Rect(info.get("bbox") or info.get("transform") or (0, 0, 0, 0))
            if rect.width > 28 and rect.height > 28:
                rects.append(rect)
    except Exception:
        pass
    return rects


def _figure_above_caption(page, caption_rect):
    """The drawing whose bottom edge sits on the caption, in the same column."""
    best = None
    best_key = None
    for rect in _ink_rects(page):
        if rect.y1 > caption_rect.y0 + 14:
            continue
        if rect.height < 36 or rect.width < 50:
            continue
        if caption_rect.x0 < rect.x0 - 36 or caption_rect.x0 > rect.x1 + 12:
            continue
        gap = abs(caption_rect.y0 - rect.y1)
        if gap > 40:
            continue
        key = (gap, rect.width * rect.height)
        if best_key is None or key < best_key:
            best_key = key
            best = rect
    return best


def _overlaps(a, b) -> bool:
    if a is None or b is None:
        return False
    inter = a & b
    if inter.is_empty:
        return False
    smaller = min(a.get_area(), b.get_area()) or 1
    return inter.get_area() / smaller > 0.45


def _label_from_caption(text: str) -> str:
    match = _CAPTION_RE.match(text.strip())
    if not match:
        return text.strip()[:80]
    number = match.group(2)
    rest = (match.group(3) or "").split("/")[0].strip(" -–—:")
    label = f"Fig. {number}"
    if rest:
        label = f"{label} {rest}"
    return label[:110]


def detect_page_figures(page, page_png: bytes) -> list[dict]:
    """Crop each captioned drawing on one page. Scanned pages have no captions."""
    claimed = []
    found = []
    for text, rect in _text_lines(page):
        if not _CAPTION_RE.match(text):
            continue
        box = _figure_above_caption(page, rect)
        if box is None or any(_overlaps(box, prior) for prior in claimed):
            continue
        png = _crop_rendered(page_png, page.rect, box, _ZOOM)
        if not png or png_is_blank(png):
            continue
        width, height = _png_size(png)
        claimed.append(box)
        found.append(
            {
                "label": _label_from_caption(text),
                "png": png,
                "width": width,
                "height": height,
                "bbox": (box.x0, box.y0, box.x1, box.y1),
            }
        )
    if found:
        return found
    # No Fig. caption. A step number sitting under a drawing is the label.
    for text, rect in _text_lines(page):
        match = _STEP_RE.match(text)
        if not match:
            continue
        box = _figure_above_caption(page, rect)
        if box is None or any(_overlaps(box, prior) for prior in claimed):
            continue
        png = _crop_rendered(page_png, page.rect, box, _ZOOM)
        if not png or png_is_blank(png):
            continue
        width, height = _png_size(png)
        claimed.append(box)
        found.append(
            {
                "label": f"Step {match.group(1)}",
                "png": png,
                "width": width,
                "height": height,
                "bbox": (box.x0, box.y0, box.x1, box.y1),
            }
        )
    return found


def index_pdf_bytes(pdf_bytes: bytes) -> dict:
    """Render every page and crop captioned figures. Scanned PDFs return pages only."""
    fitz = _fitz()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    figures = []
    any_text = False
    try:
        for index, page in enumerate(doc):
            text = (page.get_text("text") or "").strip()
            if text:
                any_text = True
            png = render_page_png(page)
            width, height = _png_size(png)
            pages.append(
                {
                    "page": index + 1,
                    "png": png,
                    "width": width,
                    "height": height,
                    "text": text,
                }
            )
        if any_text:
            for index, page in enumerate(doc):
                for figure in detect_page_figures(page, pages[index]["png"]):
                    figure["page"] = index + 1
                    figures.append(figure)
    finally:
        doc.close()
    return {"pages": pages, "figures": figures, "scanned": not any_text}


def display_caption(title: str, page, label: str = "") -> str:
    """Shop caption: Doc / page / Fig."""
    doc = (title or "Manual").strip()
    try:
        page_n = int(page or 1)
    except (TypeError, ValueError):
        page_n = 1
    raw = (label or "").strip()
    match = re.search(r"fig(?:ure)?\.?\s*(\d+)", raw, re.I)
    if match:
        fig = f"Fig. {match.group(1)}"
    elif re.match(r"step\s+\d+", raw, re.I):
        fig = raw.split()[0].title() + " " + re.search(r"\d+", raw).group(0)
    elif raw:
        fig = raw
    else:
        fig = "page"
    return f"{doc} / page {page_n} / {fig}"


def brand_name(text: str) -> str:
    blob = (text or "").lower()
    for name in _BRANDS:
        if name in blob:
            return name
    return ""


def brands_conflict(job_text: str, figure_title: str) -> bool:
    """A Coleman crop does not illustrate a Thetford step."""
    job = brand_name(job_text)
    figure = brand_name(figure_title)
    return bool(job and figure and job != figure)


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text or "").strip()
    if not flat:
        return []
    parts = re.split(r"(?<=[.!?])\s+", flat)
    kept = []
    for part in parts:
        part = part.strip()
        if not part or _INSTALL_BAN_RE.search(part):
            continue
        kept.append(part)
    return kept


def _needed_tools(text: str) -> list[str]:
    match = re.search(
        r"\bNeeded\b(.{0,500}?)\b(?:Before Beginning|Remove|Install)\b",
        text or "",
        re.I | re.S,
    )
    window = match.group(1) if match else (text or "")[:800]
    found = []
    for hit in _TOOL_WORD_RE.findall(window):
        word = re.sub(r"\s+", " ", hit).strip()
        if word.lower() not in {item.lower() for item in found}:
            found.append(word)
    return found[:8]


def _numbered_order(text: str) -> list[str]:
    """Quote the remove/install steps. Skip the water-supply install lines."""
    raw_lines = []
    for raw in re.split(r"[\r\n]+", text or ""):
        line = re.sub(r"\s+", " ", raw).strip(" \t•■")
        if line:
            raw_lines.append(line)
    steps = []
    current = ""
    for line in raw_lines:
        if re.match(r"\d+[\.\)]\s+\S", line):
            if current:
                steps.append(current)
            current = line
            continue
        if current and len(line) < 90 and not re.match(
            r"^(?:remove|install|english|fran[cç]ais|espa[nñ]ol)\b", line, re.I
        ):
            current = f"{current} {line}".strip()
    if current:
        steps.append(current)
    kept = []
    for line in steps:
        if _INSTALL_BAN_RE.search(line):
            continue
        if re.search(r"closet flange|turn off rv|flush toilet to drain|trash bag", line, re.I):
            continue
        if len(line) < 18:
            continue
        if re.search(r"[àáâäèéêëìíîïòóôöùúûüñç]", line, re.I):
            continue
        if re.search(
            r"\b(retire el|pince|chasse|enveloppe|coupez|recubrimiento|dispositivo)\b",
            line,
            re.I,
        ):
            continue
        kept.append(line[:200])
    primary = [
        line
        for line in kept
        if re.search(
            r"vacuum|flush hose|clamp|cartridge|inlet seal|water valve|retainer",
            line,
            re.I,
        )
    ]
    if len(primary) >= 2:
        return primary[:5]
    focused = [
        line
        for line in kept
        if re.search(r"valve|vacuum|clamp|pedal|cartridge|flush hose|retainer|inlet seal", line, re.I)
    ]
    return (focused or kept)[:5]


def procedure_detail(text: str, doc_title: str, page) -> str:
    """How to do the step, from this chunk only.

    An empty string means the chunk is not a procedure (a one-line cite, a
    scanned page). Callers leave the locked shop line alone in that case.
    Missing tools, meter settings, pins, readings, or torque are written
    'not stated in <doc>' and never filled in.
    """
    doc = (doc_title or "the manual").strip()
    body = text or ""
    if len(re.sub(r"\s+", " ", body).strip()) < 280:
        return ""
    if not re.search(r"\b(needed|remove|install|figure|fig\.)\b", body, re.I):
        return ""
    tools = _needed_tools(body)
    meter = _METER_RE.findall(body)
    pins = []
    for hit in _PIN_RE.findall(body):
        word = re.sub(r"\s+", " ", hit).strip()
        if word.lower() not in {item.lower() for item in pins}:
            pins.append(word)
    readings = []
    for hit in _READING_RE.findall(body):
        word = re.sub(r"\s+", " ", hit).strip()
        if word not in readings:
            readings.append(word)
    order = _numbered_order(body)
    torque = ""
    for sentence in _sentences(body):
        if _TORQUE_RE.search(sentence):
            torque = sentence[:160]
            break
    if not tools and not order and not pins:
        return ""

    def stated(values: list[str]) -> str:
        if values:
            return ", ".join(values[:6])
        return f"not stated in {doc}"

    try:
        page_n = int(page or 0)
    except (TypeError, ValueError):
        page_n = 0
    page_bit = f", page {page_n}" if page_n else ""
    order_bit = " ".join(order) if order else f"not stated in {doc}"
    torque_bit = torque or f"not stated in {doc}"
    return (
        f"How ({doc}{page_bit}): Tools: {stated(tools)}. "
        f"Meter setting: {stated(meter)}. "
        f"Connector or pin: {stated(pins)}. "
        f"Expected reading: {stated(readings)}. "
        f"Order: {order_bit} "
        f"Torque or spec: {torque_bit}"
    )


def asset_path(document_id: int, page: int, kind: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (label or kind).lower()).strip("-") or kind
    return f"library-pages/{int(document_id)}/p{int(page)}-{slug}.png"


def write_asset_files(document_id: int, assets: list[dict], root: Path) -> None:
    """Write PNG files next to the library DB. The sqlite row stores the same path."""
    for asset in assets:
        rel = asset.get("image_path") or asset_path(
            document_id, asset["page"], asset["kind"], asset.get("label") or ""
        )
        asset["image_path"] = rel
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(asset["png"])


def save_assets_sqlite(db_path: str, document_id: int, assets: list[dict]) -> int:
    """Persist crops in the same sqlite file the library backup uploads."""
    conn = sqlite3.connect(db_path)
    try:
        ensure_asset_columns(conn)
        conn.execute("DELETE FROM doc_assets WHERE document_id = ?", (int(document_id),))
        for asset in assets:
            conn.execute(
                """
                INSERT INTO doc_assets
                    (document_id, page, kind, label, image_path, width, height, png_blob,
                     caption, bbox, chunk_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(document_id),
                    int(asset["page"]),
                    asset["kind"],
                    asset.get("label") or "",
                    asset.get("image_path") or "",
                    int(asset.get("width") or 0),
                    int(asset.get("height") or 0),
                    asset.get("png") or b"",
                    asset.get("caption") or "",
                    format_bbox(asset.get("bbox")),
                    asset.get("chunk_id"),
                ),
            )
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM doc_assets WHERE document_id = ?",
            (int(document_id),),
        ).fetchone()[0]
        return int(count)
    finally:
        conn.close()


def assets_from_index(indexed: dict, document_id: int) -> list[dict]:
    rows = []
    for page in indexed.get("pages") or []:
        rows.append(
            {
                "document_id": document_id,
                "page": page["page"],
                "kind": "page",
                "label": "",
                "png": page["png"],
                "width": page["width"],
                "height": page["height"],
                "image_path": asset_path(document_id, page["page"], "page", "page"),
                "caption": "",
                "bbox": "",
            }
        )
    for figure in indexed.get("figures") or []:
        rows.append(
            {
                "document_id": document_id,
                "page": figure["page"],
                "kind": "figure",
                "label": figure.get("label") or "",
                "png": figure["png"],
                "width": figure["width"],
                "height": figure["height"],
                "caption": figure.get("label") or "",
                "bbox": format_bbox(figure.get("bbox")),
                "image_path": asset_path(
                    document_id, figure["page"], "figure", figure.get("label") or "fig"
                ),
            }
        )
    return rows


PHOTO_ASK = "No manual figure covers this step. Take a photo of what you see and send it."

_FOREIGN_LINE_RE = re.compile(
    r"\b(?:retirez|installez|cabinet d|chasse|pince|alicates|inodoro|dispositivo|"
    r"trousse|coupez|serviette|suministro|recubrimiento|manguera|"
    r"anti-refoulement|crampon|tuyau|évacuation|evacuation|desodorante|"
    r"eaux usées|bac à|gants|lunettes|bride de sol|feuille d)\b",
    re.I,
)
_SECTION_HEAD_RE = re.compile(
    r"^(before beginning|preparation|prerequisites|removal|installation|"
    r"remove(?:\s+\S+){0,4}|install(?:\s+\S+){0,4}|reinstall(?:\s+\S+){0,3})\s*$",
    re.I,
)
_FOREIGN_CUT_RE = re.compile(
    r"\b(?:les|des|sur|pour|avec|dans|une|los|las|del|para|con|le|la|el|suivants|"
    r"crampons|placez|remettez|boulons|chapeaux|chasse|pince|alicates|"
    r"inodoro|dispositivo|trousse|coupez|serviette|suministro|"
    r"recubrimiento|manguera|anti-refoulement|tuyau|evacuation|évacuation|"
    r"desodorante|bride|feuille|cabinet|enveloppe|soulevez|débranchez|"
    r"debranchez|ouvrez|retirez|apriete|instale|abrazadera|tuercas|"
    r"haga|vuelva|destape|brida|receptaculo|receptáculo|"
    r"levante|coloque|envuelva|fije|separe|corra|jetez|resserrez|sous|pise)\b",
    re.I,
)
_STEP_NUM_RE = re.compile(r"^(\d+)[\.\)]\s+(\S.*)$")
_CAUTION_SENTENCE_RE = re.compile(
    r"(?:NOTE|WARNING|CAUTION)\s*:[^.]+(?:\.|$)"
    r"|Do not overtighten\.?"
    r"|Wear protective[^.]+\.",
    re.I,
)
_FIG_CALLOUT_RE = re.compile(
    r"\b(?:figs?\.?|figures?)\s*\d+(?:\s*&\s*\d+)?",
    re.I,
)
_LETTER_CALLOUT_RE = re.compile(
    r"\b(?:clamp|pocket|pin)\s+[A-C]\b",
    re.I,
)


def missing_figure_photo_ask(has_figure: bool) -> str:
    """GD line when this step has no usable manual figure."""
    if has_figure:
        return ""
    return PHOTO_ASK


YES_LINE = "Yes, go to the next step."
NO_LINE = "No, do this step again."
PHOTO_STEP = "Take a photo of this step and send it."
PHOTO_WAIT = "Send the photo before the next step."
# One chat turn can hold a few sheet actions that share a figure.
SECTION_ACTION_CAP = 4

# One shop step. Every Thetford check and every repair step uses these labels.
STEP_FIELDS = (
    "WHERE",
    "SAFETY",
    "TOOLS / METER SETTING",
    "HOW",
    "GOOD vs BAD",
    "NEXT",
    "FIGURE",
    "PHOTO",
)

# A place named in the step's own words. The first match that fits is enough.
_WHERE_RULES = (
    (r"\bbehind (?:the )?toilet\b", "Behind the toilet, under the water hose."),
    (r"\bback of (?:the )?toilet\b", "Back of the toilet."),
    (r"\bwater inlet opening\b", "In the water inlet hole."),
    (r"\bpocket\s+a\b", "Pocket A on the pedal."),
    (r"\bpocket\s+b\b", "Pocket B on the pedal."),
    (r"\bpedal pivot\b", "On the pedal pivot."),
    (r"\binlet tube\b", "On the inlet tube."),
    (r"\bflush hose\b", "On the flush hose."),
    (r"\bvacuum breaker\b", "At the vacuum breaker."),
    (r"\bcloset flange\b", "At the closet flange, under the toilet."),
    (r"\bholding tank opening\b", "Over the tank hole in the floor."),
    (r"\bon its side\b", "On the floor, with the pedal facing up."),
    (r"\bfrom (?:the )?floor\b", "The toilet sits on the floor."),
    (r"\bnozzle\b", "On the nozzle."),
    (r"\bpedal\b", "At the pedal."),
    (r"\bwater valve\b", "At the water valve."),
    (r"\bretainer\b", "At the retainer."),
    (r"\blever\b", "At the lever."),
    (r"\block\b", "At the lock."),
)


def format_step_fields(fields: dict) -> str:
    """The fixed shop template. A blank value is UNCONFIRMED."""
    lines = []
    for name in STEP_FIELDS:
        value = re.sub(r"\s+", " ", str((fields or {}).get(name) or "")).strip()
        lines.append(f"{name}: {value or 'UNCONFIRMED'}")
    lines.append(YES_LINE)
    lines.append(NO_LINE)
    return "\n".join(lines)


def _where_field(source: str) -> str:
    """Where the part is, using only a place this step's words already name."""
    found = []
    for pattern, phrase in _WHERE_RULES:
        if phrase in found:
            continue
        if re.search(pattern, source or "", re.I):
            found.append(phrase)
        if len(found) == 2:
            break
    return " ".join(found) if found else "UNCONFIRMED"


def _safety_field(sheet: str) -> str:
    """Water, power, and propane. Only a shutoff the sheet states is filled in."""
    text = sheet or ""
    bits = []
    if re.search(r"turn off rv water supply|turn off (?:the )?(?:rv )?water\b", text, re.I):
        bits.append("Turn the RV water off before this work.")
    else:
        bits.append("Water off: UNCONFIRMED.")
    if re.search(r"turn off (?:the )?power\b", text, re.I):
        bits.append("Turn the power off before this work.")
    else:
        bits.append("Power off: UNCONFIRMED.")
    if re.search(r"\bpropane\b|\blp gas\b", text, re.I):
        bits.append("The sheet names propane.")
    else:
        bits.append("Propane off: UNCONFIRMED.")
    if re.search(r"\bgloves\b", text, re.I):
        bits.append("Put on gloves and glasses.")
    return " ".join(bits)


def _tools_field(sheet: str, source: str) -> str:
    """Tools the sheet lists, and the meter setting if the sheet gives one."""
    tools = _needed_tools(sheet)
    for hit in _TOOL_WORD_RE.findall(source or ""):
        word = re.sub(r"\s+", " ", hit).strip()
        if word.lower() not in {item.lower() for item in tools}:
            tools.append(word)
    tool_bit = ", ".join(tools) if tools else "UNCONFIRMED"
    meter = ""
    for blob in (source or "", sheet or ""):
        hit = _METER_RE.search(blob)
        if hit:
            meter = hit.group(0)
            break
    return f"Tools: {tool_bit}. Meter setting: {meter or 'UNCONFIRMED'}."


def _result_clause(text: str) -> str:
    match = re.search(r"\buntil ([^.]+)", text or "", re.I)
    if not match:
        return ""
    clause = re.sub(r"\s+", " ", match.group(1)).strip(" .")
    if not clause:
        return ""
    return clause[0].upper() + clause[1:]


def _good_bad_field(source: str, action: str) -> str:
    """What the sheet says the result looks like. Anything else stays UNCONFIRMED."""
    blob = f"{source or ''}\n{action or ''}"
    good = _result_clause(action) or _result_clause(source)
    bad = ""
    if re.search(r"snaps in place", blob, re.I):
        good = good or "The pedal snaps in place"
    if re.search(r"opens and closes completely", blob, re.I):
        good = good or "The waste ball opens and closes completely"
    if re.search(r"checking for leaks at all connections", blob, re.I):
        bad = "Leaks at all connections"
    if re.search(r"if leak persists", blob, re.I):
        bad = "The leak persists from the water valve"
    return f"Good: {good or 'UNCONFIRMED'}. Bad: {bad or 'UNCONFIRMED'}."


def _next_field(next_how: str) -> str:
    """The next sheet step is the good path. A bad path the sheet omits stays UNCONFIRMED."""
    good = (next_how or "").strip() or "UNCONFIRMED"
    return f"On good: {good} On bad: UNCONFIRMED."


def _figure_field(step: dict, doc: str) -> str:
    figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
    if not figure:
        return "UNCONFIRMED"
    label = (figure.get("label") or "").strip()
    title = (figure.get("title") or doc or "").strip()
    page = figure.get("page")
    bits = [bit for bit in (label, title) if bit]
    if page:
        bits.append(f"page {page}")
    return ", ".join(bits) if bits else "UNCONFIRMED"


def _photo_field(how: str) -> str:
    import gd_step_photo as photos

    return " ".join(photos.photo_ask_lines(how))


def fill_step_fields(step: dict, sheet: str, doc: str, next_how: str = "") -> dict:
    """Fill the template from this sheet. Do not invent a missing value."""
    source = step.get("source") or ""
    how = (step.get("text") or "").strip() or "UNCONFIRMED"
    return {
        "WHERE": _where_field(source),
        "SAFETY": _safety_field(sheet),
        "TOOLS / METER SETTING": _tools_field(sheet, source),
        "HOW": how,
        "GOOD vs BAD": _good_bad_field(source, how),
        "NEXT": _next_field(next_how),
        "FIGURE": _figure_field(step, doc),
        "PHOTO": _photo_field(how),
    }


def step_field_lines(step: dict) -> list[str]:
    """Eight shop fields, then each extra action in this section, then yes or no."""
    fields = step.get("fields") or {}
    actions = []
    for item in step.get("actions") or []:
        text = (item or "").strip()
        if text and text not in actions:
            actions.append(text)
    how = (fields.get("HOW") or "").strip()
    if how and how not in actions:
        actions.insert(0, how)
    lines = []
    for name in STEP_FIELDS:
        if name == "HOW":
            lines.append(f"HOW: {actions[0] if actions else 'UNCONFIRMED'}")
            for extra in actions[1:]:
                lines.append(extra)
            continue
        lines.append(f"{name}: {(fields.get(name) or '').strip() or 'UNCONFIRMED'}")
    lines.append(YES_LINE)
    lines.append(NO_LINE)
    return lines

_ACTION_VERB = (
    r"turn|pull|put|lift|flush|take|set|push|hit|press|tighten|connect|disconnect|"
    r"lay|wash|rinse|throw|slide|cover|point|stand|read|move"
)
_AND_THEN_RE = re.compile(
    rf"\b(?:{_ACTION_VERB})\b(?:\s+\w+){{0,8}}\s+and then\s+\b(?:{_ACTION_VERB})\b",
    re.I,
)


def _word_count(sentence: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", sentence or ""))


def step_sentences(step: dict) -> list[str]:
    """The eight shop fields a tech reads for one step."""
    return step_field_lines(step)


def readability_problems(step: dict) -> list[str]:
    """HOW stays one short action. Every template field is filled."""
    problems = []
    how = step.get("text") or ""
    if _AND_THEN_RE.search(how):
        problems.append("two actions joined by and then")
    if _word_count(how) > 15:
        problems.append(f"{_word_count(how)} words: {how}")
    fields = step.get("fields") or {}
    for name in STEP_FIELDS:
        if not (fields.get(name) or "").strip():
            problems.append(f"missing {name}")
    return problems


def format_one_step(step: dict, number: int, total: int) -> str:
    """One GD turn: the eight shop fields, then a caution when the sheet has one."""
    lines = [
        "Here is the repair procedure.",
        f"Step {number} of {total}.",
        *step_field_lines(step),
    ]
    if step.get("caution"):
        lines.append(f"Caution: {step['caution']}")
    return "\n".join(line for line in lines if line).strip()


def _figures_by_number(figures: list) -> dict:
    found = {}
    for figure in figures or []:
        label = figure.get("label") if isinstance(figure, dict) else getattr(figure, "caption", "")
        for number in _figure_numbers(label or ""):
            found.setdefault(number, figure)
    return found


def _kit_paths(kind: str):
    """Demo library files. Step text is parsed from the file, not stored here."""
    root = Path(__file__).resolve().parent / "tests" / "fixtures"
    if kind == "valve":
        return root / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf", "Thetford Water Valve Kit 42109"
    if kind == "breaker":
        return root / "34123-34122-VacBrkr-1.pdf", "Thetford Vacuum Breaker Kit 34123/34122"
    return None


_THEN_SPLIT_RE = re.compile(r"\s*,?\s*\bthen\b\s*", re.I)
_AND_VERB_SPLIT_RE = re.compile(
    r"\s+\band\b\s+(?=(?:pull|turn|put|take|lift|flush|slide|throw|cover|press|hit|push|"
    r"tighten|lay|wash|rinse|set|stand|read|move|grab|place|remove|rotate|insert|install|"
    r"replace|discard|connect|disconnect|unhook|spread|wrap|secure|activate|align|grasp|"
    r"hold|lower)\b)",
    re.I,
)
_LETTER_SPLIT_RE = re.compile(r"(?:^|:)\s*[a-d]\.\s+", re.I)
_FIG_BIT_RE = re.compile(r"\(?\s*(?:see\s+)?figs?\.?\s*\d+(?:\s*&\s*\d+)?\s*\)?\.?", re.I)
_NOUN_SWAPS = (
    (r"\brv water supply line\b", "water hose"),
    (r"\bwater supply line\b", "water hose"),
    (r"\brv water supply\b", "water"),
    (r"\bwater connection\b", "water hose"),
    (r"\bcloset flange bolt covers\b", "bolt covers"),
    (r"\bcloset flange nuts\b", "nuts"),
    (r"\bcloset flange seal\b", "floor seal"),
    (r"\bcloset bolts\b", "floor bolts"),
    (r"\bmounting holes\b", "holes"),
    (r"\bholding tank opening\b", "tank hole"),
    (r"\bwater valve cartridge retainer\b", "retainer"),
    (r"\bwater valve cartridge assembly\b", "water valve"),
    (r"\bwater valve assembly\b", "water valve"),
    (r"\bwater valve drive pin\b", "drive pin"),
    (r"\bpedal return spring tab\b", "spring tab"),
    (r"\bdrive arm pin\b", "drive pin"),
    (r"\bwater inlet seal assembly\b", "inlet seal"),
    (r"\bwater inlet seal\b", "inlet seal"),
    (r"\bcompression spring\b", "spring"),
    (r"\bwater inlet opening\b", "inlet hole"),
    (r"\bsmall needle-nose pliers\b", "small pliers"),
    (r"\bneedle-nose pliers\b", "small pliers"),
    (r"\bneedle nose pliers\b", "small pliers"),
    (r"\btowel\(s\)\b", "a towel"),
    (r"\bclockwise\b", "to the right"),
    (r"\bcounter-?clockwise\b", "to the left"),
    (r"\binstructions\b", "the steps"),
    (r"\bholding tank deodorant\b", "tank deodorant"),
    (r"\bshroud\b", "cover"),
    (r"\bo-rings?\b", "rings"),
)
_FILLER_RES = (
    r"\bper rv owner's manual\b",
    r"\bcompletely\b",
    r"\bthoroughly\b",
    r"\bslightly\b",
    r"\bfirmly\b",
    r"\bwith a quick motion\b",
    r"\bholding bowl,?\s*",
    r"\bto catch water\b",
    r"\bto avoid contact with human waste\b",
    r"\(if present\)",
    r"\bif present\b",
    r"\bto assure\b",
    r"\bentire\b",
    r"\bprotective\b",
    r"\blong sleeves,?\s*(?:and\s*)?",
    r"\bnose/face mask\b",
    r"\bthetford\b",
)
# Longer, more specific frames first. Nouns are already swapped.
_ACTION_FRAMES = (
    (r"^turn off (?:the )?water$", "Turn off the water to the RV"),
    (r"^turn on (?:the )?water$", "Turn the RV water on"),
    (r"^turn (?:the )?water on$", "Turn the RV water on"),
    (r"^flush test (?:the )?toilet.*$", "Flush the toilet one time"),
    (r"^flush (?:the )?toilet.*$", "Flush the toilet one time"),
    (r"^place (?:a )?towel.*$", "Put a towel under the water hose"),
    (r"^place on (?:a |the )?trash bag$", "Put the toilet on a trash bag"),
    (r"^grab (?:the )?front underside of (?:the )?pedal$", "Grab the front of the pedal"),
    (r"^insert (?:a |the )?new water valve.*$", "Push the new valve in until it stops"),
    (r"^uncover (?:the )?tank hole$", "Take the towel off the tank hole"),
    (r"^remove (?:a |the )?towel.*$", "Take the towel off"),
    (r"^holding down (?:the )?pedal,?\s*spread (?:the )?cover apart.*$", "Pull the cover off while you hold the pedal down"),
    (r"^disconnect (?:the )?(.+) from (?:the )?(.+)$", r"Pull the \1 off the \2"),
    (r"^connect (?:the )?(.+) (?:to|onto) (?:the )?(.+)$", r"Push the \1 onto the \2"),
    (r"^remove (?:the )?(.+?) and (?:the )?nuts$", r"Take off the \1 and the nuts"),
    (r"^with pliers,\s*slide clamp ([a-c]) down (?:the )?(.+)$", r"Slide clamp \1 down the \2"),
    (r"^slide (?:the )?clamp ([a-c]) down (?:the )?(.+)$", r"Slide clamp \1 down the \2"),
    (r"^slide (?:the )?clamp ([a-c]) back(?:ward)? on (?:the )?(.+)$", r"Slide clamp \1 back on the \2"),
    (r"^slide (?:a |the )?new clamp ([a-c]) (?:up|on) (?:the )?(.+)$", r"Slide new clamp \1 on the \2"),
    (r"^remove (?:the )?(.+?) from (?:the )?(.+)$", r"Pull the \1 off the \2"),
    (r"^secure (?:it )?with (?:a |the )?new clamp ([a-c])$", r"Tighten it with new clamp \1"),
    (r"^pull (?:the )?pedal up and off.*$", "Pull the pedal up and off"),
    (r"^pull up on (?:the )?tab.*$", "Pull the tab up a little"),
    (r"^pull (?:the )?(.+?) out.*pliers.*$", r"Pull the \1 out with small pliers"),
    (r"^place (?:your )?thumb in (?:the )?(?:depression|low spot)$", "Put your thumb in the low spot"),
    (r"^place (?:your |index )?finger under (?:the )?tab.*$", "Put your finger under the retainer tab"),
    (r"^rotate (?:the )?retainer to the right until it hits (?:the )?spring$", "Turn the retainer to the right until it hits the spring"),
    (r"^rotate (?:the )?pedal.*until (?:the )?(.+?) aligns with (pocket [a-c])$", r"Turn the pedal until the \1 is in \2"),
    (r"^rotate (?:the )?(.+?) until (.+)$", r"Turn the \1 until \2"),
    (r"^rotate (?:the )?(.+)$", r"Turn the \1"),
    (r"^grasp (?:the )?(.+)$", r"Hold the \1"),
    (r"^pull (?:the )?water valve out$", "Pull the water valve out"),
    (r"^insert (?:the )?(.+?) until (.+)$", r"Push the \1 in until \2"),
    (r"^insert (?:the )?(.+?) (?:in|into) (?:the )?(.+)$", r"Put the \1 in the \2"),
    (r"^place (?:the )?(.+?) in (?:the )?closed position$", r"Set the \1 to closed"),
    (r"^align (?:the )?pedal onto (?:the )?pedal pivot$", "Set the pedal on the pivot"),
    (r"^align (?:the )?(.+?) with (pocket [a-c])$", r"Put the \1 in \2"),
    (r"^holding (?:the )?pedal down,? hit (?:the )?button.*$", "Hit the outside button until the pedal snaps"),
    (r"^hit (?:the )?button.*pedal snaps.*$", "Hit the outside button until the pedal snaps"),
    (r"^place (?:the )?toilet upright$", "Stand the toilet up"),
    (r"^activate (?:the )?pedal.*$", "Press the pedal a few times"),
    (r"^lay (?:the )?toilet on its side.*$", "Lay the toilet on its side with the pedal up"),
    (r"^install (?:a |the )?new floor seal, lip side down.*$", "Put the new floor seal on with the lip down"),
    (r"^install (?:a |the )?(.+?), lip side down.*$", r"Put the \1 on with the lip down"),
    (r"^install (?:a |the )?new (.+?) on (?:the )?(.+)$", r"Put the new \1 on the \2"),
    (r"^install (?:a |the )?(.+?) on (?:the )?(.+)$", r"Put the \1 on the \2"),
    (r"^uncover (?:the )?(.+?) and (?:remove|take) (?:a |the )?towel.*$", r"Take the towel off the \1"),
    (r"^place (?:the )?toilet on (?:the )?(?:floor|flange).*$", "Set the toilet on the floor bolts"),
    (r"^tighten (?:the )?(.+?) until (.+)$", r"Tighten the \1 until \2"),
    (r"^replace (?:the )?(.+)$", r"Put the \1 back on"),
    (r"^lift (?:the )?(.+?) from (?:the )?(.+)$", r"Lift the \1 off the \2"),
    (r"^cover (?:the )?(.+?) with (?:a )?(.+)$", r"Cover the \1 with a \2"),
    (r"^discard (?:the )?(.+)$", r"Throw the \1 away"),
    (r"^remove (?:the )?(.+)$", r"Take off the \1"),
    (r"^unhook (?:the )?(?:two )?rings.*$", "Unhook the two rings on the back of the cover"),
    (r"^spread (?:the )?cover apart.*$", "Pull the cover off while you hold the pedal down"),
    (r"^read all (?:the )?steps.*$", "Read all the steps first"),
    (r"^rinse (?:the )?toilet.*$", "Rinse the toilet"),
    (r"^drain (?:the )?holding tank.*$", "Drain the holding tank"),
    (r"^wash (?:the )?toilet.*$", "Wash the toilet"),
    (r"^add (?:the )?tank deodorant.*$", "Add the tank deodorant"),
    (r"^wear .*\bgloves\b.*$", "Put on gloves and glasses"),
    (r"^pull (?:the )?(.+)$", r"Pull the \1"),
    (r"^lift (?:the )?(.+)$", r"Lift the \1"),
    (r"^lay (?:the )?(.+)$", r"Lay the \1"),
    (r"^place (?:the )?(.+)$", r"Put the \1"),
    (r"^install (?:a |the )?(.+)$", r"Put the \1 on"),
    (r"^leave the toilet in place.*$", "Leave the toilet in place if you have room"),
)
_GLOSSARY = (
    ("water hose", "The hose brings water to the toilet."),
    ("clamp", "A clamp is a ring that holds a hose."),
    ("pedal", "The pedal is the foot lever."),
    ("retainer", "The retainer is the lock tab."),
    ("pliers", "Pliers are a hand tool."),
    ("vacuum breaker", "The vacuum breaker stops waste water going back."),
    ("bolt", "Bolts hold the toilet to the floor."),
    ("pocket", "A pocket is the hole the part fits in."),
    ("waste ball", "The waste ball is the round door in the bowl."),
    ("pod", "The pod is the small cover."),
    ("floor seal", "The floor seal sits under the toilet."),
    ("drive pin", "The drive pin is the small metal pin."),
    ("inlet seal", "The inlet seal is the ring in the hole."),
)


def _split_actions(text: str) -> list[str]:
    """One physical action. 'Then' and a second verb become the next step."""
    cleaned = _FIG_BIT_RE.sub(" ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;-")
    parts = []
    for chunk in _LETTER_SPLIT_RE.split(cleaned):
        for sentence in re.split(r"(?<=[.])\s+", chunk):
            for piece in _THEN_SPLIT_RE.split(sentence):
                for bit in _AND_VERB_SPLIT_RE.split(piece):
                    bit = re.sub(r"^(?:style\s+\w+\s+only\s*-\s*)", "", bit, flags=re.I)
                    bit = bit.strip(" .;")
                    if re.fullmatch(r"discard", bit, re.I) or _word_count(bit) >= 2:
                        parts.append(bit)
    return parts


def _polish_sentence(sentence: str, limit: int = 14) -> str:
    sentence = re.sub(r"\s+", " ", sentence or "").strip(" .")
    sentence = re.sub(r"\b(?:the|a)\s+(?:the|a)\b", "the", sentence, flags=re.I)
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if not sentence or _word_count(sentence) > limit:
        return ""
    sentence = sentence[0].upper() + sentence[1:]
    sentence = re.sub(r"\bpocket ([a-c])\b", lambda m: "pocket " + m.group(1).upper(), sentence, flags=re.I)
    sentence = re.sub(
        r"\b(clamps?\s+)([a-c])\b",
        lambda m: m.group(1) + m.group(2).upper(),
        sentence,
        flags=re.I,
    )
    sentence = re.sub(r"\b([abc])(?=,)", lambda m: m.group(1).upper(), sentence)
    sentence = re.sub(r"\band ([abc])(?=\s+away\b)", lambda m: "and " + m.group(1).upper(), sentence)
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def _short_action(raw: str) -> str:
    """Short words for one action. The nouns come from the sheet."""
    text = (raw or "").lower().replace("’", "'")
    text = re.sub(r"^(?:style\s+\w+\s*(?:only\s*)?-\s*)", "", text).strip()
    if text.endswith(":"):
        return ""
    if re.match(r"^disconnect\b", text) and "water" in text:
        return _polish_sentence("Pull the water hose off the toilet")
    if re.match(r"^connect\b", text) and "water" in text:
        return _polish_sentence("Push the water hose onto the toilet")
    if re.fullmatch(r"discard", text):
        return _polish_sentence("Throw the old part away")
    for pattern in _FILLER_RES:
        text = re.sub(pattern, " ", text, flags=re.I)
    for pattern, repl in _NOUN_SWAPS:
        text = re.sub(pattern, repl, text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    if re.search(r"\bskip\b", text) and re.search(r"\btoilet\b", text):
        text = "leave the toilet in place if you have room"
    for pattern, repl in _ACTION_FRAMES:
        match = re.match(pattern, text, re.I)
        if not match:
            continue
        try:
            done = match.expand(repl) if "\\" in repl else repl
        except re.error:
            done = repl
        polished = _polish_sentence(done)
        if polished:
            return polished
    polished = _polish_sentence(text)
    return polished


def _yes_no(action: str) -> tuple[str, str]:
    low = action.rstrip(".").lower()
    no = low + "."
    if _word_count(f"No, {no}") > 15:
        no = "do this step again."
    see = "It looks right."
    until = re.search(r"\buntil (.+)$", low)
    if until:
        tail = until.group(1)
        see = tail[0].upper() + tail[1:] + "."
        see = re.sub(r"\bpocket ([a-c])\b", lambda m: "pocket " + m.group(1).upper(), see, flags=re.I)
    else:
        frames = (
            (r"^turn off\b", "No water comes out."),
            (r"^turn the rv water on$", "Water is on."),
            (r"^flush\b", "The bowl water goes down."),
            (r"^put the new floor seal\b", "The seal lip faces down."),
            (r"^put the .+ back on$", "It is back on."),
            (r"^put a towel\b", "The towel is under the hose."),
            (r"^put the toilet on a trash bag$", "The toilet is on a trash bag."),
            (r"^grab the front\b", "You are holding the front of the pedal."),
            (r"^take the towel off the\b", "The hole is open."),
            (r"^take the towel off$", "The towel is off."),
            (r"^pull the water hose off\b", "The hose is off the toilet."),
            (r"^push the water hose\b", "The hose is on tight."),
            (r"^pull the pedal\b", "The pedal is off."),
            (r"^take off the (.+)$", "ARE_OFF"),
            (r"^throw the (.+) away$", "The {0} is in the trash."),
            (r"^throw it away$", "It is in the trash."),
            (r"^lift the toilet\b", "The toilet is off the floor."),
            (r"^cover the\b", "The hole is covered."),
            (r"^lay the toilet\b", "The toilet is on its side."),
            (r"^put your thumb\b", "Your thumb is in the low spot."),
            (r"^put your finger\b", "Your finger is under the tab."),
            (r"^pull the tab\b", "The tab is up."),
            (r"^hold the (.+)$", "You are holding the {0}."),
            (r"^put the (.+) in (pocket [a-c])$", "The {0} is in {1}."),
            (r"^put the (.+) in the (.+)$", "The {0} is in the {1}."),
            (r"^put the (.+) on\b", "The {0} is on."),
            (r"^push the (.+) in\b", "It is all the way in."),
            (r"^push the (.+) onto\b", "The {0} is on."),
            (r"^pull the (.+) out\b", "The {0} is out."),
            (r"^pull the (.+) off\b", "The {0} is off."),
            (r"^set the pedal\b", "The pedal sits on the pivot."),
            (r"^set the (.+) to closed$", "The pin is closed."),
            (r"^set the toilet\b", "The holes line up on the bolts."),
            (r"^stand the toilet\b", "The toilet is upright."),
            (r"^press the pedal\b", "The waste ball opens and closes."),
            (r"^hit the outside button\b", "The pedal snaps on."),
            (r"^slide clamp\b", "The clamp has moved."),
            (r"^slide new clamp\b", "The clamp is on."),
            (r"^tighten it with\b", "The clamp is tight."),
            (r"^tighten the nuts\b", "The toilet does not rock."),
            (r"^unhook\b", "The rings are off."),
            (r"^read all\b", "You have read the steps."),
            (r"^rinse\b", "The toilet is rinsed."),
            (r"^drain\b", "The tank is drained."),
            (r"^wash\b", "The toilet is clean."),
            (r"^put on gloves\b", "Gloves and glasses are on."),
            (r"^leave the toilet\b", "The toilet can stay down."),
            (r"^add the\b", "It is in."),
        )
        for pattern, template in frames:
            match = re.match(pattern, low, re.I)
            if not match:
                continue
            if template == "ARE_OFF":
                obj = match.group(1)
                verb = "are" if " and " in obj or obj.endswith("s") else "is"
                see = f"The {obj} {verb} off."
            else:
                see = template.format(*match.groups()) if match.groups() else template
            see = re.sub(r"\bpocket ([a-c])\b", lambda m: "pocket " + m.group(1).upper(), see, flags=re.I)
            break
    if _word_count(f"You should see: {see}") > 15:
        see = "It looks right."
    return see, no


def _as_figure(figure) -> dict:
    if isinstance(figure, dict):
        return figure
    return {
        "label": getattr(figure, "caption", "") or "",
        "png": getattr(figure, "image_png", b"") or b"",
        "page": getattr(figure, "page", 1),
    }


def _pick_figure(source: str, callouts: list, figures: list):
    """The crop this step names. The same crop may sit beside more than one step."""
    figures = [_as_figure(fig) for fig in figures or []]
    named = _numbers_named(source)
    for item in callouts or []:
        named.extend(_numbers_named(item))
    named = list(dict.fromkeys(named))
    candidates = []
    for figure in figures:
        nums = _figure_numbers(figure.get("label") or "")
        if named and any(number in named for number in nums):
            candidates.append(figure)
    if not candidates:
        talks = re.search(r"\b(?:clamp|pocket|pin)\s+[A-C]\b", source or "", re.I) or any(
            re.search(r"\b(?:clamp|pocket|pin)\b", item or "", re.I) for item in callouts or []
        )
        if talks and len(figures) == 1:
            return figures[0]
        return None
    if len(candidates) == 1:
        return candidates[0]
    words = set(re.findall(r"[a-z]{4,}", (source or "").lower()))
    best = candidates[-1]
    best_score = -1
    for figure in candidates:
        label_words = set(re.findall(r"[a-z]{4,}", (figure.get("label") or "").lower()))
        score = len(words & label_words)
        if score >= best_score:
            best = figure
            best_score = score
    return best


def _explain_for(action: str, figure, explained: set) -> str:
    bits = []
    low = (action or "").lower()
    for word, line in _GLOSSARY:
        if word in explained:
            continue
        if re.search(rf"\b{re.escape(word)}\b", low):
            bits.append(line)
            explained.add(word)
            break
    number = ""
    if figure:
        nums = _figure_numbers(figure.get("label") or "")
        if nums:
            number = f"See figure {nums[0]}."
    if number:
        bits.append(number)
    explain = " ".join(bits).strip()
    if explain and _word_count(explain) > 15:
        explain = number or bits[0]
    return explain


def _short_before(items: list[str]) -> list[str]:
    out = []
    for item in items or []:
        bits = re.split(r"\s*[:,]\s+|\s+\band\b\s+", item or "")
        for bit in bits:
            bit = re.sub(r"^(?:and|note)\s+", "", bit.strip(), flags=re.I)
            for piece in _split_actions(bit) or [bit]:
                short = _short_action(piece)
                if not short or short in out or _word_count(short) > 15:
                    continue
                if not re.match(r"^(?:Read|Rinse|Drain|Put|Wash|Leave|Add|Turn)\b", short):
                    continue
                out.append(short)
    return out[:8]


def _display_title(doc_title: str, text: str) -> str:
    """A short name from the document's own words."""
    blob = f"{doc_title}\n{text or ''}"
    low = blob.lower()
    if "water valve" in low:
        bits = ["Water valve"]
        if re.search(r"\b42049\b", blob):
            bits.append("42049")
        if re.search(r"\b42109\b", blob):
            bits.append("kit 42109")
        if len(bits) == 1:
            return "Water valve"
        return "Water valve " + " / ".join(bits[1:])
    if "vacuum breaker" in low:
        nums = [number for number in ("34122", "34123") if number in blob]
        if not nums:
            return "Vacuum breaker"
        return "Vacuum breaker " + " / ".join(nums)
    words = re.findall(r"[A-Za-z0-9]+", doc_title or "")
    return " ".join(words[:6]) or "Repair"


def _figure_group_key(step: dict):
    figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
    if not figure or not (figure.get("label") or figure.get("png")):
        return None
    return (figure.get("label") or "", figure.get("page"), figure.get("title") or "")


def _group_procedure_steps(steps: list) -> list:
    """Join a few actions that share a section and a figure into one short section."""
    groups = []
    current: list = []
    for step in steps or []:
        if not current:
            current = [step]
            continue
        same = (
            step.get("section") == current[0].get("section")
            and _figure_group_key(step) == _figure_group_key(current[0])
            and len(current) < SECTION_ACTION_CAP
        )
        if same:
            current.append(step)
        else:
            groups.append(current)
            current = [step]
    if current:
        groups.append(current)
    merged = []
    for group in groups:
        lead = dict(group[0])
        actions = []
        sources = []
        caution = ""
        good = ""
        for step in group:
            text = (step.get("text") or "").strip()
            if text and text not in actions:
                actions.append(text)
            source = (step.get("source") or "").strip()
            if source:
                sources.append(source)
            if not caution and step.get("caution"):
                caution = step["caution"]
            gb = ((step.get("fields") or {}).get("GOOD vs BAD") or "")
            if not good and gb and "Good: UNCONFIRMED" not in gb:
                good = gb
        lead["actions"] = actions or [lead.get("text") or ""]
        lead["text"] = lead["actions"][0]
        lead["source"] = " ".join(sources)
        lead["caution"] = caution
        fields = dict(lead.get("fields") or {})
        fields["WHERE"] = _where_field(lead["source"])
        fields["HOW"] = lead["text"]
        if good:
            fields["GOOD vs BAD"] = good
        lead["fields"] = fields
        merged.append(lead)
    return merged


def procedure_from_sheet(text: str, figures: list | None = None, title: str = "") -> dict:
    """Turn one library sheet into short steps. Nothing is stored for one model."""
    parsed = factory_procedure(text or "", figures)
    raw_steps = list(parsed.get("removal") or []) + list(parsed.get("installation") or [])
    if not raw_steps:
        return {}
    explained: set[str] = set()
    steps = []
    for section in ("removal", "installation"):
        for raw in parsed.get(section) or []:
            source = raw.get("text") or ""
            callouts = list(raw.get("callouts") or [])
            figure = _pick_figure(source, callouts, figures or [])
            style_m = re.match(r"style\s+(plus|lite)\b", source, re.I)
            style_note = f"Do this only on a Style {style_m.group(1).title()}." if style_m else ""
            first_piece = True
            for piece in _split_actions(source):
                short = _short_action(piece)
                if not short:
                    continue
                if short == "Throw the old part away." and steps:
                    prev = steps[-1]["text"].rstrip(".")
                    named = re.match(
                        r"^(?:Take off|Pull) the (.+?)(?:\s+off\b.*|\s+out\b.*)?$",
                        prev,
                        re.I,
                    )
                    if named:
                        thrown = _polish_sentence(f"Throw the {named.group(1)} away")
                        if thrown:
                            short = thrown
                if (
                    short == "Take the towel off."
                    and steps
                    and steps[-1]["text"].startswith("Take the towel off")
                ):
                    continue
                if steps and steps[-1]["text"] == short:
                    continue
                if not re.match(
                    r"^(?:turn|flush|take|unhook|pull|put|cover|throw|slide|tighten|set|stand|"
                    r"press|hit|grab|lay|lift|hold|push|wrap|spread|lower|secure)\b",
                    short,
                    re.I,
                ):
                    continue
                if _too_foreign(short):
                    continue
                see, no = _yes_no(short)
                caution = ""
                if raw.get("caution") and re.search(r"\btighten\b|\bnuts?\b", short, re.I):
                    if re.search(r"\bnuts?\b", short, re.I):
                        caution = "Do not make the nuts too tight."
                    else:
                        caution = "Do not make it too tight."
                explain = _explain_for(short, figure if figure else None, explained)
                fig_num = None
                attached = None
                if figure:
                    nums = _figure_numbers(figure.get("label") or "")
                    fig_num = nums[0] if nums else None
                    attached = figure
                    if fig_num and str(fig_num) not in f"{short} {explain}":
                        extra = f"See figure {fig_num}."
                        joined = f"{explain} {extra}".strip()
                        explain = joined if _word_count(joined) <= 15 else extra
                if first_piece and style_note:
                    joined = f"{style_note} {explain}".strip()
                    if _word_count(joined) <= 15:
                        explain = joined
                    elif not explain:
                        explain = style_note
                first_piece = False
                step = {
                    "section": section,
                    "text": short,
                    "source": piece,
                    "see": see,
                    "no": no,
                    "fig": fig_num,
                    "explain": explain,
                    "caution": caution,
                    "figure": attached,
                }
                steps.append(step)
    if not steps:
        return {}
    doc = title or "the manual"
    kept = []
    for index, step in enumerate(steps):
        nxt = steps[index + 1]["text"] if index + 1 < len(steps) else ""
        step["fields"] = fill_step_fields(step, text or "", doc, nxt)
        if readability_problems(step):
            continue
        kept.append(step)
    steps = _group_procedure_steps(kept)
    if not steps:
        return {}
    for index, step in enumerate(steps):
        nxt = steps[index + 1]["text"] if index + 1 < len(steps) else ""
        step["fields"]["NEXT"] = _next_field(nxt)
    removal = [step for step in steps if step["section"] == "removal"]
    installation = [step for step in steps if step["section"] == "installation"]
    spec = "Torque is not stated in this sheet."
    for sentence in _sentences(text or ""):
        if _TORQUE_RE.search(sentence) and re.search(r"\d", sentence):
            spec = sentence.strip()
            break
    return {
        "title": _display_title(title, text),
        "doc": title or "the manual",
        "before": _short_before(parsed.get("before") or []),
        "removal": removal,
        "installation": installation,
        "steps": steps,
        "spec": spec,
    }


def thetford_kit_layout(kind: str, figures: list | None = None) -> dict:
    """Demo layout. The words are read from the kit sheet in the library."""
    paths = _kit_paths(kind)
    if not paths:
        return {}
    path, doc = paths
    if not path.is_file():
        return {}
    indexed = index_pdf_bytes(path.read_bytes())
    text = "\n".join(page["text"] for page in indexed["pages"])
    if figures is None:
        figures = [
            {
                "label": fig["label"],
                "png": fig["png"],
                "page": fig["page"],
                "title": doc,
            }
            for fig in indexed["figures"]
        ]
    return procedure_from_sheet(text, figures, doc)


_THETFORD_DEMO_PACKETS = None


def job_is_thetford(*parts) -> bool:
    """True when this turn is the Thetford toilet, not another brand's job."""
    blob = " ".join(str(part or "") for part in parts)
    return bool(
        re.search(
            r"thetford|42070|42088|42109|34122|34123|aqua-magic|flush\s+lever|flush\s+pedal",
            blob,
            re.I,
        )
    )


def thetford_demo_packets() -> list:
    """Kit sheets bundled with the app. Used when the shop library has no crops."""
    global _THETFORD_DEMO_PACKETS
    if _THETFORD_DEMO_PACKETS is not None:
        return _THETFORD_DEMO_PACKETS
    built = []
    for kind in ("valve", "breaker"):
        paths = _kit_paths(kind)
        if not paths:
            continue
        path, doc = paths
        if not path.is_file():
            continue
        indexed = index_pdf_bytes(path.read_bytes())
        text = "\n".join(page.get("text") or "" for page in indexed["pages"])
        figures = []
        for fig in indexed["figures"]:
            png = fig.get("png") or b""
            if not png or png_is_blank(png):
                continue
            figures.append(
                {
                    "label": fig.get("label") or "Fig.",
                    "png": png,
                    "page": fig.get("page") or 1,
                    "title": doc,
                }
            )
        pages = []
        for page in indexed["pages"]:
            png = page.get("png") or b""
            if not png or png_is_blank(png):
                continue
            pages.append({"page": page["page"], "png": png})
        built.append(
            {
                "title": doc,
                "page": 1,
                "excerpt": text,
                "figures": figures,
                "pages": pages,
                "file_path": str(path),
            }
        )
    _THETFORD_DEMO_PACKETS = built
    return built


def bundled_thetford_offers(
    reply: str = "",
    user_msg: str = "",
    category: str = "",
    model: str = "",
) -> list:
    """Page images and figure crops for a Thetford turn. Empty for every other job.

    Each offer carries the PNG, so the chat can show it without a library row.
    """
    if not job_is_thetford(reply, user_msg, category, model):
        return []
    blob = f"{reply or ''}\n{user_msg or ''}"
    low = blob.lower()
    names_valve = bool(re.search(r"water valve|42109|42049|weep|pedal|retainer|pocket", low))
    names_breaker = bool(re.search(r"vacuum|breaker|34122|34123", low))
    if names_breaker and not names_valve:
        want = "breaker"
    elif names_valve:
        want = "valve"
    else:
        want = ""
    named = _numbers_named(reply or "") or _numbers_named(user_msg or "")
    offers = []
    for packet in thetford_demo_packets():
        title = packet["title"]
        title_l = title.lower()
        if want == "breaker" and "breaker" not in title_l and "34122" not in title_l:
            continue
        if want == "valve" and "valve" not in title_l and "42109" not in title_l:
            continue
        crops = []
        for fig in packet.get("figures") or []:
            nums = _figure_numbers(fig.get("label") or "")
            if named and not any(number in named for number in nums):
                continue
            crops.append(fig)
        if named and not crops:
            crops = []
        elif not crops:
            crops = list(packet.get("figures") or [])
        for fig in crops:
            png = fig.get("png") or b""
            if not png:
                continue
            page = fig.get("page") or 1
            label = fig.get("label") or ""
            offers.append(
                {
                    "title": title,
                    "page": page,
                    "label": label,
                    "caption": display_caption(title, page, label),
                    "png": png,
                    "file_path": packet.get("file_path") or "",
                    "document_id": 0,
                }
            )
        for page in packet.get("pages") or []:
            png = page.get("png") or b""
            if not png:
                continue
            offers.append(
                {
                    "title": title,
                    "page": page["page"],
                    "label": "page",
                    "caption": display_caption(title, page["page"], "page"),
                    "png": png,
                    "file_path": packet.get("file_path") or "",
                    "document_id": 0,
                }
            )
            break
    return offers


_PROVING_PHOTO_CONNECTOR = (
    "Take a photo of the connector. A photo is optional. You can type what you see."
)
_PROVING_PHOTO_LEAK = (
    "Take a photo of the leak. A photo is optional. You can type what you see."
)
_PROVING_SAFETY = (
    "Water off: UNCONFIRMED. Power off: UNCONFIRMED. Propane off: UNCONFIRMED."
)
_PROVING_TOOLS = "Tools: UNCONFIRMED. Meter setting: UNCONFIRMED."
_OM_FIGURE = "UNCONFIRMED. Thetford Style II OM Permanent RV Toilet 42088, page 3."
_THETFORD_PROVING = {
    "supply": {
        "WHERE": "Back of the toilet.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": (
            "Check the water supply line connection at the water valve. "
            "Secure or tighten it as necessary."
        ),
        "GOOD vs BAD": (
            "Good: UNCONFIRMED. Bad: the leak persists from the water valve. "
            "A leak at the back, low, with the lever at rest, is the fitting. UNCONFIRMED."
        ),
        "NEXT": (
            "On good: go to the next check. "
            "On bad: if the leak persists from the water valve, replace the water valve."
        ),
        "FIGURE": _OM_FIGURE,
        "PHOTO": _PROVING_PHOTO_CONNECTOR,
    },
    "vacuum": {
        "WHERE": "At the vacuum breaker on the flush hose.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Check whether the vacuum breaker leaks while flushing.",
        "GOOD vs BAD": (
            "Good: UNCONFIRMED. Bad: it leaks while flushing. "
            "Leaks only while flushing. That limit is UNCONFIRMED."
        ),
        "NEXT": (
            "On good: go to the next check. "
            "On bad: if it leaks while flushing, replace the vacuum breaker or the water module, "
            "depending on model. "
            "Kit 34122 includes subassembly 34313, clamps 19541, and hose 34377."
        ),
        "FIGURE": "Fig. 1, Thetford Vacuum Breaker Kit 34123/34122, page 1.",
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
    "vacuum_replace": {
        "WHERE": "At the vacuum breaker on the flush hose.",
        "SAFETY": "Turn the RV water off before this work. Power off: UNCONFIRMED. Propane off: UNCONFIRMED.",
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Replace the vacuum breaker or the water module, depending on model.",
        "GOOD vs BAD": "Good: UNCONFIRMED. Bad: it leaks while flushing.",
        "NEXT": "On good: UNCONFIRMED. On bad: UNCONFIRMED.",
        "FIGURE": "Fig. 1, Thetford Vacuum Breaker Kit 34123/34122, page 1.",
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
    "valve": {
        "WHERE": "At the pedal.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": (
            "Pull the pedal off. "
            "If water valve 42049 weeps at the pedal, replace it with water valve kit 42109."
        ),
        "GOOD vs BAD": (
            "Good: UNCONFIRMED. "
            "Bad: a weep at the cartridge, the drive arm, or a cracked housing. UNCONFIRMED."
        ),
        "NEXT": (
            "On good: go to the next check. "
            "On bad: if it weeps at the pedal, replace it with kit 42109. "
            "Kit 42049 includes cartridge 42002, drive-arm seal 42006, inlet seal 42009, "
            "spring 42010, and retainer 42099."
        ),
        "FIGURE": "Fig. 1 PEDAL REMOVED, Thetford Water Valve Service Kit 42109, page 1.",
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
    "valve_replace": {
        "WHERE": "At the pedal.",
        "SAFETY": "Turn the RV water off before this work. Power off: UNCONFIRMED. Propane off: UNCONFIRMED.",
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Water valve 42049 weeps at the pedal. Replace it with water valve kit 42109.",
        "GOOD vs BAD": "Good: UNCONFIRMED. Bad: it weeps at the pedal. UNCONFIRMED.",
        "NEXT": "On good: UNCONFIRMED. On bad: UNCONFIRMED.",
        "FIGURE": "Fig. 1 PEDAL REMOVED, Thetford Water Valve Service Kit 42109, page 1.",
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
    "flange": {
        "WHERE": "Between the closet flange and the toilet.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": (
            "Between the closet flange and the toilet, check the flange nuts. "
            "If the leak continues, check the flange height. "
            "It is 7/16 inch above the floor. Replace the flange seal."
        ),
        "GOOD vs BAD": "Good: UNCONFIRMED. Bad: the leak continues.",
        "NEXT": (
            "On good: the leak checks are done. "
            "On bad: if the leak continues, replace the flange seal. "
            "Closet flange seal 02125 is on the kits. "
            "Flange seal 33239 is UNCONFIRMED. Pedal part 42067 is UNCONFIRMED."
        ),
        "FIGURE": _OM_FIGURE,
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
}
_THETFORD_PROVING_CITE = {
    "supply": "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
    "vacuum": "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2",
    "vacuum_replace": "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2",
    "valve": "📖 Source: Thetford Water Valve Service Kit 42109, page 1",
    "valve_replace": "📖 Source: Thetford Water Valve Service Kit 42109, page 1",
    "flange": "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
}


def thetford_proving_body(key: str) -> str:
    """The eight shop fields for one Thetford leak check. No source line."""
    return format_step_fields(_THETFORD_PROVING[key])


def thetford_proving_line(key: str) -> str:
    """The same check, plus the document cite Guided Diagnostics keeps."""
    return f"{thetford_proving_body(key)}\n{_THETFORD_PROVING_CITE[key]}"


def procedure_handoff(layout: dict) -> str:
    """Full procedure text. GD sends one step at a time from format_one_step."""
    steps = list(layout.get("steps") or [])
    if not steps:
        steps = list(layout.get("removal") or []) + list(layout.get("installation") or [])
    lines = ["Here is the repair procedure."]
    if layout.get("title"):
        lines.append(layout["title"])
    if layout.get("before"):
        lines.append("Before you start:")
        lines.extend(f"- {item}" for item in layout["before"])
    section = ""
    for index, step in enumerate(steps, 1):
        if step.get("section") and step["section"] != section:
            section = step["section"]
            lines.append("REMOVAL" if section == "removal" else "INSTALLATION")
        lines.append(f"{index}.")
        lines.extend(step_sentences(step))
    if layout.get("spec"):
        lines.append(layout["spec"])
    return "\n".join(lines).strip()


def _too_foreign(line: str) -> bool:
    hits = re.findall(
        r"\b(?:le|la|les|des|du|et|el|los|las|del|para|que|una|"
        r"jetez|resserrez|levante|coloque|envuelva|fije|separe|corra|sous|pince)\b",
        line or "",
        re.I,
    )
    return len(hits) >= 2


def _is_english_line(line: str) -> bool:
    if _FOREIGN_LINE_RE.search(line):
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return False
    odd = sum(1 for ch in letters if ord(ch) > 127)
    return odd / len(letters) < 0.08


def _clip_english(line: str) -> str:
    """Keep the English column when a bilingual sheet mixes languages on one line."""
    mark = _FOREIGN_CUT_RE.search(line or "")
    if mark:
        line = line[: mark.start()]
    return re.sub(r"\s+", " ", line or "").strip(" -–—")


def _manual_lines(text: str) -> list[str]:
    """English sheet lines, with wrapped Fig. numbers and sentences rejoined."""
    text = text or ""
    text = re.sub(r"\u00ad\s*", "", text)
    text = text.replace("ﬁ ", "fi").replace("ﬂ ", "fl").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"\bfl\s+oor\b", "floor", text, flags=re.I)
    text = re.sub(r"\bfl\s+ange\b", "flange", text, flags=re.I)
    text = re.sub(r"\bfi\s+nger\b", "finger", text, flags=re.I)
    text = re.sub(r"\bfi\s+cient\b", "ficient", text, flags=re.I)
    raw_lines = []
    for raw in re.split(r"[\r\n]+", text):
        line = _clip_english(re.sub(r"\s+", " ", raw).strip(" \t•■▪●*"))
        if not line:
            continue
        if re.fullmatch(r"(?:english|fran[cç]ais|espa[nñ]ol)", line, re.I):
            continue
        raw_lines.append(line)
    joined = []
    for line in raw_lines:
        if joined and re.match(r"^\d+\)", line) and re.search(r"\(figs?\.?$", joined[-1], re.I):
            joined[-1] = f"{joined[-1]} {line}".strip()
            continue
        joined.append(line)
    raw_lines = [line for line in joined if _is_english_line(line) or re.search(r"\(fig", line, re.I)]
    lines = []
    for line in raw_lines:
        if lines and re.match(r"^\d+\)", line) and re.search(r"\(figs?\.?$", lines[-1], re.I):
            lines[-1] = f"{lines[-1]} {line}".strip()
            continue
        if (
            lines
            and not re.search(r"[.!?]$", lines[-1])
            and not _SECTION_HEAD_RE.match(lines[-1])
            and not _STEP_NUM_RE.match(line)
            and not _SECTION_HEAD_RE.match(line)
            and not re.match(r"^(?:FIGURE|Fig\.)\s+\d", line, re.I)
        ):
            lines[-1] = f"{lines[-1]} {line}".strip()
            continue
        lines.append(line)
    stitched = []
    for line in lines:
        if (
            stitched
            and re.fullmatch(r"trash bag\.?", line, re.I)
            and re.search(r"\bplace on$", stitched[-1], re.I)
        ):
            stitched[-1] = f"{stitched[-1]} trash bag."
            continue
        stitched.append(line)
    return stitched


def _clean_step(text: str) -> str:
    text = re.split(
        r"\b(?:Part No\.|Kit Contains|FIGURE\s+\d|www\.thetford|Made in the USA)\b",
        text or "",
        maxsplit=1,
        flags=re.I,
    )[0]
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text or not _is_english_line(text):
        return ""
    if re.search(r"[àáâäèéêëìíîïòóôöùúûüñç]", text, re.I):
        return ""
    if _too_foreign(text):
        return ""
    if re.search(
        r"\b(?:placez|soulevez|débranchez|debranchez|remontez|ouvrez|retirez|remettez|"
        r"boulons|chapeaux|les|sur|pour|"
        r"retire el|retire la|apriete|instale|abrazadera|tuercas|haga pasar|"
        r"vuelva|destape|tape la|brida|receptaculo|receptáculo)\b",
        text,
        re.I,
    ):
        return ""
    return text + "."


def _callouts_in(text: str) -> list[str]:
    found = []
    for match in _FIG_CALLOUT_RE.finditer(text or ""):
        raw = re.sub(r"\s+", " ", match.group(0)).strip()
        label = re.sub(r"(?i)^figures?\b", "Fig.", raw)
        label = re.sub(r"(?i)^figs?\.", "Fig.", label)
        if label.lower() not in {item.lower() for item in found}:
            found.append(label)
    for match in _LETTER_CALLOUT_RE.finditer(text or ""):
        raw = re.sub(r"\s+", " ", match.group(0)).strip()
        if raw.lower() not in {item.lower() for item in found}:
            found.append(raw)
    return found


def _split_caution(text: str) -> tuple[str, str]:
    cautions = [re.sub(r"\s+", " ", hit).strip() for hit in _CAUTION_SENTENCE_RE.findall(text or "")]
    action = _CAUTION_SENTENCE_RE.sub(" ", text or "")
    action = re.sub(r"\s+", " ", action).strip(" .")
    if action:
        action += "."
    caution = " ".join(cautions).strip()
    return action, caution


def _figure_numbers(label: str) -> list[int]:
    return [int(number) for number in re.findall(r"\b(?:fig(?:ure)?s?\.?)\s*(\d+)", label or "", flags=re.I)]


def _numbers_named(text: str) -> list[int]:
    numbers = []
    for match in re.finditer(r"\b(?:figs?\.?|figures?)\s*(\d+)(?:\s*&\s*(\d+))?", text or "", flags=re.I):
        numbers.append(int(match.group(1)))
        if match.group(2):
            numbers.append(int(match.group(2)))
    return numbers


def factory_procedure(text: str, figures: list | None = None) -> dict:
    """ALLDATA-style blocks from one factory sheet.

    Prerequisites stay in ``before``. Numbered remove lines are removal.
    Numbered install lines are installation. A step keeps the figure whose
    callout it names. A step with no figure stays without an image.
    """
    figures = list(figures or [])
    before: list[str] = []
    removal: list[dict] = []
    installation: list[dict] = []
    section = ""
    current = ""
    bucket: list[dict] | None = None

    def flush():
        nonlocal current
        if not current or bucket is None:
            current = ""
            return
        cleaned = _clean_step(current)
        if not cleaned:
            current = ""
            return
        action, caution = _split_caution(cleaned)
        if len(action) < 18 and not caution:
            current = ""
            return
        bucket.append(
            {
                "text": action or cleaned,
                "callouts": _callouts_in(action or cleaned),
                "caution": caution,
                "figure": None,
            }
        )
        current = ""

    for line in _manual_lines(text):
        if re.fullmatch(r"(?:breaker|valve)", line, re.I):
            continue
        head = _SECTION_HEAD_RE.match(line)
        if head:
            flush()
            name = head.group(1).lower()
            if name in ("before beginning", "preparation", "prerequisites"):
                section = "before"
                bucket = None
            elif name == "removal" or name.startswith("remove"):
                section = "removal"
                bucket = removal
            else:
                section = "installation"
                bucket = installation
            rest = line[head.end():].strip(" .:-")
            if section == "before" and rest and not _INSTALL_BAN_RE.search(rest):
                before.append(rest if rest.endswith(".") else rest + ".")
            elif rest and bucket is not None:
                current = rest
            continue
        numbered = _STEP_NUM_RE.match(line)
        if numbered and section in ("removal", "installation"):
            flush()
            current = numbered.group(2).strip()
            continue
        if section == "before":
            if _INSTALL_BAN_RE.search(line) or re.match(r"^(?:FIGURE|Fig\.)\s+\d", line, re.I):
                continue
            if re.match(r"^(?:remove|install|reinstall)\b", line, re.I):
                continue
            item = re.sub(r"^4\s+", "", line.strip())
            item = _clean_step(item)
            if len(item) < 12:
                continue
            before.append(item)
            continue
        if current and section in ("removal", "installation"):
            if re.match(
                r"^(?:remove|install|reinstall|before|needed|kit contains|part no|"
                r"figure|fig\.|www\.|made in)\b",
                line,
                re.I,
            ):
                flush()
                continue
            if not _is_english_line(line) or _too_foreign(line):
                continue
            current = f"{current} {line}".strip()
    flush()
    _assign_step_figures(removal + installation, figures)
    return {"before": before[:8], "removal": removal, "installation": installation, "spec": ""}


def _assign_step_figures(steps: list[dict], figures: list) -> None:
    """One manual crop beside the step that names it. No crop is invented."""
    used = set()
    for step in steps:
        named = _numbers_named(step.get("text") or "")
        chosen = None
        for index, figure in enumerate(figures):
            if index in used:
                continue
            nums = _figure_numbers(figure.get("label") or "")
            if named and any(number in named for number in nums):
                chosen = index
                break
        if chosen is None and step.get("callouts") and len(figures) == 1 and 0 not in used:
            # The only crop on the sheet illustrates the letter callouts.
            if any(re.search(r"\b(?:clamp|pocket|pin)\b", item, re.I) for item in step["callouts"]):
                chosen = 0
        if chosen is None:
            continue
        used.add(chosen)
        step["figure"] = figures[chosen]


def wants_manual_image(text: str) -> bool:
    """The tech asked to show a page, a photo, the source, or a figure."""
    raw = (text or "").lower().replace("—", "-").replace("–", "-")
    raw = re.sub(r"\s+", " ", raw)
    if any(
        phrase in raw
        for phrase in (
            "show",
            "photo",
            "picture",
            "figure",
            "fig.",
            "diagram",
            "drawing",
            "illustration",
        )
    ):
        return True
    if re.search(r"\bsource\b", raw) and re.search(
        r"\b(show|see|photo|picture|pull|display|what|where)\b", raw
    ):
        return True
    return False
