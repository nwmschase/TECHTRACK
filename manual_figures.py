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


PHOTO_ASK = "No manual figure covers this step. Take a photo of what you see and send it."

_FOREIGN_LINE_RE = re.compile(
    r"\b(?:retirez|installez|cabinet d|chasse|pince|alicates|inodoro|dispositivo|"
    r"trousse|coupez|serviette|suministro|recubrimiento|manguera|"
    r"anti-refoulement|crampon|tuyau|évacuation|evacuation|desodorante|"
    r"eaux usées|bac à|gants|lunettes|bride de sol|feuille d)\b",
    re.I,
)
_SECTION_HEAD_RE = re.compile(
    r"^(before beginning|remove toilet|remove old water valve|remove old vacuum(?: breaker)?|"
    r"install new water valve|install new vacuum(?: breaker)?|reinstall toilet)\b",
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
PHOTO_STEP = "Take a photo of this step and send it."
PHOTO_WAIT = "Send the photo before the next step."

# One action, short words, a yes/no check, and the kit figure when the sheet has one.
# fig is the manual figure number, or None when that step has no picture.
_PLAIN_BEFORE = (
    "Read all the steps first.",
    "Rinse the toilet.",
    "Drain the holding tank.",
    "Put on gloves and glasses.",
    "Gloves cover your hands.",
    "Wash the toilet.",
)
# section, text, see, no, fig, explain, caution
_VALVE_PLAIN = (
    ("removal", "Turn off the water to the RV.", "No water comes out.", "turn the water off.", None, "", ""),
    ("removal", "Flush the toilet one time.", "The bowl water goes down.", "flush it one more time.", None, "", ""),
    ("removal", "Put a towel under the water hose.", "The towel is under the hose.", "move the towel under the hose.", None, "The hose brings water to the toilet.", ""),
    ("removal", "Pull the water hose off the toilet.", "The hose is off the toilet.", "pull the hose off.", None, "", ""),
    ("removal", "Take off the bolt covers.", "The bolts are bare.", "pull the covers off.", None, "Bolts hold the toilet to the floor.", ""),
    ("removal", "Lift the toilet off the floor.", "The toilet is off the floor.", "lift the toilet again.", None, "", ""),
    ("removal", "Cover the tank hole with a towel.", "The hole is covered.", "cover the hole.", None, "", ""),
    ("removal", "Pull off the old floor seal.", "The old seal is off.", "pull the old seal off.", None, "", ""),
    ("removal", "Throw the old seal away.", "The old seal is in the trash.", "throw the old seal away.", None, "", ""),
    ("removal", "Lay the toilet on its side.", "The toilet is on its side.", "lay the toilet on its side.", None, "", ""),
    ("removal", "Point the pedal up.", "The pedal points up.", "turn the pedal up.", None, "The pedal is the foot lever.", ""),
    ("removal", "Pull the pedal up and off.", "The pedal is off.", "pull the pedal off.", None, "", ""),
    ("removal", "Lift the retainer tab.", "The tab is up.", "lift the tab again.", 1, "The retainer is the lock tab. See figure 1.", ""),
    ("removal", "Turn the retainer to the right.", "The retainer hits the spring.", "turn the retainer again.", 1, "See figure 1.", ""),
    ("removal", "Pull the water valve out.", "The valve is out.", "pull the valve out.", 1, "See figure 1.", ""),
    ("removal", "Throw the old valve away.", "The old valve is in the trash.", "throw the old valve away.", None, "", ""),
    ("removal", "Pull the old inlet seal out with small pliers.", "The old seal is out.", "pull the seal out.", None, "Pliers are a hand tool.", ""),
    ("installation", "Put the new inlet seal in.", "The seal is in the hole.", "push the seal in.", 2, "See figure 2.", ""),
    ("installation", "Push the new valve in until it stops.", "The valve sits all the way in.", "push the valve in again.", None, "", ""),
    ("installation", "Turn the retainer until the tab locks.", "The tab is locked.", "turn the retainer again.", None, "", ""),
    ("installation", "Set the drive pin to closed.", "The pin matches figure 3.", "move the pin to closed.", 3, "Closed means the pin is shut. See figure 3.", ""),
    ("installation", "Set the pedal on the pivot.", "The pedal sits on the pivot.", "set the pedal on the pivot.", 4, "See figure 4.", ""),
    ("installation", "Put the spring tab in pocket A.", "The tab is in pocket A.", "put the tab in pocket A.", 4, "See figure 4.", ""),
    ("installation", "Put the drive pin in pocket B.", "The pin is in pocket B.", "put the pin in pocket B.", 4, "See figure 4.", ""),
    ("installation", "Hit the outside button until it snaps.", "The pedal snaps on.", "hit the button again.", 4, "See figure 4.", ""),
    ("installation", "Stand the toilet up.", "The toilet is upright.", "stand the toilet up.", None, "", ""),
    ("installation", "Press the pedal a few times.", "The waste ball opens and closes.", "press the pedal again.", None, "The waste ball is the round door in the bowl.", ""),
    ("installation", "Put the new floor seal on.", "The seal lip faces down.", "put the seal on lip down.", None, "", ""),
    ("installation", "Take the towel off the tank hole.", "The hole is open.", "take the towel off.", None, "", ""),
    ("installation", "Set the toilet on the floor bolts.", "The holes line up on the bolts.", "set the toilet on the bolts.", None, "", ""),
    ("installation", "Tighten the nuts until the toilet is still.", "The toilet does not rock.", "tighten the nuts a little more.", None, "", "Do not make the nuts too tight."),
    ("installation", "Put the bolt covers back on.", "The covers are on.", "press the covers on.", None, "", ""),
    ("installation", "Push the water hose onto the toilet.", "The hose is on tight.", "push the hose on again.", None, "", ""),
    ("installation", "Turn the RV water on.", "Water is on.", "turn the water on.", None, "", ""),
    ("installation", "Flush the toilet one time.", "No water leaks out.", "tighten the wet joint.", None, "", ""),
)
_BREAKER_PLAIN = (
    ("removal", "Turn off the water to the RV.", "No water comes out.", "turn the water off.", None, "", ""),
    ("removal", "Flush the toilet one time.", "The bowl water goes down.", "flush it one more time.", None, "", ""),
    ("removal", "Take the outer cover off.", "The cover is off.", "pull the cover off.", None, "Do this only if your toilet has a cover.", ""),
    ("removal", "Put a towel under the water hose.", "The towel is under the hose.", "move the towel under the hose.", None, "", ""),
    ("removal", "Pull the water hose off the toilet.", "The hose is off the toilet.", "pull the hose off.", None, "", ""),
    ("removal", "Take off the bolt covers.", "The bolts are bare.", "pull the covers off.", None, "Bolts hold the toilet to the floor.", ""),
    ("removal", "Lift the toilet off the floor.", "The toilet is off the floor.", "lift the toilet again.", None, "", ""),
    ("removal", "Cover the tank hole with a towel.", "The hole is covered.", "cover the hole.", None, "", ""),
    ("removal", "Pull off the old floor seal.", "The old seal is off.", "pull the old seal off.", None, "", ""),
    ("removal", "Throw the old seal away.", "The old seal is in the trash.", "throw the old seal away.", None, "", ""),
    ("removal", "Take the pod off.", "The pod is off.", "pull the pod off.", None, "The pod is the small cover on this model.", ""),
    ("removal", "Slide clamp A down the inlet tube.", "Clamp A is lower on the tube.", "slide clamp A down.", 1, "A clamp is a ring that holds a hose. See figure 1.", ""),
    ("removal", "Pull the inlet tube off the breaker.", "The tube is off the breaker.", "pull the tube off.", 1, "The vacuum breaker stops waste water going back. See figure 1.", ""),
    ("removal", "Slide clamp C back on the flush hose.", "Clamp C is back on the hose.", "slide clamp C back.", 1, "See figure 1.", ""),
    ("removal", "Pull the vacuum breaker off the hose.", "The breaker is off the hose.", "pull the breaker off.", 1, "See figure 1.", ""),
    ("removal", "Throw the old breaker away.", "The old breaker is in the trash.", "throw the old breaker away.", None, "", ""),
    ("removal", "Throw the old clamps away.", "The old clamps are in the trash.", "throw the old clamps away.", None, "", ""),
    ("installation", "Put the new flush hose on the nozzle.", "The hose is on the nozzle.", "push the hose on.", None, "", ""),
    ("installation", "Tighten the hose with new clamp C.", "Clamp C holds the hose.", "tighten clamp C.", 1, "See figure 1.", ""),
    ("installation", "Slide new clamp B on the flush hose.", "Clamp B is on the hose.", "slide clamp B on.", 1, "See figure 1.", ""),
    ("installation", "Push the new breaker onto the hose.", "The breaker is on the hose.", "push the breaker on.", 1, "See figure 1.", ""),
    ("installation", "Tighten the breaker with new clamp B.", "Clamp B holds the breaker.", "tighten clamp B.", 1, "See figure 1.", ""),
    ("installation", "Slide new clamp A on the inlet tube.", "Clamp A is on the tube.", "slide clamp A on.", 1, "See figure 1.", ""),
    ("installation", "Push the inlet tube on the breaker.", "The tube is on the breaker.", "push the tube on.", 1, "See figure 1.", ""),
    ("installation", "Tighten the tube with new clamp A.", "Clamp A holds the tube.", "tighten clamp A.", 1, "See figure 1.", ""),
    ("installation", "Put the pod back on.", "The pod is on.", "push the pod on.", None, "Skip this if you did not take a pod off.", ""),
    ("installation", "Put the new floor seal on.", "The seal lip faces down.", "put the seal on lip down.", None, "", ""),
    ("installation", "Take the towel off the tank hole.", "The hole is open.", "take the towel off.", None, "", ""),
    ("installation", "Set the toilet on the floor bolts.", "The holes line up on the bolts.", "set the toilet on the bolts.", None, "", ""),
    ("installation", "Tighten the nuts until the toilet is still.", "The toilet does not rock.", "tighten the nuts a little more.", None, "", "Do not make the nuts too tight."),
    ("installation", "Put the bolt covers back on.", "The covers are on.", "press the covers on.", None, "", ""),
    ("installation", "Push the water hose onto the toilet.", "The hose is on tight.", "push the hose on again.", None, "", ""),
    ("installation", "Turn the RV water on.", "Water is on.", "turn the water on.", None, "", ""),
    ("installation", "Flush the toilet one time.", "No water leaks out.", "tighten the wet joint.", None, "", ""),
)
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
    """Every sentence a tech reads for one step, each meant to stand alone."""
    lines = [step.get("text") or ""]
    if step.get("explain"):
        lines.append(step["explain"])
    lines.append(f"You should see: {step.get('see') or ''}".strip())
    lines.append(YES_LINE)
    lines.append(f"No, {step.get('no') or ''}".strip())
    if step.get("caution"):
        lines.append(step["caution"])
    return [line.strip() for line in lines if line.strip()]


def readability_problems(step: dict) -> list[str]:
    """Grade-4 bar: short sentences, one action, and a yes/no check."""
    problems = []
    blob = " ".join(step_sentences(step))
    if _AND_THEN_RE.search(blob):
        problems.append("two actions joined by and then")
    if not (step.get("see") or "").strip() or not (step.get("no") or "").strip():
        problems.append("missing yes/no check")
    for sentence in step_sentences(step):
        count = _word_count(sentence)
        if count > 15:
            problems.append(f"{count} words: {sentence}")
    return problems


def _plain_row(row) -> dict:
    section, text, see, no, fig, explain, caution = row
    return {
        "section": section,
        "text": text,
        "see": see,
        "no": no,
        "fig": fig,
        "explain": explain,
        "caution": caution,
        "figure": None,
    }


def plain_steps(kind: str) -> list[dict]:
    rows = _VALVE_PLAIN if kind == "valve" else _BREAKER_PLAIN if kind == "breaker" else ()
    return [_plain_row(row) for row in rows]


def format_one_step(step: dict, number: int, total: int) -> str:
    """One GD turn: the action, the check, and a photo ask."""
    lines = [
        "Here is the repair procedure.",
        f"Step {number} of {total}.",
        step.get("text") or "",
    ]
    if step.get("explain"):
        lines.append(step["explain"])
    lines.append(f"You should see: {step.get('see') or ''}".strip())
    lines.append(YES_LINE)
    lines.append(f"No, {step.get('no') or ''}".strip())
    if step.get("caution"):
        lines.append(f"Caution: {step['caution']}")
    lines.append(PHOTO_STEP)
    figure = step.get("figure")
    label = ""
    if isinstance(figure, dict):
        label = figure.get("label") or ""
    elif figure is not None:
        label = getattr(figure, "caption", "") or ""
    if label:
        lines.append(label)
    return "\n".join(line for line in lines if line).strip()


def _figures_by_number(figures: list) -> dict:
    found = {}
    for figure in figures or []:
        label = figure.get("label") if isinstance(figure, dict) else getattr(figure, "caption", "")
        for number in _figure_numbers(label or ""):
            found.setdefault(number, figure)
    return found


def _kit_paths(kind: str):
    root = Path(__file__).resolve().parent / "tests" / "fixtures"
    if kind == "valve":
        return (
            root / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf",
            "Water valve 42049 / kit 42109",
            "Thetford Water Valve Kit 42109",
        )
    if kind == "breaker":
        return (
            root / "34123-34122-VacBrkr-1.pdf",
            "Vacuum breaker 34122 / kit 34123",
            "Thetford Vacuum Breaker Kit 34123/34122",
        )
    return None


def thetford_kit_layout(kind: str, figures: list | None = None) -> dict:
    """Short Thetford R&R. Figures come from the kit sheet, never a made-up picture."""
    paths = _kit_paths(kind)
    if not paths:
        return {}
    _path, title, doc = paths
    if figures is None and _path.is_file():
        indexed = index_pdf_bytes(_path.read_bytes())
        figures = [
            {
                "label": fig["label"],
                "png": fig["png"],
                "page": fig["page"],
                "title": doc,
            }
            for fig in indexed["figures"]
        ]
    by_number = _figures_by_number(figures or [])
    steps = plain_steps(kind)
    if not steps:
        return {}
    for step in steps:
        number = step.get("fig")
        step["figure"] = by_number.get(number) if number else None
    removal = [step for step in steps if step["section"] == "removal"]
    installation = [step for step in steps if step["section"] == "installation"]
    return {
        "title": title,
        "doc": doc,
        "before": list(_PLAIN_BEFORE),
        "removal": removal,
        "installation": installation,
        "steps": steps,
        "spec": "Torque is not stated in this sheet.",
    }


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
        lines.append(f"{index}. {step.get('text') or ''}")
        for sentence in step_sentences(step)[1:]:
            lines.append(sentence)
    if layout.get("spec"):
        lines.append(layout["spec"])
    return "\n".join(lines).strip()


def _is_english_line(line: str) -> bool:
    if _FOREIGN_LINE_RE.search(line):
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return False
    odd = sum(1 for ch in letters if ord(ch) > 127)
    return odd / len(letters) < 0.08


def _manual_lines(text: str) -> list[str]:
    """English sheet lines, with wrapped Fig. numbers and sentences rejoined."""
    raw_lines = []
    for raw in re.split(r"[\r\n]+", text or ""):
        line = re.sub(r"\s+", " ", raw).strip(" \t•■▪●*")
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
    return lines


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
    if re.search(
        r"\b(?:placez|soulevez|débranchez|debranchez|remontez|ouvrez|retirez|"
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
            if name == "before beginning":
                section = "before"
                bucket = None
            elif name.startswith("remove"):
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
            if not _is_english_line(line):
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
