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
    "bal": ("norcoindustries.com", "balrv.com", "balrvproducts.com"),
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

NO_TAG_RE = re.compile(r"\b(no\s+(model\s+)?(tag|label|data\s*plate)|model\s+(unknown|not\s+known|not\s+recovered)|can'?t\s+find\s+(the\s+)?(tag|label|model))", re.I)
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


# Units / ratings are never model numbers (F1). Number (with , or . grouping) + optional space/hyphen + unit word.
UNIT_WORDS = (r"v|vac|vdc|volts?|a|amps?|amperes?|ah|mah|amp[\s-]?hours?|w|watts?|kw|kilowatts?|btu|btus|btuh|btu/hr?|"
              r"lbs?|pounds?|cu\.?\s*ft|cu|ft|in|gpm|psi|hz|gal|gallons?|cfm|rpm|mm|cm")
# 'K' is a unit only as thousands-of-BTU (8K, 13.5K, 15K: one or two integer digits); 4500K stays a model number.
_K_VALUE = r"\d{1,2}(?:\.\d+)?\s*-?\s*k"
UNIT_VALUE_RE = re.compile(r"(?<![a-z0-9.])(?:\d[\d,]*(?:\.\d+)?\s*-?\s*(?:" + UNIT_WORDS + r")|" + _K_VALUE + r")(?![a-z0-9])", re.I)
_UNIT_TOKEN_RE = re.compile(r"\d[\d,]*(?:\.\d+)?-?(?:" + UNIT_WORDS.replace(r"\s*", "").replace(r"[\s-]?", "") + r")|"
                            + _K_VALUE.replace(r"\s*", ""), re.I)


def is_unit_token(tok: str) -> bool:
    """True for a rating token such as 12v, 15a, 50ah, 13500btu, 6,000lb, 13.5k."""
    return bool(_UNIT_TOKEN_RE.fullmatch((tok or "").strip().lower()))


def strip_unit_values(text: str) -> str:
    """Remove rating values with or without a space ('13500 BTU', '6,000 lb', '50Ah', '12 V') before tokenizing."""
    return UNIT_VALUE_RE.sub(" ", text or "")


def model_tokens(model_text: str) -> list:
    """Distinctive model tokens: X270D, 803280, 3.0, 'ground control', 'gc'. Rating values never become tokens."""
    t = _norm(strip_unit_values(_norm(model_text)))
    t = t.replace("gc3.0", "gc 3.0").replace("gc 3", "ground control 3")
    toks = []
    for m in re.finditer(r"[a-z]+-?\d[\w.\-]*|[a-z]*\d[\w.\-]*", t):
        tok = m.group(0).strip(".-")
        if tok and tok not in toks:
            toks.append(tok)
    for phrase in ("touchscreen", "touch screen", "ground control", "unity", "level-up", "level up", "schwintek", "in-wall", "touch panel"):
        if phrase in t and phrase not in toks:
            toks.append(phrase)
    return [x for x in toks if x not in _STOP and not re.fullmatch(r"(19|20)\d\d", x)
            and not is_unit_token(x) and not re.fullmatch(r"\d", x)]


def identify_unit(history, user_msg: str, category_name: str, model_text: str) -> dict:
    blob = " ".join([model_text or ""] + [m.get("content", "") for m in (history or []) if m.get("role") == "user"] + [user_msg or ""])
    brand = detect_brand(model_text) or detect_brand(blob)
    if not brand and re.search(r"\d", model_text or ""):
        first = re.match(r"\s*(?:\d{4}\s+)?([A-Za-z][\w\-]+)", model_text or "")
        brand = first.group(1).lower() if first else ""  # unlisted brand (e.g. Brinkley): no OEM allowlist
    toks = model_tokens(model_text) or model_tokens(" ".join(m.get("content", "") for m in (history or []) if m.get("role") == "user") + " " + (user_msg or ""))
    # Model numbers typed in the complaint or read off the label ("Label/photo shows: ...") count too (Leader 3:29 PM).
    for t in re.findall(r"\b[a-z]{2,}-?\d{1,}[a-z0-9\-]*\b", _norm(strip_unit_values(_norm(blob)))):
        if len(t) >= 4 and t not in toks and not is_unit_token(t) and not re.search(r"\d(v|vac|vdc|amp|a|w|psi|btu|ohm|f)$", t):
            toks.append(t)
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
        # Unit type the tech states in their own words; used only when the category and model give no type (F3 confirmation).
        "stated_types": sorted(product_types(" ".join([m.get("content", "") for m in (history or []) if m.get("role") == "user"] + [user_msg or ""]))),
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
        "Type it from the data plate or add a photo of the plate.\n"
        "While you are at the unit, verify the customer complaint: operate it the way the customer does, give it time, "
        "and tell me exactly what it does (readings, panel display)."
    )


# ---------------- library adapter + document pin ----------------
class SqliteLibrary:
    """Read-only adapter over the TechTrack SQLite file (tests and RC harness)."""

    def __init__(self, path: str):
        import sqlite3

        self.c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def documents(self):
        cur = self.c.execute(
            "select d.id,d.title,coalesce(d.brand,''),coalesce(d.models,''),coalesce(d.product_line,''),"
            "coalesce(d.clean_title,''),coalesce(d.doc_number,''),coalesce(d.keywords,''),coalesce(d.revision_date,''),"
            "coalesce(c.name,''),coalesce(d.content_sha256,''),coalesce(d.file_path,'') from documents d left join categories c on c.id=d.category_id"
        )
        keys = ("id", "title", "brand", "models", "product_line", "clean_title", "doc_number", "keywords", "revision_date",
                "category", "content_sha256", "file_path")
        return [dict(zip(keys, r)) for r in cur.fetchall()]

    def page_count(self, doc_id):
        return self.c.execute("select count(distinct page) from doc_chunks where document_id=?", (doc_id,)).fetchone()[0]

    def docs_with_text(self, key, doc_ids):
        """{doc_id: text of chunks mentioning key} for candidate docs (case-insensitive, hyphens ignored)."""
        ids = set(doc_ids)
        out = {}
        for did, txt in self.c.execute("select document_id, chunk_text from doc_chunks where replace(lower(chunk_text),'-','') like ?", (f"%{key}%",)):
            if did in ids:
                out[did] = out.get(did, "") + " " + (txt or "")
        return out

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
                "category": getattr(getattr(d, "category", None), "name", "") or self._cat_name(d),
                "content_sha256": getattr(d, "content_sha256", "") or "", "file_path": getattr(d, "file_path", "") or "",
            })
        return out

    def _cat_name(self, d):
        try:
            if not hasattr(self, "_cats"):
                rows = self.s.execute(__import__("sqlalchemy").text("select id, name from categories")).fetchall()
                self._cats = {r[0]: r[1] for r in rows}
            return self._cats.get(getattr(d, "category_id", None), "")
        except Exception:
            return ""

    def page_count(self, doc_id):
        from sqlalchemy import func
        return self.s.query(func.count(func.distinct(self.C.page))).filter(self.C.document_id == doc_id).scalar() or 0

    def docs_with_text(self, key, doc_ids):
        from sqlalchemy import func
        ids = list(doc_ids)
        if not ids:
            return {}
        rows = (self.s.query(self.C.document_id, self.C.chunk_text)
                .filter(self.C.document_id.in_(ids))
                .filter(func.replace(func.lower(self.C.chunk_text), "-", "").like(f"%{key}%")).all())
        out = {}
        for did, txt in rows:
            out[did] = out.get(did, "") + " " + (txt or "")
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


# Word-bounded product-type words read from a doc's own title/product line or a unit's model text.
# No model numbers or brand names here: types are named by what the product IS.
PRODUCT_TYPES = {
    "fridge": r"refrigerat|\bfridge|freezer|ice\s*maker",
    "vent_fan": r"vent\s*fan|roof\s*vent|maxx\s*fan|fan\s*tastic|\bfantastic\s+fan",
    "tv_audio": r"\btv\b|television|stereo|soundbar|speaker",
    "toilet": r"toilet",
    "plumbing": r"water\s*pump|\bfaucet|\bsewer|\bdrain\b|\bholding\s+tank|\bpex\b|\bplumbing|\bwaste\s+valve|\bmacerat",
    "generator": r"generator|\bgenset",
    "power": r"inverter|converter|charger|transfer\s*switch|power\s*(center|cent|distribution|management)|\bbatter(y|ies)\b|\bsurge\b",
    "solar": r"\bsolar\b|charge\s*controller",
    "water_heater": r"water\s*heater|tankless",
    "furnace": r"furnace",
    "ac": r"air\s*condition|\ba/c\b|\bac\b\s+unit|rooftop\s+(unit|a/?c|air)|heat\s*pump|climate\s*control",
    "cooktop": r"cooktop|\brange\b|\boven\b|\bburner",
    "leveling": r"\blevel(ing|er|ers)?\b|\bjacks?\b|stabiliz",
    "awning": r"awning",
    "slide": r"\bslide",
    "door_window": r"\bdoors?\b|\bwindows?\b|\blatch|\block(s|set)?\b|\bscreen\s+door",
    "axle": r"\baxles?\b|suspension|\bbrakes?\b|\bhubs?\b|\bbearings?\b|equali[sz]er|\bleaf\s+spring|\btires?\b",
    "hitch": r"coupler|\bhitch|\btow(ing)?\b|pin\s*box|king\s*pin|fifth\s*wheel\s+hitch|gooseneck",
    "electronics": r"onecontrol|\btpms\b|\bcamera|\bmonitor|touch\s*(panel|screen)|control\s+(panel|board|box)|\bcontroller|\bremote\b|wireless|\bwi-?fi\b|bluetooth",
    "steps": r"\bsteps?\b|\bstair",
    "chassis": r"chassis|\bframes?\b",
}

# Document KINDS (form, bulletin, reference) are not product types: a bulletin about a leveling controller is a leveling doc.
# Kind categories map to a kind type, used only when a doc names no product and for jobs filed under that kind category.
# EVERY library/job category maps to types (F3). A category not listed here is UNMAPPED -> needs confirmation.
CATEGORY_TYPES = {
    "refrigerators": {"fridge"}, "furnaces": {"furnace"}, "water heaters": {"water_heater"},
    "air conditioning": {"ac"}, "slideouts": {"slide"}, "slide-outs": {"slide"}, "leveling": {"leveling"},
    "range & cooktops": {"cooktop"}, "plumbing / toilets": {"toilet", "plumbing"}, "awnings": {"awning"},
    "electrical": {"power", "generator", "solar", "electronics"}, "solar": {"solar", "power"},
    "id & reference": {"reference"}, "warranty forms": {"form"}, "tsb / recall": {"bulletin"},
    "recalls-bulletins": {"bulletin"}, "doors-windows": {"door_window"},
    "furrion-appliances": {"fridge", "cooktop", "ac", "vent_fan", "tv_audio", "water_heater", "furnace", "power", "electronics"},
    "axles-suspension-brakes": {"axle"}, "couplers-hitches-towing": {"hitch"},
    "electronics-onecontrol-tpms-cameras": {"electronics"}, "steps": {"steps"},
    "plumbing-sewer-water": {"plumbing", "toilet"}, "chassis-frames": {"chassis", "axle"},
}
# Categories that file documents by KIND (forms, bulletins, recalls, reference), not by product: any product doc may live there.
KIND_CATEGORIES = {"warranty forms", "tsb / recall", "recalls-bulletins", "id & reference"}
TYPE_NAMES = {"fridge": "fridge", "water_heater": "water heater", "furnace": "furnace", "ac": "A/C", "cooktop": "cooktop/range",
              "leveling": "leveling", "awning": "awning", "slide": "slide-out", "vent_fan": "vent fan", "toilet": "toilet",
              "plumbing": "plumbing", "generator": "generator", "power": "converter/inverter/power", "solar": "solar",
              "tv_audio": "TV/audio", "door_window": "door/window", "axle": "axle/brakes", "hitch": "hitch/coupler",
              "electronics": "control panel/electronics", "steps": "steps", "chassis": "chassis/frame", "form": "form",
              "bulletin": "bulletin", "reference": "reference"}

# Evidence tiers (F2 specificity). Higher = more specific. A pick needs MIN_PICK_TIER or more.
TIER_MODEL, TIER_MODEL_TEXT, TIER_SERIES, TIER_SERIES_TEXT, TIER_BRAND = 5, 4, 3, 2, 1
MIN_PICK_TIER = TIER_SERIES_TEXT
PRODUCT_LINE_PHRASES = ("ground control", "level up", "level-up", "unity", "schwintek", "touchscreen", "touch panel")


def product_types(text: str) -> set:
    t = (text or "").lower()
    return {k for k, rx in PRODUCT_TYPES.items() if re.search(rx, t)}


def model_keys(unit: dict) -> list:
    """Full model keys first, then series keys. (A) series = leading letters+digits (sw6de -> sw6, fcr08dcgta -> fcr08)
    or the part before a trim suffix (gswh-2 -> gswh). Units/ratings never reach here (model_tokens strips them)."""
    return [k for k, _ in model_key_tiers(unit)]


def model_key_tiers(unit: dict) -> list:
    """[(key, 'model'|'series')], compact (no hyphens), full model keys before series keys."""
    full, series = [], []
    for t in unit.get("tokens", []):
        if not re.search(r"\d", t) or is_unit_token(t):
            continue
        c = re.sub(r"[-.]", "", t)
        if len(c) >= 4 and c not in full:
            full.append(c)
        for s in (t.split("-")[0], (re.match(r"[a-z]+\d+", t) or [None])[0]):
            if s and re.sub(r"[-.]", "", s) != c and len(s) >= 3 and (re.search(r"[a-z]", s) and len(s) >= 3) and s not in series:
                series.append(s)
    return [(k, "model") for k in full] + [(k, "series") for k in series if k not in full]


def _field_tokens(text: str) -> set:
    """Doc field -> alnum tokens; hyphenated tokens give both the joined form and each part (FCR08DCGTA-BL -> fcr08dcgtabl, fcr08dcgta, bl)."""
    out = set()
    for raw in re.split(r"[^a-z0-9\-.]+", _norm(text)):
        raw = raw.strip("-.")
        if not raw:
            continue
        out.add(re.sub(r"[-.]", "", raw))
        out.update(p for p in re.split(r"[-.]", raw) if p)
    return out


def _key_in(key: str, toks: set, kind: str) -> bool:
    """A full model key matches a doc token exactly. A series key matches a token equal to it or that continues with a
    LETTER (sw6 -> sw6de, sw6del) but not a digit (sw6 !-> sw60)."""
    if key in toks:
        return True
    if kind == "series":
        return any(t.startswith(key) and len(t) > len(key) and t[len(key)].isalpha() for t in toks)
    return False


def doc_product_types(doc: dict) -> set:
    """The doc's own words decide its type (title / clean title / product line); its filing category is used only
    when the doc names no type. Content beats filing (a misfiled range is still a range)."""
    own = product_types(" ".join(str(doc.get(k, "") or "") for k in ("title", "clean_title", "product_line")))
    if own:
        return own
    return set(CATEGORY_TYPES.get((doc.get("category") or "").strip().lower(), set()))


def unit_product_types(unit: dict) -> set:
    """Allowed doc types for the job: category (authoritative) + type words in the model text. If neither gives a type,
    the type the tech STATES in their own messages counts (that is the answer to the confirmation question)."""
    cat = set(CATEGORY_TYPES.get((unit.get("category") or "").strip().lower(), set()))
    t = cat | product_types(unit.get("model", ""))
    return t or set(unit.get("stated_types") or ())


def type_needs_confirmation(unit: dict) -> bool:
    return not unit_product_types(unit)


def doc_evidence(unit: dict, doc: dict, page_text: str = "") -> tuple:
    """(tier, key_len, where). Structured fields (title/models/doc number/clean title/product line) beat keywords and page text;
    a full model key beats a series key."""
    tiers = model_key_tiers(unit)
    meta = _field_tokens(" ".join(str(doc.get(k, "") or "") for k in ("title", "models", "doc_number", "clean_title", "product_line")))
    soft = _field_tokens(str(doc.get("keywords", "") or "") + " " + (page_text or ""))
    best = (0, 0, "")
    for key, kind in tiers:
        for toks, tier_model, tier_series, where in ((meta, TIER_MODEL, TIER_SERIES, "fields"), (soft, TIER_MODEL_TEXT, TIER_SERIES_TEXT, "text")):
            if _key_in(key, toks, kind):
                cand = (tier_model if kind == "model" else tier_series, len(key), where)
                best = max(best, cand)
    if best[0] < TIER_SERIES:
        blob = _norm(" ".join(str(doc.get(k, "") or "") for k in ("title", "product_line", "clean_title", "models")))
        for ph in PRODUCT_LINE_PHRASES:
            if ph in unit.get("tokens", []) and ph in blob:
                best = max(best, (TIER_SERIES, len(ph), "product line"))
    return best


def model_hit_len(unit: dict, doc: dict) -> int:
    """Back-compat: key length of the best model/series evidence in the doc's fields+keywords (0 = none)."""
    return doc_evidence(unit, doc)[1]


def doc_eligible(unit: dict, doc: dict, tier: int) -> str:
    """'' if the doc may be pinned, else why not. Hard filters: brand, then product type (never skipped)."""
    ub, db = unit.get("brand") or "", _doc_brand(doc)
    if ub and db and ub != db:
        return "other brand"
    if not db and tier < TIER_MODEL_TEXT:
        return "doc brand unknown and no exact model match"
    if not ub and tier < TIER_MODEL_TEXT:
        return "unit brand unknown and no exact model match"
    ut, dt = unit_product_types(unit), doc_product_types(doc)
    if not ut:
        return "unit type not confirmed"
    if not dt:
        return "doc type unknown"
    if not (ut & dt):
        return "wrong product type"
    return ""


def _doc_kind(doc: dict) -> int:
    """General preference between documents for the SAME evidence: a troubleshooting/service manual over a plain manual over a
    write-up / warranty form (forms carry no diagnostic steps)."""
    tl = str(doc.get("title", "")).lower()
    if re.search(r"write-?up|warranty|\bform\b|\bclaim\b", tl):
        return 0
    return 2 if re.search(r"trouble\s*shoot|diagnos|service\s+(manual|and\s+training|&\s+training)|repair\s+manual", tl) else 1


def _identity_keys(doc: dict) -> set:
    """Same manual = same file hash, same doc number, or same normalized title (duplicate uploads)."""
    keys = set()
    if doc.get("content_sha256"):
        keys.add("h:" + doc["content_sha256"].lower())
    for n in re.split(r"[;,]", str(doc.get("doc_number") or "")):
        n = re.sub(r"[^a-z0-9]", "", n.lower())
        if len(n) >= 5:
            keys.add("n:" + n)
    t = re.sub(r"[^a-z0-9]", "", str(doc.get("title", "")).lower())
    if len(t) >= 12:
        keys.add("t:" + t)
    return keys or {"id:" + str(doc.get("id"))}


def _distinct_manuals(docs: list) -> int:
    """Number of different manuals among docs (union of shared identity keys)."""
    groups = []
    for d in docs:
        k = _identity_keys(d)
        hit = [g for g in groups if g & k]
        merged = set(k).union(*hit) if hit else set(k)
        groups = [g for g in groups if g not in hit] + [merged]
    return len(groups)


def _matched_key(unit: dict, doc: dict, page_text: str = "") -> str:
    """The most specific model/series key this doc carries (used to tell 'same model' from 'different models')."""
    meta = _field_tokens(" ".join(str(doc.get(k, "") or "") for k in ("title", "models", "doc_number", "clean_title", "product_line")))
    soft = _field_tokens(str(doc.get("keywords", "") or "") + " " + (page_text or ""))
    for key, kind in model_key_tiers(unit):
        if _key_in(key, meta, kind) or _key_in(key, soft, kind):
            return key
    return ""


def _one_per_manual(docs: list) -> list:
    """Collapse duplicate uploads of one manual (shared hash / doc number / title) to one representative (lowest id)."""
    groups = []
    for d in sorted(docs, key=lambda x: x["id"]):
        k = _identity_keys(d)
        for g in groups:
            if g["keys"] & k:
                g["keys"] |= k
                break
        else:
            groups.append({"keys": set(k), "doc": d})
    return [g["doc"] for g in groups]


def set_kind_rank(doc: dict) -> int:
    """Order inside an equal-evidence set (Leader 5:21 PM): service/troubleshooting > installation > owner > other > bulletin > form."""
    tl = " ".join(str(doc.get(k, "") or "") for k in ("title", "clean_title")).lower()
    if re.search(r"write-?up|warranty|\bform\b|\bclaim\b|flat\s*rate", tl):
        return 0
    if re.search(r"trouble\s*shoot|diagnos|service|repair\s+manual", tl):
        return 5
    if re.search(r"install", tl):
        return 4
    if re.search(r"owner|operat|user'?s?\s+(manual|guide)", tl):
        return 3
    if re.search(r"bulletin|recall|\btsb\b|notice", tl):
        return 1
    return 2


def _page_count(library, doc: dict) -> int:
    fn = getattr(library, "page_count", None)
    if fn:
        try:
            return int(fn(doc["id"]) or 0)
        except Exception:
            return 0
    if doc.get("pages") is not None:
        return int(doc.get("pages") or 0)
    return 0


def _rev_key(doc: dict) -> str:
    """Newest revision first; digits only so '2026-03-17' and '03/2026' sort as dates where possible."""
    r = str(doc.get("revision_date") or "")
    m = re.search(r"(\d{4})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?", r) or None
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3) or 0):02d}"
    m = re.search(r"(\d{1,2})[-/.](\d{4})", r)
    return f"{m.group(2)}{int(m.group(1)):02d}00" if m else ""


def rank_manual_set(library, docs: list) -> list:
    """Deterministic order for an equal-evidence same-model set, independent of read order:
    doc kind, newest revision, more pages, then a content key (doc number / normalized title), then id."""
    def key(d):
        content = (str(d.get("doc_number") or "").lower(), re.sub(r"[^a-z0-9]", "", str(d.get("title", "")).lower()))
        return (-set_kind_rank(d), _neg(_rev_key(d)), -_page_count(library, d), content, d["id"])
    return sorted(docs, key=key)


def _neg(s: str) -> str:
    """Sort helper: newest (largest) date string first, empty last."""
    return "".join(chr(0x7f - ord(c)) for c in s) if s else "\x7f" * 9


def _model_count(doc: dict) -> int:
    return len([m for m in re.split(r"[;,]", str(doc.get("models") or "")) if m.strip()])


def no_manual_line(unit: dict, how: str = "none", detail: str = "") -> str:
    t = sorted(unit_product_types(unit))
    shown = [x for x in unit.get("tokens", []) if re.search(r"\d", x) and re.sub(r"[-.]", "", x) in model_keys(unit)]
    model = (shown[0] if shown else " ".join(model_keys(unit)[:1])).upper()
    if how == "needs_confirmation":
        return (f"Confirm the unit type before I pick a manual{(' for ' + detail) if detail else ''}: "
                "what kind of unit is it (for example refrigerator, water heater, furnace, A/C, leveling, slide-out)?")
    what = " ".join(x for x in ((unit.get("brand") or "").title(), model, TYPE_NAMES.get(t[0], "") if t else "") if x)
    if how == "ambiguous":
        return f"Several different {what or 'matching'} manuals match equally ({detail}); not guessing - checking the official site"
    return f"No {what or 'matching'} manual found"


def _text_hits(library, keys, doc_ids) -> dict:
    """{doc_id: page text that mentions a key}, only for the given candidate docs. Uses library.docs_with_text when the
    adapter has it (one query per key), else nothing (test fixtures)."""
    fn = getattr(library, "docs_with_text", None)
    if not fn or not keys or not doc_ids:
        return {}
    out = {}
    for k in keys:
        for did, txt in (fn(k, doc_ids) or {}).items():
            out[did] = out.get(did, "") + " " + txt
    return out


def select_manual(library, unit: dict, exclude_ids=(), available=None) -> dict:
    """THE manual selector for every search (GD, library search, Bay PDF, rule 11).

    1. Type gate first: no job type (unmapped category, no type word, none stated) -> how='needs_confirmation' (ask the tech).
    2. Evidence per doc (specificity): exact model in fields (5) > exact model in keywords/page text (4) > series in fields (3)
       > series in keywords/page text or product-line phrase (2) > brand only (1). A pick needs tier >= 2.
    3. Hard filters: brand (no borrowing) and product type.
    4. Best (tier, key length, doc kind). If the best group holds DIFFERENT manuals -> how='ambiguous', no pick (web lookup runs).
       Duplicate uploads of one manual are one manual (identity: hash / doc number / title).
    5. available(doc) -> bool (e.g. the PDF file can be fetched): an unavailable doc is skipped and the next group is tried.
    6. Exact-model docs that exist only under another product type -> how='needs_confirmation' (category may be wrong).
    Returns {"doc", "how": exact|series|ambiguous|needs_confirmation|none, "tier", "miss_line", "rejected": [(id, reason)]}.
    """
    rejected = []
    if type_needs_confirmation(unit):
        return {"doc": None, "how": "needs_confirmation", "tier": 0, "miss_line": no_manual_line(unit, "needs_confirmation"), "rejected": rejected}
    docs = [d for d in library.documents() if d["id"] not in exclude_ids]
    keys = [k for k, _ in model_key_tiers(unit)]
    ub = unit.get("brand") or ""
    text_ids = [d["id"] for d in docs if not ub or _doc_brand(d) in ("", ub)]
    page = _text_hits(library, keys, text_ids) if keys else {}
    scored, wrong_type_exact = [], []
    for d in docs:
        tier, klen, where = doc_evidence(unit, d, page.get(d["id"], ""))
        if tier < MIN_PICK_TIER:
            continue
        why = doc_eligible(unit, d, tier)
        if why:
            rejected.append((d["id"], why))
            if why == "wrong product type" and tier >= TIER_MODEL_TEXT and _doc_brand(d) in ("", ub):
                wrong_type_exact.append(d)
            continue
        # Specificity order: evidence tier, key length, doc kind, then a doc written for fewer models (more specific to this unit).
        scored.append(((tier, klen), d))
    scored.sort(key=lambda x: x[0], reverse=True)
    i = 0
    while i < len(scored):
        top = scored[i][0]
        group = [d for k, d in scored if k == top]
        i += len(group)
        ok = []
        for d in group:
            if available is not None and not available(d):
                rejected.append((d["id"], "file unreachable"))
                continue
            ok.append(d)
        if not ok:
            continue
        manuals = _one_per_manual(ok)
        keys = {_matched_key(unit, d, page.get(d["id"], "")) for d in manuals}
        types = [doc_product_types(d) & unit_product_types(unit) for d in manuals]
        if len(manuals) > 1 and (len(keys) > 1 or not set.intersection(*types)):
            # Equal evidence but DIFFERENT models or product types: not the same unit's documentation -> web lookup.
            ids = ", ".join(str(d["id"]) for d in manuals[:5])
            return {"doc": None, "docs": [], "how": "ambiguous", "tier": top[0], "miss_line": no_manual_line(unit, "ambiguous", f"docs {ids}"),
                    "rejected": rejected, "tied": [d["id"] for d in manuals]}
        ranked = rank_manual_set(library, manuals)
        how = "exact" if top[0] >= TIER_MODEL_TEXT else "series"
        if len(ranked) > 1:
            how += "_set"
        return {"doc": ranked[0], "docs": ranked, "how": how, "tier": top[0], "miss_line": "", "rejected": rejected}
    if wrong_type_exact:
        kinds = sorted({TYPE_NAMES.get(t, t) for d in wrong_type_exact for t in doc_product_types(d)})
        unit_c = dict(unit, stated_types=())
        return {"doc": None, "how": "needs_confirmation", "tier": 0,
                "miss_line": no_manual_line(unit_c, "needs_confirmation",
                                            f"{([x for x in unit.get('tokens', []) if re.search(r'[0-9]', x)] or [''])[0].upper()} (the library has it as {', '.join(kinds)}, not {unit.get('category') or 'this category'})"),
                "rejected": rejected}
    return {"doc": None, "how": "none", "tier": 0, "miss_line": no_manual_line(unit), "rejected": rejected}


def pin_document(library, unit: dict, exclude_ids=()) -> dict | None:
    """Back-compat wrapper (rule 11 imports this): same answer as select_manual."""
    return select_manual(library, unit, exclude_ids)["doc"]


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


SET_READ_MAX = 3


def load_section_set(library, docs: list, symptom: str = "") -> dict:
    """Read the troubleshooting section across an equal-evidence same-model set (ranked by rank_manual_set).
    Every page marker names its source doc, so each cited page can be attributed: [PAGE n | <doc title>]."""
    docs = [d for d in (docs or []) if d][:SET_READ_MAX]
    if len(docs) <= 1:
        sect = load_section(library.chunks(docs[0]["id"]), symptom) if docs else {"pages": [], "text": "", "mode": "empty", "thin": True}
        sect["titles"] = [docs[0].get("title", "")] if docs else []
        return sect
    parts, pages, modes, titles = [], [], [], []
    for d in docs:
        sec = load_section(library.chunks(d["id"]), symptom)
        if not sec.get("text"):
            continue
        title = d.get("title", "")
        titles.append(title)
        parts.append(re.sub(r"\[PAGE (\d+)\]", lambda m: f"[PAGE {m.group(1)} | {title}]", sec["text"]))
        pages += [f"{title} p.{p}" for p in sec["pages"]]
        modes.append(sec["mode"])
    text = "\n\n".join(parts)
    return {"pages": pages, "text": text, "mode": "section" if "section" in modes else (modes[0] if modes else "empty"),
            "thin": len(text) < THIN_SECTION_CHARS, "titles": titles}


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

NO_SPECIAL_TESTER_RULE = """
Never REQUIRE a proprietary tester (e.g. Peacemaker/AC bypass tool). If you mention one, give the component-by-component isolation
with a meter as the primary path (capacitor, fan motor, compressor windings/amps, relays/board), so a tech without it can finish.
"""

PAIRED_RULE = """
Paired/synchronized mechanisms (slide columns/motors left+right, jack pairs): when the symptom involves both sides (room runs crooked,
both motors strain), evaluate BOTH sides and recommend the repair on both as a matched set at the assembly level the source lists,
followed by re-adjustment/sync and cycle verification. Print part numbers only when they appear in the source text above.
When a component is condemned and the tech asks whether anything else needs checking, either name the one remaining check or commit to the repair.
"""

WARRANTY_SHOP_RULE = """
RULE 9 - the user is a WARRANTY SHOP tech, never a consumer. Never say "call a technician / contact a service agent / have it serviced".
When the source says contact an authorized service agent / the OEM, or a part is not field-serviceable or not on the parts list:
tell the tech to document the findings and submit them to the OEM for authorization, and output a block titled
"OEM AUTHORIZATION FINDINGS" with: Complaint verified (how); Tests and readings (each); Ruled out; Manual page showing the part is not
field-serviceable (or "not on the parts list"); Requested authorization (e.g. replace complete unit).
"""

VERIFY_FIRST_RULE = """
STEP ONE (official rule 8): the complaint is NOT yet verified. Your first lines must have the tech VERIFY THE CUSTOMER COMPLAINT:
operate the unit as the customer would, give it the time it needs (e.g. pull-down time for a fridge/AC), and measure/observe the symptom
(temps, voltages, what the panel shows). Ask for the result. No diagnostic tests or part calls until the complaint is verified.
A safety line may come first.
"""

NPF_RULE = f"""
If the verification shows the unit WORKS AS DESIGNED (complaint not reproduced, readings normal), say "No Problem Found - operating as designed",
give a short customer explanation in plain words (why it seemed wrong), and condemn NO part. Otherwise continue the diagnostic walk.
NEVER call No Problem Found while the tech reports the complaint is still present. First run the manual's DIFFERENTIATING checks.
NPF READINESS: before No Problem Found, the tech must also have INSPECTED the path the complaint depends on (open the access/cover on that path
and check for ice, debris, blockage, leaks or loose parts) and reported it. Operating the unit alone is not enough.
SPLIT RULE: if the complaint reproduces through one path but not another (e.g. a bypass, direct power, or an alternate control works),
the fault is in the part only the failing path uses: isolate and repair that part.
"""
PENDING_RULE = """
DECISIVE TEST NOT AVAILABLE YET: the tech cannot do the deciding test now. Give the REPAIR DECISION from the manual: for each possible
result, the repair with its page citation, plus the shop/OEM tech-line escalation. Do not just repeat the test.
"""

UNITY_NOT_SURE_RULE = """
ONECONTROL / UNITY = NOT SURE: before the load-specific tests, walk the tech through identifying the controller: find the OneControl/Unity
controller (or confirm none exists), read its label: model (e.g. Unity X270D) and IDS part #. When the tech reports it, the Unity path
applies if it is a OneControl/Unity board; if there is none, continue without the Unity path.
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
    facts = pin.get("facts") or {}
    if facts:
        sysmsg += "\nFACTS ON FILE (already reported by the tech; NEVER ask for these again, build on them):\n" + "\n".join(f"- {k}: {v}" for k, v in facts.items()) + "\n"
    if facts.get("label_diagram"):
        sysmsg += ("\nUNIT LABEL / DIAGRAM (tech-reported; this unit's own wiring - it beats general knowledge): " + facts["label_diagram"] +
                   "\nUse it: check every fuse, breaker and lead it shows AT THE UNIT (e.g. an inline fuse on the red lead) before sending the tech "
                   "to the coach distribution panel. Ask where that inline fuse sits if the tech hasn't said.\n")
    if "plugs" not in facts:
        sysmsg += "\nInclude one plug/connector seating check (controller, panel and motor connectors for this circuit) early in the walk unless the tech already reported it.\n"
    sysmsg += NO_SPECIAL_TESTER_RULE + PAIRED_RULE + WARRANTY_SHOP_RULE
    if not facts.get("complaint_verified"):
        sysmsg += VERIFY_FIRST_RULE
    else:
        sysmsg += NPF_RULE
    if pin.get("unity_mode") == "identify":
        sysmsg += UNITY_NOT_SURE_RULE
    if pin.get("unavailable"):
        sysmsg += PENDING_RULE
        sysmsg += ("\nSTEPS THE TECH COULD NOT DO (never ask them again): \n- " + "\n- ".join(pin["unavailable"][-6:]) +
                   "\nUse an alternate test that isolates the same thing, or move to the next step. If the results already isolate the fault "
                   "(e.g. motor runs on direct 12 V, wiring good, no output from the controller/panel), give the repair now.\n")
    twice = [" ".join(a[0][-1]) for a in (pin.get("asks") or []) if a[1] >= REPEAT_MAX_ASKS]
    if twice:
        sysmsg += ("\nNO-REPEAT RULE: these tests were already asked twice. NEVER ask them again. Accept the tech's answer (a normal/OK "
                   "result counts as recorded), and either give the next different step or route to shop/OEM authorization:\n- "
                   + "\n- ".join(twice[-8:]) + "\n")
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
    pages = set()
    for p in pin.get("pages") or []:  # ints (one manual) or "<title> p.N" (a manual set)
        m = re.search(r"(\d+)$", str(p))
        if m:
            pages.add(int(m.group(1)))
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


# ---------------- GD guard: never condemn a part before its isolation reading is recorded (Leader 5:21 PM) ----------------
CONDEMN_RE = re.compile(
    r"\b(?:replace|replacing|condemn(?:ed)?|install\s+(?:a\s+)?new|order\s+(?:a\s+)?(?:new|replacement))\s+(?:the\s+|a\s+|an\s+|this\s+)?"
    r"(?P<part>[a-z0-9][a-z0-9\-/ ]{2,60}?)(?=\s*(?:[.,;:()\[\n]|$|\s(?:and|with|then|if|because|per|now|assembly|as)\b))"
    r"|\b(?:the\s+)?(?P<part2>[a-z0-9][a-z0-9\-/]{2,30}(?:\s[a-z0-9\-/]{2,30})?)\s+is\s+(?:bad|faulty|failed|defective|dead|shorted|the\s+fault)\b",
    re.I,
)
ISOLATION_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:v|vac|vdc|volts?|ohms?|Ω|k\s*ohms?|a|amps?|ma|psi|°\s*[fc]?|deg)\b|\b(?:continuity|no\s+continuity|open\s+circuit|"
    r"reads?\s+(?:open|ol|0|zero)|\bol\b|shorted|short\s+to\s+ground|blown|open\b|jumper(?:ed)?|bypass(?:ed)?|direct\s+(?:12v\s+)?power|"
    r"runs?\s+on\s+(?:direct|jumper)|no\s+(?:power|voltage)\s+(?:at|to|out))",
    re.I,
)
_PART_STOP = {"the", "a", "an", "it", "this", "part", "parts", "no", "new", "complete", "whole", "entire", "same", "one", "assembly", "assemblies", "kit",
              "both", "matched", "set", "pair"}


def _part_heads(part: str) -> set:
    """The part's noun: last word before any location phrase ('15A inline fuse in the front holder' -> fuse)."""
    core = re.split(r"(?<=\w)\s(?:in|on|at|of|from|inside|behind|under|near|for|part|p/n|fully|together|now|instead|first|as|both)\b",
                    (part or "").lower().strip())[0]
    words = [w for w in re.findall(r"[a-z0-9]+", core) if w not in _PART_STOP and len(w) >= 3 and not re.fullmatch(r"\d+[a-z]?", w)]
    return {words[-1].rstrip("s")} if words else set()


# Words that name the same component class: a request naming one names the others.
_PART_SYNONYMS = [{"pcb", "board"}]


def _part_words(part: str) -> set:
    """Every identifying word of the part ('inverter pcb' -> {inverter, pcb, board}); a request/answer naming any of them names the part."""
    words = _part_words_raw(part)
    for group in _PART_SYNONYMS:
        if words & group:
            words |= group
    return words


def _part_words_raw(part: str) -> set:
    core = re.split(r"(?<=\w)\s(?:in|on|at|of|from|inside|behind|under|near|for|part|p/n|fully|together|now|instead|first|as|both)\b",
                    (part or "").lower().strip())[0]
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", core)
            if w not in _PART_STOP and w not in _PART_GENERIC and len(w) >= 3 and not re.fullmatch(r"\d+[a-z]?", w)} | _part_heads(part)


# Position/side words never identify a part on their own.
_PART_GENERIC = {"front", "rear", "left", "right", "top", "bottom", "upper", "lower", "lead", "main", "inside", "outside", "interior",
                 "exterior", "old", "driver", "passenger", "curb", "road", "side"}


def _clauses(line: str) -> list:
    """Sentences of one reply line ('Replace X. Do not replace Y.' -> two)."""
    return [x for x in re.split(r"(?<=[.;!?])\s+(?=[A-Z(])", line or "") if x.strip()]


def _negated(sentence: str) -> bool:
    return bool(NEGATED_CONDEMN_RE.search(sentence) or NO_REPLACE_RE.search(sentence)
                or re.search(r"\bcondemn\w*\s+(?:no|none|nothing)\b", sentence, re.I))


_NEG_BEFORE_RE = re.compile(r"(?:\bdo\s+not|\bdon.?t|\bnever|\bno\s+need\s+to|\bnot\s+yet|\bnot|\bno|\bwithout)\s+(?:\w+\s+){0,2}$", re.I)


def _verb_negated(text: str, start: int) -> bool:
    return bool(_NEG_BEFORE_RE.search(text[max(0, start - 30):start]))


def unnegated_condemn(line: str) -> bool:
    """True when some condemn/replace verb in the line is not itself negated ('Replace X (do not replace Y)' -> True)."""
    for rx in (CONDEMN_RE, REPLACE_ANY_RE):
        for m in rx.finditer(line or ""):
            if not _verb_negated(line, m.start()) and not re.search(r"\bcondemn\w*\s+(?:no|none|nothing)\b", m.group(0), re.I):
                return True
    return False


# A conditional whose condition is counterfactual or declared already met ('If they would still drift (matches what you already
# have), replace ...') is not a repair decision awaiting a result: while a test is pending it is treated as unconditional.
COUNTERFACTUAL_RE = re.compile(r"\bwould\b|\bmatches\b|\balready\s+(?:have|has|had|show\w*|recorded|seen)\b|\bas\s+expected\b", re.I)


def _counterfactual_conditional(line: str) -> bool:
    if not CONDITIONAL_LINE_RE.match(line or ""):
        return False
    m = REPLACE_ANY_RE.search(line) or CONDEMN_RE.search(line)
    return bool(m and COUNTERFACTUAL_RE.search(line[:m.start()]))


def condemned_parts(reply: str) -> list:
    out = []
    for m in CONDEMN_RE.finditer(reply or ""):
        if _verb_negated(reply, m.start()) or re.search(r"\bcondemn\w*\s+(?:no|none|nothing)\b", m.group(0), re.I):
            continue
        part = (m.group("part") or m.group("part2") or "").strip()
        if part and _part_heads(part) and part.lower() not in out:
            out.append(part.lower())
    return out


# A tech's test RESULT without a number: names a test and gives its outcome ("Winding and ground checks look normal/OK").
# A visual "plugs look seated/OK" is not a test result. A meter value is preferred, not required.
TEST_RESULT_RE = re.compile(
    r"\b(?:check(?:s|ed)?|test(?:s|ed)?|reading|reads?|measur\w*|ohm(?:s|ed)?|meter(?:ed)?|winding|ground|isolation|continuity|volt(?:s|age)?)\b.{0,60}?"
    r"\b(?:normal|ok|okay|good|fine|pass(?:ed|es)?|in\s+spec|within\s+spec|correct)\b"
    r"|\b(?:normal|ok|okay|good|fine|pass(?:ed|es)?|in\s+spec)\b.{0,30}?\b(?:check(?:s|ed)?|test(?:s|ed)?|reading)\b",
    re.I,
)
WHOLE_UNIT_HEADS = {"unit", "appliance", "rooftop"}


def session_tests(history: list, user_msg: str = "") -> list:
    """Every (GD request, tech answer) pair of the session, oldest first. The answer's request is the GD message just before it."""
    pairs, last_gd = [], ""
    for m in list(history or []) + ([{"role": "user", "content": user_msg}] if user_msg else []):
        if m.get("role") == "assistant":
            last_gd = m.get("content", "") or ""
        elif m.get("role") == "user":
            pairs.append((last_gd, m.get("content", "") or ""))
    return pairs


# A test the tech reports as not done (pending, not in the notes, skipped, not checked) is NOT a result, even when the same
# sentence adds "looks normal/OK": nothing was measured.
NOT_DONE_RE = re.compile(r"\b(?:pending|not\s+(?:yet\s+)?(?:done|completed|checked|tested)|"
                         r"isn.?t\s+done|aren.?t\s+done|"
                         r"haven.?t\s+(?:done|checked|tested|run)|didn.?t\s+(?:do|check|test|run|get)|skipped|no\s+result\s+(?:yet|recorded))\b", re.I)
PENDING_TEST_WORD_RE = re.compile(r"\b(?:test\w*|check\w*|unplug\w*|isolat\w*|reading|jump\w*|jumper\w*|bypass\w*|measur\w*|volt\w*|ohm\w*|"
                                  r"continuity|pressure|plumbing|leak[- ]?down|swap\s+test|tech[- ]line)\b", re.I)


def _is_result(sentence: str) -> bool:
    if NOT_DONE_RE.search(sentence or ""):
        return False
    return bool(ISOLATION_RE.search(sentence) or TEST_RESULT_RE.search(sentence))


def _sents(msg: str) -> list:
    return [x.strip() for x in re.split(r"(?<=[.;!?])\s+|\n+|\s+[\u2014-]\s+", msg or "") if x.strip()]


_PENDING_GENERIC = {"anything", "nothing", "yet", "haven", "didn", "checked", "check", "run", "ran", "tested", "test", "done", "still",
                    "notes", "any", "all", "everything", "pending", "get", "got", "separate", "are", "was", "were", "is"}


def pending_isolation_tests(tech_msgs: list) -> list:
    """Isolation tests the tech reported as not done and has not reported a result for since. Each entry: the tech's sentence."""
    pend = []  # [(sig, sentence)]
    for msg in tech_msgs or []:
        for sent in _sents(msg):
            sig = frozenset(w for w in _ask_sig(NOT_DONE_RE.sub(" ", sent)) if w not in _PENDING_GENERIC)
            if NOT_DONE_RE.search(sent) and PENDING_TEST_WORD_RE.search(sent):
                if sig and not any(_overlap(sig, p[0]) for p in pend):
                    pend.append((sig, sent))
            elif _is_result(sent.lower()) and sig:
                pend = [p for p in pend if not _overlap(sig, p[0])]
    return [p[1] for p in pend]


def _overlap(a: frozenset, b: frozenset) -> bool:
    return bool(a) and bool(b) and len(a & b) / max(1, min(len(a), len(b))) >= 0.5


REPLACE_ANY_RE = re.compile(r"\b(?:replace[sd]?|replacing|replacement|condemn(?:s|ed)?|install\s+(?:a\s+)?new|order\s+(?:a\s+)?(?:new|replacement)|swap\s+(?:in|out|the)|r\s*&\s*r)\b", re.I)


NO_REPLACE_RE = re.compile(r"\bno\s+(?:\w+\s+){0,2}(?:r\s*&\s*r|replacement|swap)\b", re.I)


# A line that presumes a replacement goes ahead ('commit to the repair', 'Did both cartridges go in?', 'Which repair did you
# complete?') is a replace directive in other words.
PRESUMED_REPLACE_RE = re.compile(r"\bcommit\s+to\s+the\s+(?:repair|replacement|swap|part)|\bproceed\s+with\s+the\s+(?:repair|replacement|swap)\b|"
                                 r"\bgo\s+ahead\s+(?:and\s+)?(?:replace|install|swap|order)\b|\bdid\s+(?:the\s+|both\s+)?(?:new\s+)?(?:\w+\s+){0,3}go\s+in\b|"
                                 r"\bwhich\s+(?:repair|part|replacement)s?\s+did\s+you\b", re.I)


def hold_while_pending(reply: str, pending: list) -> str:
    """While an isolation test is pending, NO condemn/replace line survives: unconditional, conditional ('If <x>, replace ...'),
    counterfactual, tech-proposed or OEM replacement request alike, and no line that presumes the replacement went ahead.
    A conditional's condition can already be met by recorded results (RC20 215fce8 turn 6), so a conditional is not a safe
    exemption; the repair plan returns once the pending result is recorded. Verify/after-repair follow-ups stay."""
    if not pending:
        return reply
    out, held = [], False
    for line in (reply or "").splitlines():
        if (((unnegated_condemn(line) and not REPAIR_FOLLOW_RE.search(line)) or PRESUMED_REPLACE_RE.search(line))
                and not re.match(r"\s*before\s+condemning\b", line, re.I)):
            if not held:
                out.append(f"Hold all part replacement: an isolation test is still pending (\"{pending[0][:140]}\"). No part is replaced or "
                           f"submitted for replacement until that result is recorded. Do that test, or call the shop/OEM tech line with the "
                           f"findings so far. [{LABEL_GENERAL}]")
                held = True
            continue
        out.append(line)
    return "\n".join(out)



def isolation_recorded(part: str, tech_msgs: list, requests: list = None) -> bool:
    """True when the session holds a recorded test of the part: a tech sentence with a reading OR a test result (normal/OK) that
    either names the part itself or answers a GD request that named the part. A whole-unit call (unit/appliance/rooftop) is an
    elimination conclusion: it needs at least one recorded test result in the session."""
    heads = _part_words(part)
    reqs = list(requests) if requests is not None else [""] * len(tech_msgs or [])
    reqs += [""] * (len(tech_msgs or []) - len(reqs))
    named = lambda text: any(re.search(r"\b" + re.escape(h) + r"s?\b", (text or "").lower()) for h in heads)
    whole = bool(_part_heads(part) & WHOLE_UNIT_HEADS)
    for msg, req in zip(tech_msgs or [], reqs):
        for low in re.split(r"(?<=[.;!?])\s+|\n+", (msg or "").lower()):
            if not _is_result(low):
                continue
            if whole or named(low) or (req and named(req)):
                return True
    return False


# (c) Observation counts as isolation for a MECHANICAL failure when it is recorded against the part AND the pinned manual gives no
# electrical test for that part/failure.
MECH_OBS_RE = re.compile(r"\b(?:bind\w*|flex\w*|deflect\w*|crooked|out\s+of\s+(?:sync|square|level)|racking|seiz\w*|stuck|grind\w*|slip\w*|"
                         r"skip\w*|drags?|dragging|drifts?|drifting|leaks?\s+down|won.?t\s+(?:turn|rotate|move)|wobbl\w*|cracked|broken|stripped)\b", re.I)
ELECTRICAL_TEST_RE = re.compile(r"\b(?:volt\w*|vdc|vac|ohm\w*|amp(?:s|erage)?|continuity|meter|resistance)\b", re.I)
# A bypass/direct-power/alternate-control result in a message that names the part (the split test) is that part's isolation.
SPLIT_RESULT_RE = re.compile(r"\b(?:bypass\w*|jumper\w*|direct\s+(?:12\s*v\s+)?power|peacemaker|alternate\s+control)\b[^.\n]{0,40}\b(?:cools?|works?|runs?|operates?|heats?|lights?)\b", re.I)


def manual_has_electrical_test(part: str, section_text: str) -> bool:
    words = _part_words(part)
    for sent in re.split(r"(?<=[.;!?])\s+|\n+", (section_text or "").lower()):
        if ELECTRICAL_TEST_RE.search(sent) and any(re.search(r"\b" + re.escape(w) + r"s?\b", sent) for w in words):
            return True
    return False


def mechanical_observation_recorded(part: str, tech_msgs: list, requests: list, section_text: str) -> bool:
    """The observation must name the part's own noun (valve, motor, gearbox), not the system it sits in."""
    if manual_has_electrical_test(part, section_text):
        return False
    words = _part_heads(part)
    named = lambda t: any(re.search(r"\b" + re.escape(w) + r"s?\b", (t or "").lower()) for w in words)
    reqs = list(requests or []) + [""] * max(0, len(tech_msgs or []) - len(requests or []))
    for msg, req in zip(tech_msgs or [], reqs):
        for sent in re.split(r"(?<=[.;!?])\s+|\n+", (msg or "").lower()):
            if MECH_OBS_RE.search(sent) and (named(sent) or (req and named(req))):
                return True
    return False


def split_result_recorded(part: str, tech_msgs: list) -> bool:
    words = _part_words(part)
    return any(SPLIT_RESULT_RE.search(m or "") and any(re.search(r"\b" + re.escape(w) + r"s?\b", (m or "").lower()) for w in words)
               for m in tech_msgs or [])


# Adjust/synchronize before condemn: when the pinned manual has adjustment or synchronization procedures, one must be recorded first.
ADJUST_RE = re.compile(r"\b(?:synchroniz\w*|re-?sync\w*|cable\s+(?:tension|adjust\w*)|adjust\w*\s+(?:the\s+)?(?:\w+\s+)?cables?|"
                       r"take\s+(?:the\s+)?slack|re-?learn|erase[- ]learn|zero[- ]point|re-?index|re-?time|timing\s+mark)\b", re.I)


def manual_adjust_steps(section_text: str) -> list:
    return [l.strip() for l in re.split(r"(?<=[.;!?])\s+|\n+", section_text or "") if ADJUST_RE.search(l)][:3]


def adjustment_recorded(tech_msgs: list, requests: list) -> bool:
    reqs = list(requests or []) + [""] * max(0, len(tech_msgs or []) - len(requests or []))
    for msg, req in zip(tech_msgs or [], reqs):
        if ADJUST_RE.search(msg or "") or (req and ADJUST_RE.search(req) and (msg or "").strip() and not NOT_CHECKED_RE.search(msg or "")):
            return True
    return False


def unproven_condemns(reply: str, tech_msgs: list, requests: list = None, section_text: str = "") -> list:
    out = []
    for p in condemned_parts(reply):
        if isolation_recorded(p, tech_msgs, requests) or split_result_recorded(p, tech_msgs):
            continue
        if mechanical_observation_recorded(p, tech_msgs, requests, section_text):
            continue
        out.append(p)
    return out


def unadjusted_condemns(reply: str, tech_msgs: list, requests: list, section_text: str) -> list:
    """Parts condemned while the manual's adjustment/synchronization step is still unrecorded."""
    if not manual_adjust_steps(section_text) or adjustment_recorded(tech_msgs, requests):
        return []
    return condemned_parts(reply)


def hold_for_adjustment(reply: str, parts: list, section_text: str) -> str:
    steps = manual_adjust_steps(section_text)
    out = []
    for line in (reply or "").splitlines():
        if any(p in line.lower() for p in parts) and CONDEMN_RE.search(line):
            out.append(f"Before condemning the {parts[0]}, do the manual's adjustment/synchronization step and report the result: "
                       f"{steps[0][:220]} [{LABEL_GENERAL}]")
        else:
            out.append(line)
    return "\n".join(out)


# NPF guard: never call No Problem Found while the complaint is still reported present.
NPF_CALL_RE = re.compile(r"\b(?:no\s+problem\s+found|operating\s+as\s+designed|works\s+as\s+designed)\b", re.I)
STILL_PRESENT_RE = re.compile(r"\b(?:still|continues?\s+to)\b[^.\n]{0,40}\b(?:not|isn.?t|won.?t|doesn.?t|no)\b|\bcomplaint\s+(?:is\s+)?(?:still\s+)?present\b|"
                              r"\bstill\s+(?:crooked|leaks?|drifts?|dead|warm|hot|cold|noisy|tripping|faults?)\b", re.I)


def npf_blocked(reply: str, tech_msgs: list) -> str:
    """The tech sentence showing the complaint is still present, when the reply calls NPF; else ''."""
    if not NPF_CALL_RE.search(reply or ""):
        return ""
    for msg in reversed(tech_msgs or []):
        for sent in re.split(r"(?<=[.;!?\]])\s+|\n+", msg or ""):
            if STILL_PRESENT_RE.search(sent):
                return sent.strip()
    return ""


INSPECTION_RESULT_RE = re.compile(r"\b(?:no\s+(?:ice|frost\s+build-?up|debris|blockage|obstruction|leaks?|damage|corrosion|restriction)|"
                                  r"(?:clear|unobstructed|unrestricted|clean)\b[^.\n]{0,30}\b(?:passage|path|duct|vent|line|coil|filter)|"
                                  r"(?:removed|pulled|opened)\s+(?:the\s+)?[\w\s-]{0,25}?(?:cover|panel|access)\b[^.\n]{0,80}\b(?:no|clear|ok|normal|good))", re.I)


REPAIR_DONE_RE = re.compile(r"\b(?:after\s+(?:the\s+)?(?:re-?seat\w*|repair|replacement|adjustment|re-?calibration|realign\w*|reposition\w*)|replaced|re-?seat\w*\s+(?:already\s+)?done|re-?seated|seated\s+it|fix\s+(?:is\s+)?complete|already\s+(?:aimed|bent|seated|adjusted)|"
                            r"zero\s*point\s+calibration[^.\n]{0,60}\bset\b|installed|adjusted|re-?calibrated|calibrated|zero[- ]point\s+(?:set|done)|"
                            r"re-?positioned|repositioned|realigned|reoriented|re-?aimed|tightened|snugged|re-?synced|reprogrammed|flashed|"
                            r"cleaned|repaired|bent)\b", re.I)


def npf_unready(reply: str, tech_msgs: list) -> bool:
    """True when the reply calls NPF but no tech sentence records an inspection of the complaint's path."""
    if not NPF_CALL_RE.search(reply or ""):
        return False
    if any(REPAIR_DONE_RE.search(m or "") for m in tech_msgs or []):  # "as designed" after a repair is a close-out, not an NPF
        return False
    return not any(INSPECTION_RESULT_RE.search(x) and not NOT_DONE_RE.search(x) for m in tech_msgs or [] for x in _sents(m))


def hold_npf_inspection(reply: str) -> str:
    kept = [l for l in (reply or "").splitlines() if not NPF_CALL_RE.search(l) and not re.match(r"\s*customer\s+explanation\b", l, re.I)]
    kept.insert(0, "Not No Problem Found yet: the complaint did not reproduce, but the path it depends on has not been inspected. Open the "
                   "access/cover on that path and check for ice, debris, blockage, leaks or loose parts, then report what you found (for a "
                   f"compartment that is not cold: the interior airflow cover and the passage behind it). [{LABEL_GENERAL}]")
    return "\n".join(kept)


def hold_npf(reply: str, evidence: str) -> str:
    kept = [l for l in (reply or "").splitlines() if not NPF_CALL_RE.search(l)]
    kept.insert(0, f"Not No Problem Found: the complaint is still present (\"{evidence[:160]}\"). Run the manual's differentiating check "
                   f"next; if another path (bypass, direct power, alternate control) works, the fault is in the part only the failing path uses. [{LABEL_GENERAL}]")
    return "\n".join(kept)


# ---- NO-REPEAT rule: GD never asks for the same test a third time ----
ASK_LINE_RE = re.compile(r"\b(?:report|probe|measure|read|check|test|clamp|send|tell me)\b", re.I)
REPEAT_MAX_ASKS = 2
_ASK_STOP = {"the", "a", "an", "and", "or", "to", "of", "on", "at", "in", "it", "is", "each", "then", "same", "report", "power", "off",
             "general", "trade", "knowledge", "library", "good", "bad", "not", "with", "for", "your", "all", "three", "those"}


def _ask_sig(line: str) -> frozenset:
    line = re.sub(r"\[(?:library|general|web)[^\]]*\]", " ", line or "", flags=re.I)
    return frozenset(w for w in re.findall(r"[a-z]{3,}", line.lower()) if w not in _ASK_STOP)


def _same_ask(a: frozenset, b: frozenset) -> bool:
    return bool(a) and bool(b) and len(a & b) / max(1, len(a | b)) >= 0.6


# The repair itself and its post-repair verify are directions, not test requests: never capped.
REPAIR_FOLLOW_RE = re.compile(r"\bverify\b|\breconnect\b|after (?:the |both )?(?:repair|swap|replac\w*|new|parts?)|\b(?:swapped|installed)\b", re.I)


def ask_counts(pin: dict) -> list:
    return pin.setdefault("asks", [])  # [[sig words, ...], count]: one group per test request; every wording is kept


def cap_repeats(reply: str, pin: dict, last_answer: str = "") -> str:
    """Drop any ask line already asked REPEAT_MAX_ASKS times; when that leaves no ask, accept the answer and route on.
    A request group keeps every wording it was asked in, so a re-worded third ask still matches (similarity is not transitive)."""
    asks = ask_counts(pin)
    kept, capped, bumped = [], [], set()
    for line in (reply or "").splitlines():
        repair_line = bool(CONDEMN_RE.search(line) or REPAIR_FOLLOW_RE.search(line))
        sig = _ask_sig(line) if ASK_LINE_RE.search(line) and not repair_line else frozenset()
        if not sig:
            kept.append(line); continue
        gi = next((i for i, a in enumerate(asks) if any(_same_ask(sig, frozenset(w)) for w in a[0])), None)
        if gi is not None and asks[gi][1] >= REPEAT_MAX_ASKS and gi not in bumped:
            capped.append(line.strip()); continue
        if gi is None:
            asks.append([[sorted(sig)], 1]); bumped.add(len(asks) - 1)
        else:
            if sorted(sig) not in asks[gi][0]:
                asks[gi][0].append(sorted(sig))
            if gi not in bumped:  # several lines of one reply asking the same test count once
                asks[gi][1] += 1; bumped.add(gi)
        kept.append(line)
    if not capped:
        return reply
    pin.setdefault("repeat_capped", []).extend(capped)
    if not any(ASK_LINE_RE.search(l) or CONDEMN_RE.search(l) for l in kept):
        ans = (last_answer or "").strip()
        kept.append(("Accepted as reported: \"" + ans[:160] + "\". " if ans else "Accepted as reported. ") +
                    "That test has been asked twice and will not be asked again. If the recorded results isolate a part that is not "
                    "field-serviceable, document the findings and submit them to the OEM for authorization; otherwise go to the next "
                    f"step in the section. [{LABEL_GENERAL}]")
    return "\n".join(kept)


# Upstream-first sequence: when a reply directs an unconditional correction "first" (supply, feed, ground, connection, setting),
# a part condemned in the same reply waits for that correction's result; the manual's "correct X first, then replace Y if it remains".
FIRST_FIX_RE = re.compile(r"\b(?:correct|repair|fix|restore|bring|re-?establish)\b[^\n]{0,90}\bfirst\b|^\s*first[,:]?\s+(?:correct|repair|fix|restore)\b",
                          re.I)
CONDITIONAL_LINE_RE = re.compile(r"^\s*(?:if|when|once|should|after)\b", re.I)
NEGATED_CONDEMN_RE = re.compile(r"\b(?:do\s+not|don.?t|never|no\s+need\s+to|not\s+yet)\s+(?:\w+\s+){0,2}(?:replace|condemn|order)\b", re.I)


def first_fix_line(reply: str) -> str:
    for line in (reply or "").splitlines():
        if FIRST_FIX_RE.search(line) and not CONDITIONAL_LINE_RE.match(line) and not CONDEMN_RE.search(line):
            return line.strip()
    return ""


def sequence_condemns(reply: str) -> str:
    """Make each unconditional condemn line conditional on the upstream 'first' correction given in the same reply."""
    first = first_fix_line(reply)
    if not first:
        return reply
    step = re.sub(r"\s*\[[^\]]*\]\s*$", "", first)[:160].rstrip(" .")
    out = []
    for line in (reply or "").splitlines():
        if (CONDEMN_RE.search(line) and unnegated_condemn(line) and not CONDITIONAL_LINE_RE.match(line)
                and line.strip() != first and not REPAIR_FOLLOW_RE.search(line)):
            body = line.strip()
            out.append(f"Only if the complaint remains after that first correction ({step}): {body[0].lower() + body[1:]}")
        else:
            out.append(line)
    return "\n".join(out)


def hold_condemns(reply: str, parts: list) -> str:
    """Rewrite each line that condemns an unproven part into the isolation-reading ask."""
    out = []
    for line in (reply or "").splitlines():
        hit = [p for p in parts if p in line.lower() and CONDEMN_RE.search(line)]
        if hit:
            out.append(f"Before condemning the {hit[0]}, record its isolation reading (the meter value or jumper/bypass result at the "
                       f"{hit[0]} itself) and send it. [{LABEL_GENERAL}]")
        else:
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
    if (pin.get("unit") or {}).get("brand") not in ("", None, "lippert"):
        return  # another brand's own controller (e.g. BAL) is not OneControl-managed
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
    pin["pages"] = sorted(pages, key=str)


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


# Reported facts: once in session state, never asked again (Leader 2026-10-16).
FACT_PATTERNS = {
    "complaint_verified": re.compile(r"\b(verif\w*|confirm\w*|reproduc\w*|duplicat\w*|ran\s+(it|the)|operated|tested\s+it|works?\s+as\s+designed|could\s*n.t\s+reproduce|reached|got\s+down\s+to|temps?\b|degrees|\d+\s*°?\s*f\b)", re.I),
    "lcd_text": re.compile(r"\b(lcd|screen|display|touch\s*pad|touchpad|panel)\b.*\b(shows?|says|reads|display\w*|blank|ready|error)\b", re.I),
    "fault_code": re.compile(r"\b(e\d{1,2}|er\d{1,2}|code\s+\w+|fault\s+code|no\s+(fault|error)\s+code|motor\s+fault|blinking\s+\d)\b", re.I),
    "unity_label": re.compile(r"\b(ids\s*(part)?\s*#?|x270\w*|label\s+says|unity\s+(board|controller)\s+label|no\s+onecontrol|not\s+(a\s+)?onecontrol)\b", re.I),
    "fuses": re.compile(r"\b(fuses?|breakers?)\b", re.I),
    "motor_fault": re.compile(r"\bmotor\s+fault\b", re.I),
    "zero_point_done": re.compile(r"\bzero[\s-]?point\b.*\b(done|complete\w*|finished|calibrated)\b", re.I),
    "plugs": re.compile(r"\b(plugs?|connectors?|connections?|harness)\b.*\b(seated|checked|tight|good|ok|fine|loose)\b|\bno\s+loose\s+connections\b", re.I),
    "label_diagram": re.compile(r"\b(label|sticker|data\s*plate|wiring\s*diagram|circuit\s*diagram|schematic)\b.*\b(shows?|says|reads|fuse|amp|\d+\s*a\b|lead|wire)", re.I),
    "input_voltage": re.compile(r"\b\d+(\.\d+)?\s*v(dc|ac)?\b|\bvoltage\s+(good|ok|correct)\b", re.I),
}
ASK_PATTERNS = {
    "lcd_text": re.compile(r"\b(lcd|screen|display|touch\s*pad)\b.*\b(text|message|code|shows?|read)\b", re.I),
    "unity_label": re.compile(r"\b(label|ids|part\s*(number|#))\b", re.I),
    "fuses": re.compile(r"\b(fuses?|breakers?)\b", re.I),
    "motor_fault": re.compile(r"\bmotor\s+fault\b", re.I),
    "zero_point_done": re.compile(r"\bzero[\s-]?point\b", re.I),
    "plugs": re.compile(r"\b(plugs?|connectors?)\b.*\b(seat\w*|check|tight)\b", re.I),
    "complaint_verified": re.compile(r"\b(verify|confirm|reproduce|operate)\b.*\b(complaint|problem|symptom|unit)\b", re.I),
}


UNAVAILABLE_RE = re.compile(r"\b(pending|not\s+(?:done|available)\s+yet|isn.?t\s+done|not\s+recorded|can.?t\s+(get|do|measure|reach|access)|unable\s+to|no\s+way\s+to|don.?t\s+have\s+(a|the)|n/?a\b|not\s+available)", re.I)


def _norm_step(text: str) -> str:
    lines = [l for l in (text or "").splitlines() if l.strip() and not l.startswith(("Safety first", "Using:", "No manual"))]
    return re.sub(r"[^a-z0-9]+", " ", " ".join(lines).lower()).strip()


def is_repeat(reply: str, history: list) -> bool:
    prev = [m.get("content", "") for m in (history or []) if m.get("role") == "assistant"][-1:]
    if not prev:
        return False
    a, b = set(_norm_step(reply).split()), set(_norm_step(prev[0]).split())
    return bool(a) and len(a & b) / max(1, len(a | b)) > 0.8


def record_facts(pin: dict, user_msg: str) -> None:
    if user_msg and UNAVAILABLE_RE.search(user_msg):
        pin.setdefault("unavailable", []).append(user_msg.strip()[:300])
    if not user_msg or NOT_CHECKED_RE.search(user_msg):
        return
    facts = pin.setdefault("facts", {})
    for key, rx in FACT_PATTERNS.items():
        if key == "complaint_verified" and pin.get("turns", 0) == 0 and not re.search(r"verif|confirm|reproduc|ran |operated|tested", user_msg, re.I):
            continue  # the customer complaint itself is not a verification
        if rx.search(user_msg) and key not in facts:
            facts[key] = user_msg.strip()[:300]


CONSUMER_RE = re.compile(r"(call|contact|consult|have)\s+(a|an|your)\s+(qualified\s+|certified\s+|authorized\s+|local\s+)*(technician|service\s+(agent|center|tech)|dealer|professional)[^.\n]*\.?", re.I)


def shop_voice(reply: str) -> str:
    """Rule 9: consumer 'call a technician' lines become the shop's OEM-authorization step."""
    return CONSUMER_RE.sub("document the findings and submit them to the OEM for authorization.", reply or "")


def drop_reasks(reply: str, pin: dict) -> str:
    """Remove a line that asks again for a fact already on file. Keeps procedure lines that only mention it."""
    facts = pin.get("facts") or {}
    if not facts:
        return reply
    kept, dropped = [], 0
    for line in (reply or "").splitlines():
        asks = bool(re.search(r"\?|\b(report|send|tell me|read|check|confirm|find|locate)\b", line, re.I))
        hit = any(k in facts and rx.search(line) for k, rx in ASK_PATTERNS.items())
        if asks and hit and not re.search(r"\bverify\b|VERIFY|after the (repair|new)|\bre-?(run|check)\b", line):
            dropped += 1
            continue
        kept.append(line)
    out = "\n".join(kept).strip()
    return out if out and dropped < len(kept) + dropped else reply


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
    carry = {}
    if pin and pin.get("mode") == "no_manual" and set(model_keys(unit)) - set(model_keys(pin["unit"])) \
            and pin_document(library, unit, exclude_ids=exclude_doc_ids):
        # A model number arrived later (complaint, label text/photo): re-pin with the real manual, keep what the tech reported.
        carry = {k: pin[k] for k in ("facts", "turns", "unavailable", "checked") if k in pin}
        pin = None
    if not pin:
        if not unit["identified"]:
            reply = unit_question(unit)
            log_turn(log_path, {"stage": "identify", "seconds": round(time.time() - t0, 2)})
            return {"reply": reply, "mode": "identify", "pin": None, "usage": {}, "seconds": round(time.time() - t0, 2)}
        sel = select_manual(library, unit, exclude_ids=exclude_doc_ids)
        if sel["how"] == "needs_confirmation":
            # F3: no confirmed unit type (unmapped category, or the model only exists under another type): ask, never skip the gate.
            log_turn(log_path, {"stage": "confirm_type", "seconds": round(time.time() - t0, 2)})
            return {"reply": sel["miss_line"], "mode": "confirm_type", "pin": None, "usage": {}, "seconds": round(time.time() - t0, 2)}
        pin = {"unit": unit, "checked": {}, "fault_code_asked": False, "web": {}, "selection": {"how": sel["how"], "tier": sel.get("tier", 0)}}
        pin.update(carry)
        doc = sel["doc"]
        sect = load_section_set(library, sel.get("docs") or ([doc] if doc else []), user_msg + " " + model_text) if doc else {"thin": True}
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
            # No same-brand manual in the library or on an official site: never borrow another brand.
            doc = {"id": None, "title": "NO MANUAL", "url": ""}
            sect = {"pages": [], "text": (
                f"NO {unit.get('brand') or ''} {unit.get('model')} MANUAL in the shop library or on an official OEM site. "
                f"Every step must be tagged [{LABEL_GENERAL}]. Never state brand- or model-specific specs; say 'spec not available - "
                "confirm with the OEM' instead. Never use another brand's manual."), "mode": "no_manual"}
        web_src = bool(doc.get("url"))
        pin.update({
            "doc_id": doc.get("id"), "doc_title": doc.get("title", ""), "url": doc.get("url", ""),
            "revision": doc.get("revision_date", ""),
            "source_label": (f"{LABEL_WEB}: {doc['url']}" if web_src else
                             (LABEL_GENERAL if doc.get("title") == "NO MANUAL" else
                              f"{LABEL_LIBRARY}: " + " + ".join(sect.get("titles") or [doc.get("title", "")]))),
            "set_docs": [{"id": d.get("id"), "title": d.get("title", "")} for d in (sel.get("docs") or [])] if not web_src else [],
            "pages": sect["pages"], "section_text": sect["text"], "mode": sect["mode"],
            "needs_fault_code": bool(FAULT_CODE_HINT_RE.search(sect["text"])),
            "turns": 0,
        })
        apply_unity_path(pin, library, unity_gate, user_msg + " " + model_text + " " + category_name, exclude_doc_ids, web_get)
        if (unity_gate or "").strip() == "Not sure" and ONECONTROL_COMPLAINT_RE.search(user_msg + " " + model_text + " " + category_name) \
                and unit.get("brand") in ("", "lippert"):
            pin["unity_mode"] = "identify"
        record_facts(pin, user_msg)
        pin_store["gd_pin"] = pin
    else:
        update_step_state(pin, history, user_msg)
        record_facts(pin, user_msg)
        if pin.get("unity_mode") == "identify" and "unity_label" in (pin.get("facts") or {}):
            if re.search(r"no\s+onecontrol|not\s+(a\s+)?onecontrol|no\s+unity|none", pin["facts"]["unity_label"], re.I):
                pin["unity_mode"] = "no"
            else:
                pin["unity_mode"] = "yes"
                apply_unity_path(pin, library, "Yes", user_msg + " " + model_text + " " + category_name + " " + " ".join(m.get("content", "") for m in history if m.get("role") == "user"), exclude_doc_ids, web_get)
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
    if is_repeat(reply, history):
        pin["repeats"] = pin.get("repeats", 0) + 1
        retry = msgs + [{"role": "assistant", "content": reply},
                            {"role": "user", "content": "You repeated your previous step word for word. The tech already answered it. "
                             "Do NOT repeat it. Give the next different step, or the repair if the evidence already isolates the fault."}]
        try:
            again = chat_fn(retry, REPLY_MAX_TOKENS, LATER_REASONING)
            u2 = usage_fn() if usage_fn else {}
            usage = {k: (usage.get(k, 0) + u2.get(k, 0)) if isinstance(u2.get(k), int) else u2.get(k, usage.get(k))
                     for k in set(usage) | set(u2)}
            usage["repeat_retry"] = True
            if again and again.strip() and not is_repeat(again, history):
                reply = again.strip()
        except Exception:
            pass
    pairs = session_tests(history, user_msg)
    tech_msgs, requests = [a for _, a in pairs], [q for q, _ in pairs]
    sec = pin.get("section_text", "")
    npf_ev = npf_blocked(reply, tech_msgs)
    if npf_ev:
        reply = hold_npf(reply, npf_ev)
        pin.setdefault("npf_held", []).append(npf_ev[:200])
    elif npf_unready(reply, tech_msgs):
        reply = hold_npf_inspection(reply)
        pin.setdefault("npf_held", []).append("no inspection recorded")
    held = unproven_condemns(reply, tech_msgs, requests, sec)
    if held:  # deterministic hold, no extra model call (one primary call per turn)
        reply = hold_condemns(reply, held)
        pin.setdefault("condemn_held", []).extend(held)
    unadj = unadjusted_condemns(reply, tech_msgs, requests, sec)
    if unadj:
        reply = hold_for_adjustment(reply, unadj, sec)
        pin.setdefault("adjust_held", []).extend(unadj)
    pend = pending_isolation_tests(tech_msgs)
    if pend:
        hp = hold_while_pending(reply, pend)
        if hp != reply:
            pin.setdefault("pending_held", []).append(pend[0][:200])
            reply = hp
    seq = sequence_condemns(reply)
    if seq != reply:
        pin.setdefault("sequence_held", []).append(first_fix_line(reply)[:200])
        reply = seq
    reply = drop_reasks(reply, pin)
    reply = cap_repeats(reply, pin, user_msg)
    reply = shop_voice(reply)
    reply = enforce_labels(reply, pin)
    reply = ensure_verify(reply) if re.search(r"calibrat|replace|program|resync", reply, re.I) else reply
    if first:
        if pin["mode"] == "no_manual":
            kind = {"fridge": "fridge", "water_heater": "water heater", "furnace": "furnace", "ac": "A/C", "cooktop": "cooktop",
                    "leveling": "leveling", "awning": "awning", "slide": "slide-out", "vent_fan": "vent fan"}
            t = sorted(product_types(unit.get("model", "") + " " + unit.get("category", "")))
            what = f"{(unit.get('brand') or '').title()} {kind.get(t[0], '') if t else ''}".strip() or "this unit"
            head = (f"No {what} manual found in the library or on an official OEM site - using the unit label if you have it, "
                    "otherwise steps below are general trade knowledge.")
        else:
            if len(pin.get("set_docs") or []) > 1:
                head = (f"Using {len(pin['set_docs'])} manuals for this model (each step cites its page's manual): "
                        + "; ".join(d["title"] for d in pin["set_docs"][:SET_READ_MAX]) + ".")
            else:
                head = f"Using: {pin['doc_title']}" + (f" ({pin['url']})" if pin.get("url") else "") + f" - read {pin['mode'].replace('_',' ')}, pages {pin['pages'][0]}-{pin['pages'][-1]}."
        reply = SAFETY_LINE + "\n" + head + "\n" + reply
    if pin.get("needs_fault_code") and re.search(r"fault|error|code", reply, re.I):
        pin["fault_code_asked"] = True
    pin["turns"] = pin.get("turns", 0) + 1
    secs = round(time.time() - t0, 2)
    ctx_chars = sum(len(m.get("content") or "") for m in msgs)
    web_calls = 0
    try:
        web_calls = int(((pin.get("web") or {}).get("search_usage") or {}).get("server_side_tool_usage_details", {}).get("web_search_calls") or 0)
    except Exception:
        web_calls = 0
    pin["web_calls_session"] = web_calls
    rec = {"stage": "walk", "first": first, "web_calls_session": web_calls, "web_calls_flag_over_12": web_calls > 12, "messages_sent": len(msgs), "context_chars_sent": ctx_chars,
           "section_chars": len(pin.get("section_text") or ""), "unity_ref_chars": len(pin.get("unity_text") or ""),
           "max_tokens": REPLY_MAX_TOKENS, "doc": pin["doc_title"], "mode": pin["mode"], "effort": effort,
           "usage": usage, "cost_usd": turn_cost(usage) if usage else None, "seconds": secs}
    log_turn(log_path, rec)
    return {"reply": reply, "mode": pin["mode"], "pin": pin, "usage": usage, "seconds": secs, "reduced": reduced, "cost_usd": rec["cost_usd"], "context_chars_sent": ctx_chars}


# ---------------- Rule 10: warranty story from recorded facts only ----------------
TAG_RE = re.compile(r"\[(Library:[^\]]*|Manufacturer site:[^\]]*|General trade knowledge|INFERRED[^\]]*)\]")
REPAIR_RE = re.compile(r"\b(replaced|installed|repaired|reseated|adjusted|calibrat\w*|realigned|re-?aligned|resynced|tightened|no problem found|npf|operating as designed)\b", re.I)


OUTCOME_RE = re.compile(r"\b(works|working|fixed|resolved|tested\s+good|now\s+\w+s\b|verified|operat\w+\s+(normally|correctly|as\s+designed)|job\s+complete|cools|cooling|heats|levels|powers?\s+(up|on)|powered\s+(up|on)|back\s+on|lights?\s+(on|up)|runs|running)\b", re.I)
NPF_RE = re.compile(r"\b(no\s+problem\s+found|npf|operating\s+as\s+designed|works\s+as\s+designed)\b", re.I)


def warranty_story(pin: dict, history: list, model_text: str = "") -> str:
    """Complaint / findings / tests / cause / correction built ONLY from what the tech typed and the sources GD cited.

    Deterministic: no model call, so no reading can be invented. Tech text is quoted verbatim.
    """
    pin = pin or {}
    msgs = [m for m in (history or []) if m.get("role") in ("user", "assistant")]
    users = [(i, m["content"].strip()) for i, m in enumerate(msgs) if m["role"] == "user" and (m.get("content") or "").strip()]
    if not users:
        return "No session recorded."
    complaint = users[0][1]
    facts = pin.get("facts") or {}
    verified = facts.get("complaint_verified", "")
    tests = []
    for i, text in users[1:]:
        if text == verified:
            continue
        prev = next((msgs[j]["content"] for j in range(i - 1, -1, -1) if msgs[j]["role"] == "assistant"), "")
        tags = sorted(set(TAG_RE.findall(prev))) or ["source not cited"]
        tests.append(f"- {text}\n  (step source: {'; '.join(tags)})")
    last_gd = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant"), "")
    repairs = [t for _, t in users[1:] if (REPAIR_RE.search(t) and OUTCOME_RE.search(t)) or NPF_RE.search(t)]
    escalated = "OEM AUTHORIZATION FINDINGS" in "\n".join(m["content"] for m in msgs if m["role"] == "assistant")
    unit = (pin.get("unit") or {}).get("model") or model_text or "not recorded"
    out = [
        f"UNIT: {unit}",
        "",
        "1. CUSTOMER COMPLAINT",
        complaint,
        "",
        "2. ON-ARRIVAL FINDINGS (complaint verification)",
        verified or "Not recorded in this session.",
        "",
        "3. TESTS AND READINGS (tech's recorded words, with the manual source of each step)",
        "\n".join(tests) or "None recorded.",
        "",
        "4. CAUSE",
        ("Per the tests above; GD's last diagnosis: " + _first_line(last_gd)) if tests else "Not determined in this session.",
        "",
        "5. CORRECTION",
        repairs[-1] if repairs else ("OPEN - pending OEM authorization." if escalated else "OPEN - no correction recorded in this session."),
    ]
    if escalated:
        out += ["", "OEM AUTHORIZATION: this story is the submission (rule 9). Requested authorization per GD's findings block above."]
    return "\n".join(out)


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        l = line.strip()
        if l and not l.startswith(("Safety first", "Using:", "No manual")):
            return l[:400]
    return "not recorded"
