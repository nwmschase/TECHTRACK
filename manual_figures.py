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
from pathlib import Path

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.20.0"

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


def _kit_paths(kind: str):
    """Demo library files. Step text is parsed from the file, not stored here."""
    root = Path(__file__).resolve().parent / "tests" / "fixtures"
    if kind == "valve":
        return root / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf", "Thetford Water Valve Kit 42109"
    if kind == "breaker":
        return root / "34123-34122-VacBrkr-1.pdf", "Thetford Vacuum Breaker Kit 34123/34122"
    return None


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


def _figure_numbers(label: str) -> list[int]:
    return [int(number) for number in re.findall(r"\b(?:fig(?:ure)?s?\.?)\s*(\d+)", label or "", flags=re.I)]


def _numbers_named(text: str) -> list[int]:
    numbers = []
    for match in re.finditer(r"\b(?:figs?\.?|figures?)\s*(\d+)(?:\s*&\s*(\d+))?", text or "", flags=re.I):
        numbers.append(int(match.group(1)))
        if match.group(2):
            numbers.append(int(match.group(2)))
    return numbers


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


