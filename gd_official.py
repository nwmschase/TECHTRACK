"""Guided Diagnostics official method (Chase approved 2026-10-16).

1. Identify the exact unit first (brand + model). No diagnostic steps before that.
2. Pin the manual: library first (metadata first, wrong brand refused); web
   fallback on official OEM domains only when there is no model match, the
   troubleshooting pages are missing or thin, or the tech asks.
3. Read the full troubleshooting section before the first diagnostic reply
   (whole manual when there is no clear section).
4. Walk one action per line; hold a step the tech reports "not checked"; ask
   for fault codes; end with a verify step.
5. Label every step: Library / Manufacturer site (URL) / General trade knowledge.

This module does not import rv_techtrack or Streamlit. The app passes a
library adapter and a chat function. The Bay PDF builder does not use it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from urllib.parse import urlparse

GD_OFFICIAL_REVISION = "gd-official-1"

REPLY_MAX_TOKENS = 1500
FIRST_READ_REASONING = "medium"
LATER_REASONING = "low"
THIN_SECTION_CHARS = 1500
# grok-4.6 list price per 1M tokens (docs.x.ai/docs/models/grok-4.6, 2026-10-16).
PRICE_PER_M = {"input": 2.00, "cached": 0.50, "output": 6.00}

LABEL_LIBRARY = "Library"
LABEL_WEB = "Manufacturer site"
LABEL_GENERAL = "General trade knowledge"

# Official OEM domains only (Leader 2026-10-16). Suffix match on the host.
OFFICIAL_DOMAINS = {
    "lippert": ("lci1.com", "lippert.com", "lippertcomponents.com", "=lci-support-doc.s3.amazonaws.com"),
    "dometic": ("dometic.com",),
    "furrion": ("furrion.com",),
    "thetford": ("thetford.com",),
    "suburban": ("airxcel.com", "suburbanrv.com"),
    "atwood": ("dometic.com", "airxcel.com"),
    "coleman-mach": ("airxcel.com", "rvcomfort.com"),
    "girard": ("girardrv.com",),
    "bal": ("norcoindustries.com", "balrv.com"),
    "norcold": ("norcold.com", "thetford.com"),
    "truma": ("truma.com", "trumaservice.com"),
    "power gear": ("lci1.com", "lippert.com"),
    "kwikee": ("lci1.com", "lippert.com"),
    "hwh": ("hwh.com",),
    "renogy": ("renogy.com",),
    "victron": ("victronenergy.com",),
    "maxxair": ("maxxair.com",),
}

BRAND_ALIASES = {
    "lci": "lippert", "onecontrol": "lippert", "ground control": "lippert",
    "unity": "lippert", "level-up": "lippert", "level up": "lippert",
    "schwintek": "lippert", "solera": "lippert", "furrion": "furrion",
    "coleman": "coleman-mach", "mach": "coleman-mach", "airxcel": "coleman-mach",
    "atwood": "atwood", "maxxfan": "maxxair", "maxx air": "maxxair", "power gear": "power gear", "kwikee": "kwikee",
}
KNOWN_BRANDS = tuple(sorted(set(OFFICIAL_DOMAINS) | set(BRAND_ALIASES), key=len, reverse=True))

NO_TAG_RE = re.compile(r"\b(no\s+(model\s+)?(tag|label|data\s*plate)|model\s+(unknown|not\s+known)|can'?t\s+find\s+(the\s+)?(tag|label|model))", re.I)
LOW_V_UNDER_LOAD_RE = re.compile(
    r"\b(voltage\s+drop\w*|drop\w*\s+(heavily\s+)?under\s+load|low\s+voltage|volts?\s+(drops?|sag\w*)|sag\w*\s+under\s+load|"
    r"battery\s+voltage\s+(drops?|dropped|sags?|falls?))\b",
    re.I,
)
NOT_CHECKED_RE = re.compile(
    r"\b(not\s+(yet\s+)?checked|haven'?t\s+checked|didn'?t\s+check|did\s+not\s+check|not\s+tested|skipped|n/?c)\b",
    re.I,
)
WEB_ASK_RE = re.compile(r"\b(look\s+(it\s+)?up\s+online|search\s+(the\s+)?web|online\s+manual|manufacturer'?s?\s+(site|website))\b", re.I)
SECTION_HEAD_RE = re.compile(
    r"\b(troubleshoot\w*|diagnos\w*|fault\s+codes?|error\s+codes?|failure\s+codes?|"
    r"symptom|zero[\s-]?point|calibrat\w*|problem\s*/\s*cause|if\s+the\s+\w+\s+(does\s+not|will\s+not|won'?t))",
    re.I,
)
FAULT_CODE_HINT_RE = re.compile(r"\b(fault|error|failure)\s+code|\bcode\s+[A-Z]?\d|\bblink|\bflash", re.I)
SAFETY_LINE = (
    "Safety first: chock the wheels, keep everyone clear of jacks/slides, and "
    "disconnect power before touching wiring."
)


# ---------------- unit identification ----------------
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("®", "").replace("™", "")).strip()


def detect_brand(text: str) -> str:
    t = _norm(text)
    for b in KNOWN_BRANDS:
        if re.search(r"(?<![a-z])" + re.escape(b) + r"(?![a-z])", t):
            return BRAND_ALIASES.get(b, b)
    return ""


_STOP = {"lippert", "onecontrol", "the", "and", "with", "for", "rv", "point", "pt", "4pt", "6pt",
         "fifth", "wheel", "system", "leveler", "leveling", "auto", "level", "manual", "service",
         "owner", "owners", "guide", "pn", "part"}


def model_tokens(model_text: str) -> list:
    """Distinctive model tokens: X270D, 803280, 3.0, 'ground control', 'gc'."""
    t = _norm(model_text)
    t = t.replace("gc3.0", "gc 3.0").replace("gc 3", "ground control 3")
    toks = []
    for m in re.finditer(r"[a-z]*\d[\w.\-]*", t):
        tok = m.group(0).strip(".-")
        if tok and tok not in toks:
            toks.append(tok)
    for phrase in ("touchscreen", "touch screen", "ground control", "unity", "level-up", "level up", "schwintek", "in-wall", "touch panel"):
        if phrase in t and phrase not in toks:
            toks.append(phrase)
    return [x for x in toks if x not in _STOP and not re.fullmatch(r"(19|20)\d\d", x)]


def identify_unit(history, user_msg: str, category_name: str, model_text: str) -> dict:
    blob = " ".join([model_text or ""] + [m.get("content", "") for m in (history or []) if m.get("role") == "user"] + [user_msg or ""])
    brand = detect_brand(model_text) or detect_brand(blob)
    toks = model_tokens(model_text) or model_tokens(" ".join(m.get("content", "") for m in (history or []) if m.get("role") == "user") + " " + (user_msg or ""))
    has_model = any(re.search(r"\d", x) for x in toks) or any(x in ("ground control", "unity") for x in toks)
    # No tag on the unit: brand + product type is the identification; model specs stay unconfirmed.
    no_tag = bool(NO_TAG_RE.search(blob))
    if brand and no_tag:
        has_model = True
    return {
        "brand": brand,
        "model": (model_text or "").strip(),
        "tokens": toks,
        "category": category_name or "",
        "identified": bool(brand and has_model),
        "model_unknown": bool(brand and no_tag),
    }


def unit_question(unit: dict) -> str:
    missing = []
    if not unit.get("brand"):
        missing.append("brand")
    if not unit.get("identified"):
        missing.append("exact model / part number and controller or board")
    return (
        f"{SAFETY_LINE}\n"
        f"Before any test steps I need the exact unit: {', '.join(missing)}. "
        "Type it from the data plate or add a photo of the plate."
    )


# ---------------- library adapter + document pin ----------------
class SqliteLibrary:
    """Read-only adapter over the TechTrack SQLite file (tests and RC harness)."""

    def __init__(self, path: str):
        import sqlite3

        self.c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def documents(self):
        cur = self.c.execute(
            "select id,title,coalesce(brand,''),coalesce(models,''),coalesce(product_line,''),"
            "coalesce(clean_title,''),coalesce(doc_number,''),coalesce(keywords,''),coalesce(revision_date,'') from documents"
        )
        keys = ("id", "title", "brand", "models", "product_line", "clean_title", "doc_number", "keywords", "revision_date")
        return [dict(zip(keys, r)) for r in cur.fetchall()]

    def chunks(self, doc_id):
        cur = self.c.execute("select page, chunk_text from doc_chunks where document_id=? order by page, id", (doc_id,))
        return [{"page": p, "text": t or ""} for p, t in cur.fetchall()]


class OrmLibrary:
    """Adapter over the app's SQLAlchemy session (live app path)."""

    def __init__(self, session, Document, DocChunk):
        self.s, self.D, self.C = session, Document, DocChunk

    def documents(self):
        out = []
        for d in self.s.query(self.D).all():
            out.append({
                "id": d.id, "title": d.title or "", "brand": d.brand or "", "models": d.models or "",
                "product_line": d.product_line or "", "clean_title": d.clean_title or "",
                "doc_number": d.doc_number or "", "keywords": d.keywords or "", "revision_date": d.revision_date or "",
            })
        return out

    def chunks(self, doc_id):
        rows = self.s.query(self.C).filter(self.C.document_id == doc_id).order_by(self.C.page, self.C.id).all()
        return [{"page": r.page, "text": r.chunk_text or ""} for r in rows]


def _doc_brand(doc: dict) -> str:
    return detect_brand(doc.get("brand", "")) or detect_brand(doc.get("title", "") + " " + doc.get("product_line", ""))


def brand_conflict(unit: dict, doc: dict) -> bool:
    """True when the document names another brand than the unit."""
    db = _doc_brand(doc)
    return bool(unit.get("brand") and db and db != unit["brand"])


def score_document(unit: dict, doc: dict) -> tuple:
    """(model_hits, troubleshooting_title, brand_ok). Metadata fields first, title second."""
    if brand_conflict(unit, doc):
        return (-1, 0, False)
    if unit.get("brand") and _doc_brand(doc) != unit["brand"]:
        return (-1, 0, False)  # a named brand needs a document of that brand
    meta = _norm(" ".join([doc.get("models", ""), doc.get("product_line", ""), doc.get("doc_number", ""), doc.get("clean_title", "")]))
    title = _norm(doc.get("title", ""))
    hits = 0
    meta_ns, title_ns = meta.replace(" ", ""), title.replace(" ", "")
    for tok in unit.get("tokens", []):
        t_ns = tok.replace(" ", "")
        if tok in meta or t_ns in meta_ns:
            hits += 2
        elif tok in title or t_ns in title_ns:
            hits += 1
    trouble = 1 if re.search(r"troubleshoot|diagnos|service manual", title) else 0
    return (hits, trouble, True)


def pin_document(library, unit: dict, exclude_ids=()) -> dict | None:
    """Best same-brand document with a model match, or None (=> web trigger)."""
    best, best_key = None, None
    for doc in library.documents():
        if doc["id"] in exclude_ids:
            continue
        hits, trouble, ok = score_document(unit, doc)
        if not ok or hits <= 0:
            continue
        # Model-number tokens (digits) must match when the unit has them.
        digit_toks = [t for t in unit.get("tokens", []) if re.search(r"\d", t) and len(t) >= 3]
        text = _norm(" ".join(str(doc.get(k, "")) for k in ("title", "models", "doc_number", "clean_title", "keywords")))
        digit_hit = any(t in text for t in digit_toks)
        key = (digit_hit, trouble, hits)
        if best_key is None or key > best_key:
            best, best_key = doc, key
    if not best:
        return None
    digit_toks = [t for t in unit.get("tokens", []) if re.search(r"\d", t) and len(t) >= 3]
    if digit_toks and not best_key[0]:
        return None
    return best


# ---------------- section reading ----------------
def load_section(chunks: list, symptom: str = "") -> dict:
    """Pages of the troubleshooting section in order; whole manual if none is clear."""
    pages = {}
    for ch in chunks:
        pages.setdefault(int(ch.get("page") or 1), []).append(ch.get("text") or "")
    if not pages:
        return {"pages": [], "text": "", "mode": "empty", "thin": True}
    page_text = {p: "\n".join(v) for p, v in sorted(pages.items())}
    sym = [w for w in re.findall(r"[a-z]{4,}", _norm(symptom)) if w not in _STOP][:12]
    hit_pages = []
    for p, t in page_text.items():
        heads = len(SECTION_HEAD_RE.findall(t))
        symh = sum(1 for w in sym if w in t.lower())
        if heads >= 2 or (heads and symh):
            hit_pages.append(p)
    if hit_pages:
        lo, hi = min(hit_pages), max(hit_pages)
        # Contiguous section: include the pages between the first and last hit.
        sel = [p for p in page_text if lo <= p <= hi]
        mode = "section"
    else:
        sel = list(page_text)
        mode = "whole_manual"
    text = "\n\n".join(f"[PAGE {p}]\n{page_text[p]}" for p in sel)
    return {"pages": sel, "text": text, "mode": mode, "thin": len(text) < THIN_SECTION_CHARS}


# ---------------- web fallback (official domains only) ----------------
def allowed_domains_for(brand: str) -> tuple:
    return OFFICIAL_DOMAINS.get(brand or "", ())


def url_is_official(url: str, brand: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    for d in allowed_domains_for(brand):
        if d.startswith("="):
            if host == d[1:]:  # exact host only (OEM CDN on a shared domain)
                return True
        elif host == d or host.endswith("." + d):
            return True
    return False


def _pdf_text(data: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        try:
            out = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, timeout=60)
            return out.stdout.decode("utf-8", "ignore")
        except Exception:
            return ""


def fetch_official_manual(unit: dict, api_key: str, *, model: str = "grok-4.6", http=None, timeout: float = 120.0) -> dict:
    """Ask xAI web_search (allowed_domains = OEM list) for the manual PDF URL, then fetch it.

    Session only. Nothing is written to R2 here. Returns {} when no official copy is found.
    """
    brand = unit.get("brand", "")
    domains = [d.lstrip("=") for d in allowed_domains_for(brand)][:5]
    if not domains or not api_key:
        return {}
    import httpx

    http = http or httpx
    prompt = (
        f"Find the official manufacturer PDF service/troubleshooting manual for: {brand} {unit.get('model','')}. "
        "Use as few searches as possible (3 or fewer). "
        "Reply with JSON only: {\"url\": \"<direct pdf url or the official document page url>\", \"title\": \"<document title>\"}. "
        "Use only the allowed domains. If none exists, reply {\"url\": \"\"}."
    )
    body = {"model": model, "input": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search", "filters": {"allowed_domains": domains}}]}
    t0 = time.time()
    try:
        r = http.post("https://api.x.ai/v1/responses", json=body, timeout=timeout,
                      headers={"Authorization": f"Bearer {api_key}"})
        data = r.json()
    except Exception as exc:
        return {"error": f"web search failed: {exc}"}
    text = ""
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                text += c.get("text", "")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        found = json.loads(m.group(0)) if m else {}
    except Exception:
        found = {}
    url = (found.get("url") or "").strip()
    usage = data.get("usage", {}) or {}
    ticks = usage.get("cost_in_usd_ticks")
    if ticks:
        usage = {**usage, "cost_usd": round(ticks / 1e10, 4)}
    result = {"search_usage": usage, "search_seconds": round(time.time() - t0, 1), "url": url, "title": found.get("title", "")}
    if not url or not url_is_official(url, brand):
        result["refused"] = bool(url)
        result["url"] = "" if not url_is_official(url, brand) else url
        return result
    try:
        if not url.lower().split("?")[0].endswith(".pdf"):
            page = http.get(url, timeout=timeout, follow_redirects=True)
            links = [u for u in re.findall(r"https?://[^\"' <>]+?\.pdf", page.text or "") if url_is_official(u, brand)]
            if not links:
                return {**result, "error": "no official PDF link on the document page"}
            result["page_url"], url = url, links[0]
            result["url"] = url
        pdf = http.get(url, timeout=timeout, follow_redirects=True)
        final = str(getattr(pdf, "url", url))
        if not url_is_official(final, brand):
            return {**result, "refused": True, "url": ""}
        text = _pdf_text(pdf.content)
    except Exception as exc:
        return {**result, "error": f"download failed: {exc}"}
    pages = [{"page": i + 1, "text": t} for i, t in enumerate(text.split("\f")) if t.strip()]
    result["chunks"] = pages
    result["no_text"] = not pages
    return result


# ---------------- prompt + walk ----------------
METHOD_RULES = f"""You are TechTrack Guided Diagnostics for Tacoma RV Center techs. Follow this method exactly.
- You have ALREADY read the full troubleshooting section below. Use it as the procedure.
- Walk the tech ONE ACTION PER LINE. Each line: exact probe points, meter setting, switch/button states, and what reading or result to report.
- Give only the next 1-6 lines, then ask for the reading/result. Branch: "If X, go to Y."
- Never skip a step the tech says was NOT checked. Re-ask it until they report a result.
- If the system stores fault/error codes, ask for the code (and how to read it) before other tests.
- Multi-step procedures (calibration, programming, resync) are numbered, one action per line, including preconditions (e.g. retract all jacks first).
- After any repair or calibration, end with a VERIFY step (run the function again, confirm it completes / the complaint is gone).
- Every step line ends with a source tag: [{LABEL_LIBRARY}: <manual title> p.<page>] or [{LABEL_WEB}: <url> p.<page>] or [{LABEL_GENERAL}].
  Only cite pages that appear in the excerpt below. {LABEL_GENERAL} may drive a step only if labeled, never for brand-specific specs (voltages, codes, part numbers, button sequences).
- Read the conversation. NEVER repeat a step the tech already answered or reported. Use the tech's latest result to choose the NEXT step in the section's order (or branch).
- If the tech reports a finding that skips ahead (e.g. a fault code or an output reading), accept it and continue from that point; ask for any earlier step only if the section says it must come first.
- Plain shop English. No preamble, no "according to the manual".
"""

CHARGE_PATH_RULES = f"""
12V CHARGING-PATH WALK (the appliance is cleared and the tech found low battery voltage under load). Hand off to this walk.
The WHOLE walk is [{LABEL_GENERAL}]; tag every line of it that way. Never invent model-specific specs for the appliance
(e.g. its required voltage); if one is needed and not in the excerpt, say "spec not in the manual excerpt - confirm with the OEM".
 C1. Have the tech MAP what is installed, source to battery: converter/charger, fuses and breakers, battery isolator/disconnect,
     busbars, battery BMS (lithium), cable runs. Wait for the map before testing.
 C2. VOLTAGE-DROP TEST each component IN ORDER from converter to battery, WITH CURRENT FLOWING (charging or a load on):
     meter leads across each component (input side to output side of the same conductor), one component per line, report each reading.
     Any single component or connection dropping noticeably more than the others is the fault; fix or replace it.
 C3. VERIFY: after the repair, recheck voltage at the battery under charge, let the batteries charge, then rerun the original function
     (e.g. Auto Level) and confirm it completes.
 C4. FLAG a battery capacity test (amp-draw / Ah load test or BMS state-of-health) before release if it was not done.
Do not recommend replacing the appliance controller/touchpad when it powered, communicated, and the voltage under load was low.
"""

ONECONTROL_COMPLAINT_RE = re.compile(
    r"\b(slide|slides|slide-?out|awning|level\w*|jack|jacks|light|lights|tank|tanks|water\s+pump|generator|"
    r"stabilizer|landing\s+gear|onecontrol|one\s+control|unity|x270\w*|touch\s+panel|panel)\b",
    re.I,
)

UNITY_PATH_RULES = f"""
ONECONTROL / UNITY PATH (selector = Yes; this complaint is a OneControl-managed load). Include these checks in order,
merged with the pinned procedure, skipping any the tech already reported:
 U1. Identify the controller: model (e.g. Unity X270D) and IDS part # from its label (ask for a label photo or the number).
 U2. Controller input: battery voltage at the controller power inputs, and its dedicated fuses/breakers (amp rating and that each feed is dedicated).
 U3. Comms: panel/app command reaches the controller (audible relay click at the controller, panel/app response).
 U4. Output: meter on the controller's motor output terminals for that load WHILE the command is held, both directions. Good = full battery voltage that switches polarity between extend and retract. Bad = open/floating or collapses under command.
 U5. Split controller vs. motor/wiring: if output is good at the controller but the motor does not run, test the harness/motor at the motor end (and load-test). If output is bad at the controller with good input and comms, the controller output has failed.
 U6. After controller replacement: transfer wiring, program/pair/resync per the OneControl procedure, then VERIFY every load on that controller (slides, awning, etc.).
Brand-specific values (voltages, amp ratings, terminal names, button sequences, part numbers) must come from a cited Lippert source in the excerpts; otherwise say "per Lippert doc - not in excerpt" and do not invent them.
U-steps not in the excerpts are tagged [{LABEL_GENERAL}].
"""


def build_messages(pin: dict, history: list, user_msg: str, hints: str = "") -> list:
    src = pin.get("source_label", "")
    sysmsg = METHOD_RULES + f"\nUNIT: {pin['unit'].get('brand','')} | {pin['unit'].get('model','')}\n"
    sysmsg += f"PINNED DOCUMENT: {pin.get('doc_title','')} | source tag to use: [{src}] | read mode: {pin.get('mode')}\n"
    held = [s for s, v in pin.get("checked", {}).items() if v == "not checked"]
    if held:
        sysmsg += f"\nHELD STEP (tech reported NOT CHECKED, re-ask it now before anything else): {held[-1]}\n"
    reported = [m.get("content", "") for m in (history or []) if m.get("role") == "user"][1:] + [user_msg]
    reported = [r for r in reported if r and not NOT_CHECKED_RE.search(r)]
    if reported:
        sysmsg += "\nTECH HAS REPORTED (treat as done; do NOT ask these again; move to the next step):\n- " + "\n- ".join(reported[-12:]) + "\n"
    if pin.get("needs_fault_code") and not pin.get("fault_code_asked"):
        sysmsg += "\nThis system stores fault codes: ask for the current fault code in this reply.\n"
    if pin.get("unity_path"):
        sysmsg += UNITY_PATH_RULES
        if pin.get("unity_text"):
            sysmsg += "\n===== LIPPERT ONECONTROL / UNITY REFERENCE =====\n" + pin["unity_text"] + "\n"
    if pin.get("charge_path"):
        sysmsg += CHARGE_PATH_RULES
    if pin["unit"].get("model_unknown"):
        sysmsg += "\nMODEL UNKNOWN (no tag): use only generic steps for this brand's system type; never state model-specific specs.\n"
    if hints:
        sysmsg += f"\nSHOP HINT (not a source, do not cite): {hints}\n"
    sysmsg += "\n===== FULL TROUBLESHOOTING SECTION =====\n" + pin.get("section_text", "")
    msgs = [{"role": "system", "content": sysmsg}]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip():
            msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})
    return msgs


_TAG_RE = re.compile(r"\[(Library|Manufacturer site|General trade knowledge)[^\]]*\]")


def enforce_labels(reply: str, pin: dict) -> str:
    """Untagged step lines get the General tag; library page cites outside the read pages are relabeled."""
    pages = set(pin.get("pages") or [])
    out = []
    for line in (reply or "").splitlines():
        s = line.strip()
        is_step = bool(re.match(r"^(\d+[.)]|[-•*])\s+\S", s))
        if is_step and not _TAG_RE.search(s):
            line = line.rstrip() + f" [{LABEL_GENERAL}]"
        for m in re.finditer(r"\[(Library|Manufacturer site):[^\]]*?p\.?\s*(\d+)[^\]]*\]", line):
            if pages and int(m.group(2)) not in pages:
                line = line.replace(m.group(0), f"[{LABEL_GENERAL}]")
        out.append(line)
    return "\n".join(out)


REPAIR_WORDS_RE = re.compile(r"\b(calibrat\w*|replace\w*|program\w*|resync\w*|reset|repair)\b", re.I)


def ensure_verify(reply: str) -> str:
    if REPAIR_WORDS_RE.search(reply or "") and not re.search(r"\bverif\w*", reply or "", re.I):
        reply = (reply or "").rstrip() + (
            f"\nVERIFY: run the function again (full cycle, 2-3 times) and confirm it completes and the complaint is gone. [{LABEL_GENERAL}]"
        )
    return reply


def update_step_state(pin: dict, history: list, user_msg: str) -> None:
    last_asst = ""
    for m in reversed(history or []):
        if m.get("role") == "assistant":
            last_asst = m.get("content") or ""
            break
    if not last_asst:
        return
    first_step = ""
    for line in last_asst.splitlines():
        if line.strip().startswith("Using:"):
            continue
        if re.match(r"^\s*(\d+[.)]|[-•*])\s+\S", line) or len(line.strip()) > 20:
            first_step = _TAG_RE.sub("", line).strip()
            break
    checked = pin.setdefault("checked", {})
    if NOT_CHECKED_RE.search(user_msg or ""):
        if first_step:
            checked[first_step] = "not checked"
    else:
        for k, v in list(checked.items()):
            if v == "not checked":
                checked[k] = "reported"
    if re.search(r"fault|error|code", last_asst, re.I):
        pin["fault_code_asked"] = True


UNITY_DOC_RE = re.compile(r"unity|onecontrol|x270", re.I)


# Lippert official OneControl Unity Board troubleshooting manual (CCD-0002117), served from Lippert's
# support CDN (linked from https://support.lci1.com/documents/ccd-0002117).
LIPPERT_UNITY_REF_URL = "https://lci-support-doc.s3.amazonaws.com/manuals/electronics/onecontrol/ccd-0002117.pdf"


def _unity_docs(library, exclude_ids=()):
    oem, shop = None, None
    for doc in library.documents():
        if doc["id"] in exclude_ids or _doc_brand(doc) not in ("", "lippert"):
            continue
        title = doc.get("title", "")
        t = title + " " + doc.get("keywords", "")
        if not (UNITY_DOC_RE.search(title) and re.search(r"diagnos|troubleshoot|service", t, re.I)):
            continue
        if re.search(r"troubleshooting and service manual", title, re.I) and not re.search(r"tacoma|primary", t, re.I):
            oem = oem or doc
        else:
            score = bool(re.search(r"x270", t, re.I))
            if shop is None or score > shop[0]:
                shop = (score, doc)
    return oem, (shop[1] if shop else None)


def apply_unity_path(pin: dict, library, unity_gate: str, blob: str, exclude_ids=(), web_get=None) -> None:
    """Selector Yes + OneControl-managed complaint: add the Unity/X270 path and Lippert Unity references."""
    if (unity_gate or "").strip() != "Yes" or not ONECONTROL_COMPLAINT_RE.search(blob or ""):
        return
    pin["unity_path"] = True
    parts, refs, pages = [], [], set(pin.get("pages") or [])
    oem, shop = _unity_docs(library, exclude_ids)
    for doc, kind in ((oem, "Lippert OEM"), (shop, "shop diagnostic")):
        if not doc or doc.get("id") == pin.get("doc_id"):
            continue
        sect = load_section(library.chunks(doc["id"]), "unity output relay voltage fuse")
        parts.append(f"[{kind}; source tag: {LABEL_LIBRARY}: {doc['title']}]\n" + sect["text"])
        refs.append(doc["title"])
        pages |= set(sect["pages"])
    if not oem and web_get:
        try:
            text = web_get(LIPPERT_UNITY_REF_URL)
        except Exception:
            text = ""
        if text:
            parts.append(f"[Lippert OEM; source tag: {LABEL_WEB}: {LIPPERT_UNITY_REF_URL}]\n" + text)
            refs.append(LIPPERT_UNITY_REF_URL)
    pin["unity_refs"] = refs
    pin["unity_text"] = "\n\n".join(parts)
    pin["pages"] = sorted(pages)


def official_pdf_text(url: str, brand: str = "lippert", http=None) -> str:
    """Download one official-domain PDF and return its text (pages split by [PAGE n])."""
    if not url_is_official(url, brand):
        return ""
    import httpx

    r = (http or httpx).get(url, timeout=60, follow_redirects=True)
    if not url_is_official(str(getattr(r, "url", url)), brand):
        return ""
    pages = [t for t in _pdf_text(r.content).split("\f") if t.strip()]
    return "\n\n".join(f"[PAGE {i+1}]\n{t}" for i, t in enumerate(pages))


def turn_cost(usage: dict) -> float:
    p = int(usage.get("prompt_tokens") or 0)
    c = int(usage.get("cached_tokens") or 0)
    # xAI chat completions report reasoning tokens apart from completion tokens; both bill as output.
    o = int(usage.get("completion_tokens") or 0) + int(usage.get("reasoning_tokens") or 0)
    return round(((p - c) * PRICE_PER_M["input"] + c * PRICE_PER_M["cached"] + o * PRICE_PER_M["output"]) / 1e6, 5)


def log_turn(path: str, record: dict) -> None:
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def official_turn(
    user_msg: str,
    category_name: str,
    model_text: str,
    history: list,
    *,
    library,
    chat_fn,
    pin_store: dict,
    usage_fn=None,
    web_fetch_fn=None,
    hints: str = "",
    log_path: str = "",
    exclude_doc_ids=(),
    unity_gate: str = "",
    web_get=None,
) -> dict:
    """One GD turn. Returns {reply, mode, pin, usage, seconds, reduced}.

    chat_fn(messages, max_tokens, reasoning_effort) -> str; raise to fall back.
    """
    t0 = time.time()
    unit = identify_unit(history, user_msg, category_name, model_text)
    pin = pin_store.get("gd_pin")
    if pin and pin["unit"].get("model") != unit.get("model") and unit.get("identified"):
        pin = None  # unit changed
    if not pin:
        if not unit["identified"]:
            reply = unit_question(unit)
            log_turn(log_path, {"stage": "identify", "seconds": round(time.time() - t0, 2)})
            return {"reply": reply, "mode": "identify", "pin": None, "usage": {}, "seconds": round(time.time() - t0, 2)}
        pin = {"unit": unit, "checked": {}, "fault_code_asked": False, "web": {}}
        doc = pin_document(library, unit, exclude_ids=exclude_doc_ids)
        sect = load_section(library.chunks(doc["id"]), user_msg + " " + model_text) if doc else {"thin": True}
        want_web = (doc is None) or sect.get("thin") or bool(WEB_ASK_RE.search(user_msg or ""))
        if want_web and web_fetch_fn:
            web = web_fetch_fn(unit) or {}
            pin["web"] = {k: v for k, v in web.items() if k != "chunks"}
            if web.get("chunks"):
                wsect = load_section(web["chunks"], user_msg)
                if not wsect.get("thin") or doc is None:
                    doc = {"id": None, "title": web.get("title") or web.get("url"), "url": web["url"]}
                    sect = wsect
        if not doc or not sect.get("text"):
            reply = (
                f"{SAFETY_LINE}\nNo {unit.get('brand') or ''} {unit.get('model')} manual is in the shop library"
                + (" and no official manufacturer copy was found online" if web_fetch_fn else "")
                + ". Upload the manual (or the data-plate photo) and send again. I will not use another brand's manual."
            )
            return {"reply": reply, "mode": "no_manual", "pin": None, "usage": {}, "seconds": round(time.time() - t0, 2)}
        web_src = bool(doc.get("url"))
        pin.update({
            "doc_id": doc.get("id"), "doc_title": doc.get("title", ""), "url": doc.get("url", ""),
            "revision": doc.get("revision_date", ""),
            "source_label": f"{LABEL_WEB}: {doc['url']}" if web_src else f"{LABEL_LIBRARY}: {doc.get('title','')}",
            "pages": sect["pages"], "section_text": sect["text"], "mode": sect["mode"],
            "needs_fault_code": bool(FAULT_CODE_HINT_RE.search(sect["text"])),
            "turns": 0,
        })
        apply_unity_path(pin, library, unity_gate, user_msg + " " + model_text + " " + category_name, exclude_doc_ids, web_get)
        pin_store["gd_pin"] = pin
    else:
        update_step_state(pin, history, user_msg)
        if unity_gate == "Yes" and not pin.get("unity_path"):
            apply_unity_path(pin, library, unity_gate, user_msg + " " + model_text + " " + category_name, exclude_doc_ids, web_get)
    if not pin.get("charge_path") and LOW_V_UNDER_LOAD_RE.search(user_msg or ""):
        pin["charge_path"] = True
    first = pin.get("turns", 0) == 0
    msgs = build_messages(pin, history, user_msg, hints)
    effort = FIRST_READ_REASONING if first else LATER_REASONING
    reduced = False
    reply = chat_fn(msgs, REPLY_MAX_TOKENS, effort)
    usage = usage_fn() if usage_fn else {}
    reply = enforce_labels(reply, pin)
    reply = ensure_verify(reply) if re.search(r"calibrat|replace|program|resync", reply, re.I) else reply
    if first:
        head = f"Using: {pin['doc_title']}" + (f" ({pin['url']})" if pin.get("url") else "") + f" - read {pin['mode'].replace('_',' ')}, pages {pin['pages'][0]}-{pin['pages'][-1]}."
        reply = head + "\n" + reply
    if pin.get("needs_fault_code") and re.search(r"fault|error|code", reply, re.I):
        pin["fault_code_asked"] = True
    pin["turns"] = pin.get("turns", 0) + 1
    secs = round(time.time() - t0, 2)
    ctx_chars = sum(len(m.get("content") or "") for m in msgs)
    rec = {"stage": "walk", "first": first, "messages_sent": len(msgs), "context_chars_sent": ctx_chars,
           "section_chars": len(pin.get("section_text") or ""), "unity_ref_chars": len(pin.get("unity_text") or ""),
           "max_tokens": REPLY_MAX_TOKENS, "doc": pin["doc_title"], "mode": pin["mode"], "effort": effort,
           "usage": usage, "cost_usd": turn_cost(usage) if usage else None, "seconds": secs}
    log_turn(log_path, rec)
    return {"reply": reply, "mode": pin["mode"], "pin": pin, "usage": usage, "seconds": secs, "reduced": reduced, "cost_usd": rec["cost_usd"], "context_chars_sent": ctx_chars}
