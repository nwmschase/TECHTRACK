"""
Bay procedure PDF — printable diagnostic checks from this shop's Document Library.

Product (Chase-locked):
  Tech enters a customer concern (+ optional brand / model / category / WO#).
  Retrieve with the same Document Library stack Guided Diagnostics uses (no live web).
  Compile a printable PDF: header + ordered checks / written flowchart language
  + cited library figures when available + optional blank Concern/Cause/Correction.
  Nav/button label is always "Bay procedure PDF" — never "AI report".
  Do not auto-write a warranty story. Leave the 3C block blank when included.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
import re
import textwrap

from gd_library_coach import (
    AC_PRODUCT_LOCK,
    COOKTOP_PRODUCT_LOCK,
    FACR_FREEZE_SEARCH_BOOST,
    FCR_E2_FAN_FAULT_PRODUCT_LOCK,
    FIREFLY_CAN_SEARCH_BOOST,
    ICE_MOISTURE_PRODUCT_LOCK,
    ICE_MOISTURE_SEARCH_BOOST,
    ICE_MOISTURE_SHOP_LINE,
    LEVEL_UP_PRODUCT_LOCK,
    PSX1_PRODUCT_LOCK,
    WATER_HEATER_PRODUCT_LOCK,
    ac_search_symptom,
    cooktop_search_symptom,
    ice_moisture_search_symptom,
    is_air_conditioning_context,
    is_cooktop_pan_on_flameout_context,
    is_facr_rooftop_freeze_context,
    is_fcr_e2_fan_fault_context,
    is_firefly_can_path_context,
    is_fridge_ice_moisture_context,
    is_furrion_ccd_0008122,
    is_level_up_advantage_context,
    is_stabilizer_override_pin_context,
    is_water_heater_context,
    level_up_search_symptom,
    page_has_figure_or_terminal_layout,
    rank_chunks_for_ac,
    rank_chunks_for_cooktop_pan_on,
    rank_chunks_for_fcr_fan_fault,
    rank_chunks_for_ice_moisture,
    rank_chunks_for_level_up,
    rank_chunks_for_stabilizer_override,
    rank_chunks_for_water_heater,
    stabilizer_search_symptom,
    water_heater_search_symptom,
)

BAY_PROCEDURE_LABEL = "Bay procedure PDF"

# Written flowchart language for known product paths (library-backed, not live web).
ICE_MOISTURE_CHECKS = (
    (
        "Note the rear/back-wall ice or frost pattern (including half from the top). "
        "This is Ice and Moisture → Ice or Moisture in the Fridge — not a no-power fuse / 12V tree.",
        "Furrion FCR08/FCR10 SM CCD-0008122",
        36,
    ),
    (
        "Check whether the temperature dial is at max. If it is, back it off and recheck the frost pattern.",
        "Furrion FCR08/FCR10 SM CCD-0008122",
        36,
    ),
    (
        "Inspect the door gasket / seal for leaks that let moisture in. Repair or reseat before condemning the cooling unit.",
        "Furrion FCR08/FCR10 SM CCD-0008122",
        36,
    ),
    (
        "Verify cooling performance from the Ice and Moisture page. Watch / replace only from that section "
        "(CCD-0008122 p.36 / Fig.36).",
        "Furrion FCR08/FCR10 SM CCD-0008122",
        36,
    ),
)

FIREFLY_CAN_CHECKS = (
    (
        "Confirm Manual Mode dump works. If dump works, hydraulics / pump / valves are proven — "
        "do not start at pump or valve R&R.",
        "Firefly CAN / Level-Up Manual Mode path",
        None,
    ),
    (
        "Confirm Auto works. If Auto works, the controller and sensors are good enough to run Auto — "
        "the remaining path is Firefly CAN, not a dead leveling controller.",
        "Firefly CAN / Level-Up Manual Mode path",
        None,
    ),
    (
        "CAN isolate: disconnect Firefly / CAN modules one at a time (slides, jacks, panels) and retest "
        "Manual Mode / Auto after each isolate. A recovered network names the dropped module.",
        "Firefly CAN / Level-Up Manual Mode path",
        None,
    ),
    (
        "Check CAN terminators. Measure terminator resistance (~120 ohm) at each end of the bus. "
        "Look for a missing terminator, an extra terminator, or damaged CAN wiring.",
        "Firefly CAN / Level-Up Manual Mode path",
        None,
    ),
)

FIG_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d+", re.I)


@dataclass
class BayCheck:
    text: str
    source_title: str = ""
    source_page: int | None = None
    kind: str = "check"  # check | figure | note


@dataclass
class BayFigure:
    title: str
    page: int | None = None
    caption: str = ""
    excerpt: str = ""
    image_png: bytes | None = None


@dataclass
class BayProcedure:
    concern: str
    brand: str = ""
    model: str = ""
    category: str = ""
    wo_number: str = ""
    created: datetime = field(default_factory=datetime.now)
    sources: list[dict] = field(default_factory=list)
    checks: list[BayCheck] = field(default_factory=list)
    figures: list[BayFigure] = field(default_factory=list)
    include_3c: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def model_line(self) -> str:
        parts = [p for p in (self.brand.strip(), self.model.strip()) if p]
        return " ".join(parts) or "—"


def model_text_from(brand: str = "", model: str = "") -> str:
    return " ".join(p for p in ((brand or "").strip(), (model or "").strip()) if p)


def chunk_as_dict(ch) -> dict:
    """Normalize a DocChunk or dict used by ranking helpers."""
    if isinstance(ch, dict):
        excerpt = ch.get("excerpt") or ch.get("chunk_text") or ""
        return {
            "title": ch.get("title") or "",
            "page": ch.get("page"),
            "excerpt": excerpt,
            "chunk_text": excerpt,
            "file_path": ch.get("file_path"),
            "category": ch.get("category") or ch.get("category_name") or "",
            "document_id": ch.get("document_id"),
        }
    excerpt = getattr(ch, "chunk_text", "") or getattr(ch, "excerpt", "") or ""
    return {
        "title": getattr(ch, "title", "") or "",
        "page": getattr(ch, "page", None),
        "excerpt": excerpt,
        "chunk_text": excerpt,
        "file_path": getattr(ch, "file_path", None),
        "category": getattr(ch, "category", "") or getattr(ch, "category_name", "") or "",
        "document_id": getattr(ch, "document_id", None),
    }


def rewrite_bay_search_symptom(
    category_name: str = "",
    model_text: str = "",
    concern: str = "",
) -> str:
    """Same search-boost chain GD chat uses (Document Library only — no live web)."""
    symptom = (concern or "").strip()
    if not symptom:
        return symptom
    ice = is_fridge_ice_moisture_context(category_name, model_text, symptom)
    if ice:
        symptom = ice_moisture_search_symptom(category_name, model_text, symptom)
        if ICE_MOISTURE_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {ICE_MOISTURE_SEARCH_BOOST}".strip()
    symptom = level_up_search_symptom(category_name, model_text, symptom)
    if is_firefly_can_path_context(category_name, model_text, symptom):
        if FIREFLY_CAN_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {FIREFLY_CAN_SEARCH_BOOST}".strip()
    symptom = ac_search_symptom(category_name, model_text, symptom)
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        if FACR_FREEZE_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {FACR_FREEZE_SEARCH_BOOST}".strip()
    symptom = water_heater_search_symptom(category_name, model_text, symptom)
    symptom = cooktop_search_symptom(category_name, model_text, symptom)
    symptom = stabilizer_search_symptom(category_name, model_text, symptom)
    return symptom


def rank_bay_chunks(
    chunks,
    category_name: str = "",
    model_text: str = "",
    concern: str = "",
    limit: int = 8,
) -> list:
    """Apply the same product ranking GD uses."""
    pages = [chunk_as_dict(ch) for ch in (chunks or [])]
    query = f"{model_text or ''} {concern or ''}".strip()
    if is_fridge_ice_moisture_context(category_name, model_text, concern):
        return rank_chunks_for_ice_moisture(pages, query, limit=limit)
    if is_firefly_can_path_context(category_name, model_text, concern) or is_level_up_advantage_context(
        category_name, model_text, concern
    ):
        return rank_chunks_for_level_up(pages, query, limit=limit)
    if is_fcr_e2_fan_fault_context(category_name, model_text, concern):
        return rank_chunks_for_fcr_fan_fault(pages, query, limit=limit)
    if is_air_conditioning_context(category_name, model_text, concern):
        return rank_chunks_for_ac(pages, query, limit=limit)
    if is_water_heater_context(category_name, model_text, concern):
        return rank_chunks_for_water_heater(pages, query, limit=limit)
    if is_cooktop_pan_on_flameout_context(category_name, model_text, concern):
        return rank_chunks_for_cooktop_pan_on(pages, query, limit=limit)
    if is_stabilizer_override_pin_context(category_name, model_text, concern):
        return rank_chunks_for_stabilizer_override(pages, query, limit=limit)
    return pages[:limit]


def _page_int(value):
    try:
        n = int(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def pick_cited_figures(chunks, limit: int = 4) -> list[BayFigure]:
    """Figures from retrieved library pages (Fig. / diagram language), not the live web."""
    out = []
    seen = set()
    for ch in chunks or []:
        d = chunk_as_dict(ch)
        excerpt = d.get("excerpt") or ""
        title = (d.get("title") or "Shop library").strip()
        page = _page_int(d.get("page"))
        key = (title.lower(), page)
        if key in seen:
            continue
        fig_hit = FIG_RE.search(excerpt) or page_has_figure_or_terminal_layout(excerpt)
        if not fig_hit:
            continue
        seen.add(key)
        cap = fig_hit.group(0) if hasattr(fig_hit, "group") else "Library figure"
        out.append(
            BayFigure(
                title=title,
                page=page,
                caption=cap,
                excerpt=excerpt[:500],
                image_png=d.get("image_png"),
            )
        )
        if len(out) >= limit:
            break
    return out


def _unique_sources(chunks) -> list[dict]:
    out = []
    seen = set()
    for ch in chunks or []:
        d = chunk_as_dict(ch)
        title = (d.get("title") or "").strip() or "Shop library"
        page = _page_int(d.get("page"))
        key = (title.lower(), page)
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "page": page, "excerpt": (d.get("excerpt") or "")[:400]})
    return out


def _excerpt_check(d: dict) -> BayCheck | None:
    excerpt = re.sub(r"\s+", " ", (d.get("excerpt") or "").strip())
    if len(excerpt) < 40:
        return None
    # Keep written-flowchart language; drop raw INDEX dump tails.
    sentence = excerpt.split(". ")
    text = ". ".join(sentence[:2]).strip()
    if text and not text.endswith("."):
        text += "."
    if len(text) > 420:
        text = text[:417].rstrip() + "..."
    return BayCheck(
        text=text,
        source_title=(d.get("title") or "").strip(),
        source_page=_page_int(d.get("page")),
        kind="check",
    )


def _lock_note(category_name: str, model_text: str, concern: str) -> list[str]:
    notes = []
    if is_fridge_ice_moisture_context(category_name, model_text, concern):
        notes.append(ICE_MOISTURE_PRODUCT_LOCK.strip().splitlines()[0])
    if is_firefly_can_path_context(category_name, model_text, concern) or is_level_up_advantage_context(
        category_name, model_text, concern
    ):
        notes.append("Level-Up Manual Mode → Firefly CAN isolate / terminator (not Unity board SM).")
    if is_facr_rooftop_freeze_context(category_name, model_text, concern):
        notes.append("FACR rooftop freeze/condensate → CCD-0007990 with CCD-0008666.")
    if is_fcr_e2_fan_fault_context(category_name, model_text, concern):
        notes.append(FCR_E2_FAN_FAULT_PRODUCT_LOCK.strip().splitlines()[0])
    if is_air_conditioning_context(category_name, model_text, concern) and not is_facr_rooftop_freeze_context(
        category_name, model_text, concern
    ):
        notes.append(AC_PRODUCT_LOCK.strip().splitlines()[0])
    if is_water_heater_context(category_name, model_text, concern):
        notes.append(WATER_HEATER_PRODUCT_LOCK.strip().splitlines()[0])
    if is_cooktop_pan_on_flameout_context(category_name, model_text, concern):
        notes.append(COOKTOP_PRODUCT_LOCK.strip().splitlines()[0])
    if is_stabilizer_override_pin_context(category_name, model_text, concern):
        notes.append(PSX1_PRODUCT_LOCK.strip().splitlines()[0])
    if is_level_up_advantage_context(category_name, model_text, concern):
        notes.append(LEVEL_UP_PRODUCT_LOCK.strip().splitlines()[0])
    return notes


def compile_bay_procedure(
    concern: str,
    brand: str = "",
    model: str = "",
    category: str = "",
    wo_number: str = "",
    chunks=None,
    figures: list[BayFigure] | None = None,
    include_3c: bool = True,
    created: datetime | None = None,
) -> BayProcedure:
    """
    Compile ordered bay checks from product-lock language + ranked library excerpts.

    Works with or without live chunks so unit tests do not need a shop DB.
    """
    concern = (concern or "").strip()
    brand = (brand or "").strip()
    model = (model or "").strip()
    category = (category or "").strip()
    if category in ("(any)", "-"):
        category = ""
    model_text = model_text_from(brand, model)
    ranked = rank_bay_chunks(chunks, category, model_text, concern, limit=8)
    sources = _unique_sources(ranked)
    checks: list[BayCheck] = []

    ice = is_fridge_ice_moisture_context(category, model_text, concern)
    firefly = is_firefly_can_path_context(category, model_text, concern)

    if ice:
        for text, title, page in ICE_MOISTURE_CHECKS:
            checks.append(BayCheck(text=text, source_title=title, source_page=page))
        # Keep CCD-0008122 / Ice and Moisture on the source list even with empty library.
        if not any("ccd-0008122" in (s.get("title") or "").lower() for s in sources):
            sources.insert(
                0,
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 36,
                    "excerpt": "Ice and Moisture / Ice or Moisture in the Fridge / Fig. 36",
                },
            )
    if firefly:
        for text, title, page in FIREFLY_CAN_CHECKS:
            checks.append(BayCheck(text=text, source_title=title, source_page=page))

    used_titles_pages = {(c.source_title.lower(), c.source_page) for c in checks}
    for d in ranked:
        chk = _excerpt_check(d)
        if not chk:
            continue
        key = (chk.source_title.lower(), chk.source_page)
        if key in used_titles_pages:
            continue
        # Ice path: do not let fuse / 12V excerpts compete with p.36 language.
        if ice:
            hay = f"{chk.source_title} {chk.text}".lower()
            if any(k in hay for k in ("fuse location", "15a", "no power", "12v inverter")) and "moisture" not in hay:
                continue
            if is_furrion_ccd_0008122(chk.source_title) and chk.source_page == 36:
                used_titles_pages.add(key)
                continue
        used_titles_pages.add(key)
        checks.append(chk)
        if len(checks) >= 12:
            break

    if not checks:
        checks.append(
            BayCheck(
                text=(
                    "No matching manual excerpt was retrieved. Re-check category / model keywords, "
                    "or ask a manager to index the service manual in Document Library. "
                    "Do not invent OEM steps from the live web."
                ),
                source_title="Document Library",
                kind="note",
            )
        )

    figs = list(figures or [])
    if not figs:
        figs = pick_cited_figures(ranked)

    return BayProcedure(
        concern=concern or "(no concern entered)",
        brand=brand,
        model=model,
        category=category,
        wo_number=(wo_number or "").strip(),
        created=created or datetime.now(),
        sources=sources,
        checks=checks,
        figures=figs,
        include_3c=include_3c,
        notes=_lock_note(category, model_text, concern),
    )


def procedure_plain_text(proc: BayProcedure) -> str:
    """Single string for unit tests and PDF fallback."""
    lines = [
        BAY_PROCEDURE_LABEL,
        f"Customer concern: {proc.concern}",
        f"Brand / model: {proc.model_line}",
        f"Category: {proc.category or '—'}",
        f"Work order: {proc.wo_number or '—'}",
        f"Date: {proc.created.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Sources (shop Document Library):",
    ]
    if proc.sources:
        for s in proc.sources:
            page = f" p.{s['page']}" if s.get("page") else ""
            lines.append(f"- {s.get('title') or 'Manual'}{page}")
    else:
        lines.append("- (no indexed excerpt retrieved this pass)")
    lines.append("")
    lines.append("Diagnostic checks (written flowchart language):")
    for i, chk in enumerate(proc.checks, 1):
        cite = ""
        if chk.source_title:
            page = f" - page {chk.source_page}" if chk.source_page else ""
            cite = f" Source: {chk.source_title}{page}."
        lines.append(f"{i}. {chk.text}{cite}")
    if proc.figures:
        lines.append("")
        lines.append("Cited library figures:")
        for fig in proc.figures:
            page = f" p.{fig.page}" if fig.page else ""
            lines.append(f"- {fig.caption or 'Figure'} — {fig.title}{page}")
            if fig.excerpt:
                lines.append(f"  {fig.excerpt[:240]}")
    if proc.include_3c:
        lines.extend(
            [
                "",
                "Concern / Cause / Correction (blank — tech writes the warranty story):",
                "CONCERN:",
                "",
                "",
                "CAUSE:",
                "",
                "",
                "CORRECTION:",
                "",
                "",
            ]
        )
    if proc.notes:
        lines.append("")
        lines.append("Path notes:")
        lines.extend(f"- {n}" for n in proc.notes)
    # Always keep Ice/Moisture shop line discoverable on ice jobs.
    blob = f"{proc.concern} {proc.model_line} {proc.category}"
    if is_fridge_ice_moisture_context(proc.category, proc.model_line, proc.concern):
        if "ice and moisture" not in "\n".join(lines).lower():
            lines.append(ICE_MOISTURE_SHOP_LINE)
        if "ccd-0008122" not in "\n".join(lines).lower():
            lines.append("Cite CCD-0008122 Ice and Moisture p.36 / Fig.36.")
    _ = blob
    return "\n".join(lines).strip() + "\n"


def suggested_pdf_filename(proc: BayProcedure) -> str:
    wo = re.sub(r"[^A-Za-z0-9_-]+", "", (proc.wo_number or "").replace(" ", "-"))
    if wo:
        return f"bay_procedure_{wo}.pdf"
    return "bay_procedure.pdf"


def _latin1_safe(text: str) -> str:
    """PDF core fonts are Latin-1. Drop emoji / smart punctuation."""
    if not text:
        return ""
    repl = {
        "📖": "Source:",
        "→": "->",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "×": "x",
        "≈": "~",
        "≥": ">=",
        "≤": "<=",
        "ohm": "ohm",
    }
    out = text
    for a, b in repl.items():
        out = out.replace(a, b)
    return out.encode("latin-1", "replace").decode("latin-1")


def _render_pdf_fpdf2(proc: BayProcedure) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    def write(text, *, size=11, bold=False, italic=False, color=(0, 0, 0), h=5):
        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(*color)
        style = ""
        if bold:
            style += "B"
        if italic:
            style += "I"
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(pdf.epw, h, _latin1_safe(text or ""))

    write(BAY_PROCEDURE_LABEL, size=16, bold=True, color=(1, 20, 124), h=8)
    write(
        "Tacoma RV Center  |  shop Document Library  |  not live web",
        size=10,
        color=(3, 137, 68),
    )
    pdf.ln(2)

    header = [
        ("Customer concern", proc.concern),
        ("Brand / model", proc.model_line),
        ("Category", proc.category or "-"),
        ("Work order", proc.wo_number or "-"),
        ("Date", proc.created.strftime("%Y-%m-%d")),
    ]
    for label, value in header:
        write(f"{label}:", size=10, bold=True)
        write(value or "-", size=11)
        pdf.ln(1)

    write("Sources (shop Document Library)", size=12, bold=True, h=6)
    if proc.sources:
        for s in proc.sources:
            page = f" p.{s['page']}" if s.get("page") else ""
            write(f"- {s.get('title') or 'Manual'}{page}", size=10)
    else:
        write("- (no indexed excerpt retrieved this pass)", size=10)
    pdf.ln(2)

    write("Diagnostic checks", size=12, bold=True, h=6)
    for i, chk in enumerate(proc.checks, 1):
        cite = ""
        if chk.source_title:
            page = f" - page {chk.source_page}" if chk.source_page else ""
            cite = f"  Source: {chk.source_title}{page}"
        write(f"{i}. {chk.text}{cite}", size=11)
        pdf.ln(1)

    if proc.figures:
        write("Cited library figures", size=12, bold=True, h=6)
        for fig in proc.figures:
            page = f" p.{fig.page}" if fig.page else ""
            write(f"- {fig.caption or 'Figure'} -- {fig.title}{page}", size=10)
            if fig.excerpt:
                write(fig.excerpt[:360], size=10)
            if fig.image_png:
                try:
                    pdf.set_x(pdf.l_margin)
                    pdf.image(BytesIO(fig.image_png), w=min(170, pdf.epw))
                    pdf.ln(2)
                except Exception:
                    pass
            pdf.ln(1)

    if proc.include_3c:
        box_h = 16
        if pdf.get_y() + 78 > pdf.h - 14:
            pdf.add_page()
        pdf.set_auto_page_break(auto=False)
        pdf.ln(2)
        write("Concern / Cause / Correction", size=12, bold=True, h=6)
        write(
            "Blank on purpose. TechTrack does not write the warranty story from this PDF.",
            size=9,
            italic=True,
        )
        for label in ("CONCERN", "CAUSE", "CORRECTION"):
            if pdf.get_y() + box_h + 10 > pdf.h - 12:
                pdf.add_page()
            pdf.ln(1)
            write(f"{label}:", size=11, bold=True)
            pdf.set_x(pdf.l_margin)
            y = pdf.get_y()
            pdf.set_draw_color(160, 160, 160)
            pdf.rect(pdf.l_margin, y, pdf.epw, box_h)
            pdf.set_xy(pdf.l_margin, y + box_h + 2)
        pdf.set_auto_page_break(auto=True, margin=16)

    raw = pdf.output()
    return bytes(raw) if not isinstance(raw, (bytes, bytearray)) else bytes(raw)


def _escape_pdf(text: str) -> str:
    return _latin1_safe(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf_minimal(proc: BayProcedure) -> bytes:
    """Tiny PDF 1.4 writer so tests stay green without extra deps."""
    width, height = 612, 792
    margin = 48
    lines = []
    for raw in procedure_plain_text(proc).splitlines():
        wrapped = textwrap.wrap(_latin1_safe(raw), width=92) or [""]
        lines.extend(wrapped)
    pages = []
    per_page = 52
    for i in range(0, max(len(lines), 1), per_page):
        pages.append(lines[i : i + per_page])

    content_objs = []
    for page_lines in pages:
        y = height - margin
        cmds = ["BT", "/F1 10 Tf", "14 TL"]
        first = True
        for line in page_lines:
            safe = _escape_pdf(line)
            if first:
                cmds.append(f"1 0 0 1 {margin} {y} Tm ({safe}) Tj")
                first = False
            else:
                cmds.append("T*")
                cmds.append(f"({safe}) Tj")
        cmds.append("ET")
        stream = "\n".join(cmds).encode("latin-1", "replace")
        content_objs.append(stream)

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    font_id = 3 + len(pages) * 2
    for i, _page in enumerate(pages):
        content_id = 3 + len(pages) + i
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("ascii")
        )
    for stream in content_objs:
        objs.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)


def render_bay_procedure_pdf(proc: BayProcedure) -> bytes:
    """Return non-empty PDF bytes. Prefer fpdf2; fall back to a minimal writer."""
    try:
        data = _render_pdf_fpdf2(proc)
        if data and data.startswith(b"%PDF") and len(data) > 80:
            return data
    except Exception:
        pass
    data = _render_pdf_minimal(proc)
    if not data or not data.startswith(b"%PDF"):
        raise RuntimeError("Bay procedure PDF renderer produced empty output")
    return data
