"""Library category audit (R1). One general rule, no doc ids:

A document's own words (title / clean title / product line) name its product type (product_types).
Its filing category must map to a type set that includes that type (category_types: curated map, else
learned from the category name and the documents filed in it, so new categories need no code change). If not, the doc is
MISFILED and the proposed category is the library category whose type set contains the doc's types, choosing the most
specific category (fewest mapped types), then the one already holding the most documents. A category with no type map is
reported as UNMAPPED. Manager Tools: dry run -> confirm -> backup -> apply -> rollback. Idempotent (a clean library plans 0).
"""
import json
import re
from datetime import datetime

MODULE_REVISION = "v4.20.11"

# ---------------------------------------------------------------- product / category types
# v4.20.9 (Chase t1729u "delete"): moved here from the old manual picker module (deleted). Only the type maps
# the category audit uses came along; the picker, brand detection and scoring are gone.
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
KIND_WORDS = r"\bforms?\b|bulletin|recall|\btsb\b|reference"   # a category named by document kind, not product
TYPE_NAMES = {"fridge": "fridge", "water_heater": "water heater", "furnace": "furnace", "ac": "A/C", "cooktop": "cooktop/range",
              "leveling": "leveling", "awning": "awning", "slide": "slide-out", "vent_fan": "vent fan", "toilet": "toilet",
              "plumbing": "plumbing", "generator": "generator", "power": "converter/inverter/power", "solar": "solar",
              "tv_audio": "TV/audio", "door_window": "door/window", "axle": "axle/brakes", "hitch": "hitch/coupler",
              "electronics": "control panel/electronics", "steps": "steps", "chassis": "chassis/frame", "form": "form",
              "bulletin": "bulletin", "reference": "reference"}

_LEARNED_CATEGORY_TYPES = {}
CATEGORY_TYPE_SHARE = 0.3   # a type named by >= 30% of a category's typed docs belongs to that category


def product_types(text: str) -> set:
    t = (text or "").lower()
    return {k for k, rx in PRODUCT_TYPES.items() if re.search(rx, t)}


def learn_categories(docs) -> None:
    """Category -> product-type sets learned from the library rows (dicts with title, clean_title, product_line,
    category): a category's own name plus the types >= CATEGORY_TYPE_SHARE of its typed documents name. Idempotent."""
    global _LEARNED_CATEGORY_TYPES
    per_cat = {}
    for d in docs or ():
        cat = (d.get("category") or "").strip().lower()
        if cat:
            own = product_types(" ".join(str(d.get(k, "") or "") for k in ("title", "clean_title", "product_line")))
            per_cat.setdefault(cat, []).append(own)
    learned = {}
    for cat, owns in per_cat.items():
        typed = [o for o in owns if o]
        counts = {}
        for o in typed:
            for t in o:
                counts[t] = counts.get(t, 0) + 1
        learned[cat] = product_types(cat) | {t for t, n in counts.items() if n >= max(1.0, CATEGORY_TYPE_SHARE * len(typed))}
    _LEARNED_CATEGORY_TYPES = learned


def category_types(category: str):
    """Product types of a library/job category: the curated map where it has the category, else what the library
    itself shows (its name + its documents). None when nothing is known (unmapped)."""
    key = (category or "").strip().lower()
    if key in CATEGORY_TYPES:
        return set(CATEGORY_TYPES[key])
    if key in _LEARNED_CATEGORY_TYPES and _LEARNED_CATEGORY_TYPES[key]:
        return set(_LEARNED_CATEGORY_TYPES[key])
    if key and (key in KIND_CATEGORIES or re.search(KIND_WORDS, key)):
        return set()
    named = product_types(key)
    return named or None

MIN_BODY_HITS = 5
# Component types: controls, wiring/power, chassis and running gear show up inside every product's docs (a jack controller,
# an A/C thermostat board, a leveling chassis hookup). A doc whose OWN type is only a component is consistent with its
# category when the category's product words occur anywhere in its page text or keywords.
COMPONENT_TYPES = {"electronics", "power", "chassis", "axle"}


def _cats(cur):
    return {cid: name for cid, name in cur.execute("SELECT id, name FROM categories").fetchall()}


def _doc_rows(cur, cats):
    rows = cur.execute("SELECT title, COALESCE(clean_title,''), COALESCE(product_line,''), COALESCE(brand,''), category_id FROM documents").fetchall()
    return [dict(title=t, clean_title=c, product_line=p, brand=b, category=cats.get(cid, "")) for t, c, p, b, cid in rows]


def doc_own_types(title, clean_title="", product_line="") -> set:
    return product_types(" ".join(x or "" for x in (title, clean_title, product_line)))


def body_type_counts(con, doc_id) -> dict:
    """How often each product type's words occur in the doc's indexed page text."""
    cur = con.cursor()
    text = " ".join(t or "" for (t,) in cur.execute("SELECT chunk_text FROM doc_chunks WHERE document_id = ?", (doc_id,)).fetchall()).lower()
    return {k: len(re.findall(rx, text)) for k, rx in PRODUCT_TYPES.items() if re.search(rx, text)}


def dominant(counts: dict) -> set:
    """Types whose words occur at least half as often as the most frequent type (empty if no text)."""
    if not counts or max(counts.values()) < MIN_BODY_HITS:
        return set()  # too little indexed text to say anything (1-page sheets, image-only scans)
    top = max(counts.values())
    return {k for k, n in counts.items() if n * 2 >= top}


def plan(con, body_types=None) -> dict:
    """{'moves': [...], 'unmapped_categories': [...], 'no_target': [...], 'checked': n}. Read-only.

    A doc is MISFILED only when BOTH its title type and its page-text dominant type are outside the category's types
    (title and body agree it is something else). Kind categories (forms, bulletins, reference) are not audited.
    """
    body_types = body_types or (lambda did: body_type_counts(con, did))
    cur = con.cursor()
    cats = _cats(cur)
    counts = dict(cur.execute("SELECT category_id, COUNT(*) FROM documents GROUP BY category_id").fetchall())
    learn_categories(_doc_rows(cur, cats))
    ctypes = {cid: category_types(name) for cid, name in cats.items()}
    unmapped = [{"category_id": cid, "category": cats[cid], "docs": counts.get(cid, 0)} for cid, t in ctypes.items() if t is None]
    moves, no_target, checked, review = [], [], 0, []
    rows = cur.execute("SELECT id, title, COALESCE(clean_title,''), COALESCE(product_line,''), category_id FROM documents ORDER BY id").fetchall()
    for did, title, clean, pl, cid in rows:
        own = doc_own_types(title, clean, pl)
        have = ctypes.get(cid)
        if not own or not have or (cats.get(cid) or "").strip().lower() in KIND_CATEGORIES:
            continue
        checked += 1
        if own & have:
            continue
        counts = body_types(did)
        if own <= COMPONENT_TYPES:
            kw = product_types(cur.execute("SELECT COALESCE(keywords,'') FROM documents WHERE id = ?", (did,)).fetchone()[0])
            if (set(counts) | kw) & have:
                continue
        body = dominant(counts)
        if body & have:
            if not (body & own):
                # Filing agrees with the page text; the TITLE / product line is what's wrong (e.g. an OCR'd first line).
                review.append({"doc_id": did, "title": (title or "")[:80], "title_types": ", ".join(sorted(own)),
                               "body_types": ", ".join(sorted(body)), "category": cats.get(cid), "status": "metadata review (title)"})
            continue  # the page text says it does belong here
        if body and not (body & own):
            own = own | body
        options = [(len(t), -counts.get(c, 0), c) for c, t in ctypes.items() if t and own <= t] or \
                  [(len(t) - len(own & t) * 10, -counts.get(c, 0), c) for c, t in ctypes.items() if t and own & t]
        if not options:
            no_target.append({"doc_id": did, "title": title, "types": sorted(own), "category": cats.get(cid)})
            continue
        to = min(options)[2]
        moves.append({"doc_id": did, "title": (title or "")[:80], "types": ", ".join(sorted(own)),
                      "from_id": cid, "from": cats.get(cid), "to_id": to, "to": cats[to], "status": "will change"})
    return {"moves": moves, "unmapped_categories": unmapped, "no_target": no_target, "checked": checked, "metadata_review": review}


def apply(con, moves: list) -> dict:
    """Apply planned moves (documents.category_id + doc_chunks.category_id). Guarded by the current category. Returns the undo record."""
    cur = con.cursor()
    undo = {"at": datetime.now().isoformat(timespec="seconds"), "rows": []}
    for r in moves:
        if r.get("status") != "will change":
            continue
        cur.execute("UPDATE documents SET category_id = ? WHERE id = ? AND category_id = ?", (r["to_id"], r["doc_id"], r["from_id"]))
        if cur.rowcount:
            cur.execute("UPDATE doc_chunks SET category_id = ? WHERE document_id = ?", (r["to_id"], r["doc_id"]))
            undo["rows"].append({"doc_id": r["doc_id"], "from_id": r["from_id"], "to_id": r["to_id"]})
    con.commit()
    return undo


def rollback(con, undo: dict) -> int:
    cur = con.cursor()
    n = 0
    for r in (undo or {}).get("rows", []):
        cur.execute("UPDATE documents SET category_id = ? WHERE id = ? AND category_id = ?", (r["from_id"], r["doc_id"], r["to_id"]))
        cur.execute("UPDATE doc_chunks SET category_id = ? WHERE document_id = ?", (r["from_id"], r["doc_id"]))
        n += 1
    con.commit()
    return n


def upload_category_warning(title: str, category_name: str) -> str:
    """R2: '' when the chosen category fits the document's own type words, else a warning naming both."""
    own = doc_own_types(title or "")
    have = category_types(category_name)
    if have is None:
        return f"Category '{category_name}' has no product-type map; the selector will ask the tech to confirm the unit type for its docs."
    if not have:   # a kind category (forms, bulletins, reference): any product doc may live there
        return ""
    if own and not (own & have):
        names = ", ".join(sorted(TYPE_NAMES.get(t, t) for t in own))
        return f"'{title}' reads as {names}, but '{category_name}' is for {', '.join(sorted(TYPE_NAMES.get(t, t) for t in have))}."
    return ""


def render_manager_panel(st, raw_connection, backup_db=None, state_key="lib_cataudit_undo"):
    con = raw_connection()
    p = plan(con)
    st.caption(f"Dry run (no changes yet). Checked {p['checked']} documents with a stated product type.")
    st.table(p["moves"] or [{"result": "No misfiled documents."}])
    if p["unmapped_categories"]:
        st.warning("Categories with no product-type map (the selector asks the tech to confirm the type): "
                   + ", ".join(f"{u['category']} ({u['docs']})" for u in p["unmapped_categories"]))
    if p["no_target"]:
        st.warning(f"{len(p['no_target'])} document(s) name a type no category covers: " + json.dumps(p["no_target"])[:600])
    if p.get("metadata_review"):
        st.caption("Category is right but the title/product line disagrees with the page text (fix the metadata in Library):")
        st.table(p["metadata_review"])
    pick = st.multiselect("Moves to apply (untick any you disagree with)", [m["doc_id"] for m in p["moves"]],
                          default=[m["doc_id"] for m in p["moves"]], key="lib_cataudit_pick")
    todo = [m for m in p["moves"] if m["doc_id"] in pick]
    confirm = st.checkbox(f"I reviewed the dry run ({len(todo)} change(s)). Back up, then apply.", key="lib_cataudit_confirm")
    if st.button("Apply category audit", key="lib_cataudit_apply", disabled=not (todo and confirm)):
        ok, note = backup_db() if backup_db else (True, "no backup hook")
        if not ok:
            st.error(f"Backup failed, nothing changed: {note}")
            return
        undo = apply(con, todo)
        st.session_state[state_key] = undo
        st.success(f"Moved {len(undo['rows'])} document(s). Backup: {note}. Undo record: {json.dumps(undo)}")
    undo = st.session_state.get(state_key)
    if undo and st.button("Roll back the last apply", key="lib_cataudit_rollback"):
        st.success(f"Rolled back {rollback(con, undo)} document(s).")
        st.session_state.pop(state_key, None)
