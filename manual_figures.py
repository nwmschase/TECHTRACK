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
    png_blob BLOB
)
"""


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
        conn.execute(ASSET_DDL)
        conn.execute("DELETE FROM doc_assets WHERE document_id = ?", (int(document_id),))
        for asset in assets:
            conn.execute(
                """
                INSERT INTO doc_assets
                    (document_id, page, kind, label, image_path, width, height, png_blob)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                "image_path": asset_path(
                    document_id, figure["page"], "figure", figure.get("label") or "fig"
                ),
            }
        )
    return rows


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
