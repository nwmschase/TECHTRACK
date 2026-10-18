"""LEGACY manual selector (moved out of gd_official.py on branch fresh-core).

NOT used by Guided Diagnostics any more: GD now asks the page-finder (gd_pages.py ->
/workspace/techtrack-fresh/library). This file only keeps the Bay PDF builder and the
Ask-tab coach working until FIX-PLAN phase 5/6 moves them onto the page-finder too,
then it is deleted. Crude by design (exact model tokens, regex product types):
see DECISION-INVENTORY.md A1-A6, B1-B9. Do not add to it.
"""
from __future__ import annotations


import json
import os
import re
import subprocess
import tempfile
import time

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
KNOWN_BRANDS = tuple(sorted(set(OFFICIAL_DOMAINS) | set(BRAND_ALIASES), key=lambda b: (-len(b), b)))  # deterministic ties (A1)

NO_TAG_RE = re.compile(r"\b(no\s+(model\s+)?(tag|label|data\s*plate)|model\s+(unknown|not\s+known|not\s+recovered)|can'?t\s+find\s+(the\s+)?(tag|label|model))", re.I)


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
