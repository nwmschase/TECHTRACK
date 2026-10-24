"""Offline picker sweep for the NEW manual picker (pagefinder pick_manual; backburnered, no live caller since grok-search) on an app DB copy.

Same queries and same scoring as techtrack-validation/library-dialin/work/selector_sweep_fixedq.py so the numbers line up
with the main b1e363d baseline:
  self sweep : every doc with a real model number, '<brand> <model>' in its own category.
               own = the top pick is that doc; same model = the pick carries the model (fields/keywords/text);
               no-pick; wrong model; wrong type (pick's title type is not the category's type).
  cross sweep: every query x every typed category; a pick whose title type is not that category's type = wrong type.
Read-only on the DB. No LLM, no network (run through offline.sh).
Usage: QUERIES_FROM=<snapshot.db> python scripts/picker_sweep.py <app_db_copy> <index_dir> <out.json> [--keyword-only]
"""
import csv
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TYPE_RX = {  # measurement-only map, identical to the baseline script (independent of the code under test)
    "fridge": r"refrigerat|fridge|freezer", "vent_fan": r"vent\s*fan|roof\s*vent|maxx\s*fan|fan\s*tastic",
    "toilet": r"toilet", "water_heater": r"water\s*heater|tankless|gswh", "furnace": r"furnace",
    "ac": r"air\s*condition|\ba/?c\b|rooftop\s*(unit|a)|heat\s*pump", "cooktop": r"cooktop|\brange\b|\boven\b|burner",
    "leveling": r"\blevel(ing|er|ers)?\b|\bjacks?\b|stabiliz", "awning": r"awning", "slide": r"\bslide",
}
CAT_RX = {"refrigerators": {"fridge"}, "furnaces": {"furnace"}, "water heaters": {"water_heater"}, "air conditioning": {"ac"},
          "slideouts": {"slide"}, "slide-outs": {"slide"}, "leveling": {"leveling"}, "range & cooktops": {"cooktop"},
          "plumbing / toilets": {"toilet"}, "awnings": {"awning"}}
UNIT_RX = r"\d[\d,.]*\s*-?\s*(lbs?|pounds?)\b|series|^\d+k$|^\d[\d,]*$|^[a-z]-?\d$"


def types(text):
    t = (text or "").lower()
    return {k for k, rx in TYPE_RX.items() if re.search(rx, t)}


def toks(text):
    return {x.replace("-", "").replace(".", "") for x in re.split(r"[^a-z0-9\-.]+", (text or "").lower()) if x.strip(".-")}


def main():
    db, index_dir, out = sys.argv[1:4]
    keyword_only = "--keyword-only" in sys.argv
    os.environ["TT_APP_DB"] = os.path.abspath(db)
    import gd_pages
    f = gd_pages.LibraryPageFinder(index_dir=index_dir, meaning=not keyword_only, app_db=os.path.abspath(db))
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    cats = dict(c.execute("select id,name from categories").fetchall())
    docs = {r["id"]: dict(r) for r in c.execute(
        "select id, brand, coalesce(clean_title, title, '') title, coalesce(models,'') models, coalesce(doc_number,'') doc_number,"
        " coalesce(keywords,'') keywords, category_id from documents")}

    def evidence(d, m):
        k = m.lower().replace("-", "").replace(".", "")
        return 2 * (k in toks(d["models"]) | toks(d["doc_number"])) + (k in toks(d["title"]))

    def in_text(did, m):
        k = m.lower().replace("-", "").replace(".", "")
        return c.execute("select 1 from doc_chunks where document_id=? and replace(replace(lower(chunk_text),'-',''),'.','') like ? limit 1",
                         (did, f"%{k}%")).fetchone() is not None

    dup = {}
    for r in csv.DictReader(open("/workspace/techtrack-validation/library-dialin/changes-2026-10-20.csv")):
        if r["field"] == "DELETE" and r["new"].startswith("duplicate of "):
            dup[int(r["doc_id"])] = int(r["new"].split()[2])
    qdb = os.environ.get("QUERIES_FROM")
    qc = sqlite3.connect(f"file:{qdb}?mode=ro", uri=True) if qdb else c
    queries = []
    for did, brand, models in qc.execute("select id, coalesce(brand,''), coalesce(models,'') from documents"):
        allm = [m.strip() for m in models.split(";") if m.strip() and any(ch.isdigit() for ch in m)]
        ms = [m for m in allm if not re.search(UNIT_RX, m, re.I)]
        if ms:
            tgt = dup.get(did, did) if qdb else did
            if tgt in docs:
                queries.append((tgt, brand.strip(), ms[0]))

    def pick(cat, q):
        p = f.pick_manual(cat, q, "not working")
        ids = [int(m["doc_id"].lstrip("L")) for m in p.manuals]
        return (docs.get(ids[0]) if ids else None), ids

    S = {"n": 0, "own": 0, "same_model": 0, "no_pick": 0, "wrong_model": 0, "wrong_type": 0, "own_in_set": 0,
         "misses": [], "wrong": [], "not_own": [], "per_query": []}
    t0 = time.time()
    for did, brand, m in queries:
        cat = cats.get(docs[did]["category_id"], "")
        q = f"{brand} {m}".strip()
        got, ids = pick(cat, q)
        S["n"] += 1
        S["per_query"].append({"doc": did, "q": q, "cat": cat, "got": got and got["id"], "set": ids})
        if did in ids:
            S["own_in_set"] += 1
        if not got:
            S["no_pick"] += 1
            S["misses"].append({"doc": did, "q": q, "cat": cat})
            continue
        want = CAT_RX.get(cat.lower(), set()) or types(docs[did]["title"])
        gt = types(got["title"])
        if want and gt and not (gt & want):
            S["wrong_type"] += 1
            S["wrong"].append({"doc": did, "q": q, "cat": cat, "got": [got["id"], got["title"][:70]], "kind": "wrong type"})
        if got["id"] == did:
            S["own"] += 1
            S["same_model"] += 1
        else:
            S["not_own"].append({"doc": did, "q": q, "got": [got["id"], got["title"][:70]]})
            if evidence(got, m) or m.lower().replace("-", "") in toks(got["keywords"]) or in_text(got["id"], m):
                S["same_model"] += 1
            else:
                S["wrong_model"] += 1
                S["wrong"].append({"doc": did, "q": q, "got": [got["id"], got["title"][:70]], "kind": "other model"})
    C = {"n": 0, "picks": 0, "wrong_type": 0, "wrong": []}
    for did, brand, m in queries:
        for cid, cat in cats.items():
            want = CAT_RX.get(cat.lower())
            if not want:
                continue
            got, _ = pick(cat, f"{brand} {m}".strip())
            C["n"] += 1
            if got:
                C["picks"] += 1
                gt = types(got["title"])
                if gt and not (gt & want):
                    C["wrong_type"] += 1
                    if len(C["wrong"]) < 2000:
                        C["wrong"].append({"q": m, "cat": cat, "got": [got["id"], got["title"][:70]]})
    res = {"mode": "keyword-only" if keyword_only else "hybrid", "db": db, "queries_from": qdb, "seconds": round(time.time() - t0, 1),
           "self": S, "cross": C}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({"mode": res["mode"], "self": {k: v for k, v in S.items() if not isinstance(v, list)},
                      "cross": {k: v for k, v in C.items() if k != "wrong"}, "seconds": res["seconds"]}, indent=1))


if __name__ == "__main__":
    main()
