"""Library category audit (R1). One general rule, no doc ids:

A document's own words (title / clean title / product line) name its product type (gd_official.product_types).
Its filing category must map to a type set that includes that type (gd_official.CATEGORY_TYPES). If not, the doc is
MISFILED and the proposed category is the library category whose type set contains the doc's types, choosing the most
specific category (fewest mapped types), then the one already holding the most documents. A category with no type map is
reported as UNMAPPED. Manager Tools: dry run -> confirm -> backup -> apply -> rollback. Idempotent (a clean library plans 0).
"""
import json
import re
from datetime import datetime

import gd_official as go

MODULE_REVISION = "v4.19.65"
MIN_BODY_HITS = 5
# Component types: controls, wiring/power, chassis and running gear show up inside every product's docs (a jack controller,
# an A/C thermostat board, a leveling chassis hookup). A doc whose OWN type is only a component is consistent with its
# category when the category's product words occur anywhere in its page text or keywords.
COMPONENT_TYPES = {"electronics", "power", "chassis", "axle"}


def _cats(cur):
    return {cid: name for cid, name in cur.execute("SELECT id, name FROM categories").fetchall()}


def doc_own_types(title, clean_title="", product_line="") -> set:
    return go.product_types(" ".join(x or "" for x in (title, clean_title, product_line)))


def body_type_counts(con, doc_id) -> dict:
    """How often each product type's words occur in the doc's indexed page text."""
    cur = con.cursor()
    text = " ".join(t or "" for (t,) in cur.execute("SELECT chunk_text FROM doc_chunks WHERE document_id = ?", (doc_id,)).fetchall()).lower()
    return {k: len(re.findall(rx, text)) for k, rx in go.PRODUCT_TYPES.items() if re.search(rx, text)}


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
    ctypes = {cid: go.CATEGORY_TYPES.get((name or "").strip().lower()) for cid, name in cats.items()}
    unmapped = [{"category_id": cid, "category": cats[cid], "docs": counts.get(cid, 0)} for cid, t in ctypes.items() if t is None]
    moves, no_target, checked, review = [], [], 0, []
    rows = cur.execute("SELECT id, title, COALESCE(clean_title,''), COALESCE(product_line,''), category_id FROM documents ORDER BY id").fetchall()
    for did, title, clean, pl, cid in rows:
        own = doc_own_types(title, clean, pl)
        have = ctypes.get(cid)
        if not own or not have or (cats.get(cid) or "").strip().lower() in go.KIND_CATEGORIES:
            continue
        checked += 1
        if own & have:
            continue
        counts = body_types(did)
        if own <= COMPONENT_TYPES:
            kw = go.product_types(cur.execute("SELECT COALESCE(keywords,'') FROM documents WHERE id = ?", (did,)).fetchone()[0])
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
    have = go.CATEGORY_TYPES.get((category_name or "").strip().lower())
    if have is None:
        return f"Category '{category_name}' has no product-type map; the selector will ask the tech to confirm the unit type for its docs."
    if own and not (own & have):
        names = ", ".join(sorted(go.TYPE_NAMES.get(t, t) for t in own))
        return f"'{title}' reads as {names}, but '{category_name}' is for {', '.join(sorted(go.TYPE_NAMES.get(t, t) for t in have))}."
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
