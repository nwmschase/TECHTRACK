"""Idempotent library re-categorization (Manager Tools). Dry run first, backup, apply, rollback.

Each fix names the doc id AND a title prefix, so it only touches the intended row and is a no-op once applied.
Category is looked up by name, never by a hard-coded id.
"""
import json
from datetime import datetime

MODULE_REVISION = "v4.19.64"

FIXES = (
    # (doc_id, title must start with, target category name, why)
    (309, "Girard 17 inch All Glass Gas Range", "Range & Cooktops", "Gas range filed under awnings (2026-10-16 selector sweep)"),
    (631, "Power Gear T.I.P. - AUTOMATIC LEVEL CONTROLLER", "Leveling", "Leveling controller filed under slide-outs (2026-10-16 selector sweep)"),
)


def plan(con) -> list:
    """Rows a run would change. `con` is a DB-API connection (sqlite3 or SQLAlchemy raw connection)."""
    cur = con.cursor()
    cats = {name: cid for cid, name in cur.execute("SELECT id, name FROM categories").fetchall()}
    names = {cid: name for name, cid in cats.items()}
    out = []
    for doc_id, prefix, target, why in FIXES:
        row = cur.execute("SELECT id, title, category_id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            out.append({"doc_id": doc_id, "status": "skip: doc not found"}); continue
        _, title, cur_cat = row
        if not (title or "").startswith(prefix):
            out.append({"doc_id": doc_id, "title": title, "status": "skip: title does not match"}); continue
        if target not in cats:
            out.append({"doc_id": doc_id, "title": title, "status": f"skip: no category '{target}'"}); continue
        if cur_cat == cats[target]:
            out.append({"doc_id": doc_id, "title": title, "status": "already correct"}); continue
        out.append({"doc_id": doc_id, "title": title, "from_id": cur_cat, "from": names.get(cur_cat, "?"),
                    "to_id": cats[target], "to": target, "why": why, "status": "will change"})
    return out


def apply(con, rows: list) -> dict:
    """Apply 'will change' rows (documents.category_id and its doc_chunks). Returns the rollback record."""
    cur = con.cursor()
    undo = {"at": datetime.now().isoformat(timespec="seconds"), "rows": []}
    for r in rows:
        if r.get("status") != "will change":
            continue
        cur.execute("UPDATE documents SET category_id = ? WHERE id = ? AND category_id = ?", (r["to_id"], r["doc_id"], r["from_id"]))
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


def render_manager_panel(st, raw_connection, backup_db=None, state_key="lib_catfix_undo"):
    """Manager Tools expander: dry run table -> backup -> apply; rollback from this session's undo record."""
    con = raw_connection()
    rows = plan(con)
    st.caption("Dry run (no changes yet):")
    st.table(rows)
    todo = [r for r in rows if r.get("status") == "will change"]
    confirm = st.checkbox(f"I reviewed the dry run ({len(todo)} change(s)). Back up, then apply.", key="lib_catfix_confirm")
    if st.button("Apply category fixes", key="lib_catfix_apply", disabled=not (todo and confirm)):
        ok, note = backup_db() if backup_db else (True, "no backup hook")
        if not ok:
            st.error(f"Backup failed, nothing changed: {note}")
            return
        undo = apply(con, todo)
        st.session_state[state_key] = undo
        st.success(f"Changed {len(undo['rows'])} document(s). Backup: {note}. Undo record: {json.dumps(undo)}")
    undo = st.session_state.get(state_key)
    if undo and st.button("Roll back the last apply", key="lib_catfix_rollback"):
        st.success(f"Rolled back {rollback(con, undo)} document(s).")
        st.session_state.pop(state_key, None)
