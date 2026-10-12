"""Page images and figure crops for the shop Document Library.

Pages are rendered at about 150 dpi with PyMuPDF. Figures are vector drawings
and embedded images, cropped from the rendered page at the drawing box that
sits under a Fig. / Figure caption or a step number. A scanned page with no
text keeps the page image and does not grow a made-up figure.
"""
from __future__ import annotations

import gc
import io
import re
import unicodedata
import sqlite3
from pathlib import Path

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.19.57"

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
    "happijac",
    "happi jac",
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


def _release_pixmap(pix) -> None:
    """Drop one raster. The next page must not keep this buffer."""
    if pix is None:
        return
    try:
        pix.close()
    except Exception:
        pass


def _release_document(doc) -> None:
    """Close the PDF and drop MuPDF's decoded-image store."""
    fitz = _fitz()
    if doc is not None:
        try:
            doc.close()
        except Exception:
            pass
    try:
        fitz.TOOLS.store_shrink(100)
    except Exception:
        pass
    gc.collect()


def render_page_png(page, zoom: float = _ZOOM) -> bytes:
    """Rasterize one PyMuPDF page. Vector drawings become pixels here."""
    fitz = _fitz()
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    try:
        return pix.tobytes("png")
    finally:
        _release_pixmap(pix)


def walk_pdf_pages(source, start_page: int = 1, max_pages: int | None = None):
    """Yield one rendered page, then free its pixmap before the next page.

    ``source`` is PDF bytes or a filesystem path. The yielded dict is cleared
    after the caller continues, so the PNG bytes do not accumulate.
    """
    fitz = _fitz()
    if isinstance(source, (bytes, bytearray)):
        doc = fitz.open(stream=bytes(source), filetype="pdf")
    else:
        doc = fitz.open(str(source))
    try:
        total = int(doc.page_count)
        start = max(1, int(start_page or 1))
        if start > total:
            return
        last = total
        if max_pages is not None:
            last = min(total, start + max(1, int(max_pages)) - 1)
        for number in range(start, last + 1):
            page = doc[number - 1]
            text = (page.get_text("text") or "").strip()
            pix = page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM), alpha=False)
            try:
                png = pix.tobytes("png")
                width, height = int(pix.width), int(pix.height)
            finally:
                _release_pixmap(pix)
                pix = None
            figures = detect_page_figures(page, png) if text else []
            for figure in figures:
                figure["page"] = number
            rendered = {
                "page": number,
                "page_count": total,
                "png": png,
                "width": width,
                "height": height,
                "text": text,
                "figures": figures,
            }
            png = None
            figures = None
            page = None
            yield rendered
            rendered["png"] = b""
            for figure in rendered.get("figures") or []:
                figure["png"] = b""
            rendered["figures"] = []
            try:
                fitz.TOOLS.store_shrink(100)
            except Exception:
                pass
            gc.collect()
    finally:
        _release_document(doc)


def _png_size(png: bytes) -> tuple[int, int]:
    from PIL import Image

    image = Image.open(io.BytesIO(png))
    return image.size


def png_is_blank(png: bytes) -> bool:
    """True when the crop is empty, unreadable, or nearly all white."""
    if not png:
        return True
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(png)).convert("L")
    except Exception:
        return True
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


def _crop_rendered(png: bytes, page_rect, box, zoom: float, extra_bottom=None) -> bytes:
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    pad = 4
    x0 = max(0, int(box.x0 * zoom) - pad)
    y0 = max(0, int(box.y0 * zoom) - pad)
    x1 = min(image.width, int(box.x1 * zoom) + pad)
    y1 = min(image.height, int(box.y1 * zoom) + pad)
    if extra_bottom is not None:
        # The kit caption sits on the drawing's bottom edge. Include that line.
        cap_y = min(image.height, int(float(extra_bottom) * zoom) + pad)
        y1 = max(y1, cap_y)
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
    match = _CAPTION_RE.match(re.sub(r"\s+", " ", text or "").strip())
    if not match:
        return text.strip()[:80]
    number = match.group(2)
    rest = (match.group(3) or "").split("/")[0].strip(" -–—:")
    label = f"Fig. {number}"
    if rest:
        label = f"{label} {rest}"
    return label[:110]


def _caption_groups(page) -> list[tuple[str, object, float]]:
    """A Fig. caption plus the wrapped lines under it.

    'FIGURE 3 - WATER' continues as 'VALVE CLOSED' and 'POSITION'. Those
    lines are one caption. The crop has to include the last line.
    """
    lines = _text_lines(page)
    groups = []
    index = 0
    while index < len(lines):
        text, rect = lines[index]
        if not _CAPTION_RE.match(text):
            index += 1
            continue
        parts = [text]
        bottom = float(rect.y1)
        left = float(rect.x0)
        index += 1
        while index < len(lines):
            nxt, nrect = lines[index]
            if _CAPTION_RE.match(nxt) or re.match(r"^\d+[\.\)]\s+\S", nxt):
                break
            if float(nrect.y0) + 1 < bottom:
                break
            if float(nrect.y0) > bottom + 6:
                break
            if abs(float(nrect.x0) - left) > 18:
                break
            if len(nxt) > 48:
                break
            parts.append(nxt)
            bottom = float(nrect.y1)
            index += 1
        groups.append((" ".join(parts), rect, bottom))
    return groups


def _render_figure_png(page, page_png: bytes, box, extra_bottom: float) -> bytes:
    """A small drawing is rasterized from the page so it is not a soft upscale."""
    width_pt = float(box.x1) - float(box.x0)
    if width_pt < 160:
        fitz = _fitz()
        zoom = 400.0 / 72.0
        clip = fitz.Rect(
            float(box.x0) - 2,
            float(box.y0) - 2,
            float(box.x1) + 2,
            float(extra_bottom) + 2,
        )
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        try:
            png = pix.tobytes("png")
        finally:
            _release_pixmap(pix)
        if png and not png_is_blank(png):
            return png
    return _crop_rendered(page_png, page.rect, box, _ZOOM, extra_bottom=extra_bottom)


def detect_page_figures(page, page_png: bytes) -> list[dict]:
    """Crop each captioned drawing on one page. Scanned pages have no captions."""
    claimed = []
    found = []
    for text, rect, bottom in _caption_groups(page):
        box = _figure_above_caption(page, rect)
        if box is None or any(_overlaps(box, prior) for prior in claimed):
            continue
        # A wide crop keeps the caption line. A narrow crop does not: scaled to
        # 75% of the page, that caption fills the sheet. The caption is painted
        # as type under the figure either way.
        width_pt = float(box.x1) - float(box.x0)
        clip_bottom = float(box.y1) if width_pt < 160 else float(bottom)
        png = _render_figure_png(page, page_png, box, clip_bottom)
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
        png = _crop_rendered(page_png, page.rect, box, _ZOOM, extra_bottom=rect.y1)
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
        _release_document(doc)
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
    """Persist the image key and caption. The PNG itself stays in R2 or on disk."""
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
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    int(document_id),
                    int(asset["page"]),
                    asset["kind"],
                    asset.get("label") or "",
                    asset.get("image_path") or "",
                    int(asset.get("width") or 0),
                    int(asset.get("height") or 0),
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
# One shop step is one action. The pedal grab and pull are the only pair.
SECTION_ACTION_CAP = 1

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
    (r"\bholding tank opening\b", "At the holding tank opening at the closet flange."),
    (r"\bon its side\b", "On the floor, with the pedal facing up."),
    (r"\bfrom (?:the )?floor\b", "The toilet sits on the floor."),
    (r"\bnozzle\b", "On the nozzle."),
    (r"\bpedal\b", "At the pedal."),
    (r"\bwater valve\b", "At the water valve."),
    (r"\bretainer\b", "At the retainer."),
    (r"\blever\b", "At the lever."),
    (r"\block\b", "At the lock."),
)


NOT_STATED = "Not stated in this sheet."


def strip_html_comments(text: str) -> str:
    """A reply the tech reads does not carry a hidden HTML marker."""
    cleaned = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def hide_internal_marker(text: str) -> str:
    """The shop never prints the internal blank-field marker.

    The filler sentence is said at most once. A reply that never needed it
    stays without it.
    """
    cleaned = re.sub(r"\bUNCONFIRMED\b\.?", NOT_STATED, text or "", flags=re.I)
    phrase = re.compile(r"Not stated in this sheet\.?", re.I)
    found = list(phrase.finditer(cleaned))
    if len(found) > 1:
        pieces = []
        last = 0
        for index, match in enumerate(found):
            pieces.append(cleaned[last:match.start()])
            if index == 0:
                pieces.append(match.group(0))
            last = match.end()
        pieces.append(cleaned[last:])
        cleaned = "".join(pieces)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,;:])", r"\1", cleaned)
    return cleaned


_LABEL_ONLY_RE = re.compile(
    r"^(?:Water off|Power off|Propane off|Tools|Meter setting|Good|Bad|On good|On bad)\s*:?$",
    re.I,
)
_DANGLING_END_RE = re.compile(
    r"(?:\b(?:is|are|was|were|be|been|being|the|a|an|of|to|for|that|this|and|or|with|at|on|in)|:)\s*$",
    re.I,
)


def shop_field_value(value: str) -> str:
    """The words a field actually states. An unfilled field is blank.

    Dropping the blank-field marker must not leave a cut sentence such as
    'That limit is'.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    kept = []
    for part in re.split(r"(?<=[.])\s+", text):
        if NOT_STATED in part:
            rest = re.sub(re.escape(NOT_STATED), " ", part).strip(" .;")
            if not rest or _LABEL_ONLY_RE.match(rest) or _DANGLING_END_RE.search(rest):
                continue
            part = rest
        part = part.strip()
        if not part or _LABEL_ONLY_RE.match(part.strip(".")):
            continue
        kept.append(part if part.endswith(".") else part)
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


PHOTO_VISUAL = "Send a photo of what you see."
_STAY_BAD_RE = re.compile(r"^stay on this step\.?$", re.I)
_SKIP_PHOTO_START_RE = re.compile(
    r"^(?:turn|unplug|remove|torque|hoist|wash|dry|meter|set|apply|push|drop|pour|"
    r"discharge|shim|make|point|clamp|hand|open|wait|run|pull|put|lift|flush|take|"
    r"tighten|connect|disconnect|lay|rinse|throw|slide|cover|stand|read|move|grab|"
    r"place|rotate|insert|install|replace|discard|unhook|spread|wrap|secure|"
    r"activate|align|grasp|hold|lower|press|hit)\b",
    re.I,
)
_LOOK_RE = re.compile(r"\b(?:look(?:\s+for)?|watch|inspect)\b", re.I)
_VISUAL_RE = re.compile(
    r"\b(?:leak|leaks|leaking|weep|weeps|weeping|drip|drips|frost|icing)\b",
    re.I,
)
_LABEL_SPLIT_RE = re.compile(
    r"\b(Safety|Where|Tools|Do this|Good looks like|Bad looks like|Next|If it fails|Figure):\s*"
)
_PHOTO_BLOCK_RES = (
    re.compile(r"\bPHOTO:\s*", re.I),
    re.compile(re.escape("Take a photo of this step and send it."), re.I),
    re.compile(re.escape("A photo is optional."), re.I),
    re.compile(re.escape("You can type what you see."), re.I),
    re.compile(re.escape(YES_LINE), re.I),
    re.compile(re.escape(NO_LINE), re.I),
    re.compile(re.escape(PHOTO_STEP), re.I),
    re.compile(re.escape(PHOTO_WAIT), re.I),
    re.compile(re.escape(PHOTO_VISUAL), re.I),
    re.compile(r"Take a photo of the (?:connector|leak|meter reading|tag|part)\.", re.I),
)


def reply_shows_step(text: str, number: int) -> bool:
    """True when this turn is repair step N.

    Chat turns used to carry a hidden ``gd-step`` marker. A shipped reply has
    that marker stripped, so the step is also the action sentence. Older turns
    say ``Step N of`` or ``Here is the repair procedure`` plus ``Step N:``.
    ``Step 1:`` does not match ``Step 10:``. A proving check has neither, so it
    does not move the repair cursor.
    """
    raw = text or ""
    n = int(number)
    if re.search(rf"<!--\s*gd-step:{n}\s*-->", raw):
        return True
    if re.search(rf"(?<!\d)Step {n} of\b", raw):
        return True
    if "Here is the repair procedure." in raw and re.search(rf"(?<!\d)Step {n}:", raw):
        return True
    return _reply_matches_step_action(raw, n)


_STEP_ACTIONS = None


def _step_action_text(step: dict) -> str:
    return re.sub(r"\s+", " ", (step or {}).get("text") or "").strip().rstrip(".").lower()


def _reply_matches_step_action(text: str, number: int) -> bool:
    """The numbered kit step, after the HTML marker has been stripped.

    A stored turn may flatten the sentences onto one line. The action still
    has to be its own sentence, so "take off the pod" does not match
    "take off the pod rings". A cited document matches only that document's
    step, so a valve sentence cannot close a roof-unit step with the same number.
    """
    blob = re.sub(r"\s+", " ", strip_html_comments(text or "")).strip().lower()
    actions = _actions_for_reply(blob, int(number))
    if not actions:
        return False
    for action in actions:
        if re.search(rf"(?:^|[.!?]\s+){re.escape(action)}(?:[.!?]|$)", blob):
            return True
    return False


def _actions_for_reply(blob: str, number: int) -> list:
    cache = _cached_step_actions()
    keys = []
    if re.search(r"\b42109\b", blob):
        keys.append("42109")
    if re.search(r"\b3412[23]\b", blob):
        keys.append("34123")
    if re.search(r"\b2024006031\b", blob):
        keys.append("2024006031")
    actions = []
    if keys:
        for key in keys:
            actions.extend((cache.get(key) or {}).get(number) or [])
        return actions
    return list((cache.get("any") or {}).get(number) or [])


def _cached_step_actions() -> dict:
    global _STEP_ACTIONS
    if _STEP_ACTIONS is not None:
        return _STEP_ACTIONS
    found: dict = {"any": {}, "42109": {}, "34123": {}, "2024006031": {}}
    layouts = (
        ("42109", thetford_kit_layout("valve")),
        ("34123", thetford_kit_layout("breaker")),
        ("2024006031", facr_rr_layout()),
    )
    for key, layout in layouts:
        steps = list((layout or {}).get("steps") or [])
        for index, step in enumerate(steps, 1):
            action = _step_action_text(step)
            if not action:
                continue
            found[key].setdefault(index, [])
            if action not in found[key][index]:
                found[key][index].append(action)
            found["any"].setdefault(index, [])
            if action not in found["any"][index]:
                found["any"][index].append(action)
    _STEP_ACTIONS = found
    return found


def _finish_sentence(text: str) -> str:
    raw = re.sub(r"\s+", " ", text or "").strip()
    if not raw:
        return ""
    if raw[-1] not in ".!?":
        raw += "."
    return raw


def step_safety_text(step: dict) -> str:
    return shop_field_value(((step or {}).get("fields") or {}).get("SAFETY") or "")


def show_safety_for(steps: list, number: int) -> bool:
    """Safety prints on the first step of a section, and again only when it changes."""
    if number < 1 or number > len(steps or []):
        return False
    step = steps[number - 1]
    safety = step_safety_text(step)
    if not safety:
        return False
    if number == 1:
        return True
    prev = steps[number - 2]
    if (prev.get("section") or "") != (step.get("section") or ""):
        return True
    return step_safety_text(prev) != safety


def _strip_leading_number(text: str) -> str:
    """'2. Pull the pedal.' is the action. The renderer supplies 1."""
    return re.sub(r"^\d+\.\s+", "", (text or "").strip())


def step_action_lines(step: dict) -> list[str]:
    """One sheet action per line. A multi-sentence HOW is split, not glued."""
    fields = (step or {}).get("fields") or {}
    pieces = [
        _strip_leading_number(item)
        for item in (step.get("actions") or [])
        if _strip_leading_number(item)
    ]
    how = _strip_leading_number(fields.get("HOW") or "")
    if how:
        how_key = how.rstrip(".")
        if not pieces:
            pieces.append(how)
        elif pieces[0].rstrip(".") != how_key:
            pieces.insert(0, how)
    actions = []
    for piece in pieces:
        cleaned = shop_field_value(piece)
        for sentence in re.split(r"(?<=[.])\s+", cleaned):
            sentence = _finish_sentence(_strip_leading_number(sentence))
            if sentence and sentence not in actions:
                actions.append(sentence)
    if not actions:
        text = _finish_sentence(shop_field_value((step or {}).get("text") or ""))
        if text:
            actions.append(text)
    return actions


def step_heading(step: dict, number: int) -> str:
    actions = step_action_lines(step)
    title = actions[0] if actions else shop_field_value((step or {}).get("text") or "")
    title = re.sub(r"\s+", " ", title or "").strip().rstrip(".")
    return f"Step {number}: {title or 'Do this step'}"


def _good_bad_bits(value: str) -> tuple[str, str]:
    text = shop_field_value(value)
    if not text:
        return "", ""
    good_m = re.search(r"\bGood:\s*", text, re.I)
    bad_m = re.search(r"\bBad:\s*", text, re.I)
    prefix = ""
    good = ""
    bad = ""
    if good_m and bad_m and bad_m.start() > good_m.start():
        prefix = text[: good_m.start()].strip(" .")
        good = text[good_m.end() : bad_m.start()].strip(" .")
        bad = text[bad_m.end() :].strip(" .")
    elif good_m:
        prefix = text[: good_m.start()].strip(" .")
        good = text[good_m.end() :].strip(" .")
    elif bad_m:
        prefix = text[: bad_m.start()].strip(" .")
        bad = text[bad_m.end() :].strip(" .")
    else:
        good = text.strip(" .")
    if prefix:
        good = f"{prefix}. {good}".strip() if good else prefix
    good = shop_field_value(good)
    bad = shop_field_value(bad)
    if _STAY_BAD_RE.match(bad):
        bad = ""
    return good, bad


def _next_lines(value: str) -> list[str]:
    text = value or ""
    good_m = re.search(r"On good:\s*(.*?)(?:\s+On bad:|$)", text, re.I | re.S)
    bad_m = re.search(r"On bad:\s*(.*)$", text, re.I | re.S)
    good = shop_field_value(good_m.group(1) if good_m else "")
    bad = shop_field_value(bad_m.group(1) if bad_m else "")
    if _STAY_BAD_RE.match(bad):
        bad = ""
    if not good and not bad:
        leftover = shop_field_value(re.sub(r"\bOn bad:.*$", "", text, flags=re.I))
        good = re.sub(r"^On good:\s*", "", leftover, flags=re.I).strip()
        good = shop_field_value(good)
    lines = []
    if good:
        lines.append(f"Next: {_finish_sentence(good)}")
    if bad and bad.rstrip(".").lower() != (good or "").rstrip(".").lower():
        lines.append(f"If it fails: {_finish_sentence(bad)}")
    return lines


def _tools_text(value: str) -> str:
    text = shop_field_value(value)
    return re.sub(r"^Tools:\s*", "", text, flags=re.I).strip()


def step_needs_photo(step: dict) -> bool:
    """A photo helps when this step confirms something the tech can see.

    Turning a breaker off, pulling a pedal, or torquing a fitting does not.
    Looking, watching, or checking a leak, weep, drip, or frost does.
    """
    actions = step_action_lines(step)
    how = " ".join(actions)
    if _LOOK_RE.search(how):
        return True
    fields = (step or {}).get("fields") or {}
    first = (actions[0] if actions else how).strip()
    verdict = f"{how} {fields.get('GOOD vs BAD') or ''}"
    if _SKIP_PHOTO_START_RE.match(first):
        if _VISUAL_RE.search(verdict) and re.search(r"\b(?:water on|flush|leak test)\b", verdict, re.I):
            return True
        return False
    return bool(_VISUAL_RE.search(verdict))


def step_body_lines(
    step: dict,
    *,
    show_safety: bool = False,
    show_photo: bool = False,
    show_figure: bool = True,
) -> list[str]:
    """Where, Tools, Do this, Good looks like, and Next. Empty fields stay off.

    The photo line is for a Guided Diagnostics turn. The Bay PDF never asks.
    """
    fields = (step or {}).get("fields") or {}
    lines = []
    if show_safety:
        safety = step_safety_text(step)
        if safety:
            lines.append(f"Safety: {_finish_sentence(safety)}")
    where = shop_field_value(fields.get("WHERE") or "")
    if where:
        lines.append(f"Where: {_finish_sentence(where)}")
    tools = _tools_text(fields.get("TOOLS / METER SETTING") or "")
    if tools:
        lines.append(f"Tools: {_finish_sentence(tools)}")
    actions = step_action_lines(step)
    if actions:
        lines.append("Do this:")
        lines.extend(f"{index}. {action}" for index, action in enumerate(actions, 1))
    good, bad = _good_bad_bits(fields.get("GOOD vs BAD") or "")
    if good:
        lines.append(f"Good looks like: {_finish_sentence(good)}")
    if bad and _bad_worth_printing(bad):
        lines.append(f"Bad looks like: {_finish_sentence(bad)}")
    lines.extend(_next_lines(fields.get("NEXT") or ""))
    figure = shop_field_value(fields.get("FIGURE") or "")
    if show_figure and figure:
        lines.append(f"Figure: {_finish_sentence(figure)}")
    if show_photo:
        lines.append(PHOTO_VISUAL)
    return lines


def _group_body(lines: list[str]) -> list[list[str]]:
    """Each label is its own block. The Do this list stays together."""
    groups = []
    bucket = []
    for line in lines:
        if line == "Do this:":
            if bucket:
                groups.append(bucket)
            bucket = [line]
            continue
        if bucket and bucket[0] == "Do this:" and re.match(r"^\d+\. ", line):
            bucket.append(line)
            continue
        if bucket:
            groups.append(bucket)
            bucket = []
        groups.append([line])
    if bucket:
        groups.append(bucket)
    return groups


def render_step(
    step: dict,
    number: int,
    *,
    show_safety: bool = False,
    show_photo: bool = False,
    show_figure: bool = True,
    markdown: bool = False,
    intro: bool = False,
) -> str:
    """One step. PDF uses plain lines. Guided Diagnostics uses the same lines in markdown."""
    heading = step_heading(step, number)
    body = step_body_lines(
        step,
        show_safety=show_safety,
        show_photo=show_photo and markdown,
        show_figure=show_figure,
    )
    lines = []
    if intro:
        lines.extend(["Here is the repair procedure.", ""])
    lines.append(f"**{heading}**" if markdown else heading)
    if markdown:
        for group in _group_body(body):
            lines.append("")
            lines.extend(group)
    else:
        lines.extend(body)
    return "\n".join(lines).strip()


def _fields_as_step(fields: dict) -> dict:
    how = (fields or {}).get("HOW") or ""
    return {"text": how, "actions": [], "fields": fields or {}, "section": "prove"}


def format_step_fields(
    fields: dict,
    *,
    number: int = 1,
    show_safety: bool = False,
    show_photo: bool = False,
    show_figure: bool = True,
    markdown: bool = False,
) -> str:
    """The shop template. A field the sheet does not fill in is left off."""
    return render_step(
        _fields_as_step(fields),
        number,
        show_safety=show_safety,
        show_photo=show_photo,
        show_figure=show_figure,
        markdown=markdown,
    )


def _plain_heading_and_lines(text: str, number: int) -> tuple[str, list[str]]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]
    if not sentences:
        return f"Step {number}: Do this step", []
    title = sentences[0].rstrip(".")
    words = title.split()
    if len(words) > 12:
        title = " ".join(words[:12])
    actions = [_finish_sentence(sentence) for sentence in sentences]
    lines = ["Do this:"] + [f"{index}. {action}" for index, action in enumerate(actions, 1)]
    return f"Step {number}: {title}", lines


def lines_from_shop_text(text: str, number: int) -> tuple[str, list[str]]:
    """Turn a stored bay-order line into a heading plus labeled lines.

    Sheet standard collapses newlines. The labels are split back apart here,
    and the canned photo and yes or no script is dropped before paint.
    """
    raw = re.sub(r"\s+", " ", text or "").strip()
    for pattern in _PHOTO_BLOCK_RES:
        raw = pattern.sub(" ", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" .")
    if not raw:
        return f"Step {number}: Do this step", []
    heading_m = re.match(r"Step\s+(\d+)\s*:\s*", raw)
    if not heading_m:
        return _plain_heading_and_lines(raw, number)
    rest = raw[heading_m.end() :]
    label = _LABEL_SPLIT_RE.search(rest)
    if not label:
        title = rest.strip(" .")
        return f"Step {heading_m.group(1)}: {title or 'Do this step'}", []
    title = rest[: label.start()].strip(" .")
    heading = f"Step {heading_m.group(1)}: {title or 'Do this step'}"
    parts = _LABEL_SPLIT_RE.split(rest[label.start() :])
    lines = []
    index = 1
    while index + 1 < len(parts):
        name = parts[index]
        value = re.sub(r"\s+", " ", parts[index + 1]).strip()
        if name == "Do this":
            lines.append("Do this:")
            actions = re.findall(r"\d+\.\s*.*?(?=(?:\s+\d+\.\s)|$)", value)
            bodies = [
                _strip_leading_number(item)
                for item in actions
                if _strip_leading_number(item)
            ]
            if not bodies and value:
                bodies = [_strip_leading_number(value)]
            for number, body in enumerate(bodies, 1):
                if body:
                    lines.append(f"{number}. {_finish_sentence(body)}")
        elif value:
            bare = value.strip().rstrip(".")
            if name == "Bad looks like" and (
                _GENERIC_BAD_RE.match(bare) or _GENERIC_BAD_RE.match(value.strip())
            ):
                pass
            else:
                lines.append(f"{name}: {_finish_sentence(value)}")
        index += 2
    return heading, lines


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
    return " ".join(found) if found else NOT_STATED


def _safety_field(sheet: str) -> str:
    """Water, power, and propane. Only a shutoff the sheet states is filled in."""
    text = sheet or ""
    bits = []
    if re.search(r"turn off rv water supply|turn off (?:the )?(?:rv )?water\b", text, re.I):
        bits.append("Turn the RV water off before this work.")
    else:
        bits.append(f"Water off: {NOT_STATED}")
    if re.search(r"turn off (?:the )?power\b", text, re.I):
        bits.append("Turn the power off before this work.")
    else:
        bits.append(f"Power off: {NOT_STATED}")
    if re.search(r"\bpropane\b|\blp gas\b", text, re.I):
        bits.append("The sheet names propane.")
    else:
        bits.append(f"Propane off: {NOT_STATED}")
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
    tool_bit = ", ".join(tools) if tools else NOT_STATED
    meter = ""
    for blob in (source or "", sheet or ""):
        hit = _METER_RE.search(blob)
        if hit:
            meter = hit.group(0)
            break
    return f"Tools: {tool_bit}. Meter setting: {meter or NOT_STATED}"


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
    return f"Good: {good or NOT_STATED} Bad: {bad or NOT_STATED}" if (good or "").endswith(".") or not good else f"Good: {good}. Bad: {bad or NOT_STATED}"


def _next_field(next_how: str) -> str:
    """The next sheet step is the good path. A bad path the sheet omits stays UNCONFIRMED."""
    good = (next_how or "").strip() or NOT_STATED
    return f"On good: {good} On bad: {NOT_STATED}"


def _figure_field(step: dict, doc: str) -> str:
    figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
    if not figure:
        return NOT_STATED
    label = (figure.get("label") or "").strip()
    title = (figure.get("title") or doc or "").strip()
    page = figure.get("page")
    bits = [bit for bit in (label, title) if bit]
    if page:
        bits.append(f"page {page}")
    return ", ".join(bits) if bits else NOT_STATED


def _photo_field(how: str) -> str:
    import gd_step_photo as photos

    return " ".join(photos.photo_ask_lines(how))


def _step_tool_line(source: str) -> str:
    """Tools this step's own words name. The kit list is not copied onto every step."""
    tools = []
    for hit in _TOOL_WORD_RE.findall(source or ""):
        word = re.sub(r"\s+", " ", hit).strip()
        if word.lower() not in {item.lower() for item in tools}:
            tools.append(word)
    if not tools:
        return ""
    return "Tools: " + ", ".join(tools) + "."


def fill_step_fields(step: dict, sheet: str, doc: str, next_how: str = "") -> dict:
    """Fill the template from this sheet. Do not invent a missing value."""
    source = step.get("source") or ""
    how = (step.get("text") or "").strip() or NOT_STATED
    return {
        "WHERE": _where_field(source),
        "SAFETY": _safety_field(sheet),
        "TOOLS / METER SETTING": _step_tool_line(f"{source} {how}"),
        "HOW": how,
        "GOOD vs BAD": _good_bad_field(source, how),
        "NEXT": _next_field(next_how),
        "FIGURE": _figure_field(step, doc),
        "PHOTO": _photo_field(how),
    }


def step_field_lines(step: dict, *, number: int = 1, show_safety: bool = False) -> list[str]:
    """Labeled lines for one step. The photo script and the yes or no script stay off."""
    text = render_step(step, number, show_safety=show_safety, show_photo=False, markdown=False)
    return [line for line in text.splitlines() if line.strip()]

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


def step_sentences(step: dict, *, number: int = 1, show_safety: bool = False) -> list[str]:
    """Labeled lines a tech reads for one step. No photo ask."""
    return step_field_lines(step, number=number, show_safety=show_safety)


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
        if name == "TOOLS / METER SETTING":
            continue
        if not (fields.get(name) or "").strip():
            problems.append(f"missing {name}")
    return problems


def format_one_step(step: dict, number: int, total: int, *, show_safety: bool = False) -> str:
    """Labeled markdown for the Bay sheet standard. Chat uses format_chat_turn."""
    del total  # The heading is "Step N: title". The count stays off the line.
    text = render_step(
        step,
        number,
        show_safety=show_safety,
        show_photo=step_needs_photo(step),
        markdown=True,
        intro=True,
    )
    if step.get("caution"):
        text = f"{text}\n\nCaution: {step['caution']}"
    return text.strip()


def _lower_first(text: str) -> str:
    raw = (text or "").strip().rstrip(".")
    if not raw:
        return ""
    return raw[0].lower() + raw[1:]


def _place_sentence(where: str) -> str:
    text = shop_field_value(where)
    if not text or NOT_STATED in text:
        return ""
    low = _lower_first(text)
    if low.startswith(("at the ", "on the ", "in the ", "over the ")):
        return _finish_sentence(f"Go to {low.split(' ', 1)[1]}")
    if re.match(r"^(?:at|on|in|over|under|between|behind)\b", low):
        return _finish_sentence(f"Go {low}")
    if low.startswith("back of"):
        return _finish_sentence(f"Go to the {low}")
    return _finish_sentence(f"Go to {low}")


def _tool_sentences(value: str) -> list[str]:
    raw = shop_field_value(value)
    if not raw or NOT_STATED in raw:
        return []
    meter = ""
    hit = re.search(r"meter setting:\s*([^.]+)", raw, re.I)
    if hit and NOT_STATED.lower() not in hit.group(1).lower():
        meter = hit.group(1).strip(" .")
    tools = re.sub(r"meter setting:.*", "", raw, flags=re.I)
    tools = re.sub(r"^tools:\s*", "", tools, flags=re.I).strip(" .")
    if not tools or NOT_STATED.lower() in tools.lower():
        tools = ""
    lines = []
    if tools:
        lines.append(_finish_sentence(f"Use {_lower_first(tools)}"))
    if meter:
        lines.append(_finish_sentence(f"Set the meter to {_lower_first(meter)}"))
    return lines


def chat_sentences(step: dict, *, show_safety: bool = False, show_photo: bool = False) -> list[str]:
    """Plain sentences for one check. No field labels and no step counter."""
    fields = (step or {}).get("fields") or {}
    lines = []
    if show_safety:
        safety = step_safety_text(step)
        if safety:
            lines.append(_finish_sentence(safety))
    place = _place_sentence(fields.get("WHERE") or "")
    if place:
        lines.append(place)
    lines.extend(_tool_sentences(fields.get("TOOLS / METER SETTING") or ""))
    for action in step_action_lines(step):
        lines.append(_finish_sentence(action))
    good, bad = _good_bad_bits(fields.get("GOOD vs BAD") or "")
    if good and NOT_STATED not in good:
        lines.append(_finish_sentence(f"A good result is {_lower_first(good)}"))
    if bad and NOT_STATED not in bad and _bad_worth_printing(bad):
        lines.append(_finish_sentence(f"A bad result is {_lower_first(bad)}"))
    for line in _next_lines(fields.get("NEXT") or ""):
        name, _, rest = line.partition(":")
        rest = rest.strip()
        if not rest:
            continue
        if name.lower() == "next":
            lines.append(_finish_sentence(f"If it is good, {_lower_first(rest)}"))
        elif name.lower() == "if it fails":
            lines.append(_finish_sentence(f"If it is bad, {_lower_first(rest)}"))
    figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
    raw_fig = fields.get("FIGURE") or ""
    numbers = _figure_numbers((figure or {}).get("label") or "")
    if not numbers and raw_fig and NOT_STATED not in raw_fig:
        numbers = _figure_numbers(raw_fig)
    if numbers:
        page = (figure or {}).get("page") or ""
        if not page and raw_fig and NOT_STATED not in raw_fig:
            hit = re.search(r"\bpage\s+(\d+)", raw_fig, re.I)
            page = hit.group(1) if hit else ""
        blob = f"{(figure or {}).get('title') or ''} {raw_fig if NOT_STATED not in raw_fig else ''}"
        token = re.search(r"\b(42109|34122|34123|42088)\b", blob)
        shown = f"Fig. {numbers[0]}"
        if token:
            shown = f"{shown}. Kit {token.group(1)}"
            if page:
                shown = f"{shown}, page {page}"
        elif page:
            shown = f"{shown} on page {page}"
        lines.append(f"The manual shows {shown}.")
    if step.get("caution"):
        lines.append(_finish_sentence(f"Caution: {step['caution']}"))
    lines.append("What do you see?")
    if show_photo:
        lines.append(PHOTO_VISUAL)
    return [line for line in lines if line.strip()]


def format_chat_turn(step: dict, number: int, total: int, *, show_safety: bool = False) -> str:
    """One conversational repair turn. The step marker stays hidden in the shop UI."""
    del total
    lines = chat_sentences(
        step,
        show_safety=show_safety,
        show_photo=step_needs_photo(step),
    )
    lines.append(f"<!--gd-step:{int(number)}-->")
    return "\n".join(lines).strip()


def procedure_chat_text(layout: dict) -> str:
    """The full repair as sentences. Section names stay. The step counter stays off."""
    steps = list((layout or {}).get("steps") or [])
    lines = []
    title = (layout or {}).get("title") or ""
    if title:
        lines.append(title)
    section = ""
    for step in steps:
        sec = step.get("section") or ""
        if sec and sec != section:
            section = sec
            lines.append(
                {"removal": "REMOVAL", "installation": "INSTALLATION", "prove": "PROVING CHECKS"}.get(
                    sec, sec.upper()
                )
            )
        for action in step_action_lines(step):
            lines.append(_finish_sentence(action))
    return "\n".join(lines).strip()


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
    (r"\bholding tank opening\b", "holding tank opening at the closet flange"),
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
    (r"^cover (?:the )?holding tank opening\b.*$", "Cover the holding tank opening at the closet flange with a towel"),
    (r"^uncover (?:the )?holding tank opening\b.*$", "Uncover the holding tank opening at the closet flange"),
    (r"^turn off (?:the )?water$", "Turn off the water to the RV"),
    (r"^turn on (?:the )?water$", "Turn the RV water on"),
    (r"^turn (?:the )?water on$", "Turn the RV water on"),
    (r"^flush test (?:the )?toilet.*$", "Flush the toilet one time"),
    (r"^flush (?:the )?toilet.*$", "Flush the toilet one time"),
    (r"^place (?:a )?towel.*$", "Put a towel under the water hose"),
    (r"^place on (?:a |the )?trash bag$", "Put the toilet on a trash bag"),
    (r"^grab (?:the )?front underside of (?:the )?pedal$", "Grab the front of the pedal"),
    (r"^insert (?:a |the )?new water valve.*$", "Push the new valve in until it stops"),
    (r"^uncover (?:the )?tank hole$", "Uncover the holding tank opening at the closet flange"),
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
    text = re.sub(r"^\d+\.\s+", "", text).strip()
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


_BAD_FOR_GOOD = {
    "No water comes out.": "Water still comes out.",
    "Water is on.": "Water is still off.",
    "The bowl water goes down.": "The bowl water stays up.",
    "The seal lip faces down.": "The seal lip faces up.",
    "It is back on.": "It is still off.",
    "The towel is under the hose.": "The towel is not under the hose.",
    "The toilet is on a trash bag.": "The toilet is not on a trash bag.",
    "You are holding the front of the pedal.": "You are not holding the front of the pedal.",
    "The hole is open.": "The hole is still covered.",
    "The holding tank opening is covered.": "The towel misses the opening.",
    "The holding tank opening is clear.": "The towel blocks the opening.",
    "The towel is off.": "The towel is still on.",
    "The hose is off the toilet.": "The hose is still on the toilet.",
    "The hose is on tight.": "The hose is loose.",
    "The pedal is off.": "The pedal is still on.",
    "The old part is in the trash.": "The old part is still on the toilet.",
    "It is in the trash.": "It is still on the toilet.",
    "The cover is open.": "The cover is still closed.",
    "The opening sits on the pedal neck.": "The opening is off the pedal neck.",
    "The cover wraps the back.": "The cover does not wrap the back.",
    "The pedal is down.": "The pedal is still up.",
    "The front clip is on.": "The front clip is off.",
    "Both rings are on.": "A ring is off.",
    "The toilet is off the floor.": "The toilet is still on the floor.",
    "The hole is covered.": "The hole is still open.",
    "The toilet is on its side.": "The toilet is still upright.",
    "Your thumb is in the low spot.": "Your thumb is not in the low spot.",
    "Your finger is under the tab.": "Your finger is not under the tab.",
    "The tab is up.": "The tab is still down.",
    "It is all the way in.": "It is not all the way in.",
    "The pedal sits on the pivot.": "The pedal is off the pivot.",
    "The pin is closed.": "The pin is still open.",
    "The holes line up on the bolts.": "The holes do not line up.",
    "The toilet is upright.": "The toilet is still on its side.",
    "The waste ball opens and closes.": "The waste ball does not open and close.",
    "The pedal snaps on.": "The pedal does not snap on.",
    "The clamp has moved.": "The clamp has not moved.",
    "The clamp is on.": "The clamp is off.",
    "The clamp is tight.": "The clamp is loose.",
    "The toilet does not rock.": "The toilet still rocks.",
    "Toilet does not rock.": "The toilet still rocks.",
    "The rings are off.": "A ring is still on.",
    "You have read the steps.": "A step was skipped.",
    "The toilet is rinsed.": "The toilet is not rinsed.",
    "The tank is drained.": "The tank is not drained.",
    "The toilet is clean.": "The toilet is not clean.",
    "Gloves and glasses are on.": "Gloves or glasses are off.",
    "The toilet can stay down.": "The toilet was lifted when it could stay.",
    "It is in.": "It is not in.",
    "The step is finished.": "The step is not finished.",
    "It stops.": "It does not stop.",
    "Tab locks in place.": "The tab does not lock.",
    "It hits the spring.": "It does not hit the spring.",
    "The pedal snaps.": "The pedal does not snap.",
}


def _bad_for_see(see: str) -> str:
    """The failed look for this good look. Never the generic line."""
    text = _finish_sentence(see)
    if text in _BAD_FOR_GOOD:
        return _BAD_FOR_GOOD[text]
    bare = text.rstrip(".")
    if re.match(r"^You are ", bare):
        return f"You are not {bare[len('You are '):]}."
    match = re.match(r"^(The .+?) (is|are) (.+)$", bare)
    if match:
        return f"{match.group(1)} {match.group(2)} not {match.group(3)}."
    if re.match(r"^It is ", bare, re.I):
        return f"It is not {bare[6:]}."
    verb = re.match(r"^It ([a-z]+s)\b(.*)$", bare)
    if verb:
        word = verb.group(1)
        if word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        rest = (verb.group(2) or "").strip()
        return f"It does not {word} {rest}.".replace(" .", ".").strip()
    if bare:
        return f"Not this: {bare[0].lower()}{bare[1:]}."
    return "The step is not finished."


_GENERIC_BAD_RE = re.compile(
    r"^(?:it does not look right|not stated(?: in this sheet)?|unconfirmed|"
    r"do this step again|the step is not finished|not this:.*)\.?$",
    re.I,
)
_SPECIFIC_BAD_RE = re.compile(
    r"leak|drip|weep|crack|loose|rocks?|snap|lip faces|comes out|stays up|"
    r"does not open|does not lock|does not hit|not dry|still wet|ceiling|"
    r"folded|line up|off the pivot|in cool|cool\b",
    re.I,
)


def _bad_worth_printing(bad: str) -> bool:
    """A bad line names a real failure. A line that only negates Good stays off."""
    text = re.sub(r"\s+", " ", (bad or "")).strip().rstrip(".")
    if not text or _GENERIC_BAD_RE.match(text):
        return False
    if _SPECIFIC_BAD_RE.search(text):
        return True
    if re.match(r"^(?:you are not |it is not |it does not |not this:)", text, re.I):
        return False
    if re.match(r"^the .+ (?:is|are) not ", text, re.I):
        return False
    if re.search(r"\bstill\b", text, re.I):
        return False
    return True


def _yes_no(action: str) -> tuple[str, str]:
    low = action.rstrip(".").lower()
    no = low + "."
    if _word_count(f"No, {no}") > 15:
        no = "do this step again."
    see = "The step is finished."
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
            (r"^uncover the holding tank\b", "The holding tank opening is clear."),
            (r"^cover the holding tank\b", "The holding tank opening is covered."),
            (r"^take the towel off$", "The towel is off."),
            (r"^pull the water hose off\b", "The hose is off the toilet."),
            (r"^push the water hose\b", "The hose is on tight."),
            (r"^pull the pedal\b", "The pedal is off."),
            (r"^take off the (.+)$", "ARE_OFF"),
            (r"^throw the old\b", "The old part is in the trash."),
            (r"^throw the (.+) away$", "The {0} is in the trash."),
            (r"^throw it away$", "It is in the trash."),
            (r"^spread (?:the )?cover open$", "The cover is open."),
            (r"^lower (?:the )?pedal opening\b", "The opening sits on the pedal neck."),
            (r"^wrap (?:the )?cover around\b", "The cover wraps the back."),
            (r"^push (?:the )?pedal down$", "The pedal is down."),
            (r"^push (?:the )?cover into place\b", "The front clip is on."),
            (r"^secure (?:the )?back of (?:the )?cover\b", "Both rings are on."),
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
        see = "The step is finished."
    return see, _bad_for_see(see)


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
        talks = re.search(r"\b(?:clamps?|pockets?|pins?)\s+[A-C]\b", source or "", re.I) or any(
            re.search(r"\b(?:clamps?|pockets?|pins?)\s+[A-C]\b", item or "", re.I) for item in callouts or []
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


_OWNER_BEFORE_RE = re.compile(
    r"rinse the toilet|drain the holding tank|add the tank deodorant|"
    r"wash the toilet|turn the rv water on",
    re.I,
)


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
                if _OWNER_BEFORE_RE.search(short):
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


def _crop_label(figure) -> str:
    if isinstance(figure, dict):
        return figure.get("label") or ""
    return getattr(figure, "caption", "") or ""


def _matching_kit_crop(figures: list, pattern: str):
    """The first non-blank crop whose label matches. None when the sheet has no such crop."""
    found = None
    for figure in figures or []:
        item = _as_figure(figure) if not isinstance(figure, dict) else figure
        label = _crop_label(item)
        png = item.get("png") or b"" if isinstance(item, dict) else b""
        if not png or png_is_blank(png):
            continue
        if re.search(pattern, label or "", re.I):
            found = item
            break
    return found


def attach_open_kit_crops(steps: list, figures: list, doc: str = "") -> list:
    """Leave the crops the numbered instruction already named.

    A water-off line with no Fig. callout stays text. A line that says See Fig. 1
    keeps that crop. Action words alone do not add a crop.
    """
    del figures, doc
    return steps


def _ensure_visible_good_bad(step: dict) -> None:
    """Every step names a good look and a bad look that belongs to that action."""
    fields = step.setdefault("fields", {})
    good, bad = _good_bad_bits(fields.get("GOOD vs BAD") or "")
    action = (step.get("text") or "").strip()
    see, bad_sign = _yes_no(action) if action else ("", "")
    if not good:
        good = see or shop_field_value(step.get("see") or "") or "The step is finished."
    if not bad or _GENERIC_BAD_RE.match(bad):
        bad = bad_sign or ""
    if bad and _GENERIC_BAD_RE.match(bad):
        bad = ""
    good = _finish_sentence(good)
    if bad:
        fields["GOOD vs BAD"] = f"Good: {good} Bad: {_finish_sentence(bad)}"
    else:
        fields["GOOD vs BAD"] = f"Good: {good}"


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
            if not good and gb and f"Good: {NOT_STATED}" not in gb:
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


def _merge_duplicate_pedal_pull(steps: list) -> list:
    """Keep the pedal grab and the pedal pull as two steps.

    One HOW line is one action. Gluing 'Grab the front of the pedal' onto
    'Pull the pedal up and off' put two actions under one step.
    """
    return list(steps or [])


def _apply_leak_test_step(steps: list) -> None:
    """The water-on step is the leak test. Safety matches that water is on.

    A following flush is the check inside that step, not a second HOW.
    """
    if not steps:
        return
    index = None
    for cursor, step in enumerate(steps):
        blob = " ".join(step.get("actions") or []) + " " + (step.get("text") or "")
        if re.search(r"\bturn the rv water on\b", blob, re.I):
            index = cursor
    if index is None:
        return
    while len(steps) > index + 1:
        nxt = steps[index + 1]
        blob = " ".join(nxt.get("actions") or []) + " " + (nxt.get("text") or "")
        if re.search(r"\bflush\b", blob, re.I):
            steps.pop(index + 1)
            continue
        break
    last = steps[index]
    fields = dict(last.get("fields") or {})
    safety = fields.get("SAFETY") or ""
    safety = re.sub(
        r"Turn the RV water off before this work\.",
        "Turn the RV water on for the leak test.",
        safety,
        count=1,
    )
    if "Turn the RV water on for the leak test." not in safety:
        safety = f"Turn the RV water on for the leak test. {safety}".strip()
    fields["SAFETY"] = safety
    fields["WHERE"] = "At the pedal and the water valve."
    fields["GOOD vs BAD"] = (
        "Flush 3 times. Good: Dry at the pedal and the valve. "
        "Bad: any drip, so recheck the seal and the nuts."
    )
    last["fields"] = fields


def _kit_before(sheet: str, items: list[str]) -> list[str]:
    """The Needed list is said once. Owner-manual chores stay off a leak repair."""
    before = [item for item in items or [] if item and not _OWNER_BEFORE_RE.search(item)]
    tools = _needed_tools(sheet)
    if tools:
        line = "Tools: " + ", ".join(tools) + "."
        if line not in before:
            before.insert(0, line)
    return before


def _seat_pedal_removed_figure(steps: list) -> None:
    """Fig. 1 PEDAL REMOVED sits on the step that pulls the pedal off."""
    for index, step in enumerate(steps or []):
        text = (step.get("text") or "").lower()
        if not re.search(r"pull the pedal|pedal up and off", text):
            continue
        current = step.get("figure") if isinstance(step.get("figure"), dict) else None
        if current and re.search(r"pedal removed", current.get("label") or "", re.I):
            continue
        for nxt in steps[index + 1 : index + 4]:
            figure = nxt.get("figure") if isinstance(nxt.get("figure"), dict) else None
            label = (figure or {}).get("label") or ""
            if re.search(r"pedal removed", label, re.I):
                step["figure"] = figure
                nums = _figure_numbers(label)
                if nums:
                    step["fig"] = nums[0]
                fields = dict(step.get("fields") or {})
                fields["FIGURE"] = _figure_field(step, "")
                step["fields"] = fields
                return


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
                if re.fullmatch(
                    r"style\s+\w+\s*(?:only\s*)?-\s*remove pod:?",
                    (piece or "").strip(),
                    re.I,
                ) or re.fullmatch(r"remove pod:", (piece or "").strip(), re.I):
                    continue
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
                if any(
                    earlier.get("section") == section and earlier.get("text") == short
                    for earlier in steps
                ):
                    continue
                if (
                    short == "Take the towel off."
                    and steps
                    and (
                        steps[-1]["text"].startswith("Take the towel off")
                        or steps[-1]["text"].startswith("Uncover the holding tank opening")
                    )
                ):
                    continue
                if not re.match(
                    r"^(?:turn|flush|take|uncover|unhook|pull|put|cover|throw|slide|tighten|set|stand|"
                    r"press|hit|grab|lay|lift|hold|push|wrap|spread|lower|secure)\b",
                    short,
                    re.I,
                ):
                    continue
                if re.search(r"\b(?:vot|wl)\b", short, re.I):
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
    steps = _merge_duplicate_pedal_pull(_group_procedure_steps(kept))
    if not steps:
        return {}
    for index, step in enumerate(steps):
        nxt = steps[index + 1]["text"] if index + 1 < len(steps) else ""
        step["fields"]["NEXT"] = _next_field(nxt)
        _ensure_visible_good_bad(step)
    _apply_leak_test_step(steps)
    _seat_pedal_removed_figure(steps)
    attach_open_kit_crops(steps, figures or [], doc)
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
        "before": _kit_before(text or "", _short_before(parsed.get("before") or [])),
        "removal": removal,
        "installation": installation,
        "steps": steps,
        "spec": spec,
    }


_FOREIGN_LINE_RE = re.compile(
    r"\b(?:le|la|les|des|du|une|pour|avec|dans|puis|crampon|"
    r"el|los|las|para|que|del|una|luego|manguera|abrazadera|dispositivo)\b",
    re.I,
)
_LANG_HEADER_RE = re.compile(r"\b(?:FRAN[cç]ais|ESPA[nñ]OL|ITALIANO)\b", re.I)


def _english_prefix(text: str) -> str:
    """Drop the translation that starts after the English block."""
    return _LANG_HEADER_RE.split(text or "", maxsplit=1)[0].strip()


def _plain_sheet_line(raw: str) -> str:
    """Bullets, ligatures, and marks become plain English letters.

    A soft hyphen is a wrapped word, not a foreign letter. An en dash is a
    hyphen. Either one used to drop the whole line, and the next line then
    kept only the tail of the sentence.
    """
    text = unicodedata.normalize("NFKC", raw or "")
    text = text.replace("\u00ad", "")
    text = text.replace("\u00ae", "").replace("\u2122", "").replace("\u00a9", "")
    text = re.sub(r"[■•●▪▸]", " ", text)
    text = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u2011", "-")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return re.sub(r"\s+", " ", text).strip()


def _line_is_english(raw: str) -> bool:
    """One sheet line is English. A translation column is not."""
    if not raw or any(ord(ch) > 127 for ch in raw):
        return False
    if _LANG_HEADER_RE.search(raw):
        return False
    words = re.findall(r"[A-Za-z]{2,}", raw)
    foreign = _FOREIGN_LINE_RE.findall(raw)
    if len(foreign) >= 2:
        return False
    if words and len(foreign) / len(words) > 0.12:
        return False
    return True


def _english_body(text: str) -> str:
    """English column of one chunk. The French and Spanish columns stay out.

    A line that ends in a soft hyphen is the start of a word. The next English
    line continues it, with no space, so "Cov-" plus "ers" stays "Covers".
    """
    lines = []
    join_next = False
    for raw_line in (text or "").splitlines():
        hyphen_break = "\u00ad" in (raw_line or "")
        raw = _plain_sheet_line(raw_line)
        if hyphen_break:
            raw = raw.rstrip("-").rstrip()
        if not raw:
            continue
        cut = _LANG_HEADER_RE.split(raw, maxsplit=1)[0]
        cut = re.sub(r"\bENGLISH\b", "", cut, flags=re.I).strip()
        if not cut or not _line_is_english(cut):
            join_next = False
            continue
        if join_next and lines:
            lines[-1] = lines[-1] + cut
        else:
            lines.append(cut)
        join_next = hyphen_break
    return "\n".join(lines)


def _stitch_windows(parts: list[str]) -> str:
    """Join overlapping retrieval windows back into one sheet, in order."""
    kept = [part.strip() for part in parts if part and part.strip()]
    if not kept:
        return ""
    out = kept[0]
    for part in kept[1:]:
        best = 0
        limit = min(220, len(out), len(part))
        for size in range(limit, 40, -1):
            if out.endswith(part[:size]):
                best = size
                break
        if not best:
            tail = out[-240:]
            for size in range(min(180, len(part), len(tail)), 40, -1):
                idx = tail.find(part[:size])
                if idx >= 0:
                    best = size
                    out = out[: len(out) - len(tail) + idx]
                    break
        out = out + (part[best:] if best else "\n" + part)
    return out


def _order_windows(parts: list[str]) -> list[str]:
    """Put overlapping windows in sheet order. A later window starts inside an earlier one."""
    kept = [part.strip() for part in parts if part and part.strip()]
    if len(kept) <= 1:
        return kept
    used = [False] * len(kept)

    def continues(part: str, others: list[str]) -> bool:
        head = part[:70]
        return any(head and head in other and other.find(head) > 30 for other in others)

    start = 0
    for index, part in enumerate(kept):
        others = [other for other_index, other in enumerate(kept) if other_index != index]
        if not continues(part, others):
            start = index
            break
    order = [start]
    used[start] = True
    while len(order) < len(kept):
        tail = kept[order[-1]][-220:]
        best_index = -1
        best_size = -1
        for index, part in enumerate(kept):
            if used[index]:
                continue
            size = 0
            for span in range(min(160, len(part), len(tail)), 30, -1):
                if part[:span] in tail:
                    size = span
                    break
            if size > best_size:
                best_size = size
                best_index = index
        if best_index < 0:
            best_index = next(index for index, flag in enumerate(used) if not flag)
        used[best_index] = True
        order.append(best_index)
    return [kept[index] for index in order]


def _fit_english(text: str, limit: int = 4000) -> str:
    """English text only, cut at the live packet limit."""
    body = _english_body(text)
    if len(body) < 80:
        return ""
    return body[:limit]


def kit_excerpt(chunks, kind: str, limit: int = 4000) -> tuple[str, list]:
    """Kit words and crops from retrieved chunks. Not the whole PDF on disk.

    Live retrieval is about a dozen overlapping windows, joined and cut at
    4000 characters. Each window keeps its English column. A translation
    column is not stitched in, and the kit PDF on disk is not opened here.
    """
    needles = (
        ("34122", "34123", "vacuum breaker")
        if kind == "breaker"
        else ("42109", "42049", "water valve")
    )
    grouped: dict[int, list[tuple[int, str]]] = {}
    figures = []
    seen_figures = set()
    for index, chunk in enumerate(chunks or []):
        if not isinstance(chunk, dict):
            continue
        blob = " ".join(
            str(chunk.get(key) or "")
            for key in ("title", "doc_number", "clean_title", "keywords", "file_path")
        ).lower()
        # The owner manual names the water valve and the vacuum breaker.
        # That mention is not the kit sheet. Match the document, not the excerpt.
        if not any(needle in blob for needle in needles):
            continue
        excerpt = chunk.get("excerpt") or ""
        body = _english_body(excerpt)
        # A short English scrap inside a translation window is not a procedure.
        # A full kit sheet is mostly translation, so a long English column still counts.
        if len(body) < 80:
            continue
        if len(body) < 1500 and len(body) < 0.30 * max(len(excerpt), 1):
            continue
        try:
            page = int(chunk.get("page") or 0)
        except (TypeError, ValueError):
            page = 0
        grouped.setdefault(page, []).append((index, body))
        for figure in chunk.get("figures") or []:
            if not isinstance(figure, dict) or not figure.get("png"):
                continue
            key = (
                str(figure.get("label") or ""),
                str(figure.get("page") or ""),
                len(figure.get("png") or b""),
            )
            if key in seen_figures:
                continue
            seen_figures.add(key)
            figures.append(figure)
    pieces = []
    for page in sorted(grouped):
        windows = _order_windows([body for _index, body in grouped[page]])
        stitched = _stitch_windows(windows)
        if stitched:
            pieces.append(stitched)
    return _stitch_windows(pieces)[:limit], figures


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


def part_topic(text: str) -> str:
    """Which Thetford part this step is about. The reply wins over an older fact."""
    low = (text or "").lower()
    breaker = bool(re.search(r"vacuum breaker|\b34122\b|\b34123\b", low))
    valve = bool(re.search(r"\b42109\b|\b42049\b|water valve", low))
    if breaker and valve:
        breaker_at = low.find("vacuum breaker")
        valve_at = min(
            (index for index in (low.find("water valve"), low.find("42109"), low.find("42049")) if index >= 0),
            default=10**9,
        )
        return "breaker" if 0 <= breaker_at <= valve_at else "valve"
    if breaker:
        return "breaker"
    if valve:
        return "valve"
    return ""


def thetford_procedure_show_caption(reply: str) -> str:
    """Kit label for a numbered valve step. Empty on a proving turn."""
    raw = reply or ""
    marked = bool(re.search(r"<!--\s*gd-step:\d+\s*-->", raw))
    legacy = (
        ("Here is the repair procedure." in raw or bool(re.search(r"\bStep\s+\d+\s+of\s+\d+", raw)))
        and bool(re.search(r"\bStep\s+\d+\s*(?:of\s+\d+|:)", raw))
    )
    if not marked and not legacy:
        return ""
    numbers = _numbers_named(raw)
    if not numbers or not re.search(r"\b42109\b", raw):
        return ""
    return f"42109 Fig. {numbers[0]}"


def bundled_thetford_offers(
    reply: str = "",
    user_msg: str = "",
    category: str = "",
    model: str = "",
) -> list:
    """Page images and figure crops for a Thetford turn. Empty for every other job.

    Each offer carries the PNG, so the chat can show it without a library row.
    The figure follows the reply's part. A vacuum-breaker step does not show the water valve kit.
    """
    if not job_is_thetford(reply, user_msg, category, model):
        return []
    want = part_topic(reply) or part_topic(user_msg)
    if not want:
        blob = f"{reply or ''}\n{user_msg or ''}".lower()
        if re.search(r"pedal|retainer|pocket", blob):
            want = "valve"
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


def thetford_show_offer(reply: str, user_msg: str = "") -> dict | None:
    """The kit crop for a Thetford show-me. Empty when this turn is not that toilet."""
    numbered = thetford_procedure_show_offer(reply)
    if numbered and numbered.get("png"):
        return numbered
    if not job_is_thetford(reply, user_msg):
        return None
    crops = [
        item
        for item in bundled_thetford_offers(reply, user_msg, "Plumbing / Toilets", "Thetford")
        if (item.get("label") or "") != "page" and item.get("png")
    ]
    if not crops:
        return None
    named = _numbers_named(reply or "") or _numbers_named(user_msg or "")
    chosen = crops[0]
    if named:
        for item in crops:
            if any(number in named for number in _figure_numbers(item.get("label") or "")):
                chosen = item
                break
    shown = dict(chosen)
    title = shown.get("title") or ""
    nums = _figure_numbers(shown.get("label") or "")
    if "42109" in title and nums:
        caption = f"42109 Fig. {nums[0]}"
    elif "3412" in title and nums:
        caption = f"34123 Fig. {nums[0]}"
    elif nums:
        caption = f"Fig. {nums[0]}"
    else:
        caption = display_caption(title, shown.get("page") or 1, shown.get("label") or "")
    shown["label"] = caption
    shown["caption"] = caption
    shown["bundled"] = False
    shown["brand"] = "Thetford"
    shown["category_name"] = "Plumbing / Toilets"
    return shown


def thetford_procedure_show_offer(reply: str) -> dict | None:
    """The kit crop for this numbered step, captioned with the kit label."""
    caption = thetford_procedure_show_caption(reply)
    if not caption:
        return None
    number = int(caption.rsplit(" ", 1)[-1])
    for offer in bundled_thetford_offers(reply, "", "Plumbing / Toilets", "Thetford"):
        if (offer.get("label") or "") == "page":
            continue
        if number not in _figure_numbers(offer.get("label") or ""):
            continue
        if "42109" not in (offer.get("title") or ""):
            continue
        if not offer.get("png"):
            continue
        shown = dict(offer)
        shown["label"] = caption
        shown["caption"] = caption
        shown["bundled"] = False
        shown["brand"] = "Thetford"
        shown["category_name"] = "Plumbing / Toilets"
        return shown
    return None


def _png_from_local_file(path: str, page) -> bytes:
    """Bytes for a real file on disk. An R2 key is not a file and returns nothing."""
    file = Path(path or "")
    if not path or not file.is_file():
        return b""
    try:
        data = file.read_bytes()
    except Exception:
        return b""
    if data.startswith(b"\x89PNG") or data[:3] == b"\xff\xd8\xff":
        return data
    if not data.startswith(b"%PDF"):
        return b""
    fitz = _fitz()
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        try:
            index = max(0, int(page or 1) - 1)
        except (TypeError, ValueError):
            index = 0
        if index >= doc.page_count:
            index = 0
        return render_page_png(doc[index])
    except Exception:
        return b""
    finally:
        _release_document(doc)


def png_for_library_offer(src: dict) -> bytes:
    """A figure to show when the R2 object is missing.

    A bundled Thetford crop is preferred. A real local file is next.
    An empty result means show nothing. Callers do not tell the tech the
    download failed.
    """
    src = src or {}
    title = str(src.get("title") or "")
    label = str(src.get("label") or "")
    caption = str(src.get("caption") or "")
    if src.get("bundled") or job_is_thetford(title, label, caption):
        offers = bundled_thetford_offers(f"{title}\n{caption}", label or caption)
        wanted = _figure_numbers(f"{label} {caption}")
        chosen = b""
        for offer in offers:
            png = offer.get("png") or b""
            if not png or png_is_blank(png):
                continue
            nums = _figure_numbers(offer.get("label") or "")
            if wanted and any(number in wanted for number in nums):
                return png
            if not chosen and (offer.get("label") or "") != "page":
                chosen = png
        if chosen:
            return chosen
    return _png_from_local_file(str(src.get("file_path") or ""), src.get("page") or 1)


_PROVING_PHOTO_CONNECTOR = PHOTO_VISUAL
_PROVING_PHOTO_LEAK = PHOTO_VISUAL
_PROVING_NUMBER = {
    "supply": 1,
    "vacuum": 2,
    "valve": 3,
    "flange": 4,
    "vacuum_replace": 1,
    "valve_replace": 1,
}
_PROVING_SAFETY = (
    f"Water off: {NOT_STATED} Power off: {NOT_STATED} Propane off: {NOT_STATED}"
)
_PROVING_TOOLS = f"Tools: {NOT_STATED} Meter setting: {NOT_STATED}"
_OM_FIGURE = f"{NOT_STATED} Thetford Style II OM Permanent RV Toilet 42088, page 3."
_THETFORD_PROVING = {
    "supply": {
        "WHERE": "Back of the toilet.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Check the water supply line connection at the water valve.",
        "GOOD vs BAD": (
            "Good: the connection is dry. Bad: the leak persists from the water valve. "
            "A leak at the back, low, with the lever at rest, is the fitting."
        ),
        "NEXT": (
            "On good: go to the next check. "
            "On bad: fix or tighten the supply connection."
        ),
        "FIGURE": _OM_FIGURE,
        "PHOTO": _PROVING_PHOTO_CONNECTOR,
    },
    "vacuum": {
        "WHERE": "At the vacuum breaker on the flush hose.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Check whether the vacuum breaker leaks while flushing.",
        "GOOD vs BAD": "Good: no leak while flushing. Bad: it leaks only while flushing.",
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
        "SAFETY": f"Turn the RV water off before this work. Power off: {NOT_STATED} Propane off: {NOT_STATED}",
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Replace the vacuum breaker or the water module, depending on model.",
        "GOOD vs BAD": "Good: no leak while flushing. Bad: it leaks while flushing.",
        "NEXT": f"On good: {NOT_STATED} On bad: {NOT_STATED}",
        "FIGURE": "Fig. 1, Thetford Vacuum Breaker Kit 34123/34122, page 1.",
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
    "valve": {
        "WHERE": "At the pedal.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Pull the pedal off.",
        "GOOD vs BAD": (
            "Good: no weep at the pedal. "
            "Bad: a weep at the cartridge, the drive arm, or a cracked housing."
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
        "SAFETY": f"Turn the RV water off before this work. Power off: {NOT_STATED} Propane off: {NOT_STATED}",
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Water valve 42049 weeps at the pedal. Replace it with water valve kit 42109.",
        "GOOD vs BAD": "Good: no weep at the pedal. Bad: it weeps at the pedal.",
        "NEXT": f"On good: {NOT_STATED} On bad: {NOT_STATED}",
        "FIGURE": "Fig. 1 PEDAL REMOVED, Thetford Water Valve Service Kit 42109, page 1.",
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
    "flange": {
        "WHERE": "Between the closet flange and the toilet.",
        "SAFETY": _PROVING_SAFETY,
        "TOOLS / METER SETTING": _PROVING_TOOLS,
        "HOW": "Check the flange nuts for a flange 7/16 inch above the floor.",
        "GOOD vs BAD": "Good: the flange is dry. Bad: the leak continues.",
        "NEXT": (
            "On good: the leak checks are done. "
            "On bad: if the leak continues, replace the flange seal. "
            "Closet flange seal 02125 is on the kits."
        ),
        "FIGURE": _OM_FIGURE,
        "PHOTO": _PROVING_PHOTO_LEAK,
    },
}
_THETFORD_PROVING_CITE = {
    "supply": "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
    "vacuum": "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 1",
    "vacuum_replace": "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 1",
    "valve": "📖 Source: Thetford Water Valve Service Kit 42109, page 1",
    "valve_replace": "📖 Source: Thetford Water Valve Service Kit 42109, page 1",
    "flange": "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
}


def thetford_proving_body(key: str) -> str:
    """One leak check for the Bay sheet. No photo ask, no figure cite, and no source line."""
    return hide_internal_marker(
        format_step_fields(
            _THETFORD_PROVING[key],
            number=_PROVING_NUMBER[key],
            show_photo=False,
            show_figure=False,
        )
    )


def thetford_proving_line(key: str) -> str:
    """One leak check in plain sentences. A photo is asked only when it would help."""
    step = _fields_as_step(_THETFORD_PROVING[key])
    lines = chat_sentences(step, show_photo=step_needs_photo(step))
    if key == "supply":
        place = "The water supply connection is at the back of the toilet, on the water valve."
        if place not in lines:
            lines.insert(0, place)
    body = "\n".join(lines)
    return hide_internal_marker(f"{body}\n\n{_THETFORD_PROVING_CITE[key]}")


def procedure_handoff(layout: dict) -> str:
    """Full procedure text. GD sends one step at a time from format_one_step."""
    steps = list(layout.get("steps") or [])
    if not steps:
        steps = list(layout.get("removal") or []) + list(layout.get("installation") or [])
    lines = ["Here is the repair procedure.", ""]
    if layout.get("title"):
        lines.append(layout["title"])
        lines.append("")
    if layout.get("before"):
        lines.append("Before you start:")
        lines.extend(f"- {item}" for item in layout["before"])
        lines.append("")
    section = ""
    for index, step in enumerate(steps, 1):
        sec = step.get("section") or ""
        if sec and sec != section:
            section = sec
            label = {"removal": "REMOVAL", "installation": "INSTALLATION", "prove": "PROVING CHECKS"}.get(
                sec, sec.upper()
            )
            lines.append(label)
            lines.append("")
        lines.append(
            render_step(
                step,
                index,
                show_safety=show_safety_for(steps, index),
                show_photo=False,
                markdown=True,
            )
        )
        lines.append("")
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
            "what does it look like",
            "what it looks like",
            "what do they look like",
            "where is it",
            "where it is",
        )
    ):
        return True


def tech_asked_for_manual_figure(text: str) -> bool:
    """True when the tech asked to see the manual page or figure."""
    return wants_manual_image(text)
    if re.search(r"\bsource\b", raw) and re.search(
        r"\b(show|see|photo|picture|pull|display|what|where)\b", raw
    ):
        return True
    return False


# FACR08 shop sheet. Figures cite the library doc and page. No bundled PNG.
FACR_8666_DOC = "Furrion Chill FACR CCD-0008666"
FACR_7990_DOC = "Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
FACR_PART = "2024006031"


def _facr_dot(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    if not raw:
        return ""
    return raw if raw.endswith(".") else raw + "."


def _facr_figure(doc: str, page, label: str):
    """Cite a library page. page None means the sheet names the figure and not a page."""
    title = FACR_8666_DOC if doc == "8666" else FACR_7990_DOC
    figure = {"title": title, "label": label, "png": b"", "page": page or None}
    if page:
        cite = f"{label}, {title}, page {page}"
    else:
        cite = f"{label}, {title}"
    return figure, cite


def _facr_step(
    how: str,
    where: str,
    safety: str,
    good: str,
    bad: str,
    nxt: str,
    *,
    section: str = "",
    tools: str = "",
    bad_next: str = "Stay on this step.",
    doc: str = "",
    page=None,
    label: str = "",
    caution: str = "",
) -> dict:
    """One action. Empty tools and an uncited figure are left off the step."""
    fields = {
        "WHERE": _facr_dot(where),
        "SAFETY": _facr_dot(safety),
        "HOW": _facr_dot(how),
        "GOOD vs BAD": f"Good: {_facr_dot(good)} Bad: {_facr_dot(bad)}",
        "NEXT": f"On good: {_facr_dot(nxt)} On bad: {_facr_dot(bad_next)}",
        "PHOTO": PHOTO_STEP,
    }
    figure = None
    if tools:
        fields["TOOLS / METER SETTING"] = _facr_dot(tools)
    if doc and label:
        figure, cite = _facr_figure(doc, page, label)
        fields["FIGURE"] = cite
    return {
        "section": section,
        "text": _facr_dot(how),
        "actions": [_facr_dot(how)],
        "fields": fields,
        "figure": figure,
        "caution": caution,
    }


def facr_proving_layout() -> dict:
    """Numbered proving checks for FACR08HESA2-PS. Condemn waits until these are done."""
    s = _facr_step
    steps = [
        s(
            "Dry the ceiling inside the coach.",
            "Inside the coach, on the ceiling.",
            "Keep people clear of the drip.",
            "The ceiling is dry.",
            "Water is still on the ceiling.",
            "Run COOL with the fan on HIGH.",
        ),
        s(
            "Run COOL with the fan on HIGH.",
            "At the wall control.",
            "Leave both filters in the unit.",
            "The unit is running in COOL.",
            "The unit is not in COOL.",
            "Wait 15 minutes.",
        ),
        s(
            "Wait 15 minutes.",
            "At the rooftop unit.",
            "Leave the fan on HIGH.",
            "15 minutes have passed.",
            "The run was shorter than 15 minutes.",
            "Look for drip on the coil.",
        ),
        s(
            "Look for drip on the coil.",
            "On the evaporator coil.",
            "Do not condemn the unit yet.",
            "You looked at the coil for drip.",
            "Drip is still hiding the coil.",
            "Look for frost on the suction line.",
            doc="8666",
            page=20,
            label="Water enters the vehicle",
        ),
        s(
            "Look for frost on the suction line.",
            "On the suction line.",
            "Do not condemn the unit yet.",
            "The suction line is clear of frost.",
            "Frost is on the suction line.",
            "Turn the 115VAC breaker off.",
            doc="8666",
            page=20,
            label="Water enters the vehicle",
        ),
        s(
            "Turn the 115VAC breaker off.",
            "At the 115VAC breaker.",
            "Keep 115VAC off for the drain work.",
            "The breaker is off.",
            "The breaker is still on.",
            "Turn the 12VDC supply off.",
        ),
        s(
            "Turn the 12VDC supply off.",
            "At the 12VDC supply.",
            "Keep both supplies off.",
            "12VDC is off.",
            "12VDC is still on.",
            "Discharge the capacitors.",
        ),
        s(
            "Discharge the capacitors.",
            "At the capacitors.",
            "R32 is flammable.",
            "The capacitors are discharged.",
            "The capacitors still hold a charge.",
            "Remove the shroud.",
            doc="8666",
            page=18,
            label="Capacitor discharge",
            caution="R32 is flammable.",
        ),
        s(
            "Remove the shroud.",
            "On the roof, over the unit.",
            "Keep both supplies off.",
            "The shroud is off.",
            "The shroud is still on.",
            "Clear the drain openings.",
        ),
        s(
            "Clear the drain openings.",
            "In the drain openings.",
            "Keep both supplies off.",
            "The openings are clear.",
            "Debris still blocks an opening.",
            "Pour water into the pan.",
            doc="7990",
            page=7,
            label="Drainage openings",
        ),
        s(
            "Pour water into the pan.",
            "In the evaporator pan.",
            "Keep both supplies off.",
            "Water is in the pan.",
            "Water missed the pan.",
            "Watch the water leave the pan.",
        ),
        s(
            "Watch the water leave the pan.",
            "At the evaporator pan.",
            "Keep both supplies off.",
            "The pan empties.",
            "Water stands in the pan.",
            "Check the unit is within 15 degrees each way.",
            bad_next="Clear the drain openings.",
        ),
        s(
            "Check the unit is within 15 degrees each way.",
            "On the rooftop unit.",
            "Keep both supplies off.",
            "The unit is within 15 degrees each way.",
            "The unit is out of level.",
            "Center the roof gasket.",
            bad_next="Shim the unit from the outside.",
            doc="8666",
            page=6,
            label="Level note",
        ),
        s(
            "Shim the unit from the outside.",
            "Outside, under the unit.",
            "Do not slide the unit.",
            "The unit is within 15 degrees.",
            "The unit is still out of level.",
            "Center the roof gasket.",
        ),
        s(
            "Center the roof gasket.",
            "On the roof opening.",
            "Keep both supplies off.",
            "The gasket is centered.",
            "The gasket sits off center.",
            "Torque the bolts until the indicators touch.",
            doc="8666",
            page=11,
            label="Fig. 2",
        ),
        s(
            "Torque the bolts until the indicators touch.",
            "At the four roof bolts.",
            "Keep both supplies off.",
            "White indicators touch the roof. Compression is about 9/16 inch.",
            "Indicators sit off the roof.",
            "Push the filter plate tabs.",
            tools="Torque wrench, 40 to 50 in-lb.",
            doc="8666",
            page=12,
            label="Fig. 5",
        ),
        s(
            "Push the filter plate tabs.",
            "At the ceiling plate.",
            "Do not run the unit without filters.",
            "The tabs are pushed.",
            "The plate stays up.",
            "Drop the filter plate.",
            doc="8666",
            page=19,
            label="Fig. 28",
        ),
        s(
            "Drop the filter plate.",
            "At the ceiling plate.",
            "Do not run the unit without filters.",
            "The plate is down.",
            "The plate is still up.",
            "Remove both filters.",
        ),
        s(
            "Remove both filters.",
            "In the ceiling plate.",
            "Do not run the unit without filters.",
            "Both filters are out.",
            "A filter is still in.",
            "Wash the filters.",
            doc="8666",
            page=19,
            label="Fig. 29",
        ),
        s(
            "Wash the filters.",
            "At a sink.",
            "Do not run the unit without filters.",
            "The filters are clean.",
            "Dirt remains on a filter.",
            "Dry the filters.",
        ),
        s(
            "Dry the filters.",
            "At a sink.",
            "Do not run the unit without filters.",
            "The filters are dry.",
            "A filter is still wet.",
            "Open all the nozzles.",
            caution="Do not run the unit without filters.",
        ),
        s(
            "Open all the nozzles.",
            "At the ceiling nozzles.",
            "Put both filters back before a run.",
            "Every nozzle is open.",
            "A nozzle is closed.",
            "Confirm the blower spins freely.",
            doc="8666",
            page=19,
            label="Airflow rows",
        ),
        s(
            "Confirm the blower spins freely.",
            "At the blower.",
            "Keep both filters in the unit.",
            "The blower spins freely.",
            "The blower is stuck.",
            "Confirm the grilles are clear.",
        ),
        s(
            "Confirm the grilles are clear.",
            "At the grilles.",
            "Keep both filters in the unit.",
            "The grilles are clear.",
            "A grille is blocked.",
            "Seat the freeze sensor at the coil center.",
        ),
        s(
            "Seat the freeze sensor at the coil center.",
            "Center bottom of the evaporator.",
            "Keep both supplies off.",
            "The sensor sits at the center bottom.",
            "The sensor sits off the coil.",
            "Push the sensor to 1-3/16 inch deep.",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Push the sensor to 1-3/16 inch deep.",
            "Center bottom of the evaporator, 30 mm.",
            "Keep both supplies off.",
            "The sensor is 30 mm deep.",
            "The sensor is shallow.",
            "Clamp the freeze sensor in place.",
        ),
        s(
            "Clamp the freeze sensor in place.",
            "On the freeze sensor.",
            "Keep both supplies off.",
            "The clamp holds the sensor.",
            "The sensor is loose.",
            "Meter the freeze sensor cold on ohms.",
        ),
        s(
            "Meter the freeze sensor cold on ohms.",
            "At the freeze sensor leads.",
            "Keep both supplies off.",
            "The cold reading is on the meter.",
            "The meter shows no reading.",
            "Meter the freeze sensor warm on ohms.",
            tools="Meter on ohms.",
        ),
        s(
            "Meter the freeze sensor warm on ohms.",
            "At the freeze sensor leads.",
            "Keep both supplies off.",
            "The warm reading is on the meter.",
            "The meter shows no reading.",
            "Confirm the ohms reading changes smoothly.",
            tools="Meter on ohms.",
        ),
        s(
            "Confirm the ohms reading changes smoothly.",
            "At the freeze sensor leads.",
            "Keep both supplies off.",
            "The reading changes smoothly.",
            "The reading jumps or stays flat.",
            "Hand refrigerant work to a certified tech.",
            tools="Meter on ohms.",
        ),
        s(
            "Hand refrigerant work to a certified tech.",
            "At the sealed system.",
            "Do not use a halide torch.",
            "A certified tech has the job.",
            "Someone else is on the sealed system.",
            "Read the cooling amps.",
            doc="8666",
            page=18,
            label="No halide torch",
            caution="Do not use a halide torch.",
        ),
        s(
            "Read the cooling amps.",
            "At the 115V supply.",
            "Do not use a halide torch.",
            "Amps are at or under 8.2.",
            "Amps are over 8.2.",
            "Ask for authorization with the photos.",
            tools="Meter on amps.",
            doc="8666",
            page=20,
            label="Cooling amps",
        ),
    ]
    return {
        "heading": "PROVING CHECKS",
        "title": f"FACR08HESA2-PS proving checks, part {FACR_PART}",
        "before": [
            "Unit is Furrion FACR08HESA2-PS. Lippert part 2024006031.",
            "Charge is R32, 9.88 oz. Supply is 115V. Cooling limit is 8.2 A.",
            "Finish these proving checks before you condemn the unit.",
            "Do not use CCD-0007990 part numbers.",
        ],
        "steps": steps,
    }


def facr_rr_layout() -> dict:
    """Removal and install after authorization. Guided Diagnostics walks these steps."""
    s = _facr_step
    off = "Keep both supplies off."
    steps = [
        s(
            "Turn the 115VAC breaker off.",
            "At the 115VAC breaker.",
            off,
            "The breaker is off.",
            "The breaker is still on.",
            "Turn the 12VDC supply off.",
            section="removal",
        ),
        s(
            "Turn the 12VDC supply off.",
            "At the 12VDC supply.",
            off,
            "12VDC is off.",
            "12VDC is still on.",
            "Hoist the unit off the roof.",
            section="removal",
        ),
        s(
            "Hoist the unit off the roof.",
            "The unit weighs about 100 lb.",
            "Do not slide the unit.",
            "The unit is hanging on the hoist.",
            "The unit is still on the roof.",
            "Unplug the freeze sensor.",
            section="removal",
            doc="8666",
            page=11,
            label="Hoist the unit",
            caution="Do not slide the unit.",
        ),
        s(
            "Unplug the freeze sensor.",
            "At the freeze sensor plug.",
            off,
            "The freeze sensor is unplugged.",
            "The freeze sensor is still plugged in.",
            "Unplug the room sensor.",
            section="removal",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Unplug the room sensor.",
            "At the room sensor plug.",
            off,
            "The room sensor is unplugged.",
            "The room sensor is still plugged in.",
            "Unplug the unit cable.",
            section="removal",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Unplug the unit cable.",
            "At the unit cable.",
            off,
            "The unit cable is unplugged.",
            "The unit cable is still plugged in.",
            "Unplug the 115VAC cord.",
            section="removal",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Unplug the 115VAC cord.",
            "At the 115VAC cord.",
            off,
            "The 115VAC cord is unplugged.",
            "The 115VAC cord is still plugged in.",
            "Unplug the 12VDC cord.",
            section="removal",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Unplug the 12VDC cord.",
            "At the 12VDC cord.",
            off,
            "The 12VDC cord is unplugged.",
            "The 12VDC cord is still plugged in.",
            "Unplug the furnace plug.",
            section="removal",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Unplug the furnace plug.",
            "At the furnace plug.",
            off,
            "The furnace plug is unplugged.",
            "The furnace plug is still plugged in.",
            "Remove the four mounting bolts.",
            section="removal",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Remove the four mounting bolts.",
            "At the four roof bolts.",
            off,
            "All four bolts are out.",
            "A bolt is still in.",
            "Make the roof opening 14-1/4 inch square.",
            section="removal",
        ),
        s(
            "Make the roof opening 14-1/4 inch square.",
            "In the roof opening.",
            off,
            "The opening is 14-1/4 inch square.",
            "The opening is the wrong size.",
            "Point the marked side forward.",
            section="installation",
            doc="8666",
            page=7,
            label="Roof opening",
        ),
        s(
            "Point the marked side forward.",
            "On the unit base.",
            off,
            "The marked side faces forward.",
            "The marked side faces another way.",
            "Center the gasket on the opening.",
            section="installation",
            doc="8666",
            page=None,
            label="Fig. 1 This side facing forward",
        ),
        s(
            "Center the gasket on the opening.",
            "On the roof opening.",
            off,
            "The gasket is centered.",
            "The gasket sits off center.",
            "Torque the bolts until the indicators touch.",
            section="installation",
            doc="8666",
            page=11,
            label="Fig. 2",
        ),
        s(
            "Torque the bolts until the indicators touch.",
            "At the four roof bolts.",
            off,
            "White indicators touch the roof. Compression is about 9/16 inch.",
            "Indicators sit off the roof.",
            "Apply foil tape on the seams.",
            section="installation",
            tools="Torque wrench, 40 to 50 in-lb.",
            doc="8666",
            page=12,
            label="Fig. 5",
        ),
        s(
            "Apply foil tape on the seams.",
            "On the roof seams.",
            off,
            "Foil tape covers the seams.",
            "A seam is still open.",
            "Seat the freeze sensor with the clamp.",
            section="installation",
            doc="8666",
            page=13,
            label="Foil tape",
        ),
        s(
            "Seat the freeze sensor with the clamp.",
            "Center bottom of the evaporator.",
            off,
            "The sensor is clamped in place.",
            "The sensor is loose.",
            "Set the DIP switches to match the old board.",
            section="installation",
            doc="8666",
            page=16,
            label="Fig. 22",
        ),
        s(
            "Set the DIP switches to match the old board.",
            "On the control board.",
            "Do not change DIP switches with the power on.",
            "The switches match the old board.",
            "The switches do not match.",
            "Confirm there is no drip.",
            section="installation",
            doc="8666",
            page=13,
            label="DIP switches",
            caution="Do not change DIP switches with the power on.",
        ),
        s(
            "Confirm there is no drip.",
            "Inside the coach, on the ceiling.",
            "Run COOL with the fan on HIGH.",
            "There is no drip.",
            "The ceiling still drips.",
            "Confirm there is no frost.",
            section="installation",
            bad_next="Go back to the drain check.",
        ),
        s(
            "Confirm there is no frost.",
            "On the coil and the suction line.",
            "Run COOL with the fan on HIGH.",
            "There is no frost.",
            "Frost is still on the coil.",
            "Confirm cooling amps are at or under 8.2.",
            section="installation",
        ),
        s(
            "Confirm cooling amps are at or under 8.2.",
            "At the 115V supply.",
            "Do not use a halide torch.",
            "Amps are at or under 8.2.",
            "Amps are over 8.2.",
            "The install retest is done.",
            section="installation",
            tools="Meter on amps.",
            doc="8666",
            page=20,
            label="Cooling amps",
        ),
    ]
    return {
        "heading": "REPAIR PROCEDURE",
        "title": f"FACR08HESA2-PS rooftop removal and install, part {FACR_PART}",
        "before": [
            "Get authorization with the photos before removal.",
            "Order part 2024006031 only.",
            "Filters, the freeze sensor, and the gasket have no part number here.",
            "The unit weighs about 100 lb. Hoist it.",
            "Do not slide the unit.",
            "R32 is flammable. Keep flame away.",
            "Do not change DIP switches with the power on.",
            "Do not use CCD-0007990 part numbers.",
        ],
        "steps": steps,
    }
