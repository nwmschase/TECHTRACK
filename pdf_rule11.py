"""Rule 11 PDF builder (Chase via Leader 2026-10-16 2:29 PM PT).

The Bay PDF / shop sheet uses the SAME pipeline as Guided Diagnostics:
  1. identify the exact unit        -> gd_official.identify_unit
  2. get the official manual        -> gd_official.pin_document (library), then
                                       gd_official.fetch_official_manual (OEM site)
  3. read the full troubleshooting  -> gd_official.load_section (+ the rest of the
     section                           manual for removal / installation pages)
  4. the manual's real steps, one action per step, each with probe point,
     switch state and good/bad reading (strict validator below)
  5. that manual's own figure under the step (manual_figures crops of the pinned PDF)
  6. source label on every step (gd_official LABEL_* names)

Hard stops: unit not identified / no manual -> NoManual (no sheet).
Zero figures placed -> NoFigures (no sheet). Any filler string, missing
probe/state/reading or multi-action step -> StepRuleError (no sheet).
GD functions are imported, never copied.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

import gd_official as go

RULE11_REVISION = "pdf-rule11-1"

# Strings from the rejected batch sheets (B11/B13/B24/B34/B36/B40/B56) and the
# generic page-1 flowchart. None may appear anywhere on a rule-11 sheet.
FILLER_PHRASES = (
    "at the part named in this step",
    "the step is done as the cited page says",
    "stay on this step until it passes",
    "stay on that check until it passes",
    "did the first check pass",
    "go to the next step on this sheet",
    "is the complaint gone",
    "that is the confirmed correction",
    "work this as a full appliance path",
    "write pass or fail and the next step after every check",
    "thresholds and pass or fail meaning stay on this page",
    "as the manual says",
    "per the cited page",
    "unconfirmed",
    "not stated in this sheet",
    "see doc.",
)
FILLER_RE = re.compile("|".join(re.escape(p) for p in FILLER_PHRASES), re.I)

# Two actions joined in one step: "Remove X and pull Y", "Do X, then Y", "X; Y".
ACTION_VERBS = (
    "add adjust apply attach check clean close connect cut disconnect drain fill find fit "
    "feed feel follow install insert inspect jumper label lift listen look loosen lower "
    "measure mark move note open operate place plug probe pull push put read reconnect "
    "record refit reinstall remove repair replace reseat reset restore route run seat "
    "set slide start straighten switch tape test tighten touch turn unplug verify wait "
    "watch wrap write"
).split()
_VERB_ALT = "|".join(ACTION_VERBS)
MULTI_ACTION_RE = re.compile(
    rf"(;|\bthen\b|,\s*(?:and\s+)?(?:{_VERB_ALT})\b|\band\s+(?:then\s+)?(?:{_VERB_ALT})\b)",
    re.I,
)
MAX_ACTION_WORDS = 16
FIGURE_PAGE_SLACK = 1  # the figure sits on the step's manual page or the next/previous one


class NoManual(Exception):
    """Unit not identified exactly, or no official manual found: stop, no sheet."""


class NoFigures(Exception):
    """Zero manual figures placed under steps: hard fail, no sheet."""


class StepRuleError(Exception):
    """A step breaks rule 11 (filler, missing probe/state/reading, several actions)."""


@dataclass
class Step:
    action: str
    probe: str = ""
    state: str = ""
    good: str = ""
    bad: str = ""
    next: str = ""
    page: int | None = None
    figure: str | None = None  # figure id from the pinned manual's index
    source: str = "manual"  # manual | general
    kind: str = "step"  # step | note (notes are never numbered)

    @classmethod
    def from_dict(cls, d: dict) -> "Step":
        keys = cls.__dataclass_fields__
        return cls(**{k: d.get(k) for k in keys if d.get(k) is not None})


@dataclass
class Sheet:
    case: str
    concern: str
    unit: dict
    manual: dict
    diagnosis: list = field(default_factory=list)
    branches: list = field(default_factory=list)  # [{title, before:[..], steps:[Step]}]
    do_not: list = field(default_factory=list)
    flow: list = field(default_factory=list)  # [{q, yes, no}]
    figures: dict = field(default_factory=dict)  # id -> {png, page, label}


# ---------------- 1+2: unit and manual (shared with GD) ----------------
class _RecordingHttp:
    """Wraps the http client given to gd_official.fetch_official_manual so the
    builder keeps the PDF bytes (GD only needs the text)."""

    def __init__(self, http):
        self.http = http
        self.pdf_bytes = b""
        self.pdf_url = ""

    def post(self, *a, **k):
        return self.http.post(*a, **k)

    def get(self, url, *a, **k):
        r = self.http.get(url, *a, **k)
        data = getattr(r, "content", b"") or b""
        if data[:5] == b"%PDF-":
            self.pdf_bytes, self.pdf_url = data, str(getattr(r, "url", url))
        return r


def find_manual(model_text: str, concern: str, category: str, library, *,
                pdf_for_doc=None, api_key: str = "", http=None, web=True) -> dict:
    """Same order as GD: exact unit, library pin, then the OEM site.

    pdf_for_doc(doc) -> bytes|None gives the pinned library document's PDF
    (figures need the file, not only the chunks). A library pin whose file is
    not reachable is skipped like a missing document.
    """
    unit = go.identify_unit([], concern, category, model_text)
    if not unit.get("identified"):
        raise NoManual("Exact unit not identified (" + (model_text or "no model") + "). "
                       + go.unit_question(unit).split("\n", 1)[-1])
    tried = []
    exclude = []
    while True:
        doc = go.pin_document(library, unit, exclude_ids=tuple(exclude))
        if not doc:
            break
        tried.append(doc.get("title", ""))
        data = pdf_for_doc(doc) if pdf_for_doc else None
        chunks = library.chunks(doc["id"])
        if data and chunks:
            return {"unit": unit, "origin": "library", "doc": doc, "title": doc.get("title", ""),
                    "label": go.LABEL_LIBRARY, "chunks": chunks, "pdf": data, "url": "", "tried": tried}
        exclude.append(doc["id"])
    if web and api_key:
        rec = _RecordingHttp(http or __import__("httpx"))
        res = go.fetch_official_manual(unit, api_key, http=rec)
        if res.get("chunks") and rec.pdf_bytes and go.url_is_official(rec.pdf_url or res.get("url", ""), unit["brand"]):
            return {"unit": unit, "origin": "web", "doc": None, "title": res.get("title") or res.get("url"),
                    "label": go.LABEL_WEB, "chunks": res["chunks"], "pdf": rec.pdf_bytes,
                    "url": res.get("url", ""), "tried": tried, "search": res.get("search_usage", {})}
        tried.append("OEM site: " + (res.get("error") or res.get("url") or "no official manual found"))
    raise NoManual(f"No official manual found for {model_text}. Tried: " + ("; ".join(tried) or "library (no match)"))


# ---------------- 3: read the section ----------------
def read_manual(manual: dict, concern: str) -> dict:
    sec = go.load_section(manual["chunks"], concern)
    pages = {}
    for ch in manual["chunks"]:
        pages.setdefault(int(ch.get("page") or 1), []).append(ch.get("text") or "")
    rest = [p for p in sorted(pages) if p not in sec["pages"]]
    sec = dict(sec)
    sec["rest_text"] = "\n\n".join(f"[PAGE {p}]\n" + "\n".join(pages[p]) for p in rest)
    return sec


# ---------------- 5: figures from the pinned manual ----------------
def _image_block_figures(pdf_bytes: bytes, taken: dict) -> list:
    """Embedded drawings that manual_figures misses (photo figures whose caption
    sits beside or under the image, or uncaptioned step photos). Each crop keeps
    the caption line when there is one. Same pinned PDF only."""
    import pymupdf as fitz

    out = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for pno, page in enumerate(doc, 1):
            caps = []
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    t = "".join(sp["text"] for sp in ln["spans"]).strip().replace("\x03", "")
                    if re.match(r"^(Fig\.?|FIG\.?|Figure|FIGURE)\s*\d+", t):
                        caps.append((t, fitz.Rect(ln["bbox"])))
            for info in page.get_image_info():
                r = fitz.Rect(info["bbox"]) & page.rect
                if r.width < 80 or r.height < 60:
                    continue
                if any(fitz.Rect(t["bbox"]).intersects(r) for t in taken.get(pno, [])):
                    continue
                def near(c):
                    over = c[1].x1 > r.x0 - 10 and c[1].x0 < r.x1 + 10
                    if not over:
                        return None
                    if c[1].y0 >= r.y1 - 4 and c[1].y0 - r.y1 < 45:
                        return c[1].y0 - r.y1
                    if c[1].y1 <= r.y0 + 4 and r.y0 - c[1].y1 < 30:
                        return r.y0 - c[1].y1
                    if r.contains(c[1].tl):
                        return 0
                    return None
                cands = sorted((near(c), i, c) for i, c in enumerate(caps) if near(c) is not None)
                cap = cands[0][2] if cands else None
                clip = fitz.Rect(r)
                if cap:
                    clip |= cap[1]
                clip = (clip + (-4, -4, 4, 4)) & page.rect
                pix = page.get_pixmap(clip=clip, dpi=150)
                png = pix.tobytes("png")
                label = re.sub(r"\s+", " ", cap[0]).strip() if cap else "Manual figure"
                out.append({"page": pno, "label": label, "png": png, "width": pix.width, "height": pix.height,
                            "bbox": tuple(r)})
                taken.setdefault(pno, []).append({"bbox": tuple(r)})
    finally:
        doc.close()
    return out


MAX_WORDS_IN_FIGURE = 25


def _drop_text_crops(pdf_bytes: bytes, figures: list) -> list:
    """A crop that is mostly printed text (a symptom table) is not a figure."""
    import pymupdf as fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        keep = []
        for f in figures:
            page = doc[f["page"] - 1]
            words = page.get_text("words", clip=fitz.Rect(f["bbox"]))
            if len(words) <= MAX_WORDS_IN_FIGURE or page.get_images():
                if len(words) > MAX_WORDS_IN_FIGURE * 2:
                    continue
                keep.append(f)
        return keep
    finally:
        doc.close()


def manual_figures_index(pdf_bytes: bytes) -> dict:
    import manual_figures as mf

    idx = mf.index_pdf_bytes(pdf_bytes)
    idx["figures"] = _drop_text_crops(pdf_bytes, idx["figures"])
    taken = {}
    for f in idx["figures"]:
        taken.setdefault(f["page"], []).append(f)
    found = list(idx["figures"]) + _image_block_figures(pdf_bytes, taken)
    figs = {}
    for f in sorted(found, key=lambda x: (x["page"], x["bbox"][1], x["bbox"][0])):
        fid = f"p{f['page']}-{re.sub(r'[^A-Za-z0-9]+', '-', f['label'])[:40].strip('-')}"
        n, base = 2, fid
        while fid in figs:
            fid, n = f"{base}-{n}", n + 1
        figs[fid] = {"png": f["png"], "page": f["page"], "label": f["label"], "width": f["width"], "height": f["height"]}
    return figs


# ---------------- 4+6: validation ----------------
def check_action(action: str) -> list:
    errs = []
    a = (action or "").strip()
    if not a:
        return ["empty action"]
    if len(re.findall(r"[.!?](\s|$)", a)) > 1:
        errs.append("more than one sentence")
    if MULTI_ACTION_RE.search(a):
        errs.append("several actions in one step")
    if len(a.split()) > MAX_ACTION_WORDS:
        errs.append(f"over {MAX_ACTION_WORDS} words")
    return errs


def validate_steps(steps: list, where: str) -> list:
    errs = []
    for i, s in enumerate(steps, 1):
        tag = f"{where} step {i}"
        text = " ".join(str(x or "") for x in (s.action, s.probe, s.state, s.good, s.bad, s.next))
        if FILLER_RE.search(text):
            errs.append(f"{tag}: filler text '{FILLER_RE.search(text).group(0)}'")
        if s.kind == "note":
            continue
        errs += [f"{tag}: {e}" for e in check_action(s.action)]
        for name in ("probe", "state", "good", "bad"):
            if not str(getattr(s, name) or "").strip():
                errs.append(f"{tag}: missing {name}")
        if s.source == "manual" and not s.page:
            errs.append(f"{tag}: manual step without page")
    return errs


def validate_sheet(sheet: Sheet) -> dict:
    errs = validate_steps(sheet.diagnosis, "diagnosis")
    for b in sheet.branches:
        errs += validate_steps(b["steps"], b["title"])
    for line in sheet.do_not + [f.get("q", "") + f.get("yes", "") + f.get("no", "") for f in sheet.flow]:
        if FILLER_RE.search(line):
            errs.append(f"filler text in do-not/flow: {line}")
    used = [s.figure for s in all_steps(sheet) if s.figure]
    unknown = [f for f in used if f not in sheet.figures]
    if unknown:
        errs.append(f"figure ids not in the pinned manual: {unknown}")
    for s in all_steps(sheet):
        if s.figure in sheet.figures and s.page and abs(sheet.figures[s.figure]["page"] - int(s.page)) > FIGURE_PAGE_SLACK:
            errs.append(f"figure {s.figure} (page {sheet.figures[s.figure]['page']}) is not on the step's page {s.page}")
    dup = {f for f in used if used.count(f) > 1}
    if dup:
        errs.append(f"figure used twice: {sorted(dup)}")
    if errs:
        raise StepRuleError("; ".join(errs))
    placed = [f for f in used if f in sheet.figures]
    if not placed:
        raise NoFigures("Zero manual figures placed under steps. No sheet produced.")
    return {"figures": len(placed)}


def all_steps(sheet: Sheet):
    for s in sheet.diagnosis:
        yield s
    for b in sheet.branches:
        yield from b["steps"]


def source_tag(step: Step, manual: dict) -> str:
    if step.source == "general":
        return f"[{go.LABEL_GENERAL}]"
    where = manual["url"] if manual["origin"] == "web" else manual["title"]
    return f"[{manual['label']}: {where}, page {step.page}]"


# ---------------- step extraction from the section (xAI) ----------------
EXTRACT_RULES = """You write a printed shop sheet for warranty RV techs (Tacoma RV Center) from ONE official manual.
Use ONLY the manual text given. Build: a case-specific flowchart (each question with YES and NO exits that name a real step or branch),
diagnosis steps (start by verifying the complaint, end each branch with a verify step), one branch per possible repair
(removal, installation, verify), and a Do Not list.
STEP RULES (hard):
- ONE action per step: a single short imperative sentence, max 14 words. Never join actions with "and", "then", commas or semicolons.
- Every step has: probe = the exact probe point or location (terminal, plug pin, wire color, screw, part); state = the switch / power
  / valve / dial state during the step (e.g. "12 V supply OFF", "LP valve open, switch ON"); good = good reading or result
  (with the manual's number/unit when it has one); bad = bad reading or result; next = where to go on good and on bad.
- page = the manual page number the step comes from ([PAGE n] markers). source = "manual", or "general" only for a shop step the
  manual does not print (keep these few).
- figure = the id of the manual figure that shows THIS step, from the FIGURES list (its page is near the step page). Use each figure once.
  The figure page must be the step page or the page next to it, and must show the part or point the step acts on.
  Never put a figure on a step it does not show. Every branch that has matching figures in the manual gets them.
- A remark that is not an action (caution, wait explanation, "already done in diagnosis? skip") is kind "note": no number, only "action" text.
- next uses sheet labels only: "Good: go to step 4. Bad: go to Branch B." Never internal ids like D2.
- Write probe/state/good/bad/next as short plain sentences that start with a capital and end with a period.
- Never write generic filler such as "at the part named in this step" or "the step is done as the cited page says".
Reply with JSON only:
{"flow":[{"q":"","yes":"","no":""}],"diagnosis":[STEP],"branches":[{"title":"","before":[""],"steps":[STEP]}],"do_not":[""]}
STEP = {"kind":"step|note","action":"","probe":"","state":"","good":"","bad":"","next":"","page":0,"figure":null,"source":"manual|general"}"""


def _xai(messages, api_key, model="grok-4.6", http=None, timeout=420.0):
    http = http or __import__("httpx")
    for attempt in range(3):
        try:
            r = http.post("https://api.x.ai/v1/chat/completions", timeout=timeout,
                          headers={"Authorization": f"Bearer {api_key}"},
                          json={"model": model, "messages": messages, "response_format": {"type": "json_object"}})
            data = r.json()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(20)
    if "choices" not in data:
        raise RuntimeError(f"xAI error: {str(data)[:300]}")
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def extract_plan(unit, concern, manual, section, figures, api_key, *, reference="", chat=None, retries=2):
    figlist = "\n".join(f"- {fid}: page {f['page']}, {f['label']}" for fid, f in figures.items()) or "(none)"
    user = (f"UNIT: {unit.get('model')}\nCONCERN: {concern}\nMANUAL: {manual['title']}\n\n"
            f"FIGURES (this manual only):\n{figlist}\n\n"
            + (f"ACCEPTED REFERENCE SHEET FOR THIS CASE (keep its diagnosis path and branches; fix it to the step rules):\n{reference}\n\n" if reference else "")
            + f"TROUBLESHOOTING SECTION (read all of it):\n{section['text']}\n\nREST OF THE MANUAL (removal/installation pages):\n{section['rest_text']}")
    msgs = [{"role": "system", "content": EXTRACT_RULES}, {"role": "user", "content": user}]
    chat = chat or (lambda m: _xai(m, api_key))
    usage, last = [], None
    for attempt in range(retries + 1):
        print(f"[rule11] extract attempt {attempt + 1}", flush=True)
        text, u = chat(msgs)
        usage.append(u)
        plan = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        sheet_errs = []
        try:
            sh = plan_to_sheet("", concern, unit, manual, plan, figures)
            validate_sheet(sh)
            return plan, usage
        except (StepRuleError, NoFigures) as exc:
            sheet_errs = str(exc)
            print(f"[rule11] rule errors: {sheet_errs[:400]}", flush=True)
            last = exc
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": f"These steps break the rules: {sheet_errs}\nFix every one (split multi-action steps into separate steps; add probe/state/good/bad; place figures). Reply with the full JSON again."}]
    raise last


def plan_to_sheet(case, concern, unit, manual, plan, figures) -> Sheet:
    return Sheet(case=case, concern=concern, unit=unit, manual=manual,
                 diagnosis=[Step.from_dict(s) for s in plan.get("diagnosis", [])],
                 branches=[{"title": b.get("title", ""), "before": b.get("before", []),
                            "steps": [Step.from_dict(s) for s in b.get("steps", [])]} for b in plan.get("branches", [])],
                 do_not=plan.get("do_not", []), flow=plan.get("flow", []), figures=figures)


# ---------------- render ----------------
def _sentence(t: str) -> str:
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    if not t:
        return t
    t = t[0].upper() + t[1:]
    return t if t[-1] in ".!?)" else t + "."


def _tidy(s: Step) -> Step:
    from dataclasses import replace
    return replace(s, **{k: _sentence(getattr(s, k)) for k in ("probe", "state", "good", "bad", "next")})


def render_pdf(sheet: Sheet, out_pdf: str, out_md: str | None = None) -> dict:
    """Profile layout: header, case flowchart, diagnosis, branches, Do Not, sources.
    Raises before writing anything when the sheet breaks rule 11."""
    stats = validate_sheet(sheet)
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as E

    ss = getSampleStyleSheet()
    B = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10.5, leading=13.5)
    H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=17)
    H2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#0b4a8b"))
    H3 = ParagraphStyle("h3", parent=ss["Heading3"])
    ST = ParagraphStyle("st", parent=B, fontName="Helvetica-Bold", fontSize=11.5, spaceBefore=6)
    CAP = ParagraphStyle("c", parent=B, alignment=1, fontSize=9, fontName="Helvetica-Oblique")
    NOTE = ParagraphStyle("n", parent=B, fontName="Helvetica-Oblique", leftIndent=12)
    SRC = ParagraphStyle("s", parent=B, fontSize=8.5, textColor=colors.HexColor("#555555"))
    W = letter[0] - 72
    m = sheet.manual
    md = [f"# {sheet.unit.get('model')}: Shop Sheet", "", f"**Concern:** {sheet.concern}  ",
          f"**Model:** {sheet.unit.get('model')}  ", f"**Primary source:** {m['title']}" + (f" ({m['url']})" if m['url'] else "") + "  ", ""]
    st = [Paragraph(E(f"SHOP SHEET: {sheet.unit.get('model')}"), H1)]
    for k, v in (("CONCERN", sheet.concern), ("MODEL", sheet.unit.get("model", "")),
                 ("PRIMARY SOURCE", m["title"] + (f" ({m['url']})" if m["url"] else ""))):
        st += [Paragraph(k, H3), Paragraph(E(v), B)]
    st.append(Paragraph("VISUAL FLOWCHART", H2))
    rows = [["#", "Question", "YES", "NO"]] + [[str(i), Paragraph(E(f["q"]), B), Paragraph(E(f["yes"]), B), Paragraph(E(f["no"]), B)]
                                            for i, f in enumerate(sheet.flow, 1)]
    tb = Table(rows, colWidths=[0.4 * inch, 2.7 * inch, 1.8 * inch, 2.1 * inch], repeatRows=1)
    tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde8f5")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    st.append(tb)
    md += ["## Visual flowchart", ""] + [f"- **{i}. {f['q']}** YES: {f['yes']} NO: {f['no']}" for i, f in enumerate(sheet.flow, 1)] + [""]

    def img(fid):
        f = sheet.figures[fid]
        tw = W * 0.75
        th = tw * f["height"] / max(1, f["width"])
        if th > 300:
            th = 300
            tw = th * f["width"] / f["height"]
        return Image(BytesIO(f["png"]), tw, th, hAlign="CENTER")

    def steps(lst):
        out, n = [], 0
        for s in lst:
            if s.kind == "note":
                out.append(Paragraph(E("Note: " + s.action), NOTE))
                md.append(f"*Note: {s.action}*\n")
                continue
            n += 1
            s = _tidy(s)
            lines = [("Probe point", s.probe), ("Switch state", s.state), ("Do this", s.action),
                     ("Good reading", s.good), ("Bad reading", s.bad), ("Next", s.next)]
            f = [Paragraph(E(f"Step {n}: {s.action.rstrip('.')}"), ST)]
            f += [Paragraph(f"<b>{k}:</b> {E(v)}", B) for k, v in lines if v]
            f.append(Paragraph(E(source_tag(s, m)), SRC))
            md.append(f"**Step {n}: {s.action.rstrip('.')}**")
            md.extend([f"- {k}: {v}" for k, v in lines if v] + [f"- Source: {source_tag(s, m)}"])
            if s.figure:
                fg = sheet.figures[s.figure]
                cap = f"{fg['label']}. {m['title']}, page {fg['page']}."
                f += [Spacer(1, 4), img(s.figure), Paragraph(E(cap), CAP)]
                md.append(f"\n![{cap}](figure:{s.figure})\n*{cap}*")
            md.append("")
            out.append(KeepTogether(f))
        return out

    st.append(Paragraph("DIAGNOSIS CHECKS", H2))
    md += ["## Diagnosis checks", ""]
    st += steps(sheet.diagnosis)
    for b in sheet.branches:
        md += [f"## {b['title']}", "", "**Before you start**"] + [f"- {x}" for x in b["before"]] + [""]
        head = [Paragraph("REPAIR BRANCH", H2), Paragraph(E(b["title"]), H3), Paragraph("BEFORE YOU START", H3)]
        head += [Paragraph("&bull; " + E(x), B) for x in b["before"]]
        body = steps(b["steps"])
        if body and isinstance(body[0], KeepTogether):
            st.append(KeepTogether(head + body[0]._content))
            st += body[1:]
        else:
            st += head + body
    st += [PageBreak(), Paragraph("DO NOT", H2)] + [Paragraph("- " + E(x), B) for x in sheet.do_not]
    pages = sorted({s.page for s in all_steps(sheet) if s.page})
    srcs = [f"{m['label']}: {m['title']}" + (f" ({m['url']})" if m["url"] else "") + ", pages " + ", ".join(map(str, pages)) + "."]
    if any(s.source == "general" for s in all_steps(sheet)):
        srcs.append(f"{go.LABEL_GENERAL}: shop steps marked on the sheet; not printed in the manual.")
    st += [Paragraph("SOURCES", H2)] + [Paragraph("- " + E(x), B) for x in srcs]
    md += ["## Do Not", ""] + [f"- {x}" for x in sheet.do_not] + ["", "## Sources", ""] + [f"- {x}" for x in srcs]
    SimpleDocTemplate(out_pdf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
                      title=f"{sheet.unit.get('model')} shop sheet").build(st)
    if out_md:
        with open(out_md, "w") as fh:
            fh.write("\n".join(md) + "\n")
    stats.update({"steps": sum(1 for s in all_steps(sheet) if s.kind == "step"),
                  "notes": sum(1 for s in all_steps(sheet) if s.kind == "note"),
                  "branches": len(sheet.branches),
                  "figures_by_section": {"diagnosis": sum(1 for s in sheet.diagnosis if s.figure),
                                         **{b["title"]: sum(1 for s in b["steps"] if s.figure) for b in sheet.branches}}})
    return stats


def build(case, model_text, concern, category, library, *, pdf_for_doc, api_key, out_pdf, out_md=None, reference="", chat=None, http=None):
    """Full rule-11 pipeline. Raises NoManual / NoFigures / StepRuleError instead of writing a filler sheet."""
    manual = find_manual(model_text, concern, category, library, pdf_for_doc=pdf_for_doc, api_key=api_key, http=http)
    section = read_manual(manual, concern)
    figures = manual_figures_index(manual["pdf"])
    if not figures:
        raise NoFigures(f"The pinned manual ({manual['title']}) has no extractable figures. No sheet produced.")
    plan, usage = extract_plan(manual["unit"], concern, manual, section, figures, api_key, reference=reference, chat=chat)
    sheet = plan_to_sheet(case, concern, manual["unit"], manual, plan, figures)
    stats = render_pdf(sheet, out_pdf, out_md)
    stats.update({"manual": manual["title"], "origin": manual["origin"], "url": manual["url"],
                  "section_mode": section["mode"], "section_pages": section["pages"], "usage": usage})
    return stats, sheet, plan
