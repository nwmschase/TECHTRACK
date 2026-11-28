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

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.20.9"

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


def asset_path(document_id: int, page: int, kind: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (label or kind).lower()).strip("-") or kind
    return f"library-pages/{int(document_id)}/p{int(page)}-{slug}.png"



