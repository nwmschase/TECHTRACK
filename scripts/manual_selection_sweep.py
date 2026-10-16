"""Sweep: every library doc with a model number, queried with that model + its category, must pin that doc
(or a doc carrying the same model, i.e. a duplicate copy of the same manual). Read-only on a DB copy."""
import json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go

db = sys.argv[1]
c = sqlite3.connect(db)
cats = dict(c.execute("select id, name from categories"))
lib = go.SqliteLibrary(db)
docs = {d["id"]: d for d in lib.documents()}
rows, ok_strict, ok_equiv, fails, skipped = 0, 0, 0, [], []
for did, d in docs.items():
    import re
    allm = [m.strip() for m in (d.get("models") or "").split(";") if m.strip() and any(ch.isdigit() for ch in m)]
    # Capacity ratings / series names in the models field are not model numbers (e.g. '6,000 lb', '8K', '2000 Series').
    models = [m for m in allm if not re.search(r"\blb\b|series|^\d+k$|^\d[\d,]*$", m, re.I)]
    if not models:
        if allm:
            skipped.append((did, allm[0]))
        continue
    rows += 1
    brand = d.get("brand") or ""
    model = f"{brand} {models[0]}".strip()
    cat_id = c.execute("select category_id from documents where id=?", (did,)).fetchone()[0]
    cat = cats.get(cat_id, "")
    unit = go.identify_unit([], "not working", cat, model)
    sel = go.select_manual(lib, unit)
    got = sel["doc"]
    if got and got["id"] == did:
        ok_strict += 1; ok_equiv += 1
    elif got and go.model_hit_len(unit, got):
        ok_equiv += 1
    else:
        fails.append({"doc": did, "title": d["title"][:90], "query": model, "category": cat,
                      "got": got and (got["id"], got["title"][:70]), "miss": sel["miss_line"], "rejected_self": [r for r in sel["rejected"] if r[0] == did]})
print(json.dumps({"docs_with_model": rows, "pinned_self": ok_strict, "pinned_same_model": ok_equiv,
                  "pass_rate_same_model": round(ok_equiv / max(rows, 1), 3), "skipped_ratings_not_models": skipped, "failures": fails}, indent=1))
