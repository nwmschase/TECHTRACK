"""Selector sweep (version-agnostic, read-only on a DB copy).
1. Self sweep: every doc with a real model number, queried '<brand> <model>' with its own category.
2. Cross sweep: every such model x every library category -> a pick whose own title type is not a type of that category = WRONG TYPE.
3. Ambiguous-tie pick: a pick where another doc (different manual: other doc_number/title) of the same brand carries the query
   model with equal evidence (models-field vs title-only) and the same doc kind - i.e. the pick was decided by order, not evidence.
Usage: python selector_sweep.py <repo_dir> <db_copy> <out.json>
"""
import json, re, sqlite3, sys
repo, db, out = sys.argv[1:4]
sys.path.insert(0, repo)
import gd_official as go

TYPE_RX = {  # measurement-only map, independent of the code under test
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

c = sqlite3.connect(db)
cats = dict(c.execute("select id,name from categories"))
dcat = dict(c.execute("select id,category_id from documents"))
lib = go.SqliteLibrary(db)
docs = {d["id"]: d for d in lib.documents()}

def evidence(d, m):
    """2 x (model in models/doc-number field) + 1 x (model named in the title)."""
    k = m.lower().replace("-", "").replace(".", "")
    f = k in toks(d.get("models", "")) | toks(d.get("doc_number", ""))
    t = k in toks(d.get("title", ""))
    return 2 * f + t

def in_text(d, m):
    k = m.lower().replace("-", "").replace(".", "")
    return c.execute("select 1 from doc_chunks where document_id=? and replace(replace(lower(chunk_text),'-',''),'.','') like ? limit 1", (d["id"], f"%{k}%")).fetchone() is not None

def kind(d):
    t = d["title"].lower()
    if re.search(r"write-?up|warranty|\bform\b|\bclaim\b", t):
        return 0
    return 2 if re.search(r"trouble\s*shoot|diagnos|service\s+(manual|and\s+training|&\s+training)|repair\s+manual", t) else 1

def ident(d):
    return (d.get("doc_number") or "").lower() or re.sub(r"\W", "", d["title"].lower())

def dtypes(d):
    return types(d["title"]) or CAT_RX.get(cats.get(dcat[d["id"]], "").lower(), set())

def nmodels(d):
    return len([x for x in re.split(r"[;,]", d.get("models") or "") if x.strip()])

def ambiguous(pick, brand, m, want):
    e = evidence(pick, m)
    if not e:
        return False
    for o in docs.values():
        if o["id"] == pick["id"] or ident(o) == ident(pick) or o["id"] in REJ:
            continue
        if (o.get("brand") or "").lower() != (brand or "").lower():
            continue
        if evidence(o, m) == e and kind(o) == kind(pick) and nmodels(o) == nmodels(pick) and (not want or dtypes(o) & want):
            return True
    return False

REJ = set()

def run(unit):
    """(doc, how); REJ = ids the selector's hard filters (brand/type) refused - those cannot be tie partners."""
    REJ.clear()
    s = go.select_manual(lib, unit)
    REJ.update(i for i, why in s.get("rejected", []) if why != "file unreachable")
    return s.get("doc"), s.get("how", "")

queries = []
for did, d in docs.items():
    allm = [m.strip() for m in (d.get("models") or "").split(";") if m.strip() and any(ch.isdigit() for ch in m)]
    models = [m for m in allm if not re.search(UNIT_RX, m, re.I)]
    if models:
        queries.append((did, (d.get("brand") or "").strip(), models[0]))

res = {"self": {"n": 0, "pinned_same_model": 0, "pinned_self": 0, "no_pick": 0, "wrong_model": 0, "wrong_type": 0, "ambiguous_tie_picks": 0,
                "how": {}, "misses": [], "wrong": [], "ties": []},
       "cross": {"n": 0, "picks": 0, "wrong_type": 0, "wrong": []}}
S = res["self"]
for did, brand, m in queries:
    cat = cats.get(dcat[did], "")
    unit = go.identify_unit([], "not working", cat, f"{brand} {m}".strip())
    got, how = run(unit)
    S["n"] += 1; S["how"][how] = S["how"].get(how, 0) + 1
    want = CAT_RX.get(cat.lower(), set()) or types(docs[did]["title"])
    if not got:
        S["no_pick"] += 1; S["misses"].append({"doc": did, "q": f"{brand} {m}", "cat": cat, "how": how}); continue
    gt = types(got["title"])
    if want and gt and not (gt & want):
        S["wrong_type"] += 1; S["wrong"].append({"doc": did, "q": m, "cat": cat, "got": [got["id"], got["title"][:60]]})
    if got["id"] == did:
        S["pinned_self"] += 1; S["pinned_same_model"] += 1
    elif evidence(got, m) or m.lower().replace("-", "") in toks(got.get("keywords", "")) or in_text(got, m):
        S["pinned_same_model"] += 1
    else:
        S["wrong_model"] += 1; S["wrong"].append({"doc": did, "q": m, "got": [got["id"], got["title"][:60]], "kind": "other model"})
    if ambiguous(got, brand, m, want):
        S["ambiguous_tie_picks"] += 1; S["ties"].append({"doc": did, "q": m, "got": got["id"]})
C = res["cross"]
for did, brand, m in queries:
    for cid, cat in cats.items():
        want = CAT_RX.get(cat.lower())
        if not want:
            continue
        unit = go.identify_unit([], "not working", cat, f"{brand} {m}".strip())
        got, how = run(unit)
        C["n"] += 1
        if got:
            C["picks"] += 1
            gt = types(got["title"])
            if gt and not (gt & want):
                C["wrong_type"] += 1
                if len(C["wrong"]) < 40: C["wrong"].append({"q": m, "cat": cat, "got": [got["id"], got["title"][:60]]})
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({"self": {k: v for k, v in S.items() if not isinstance(v, list)}, "cross": {k: v for k, v in C.items() if k != "wrong"}}, indent=1))
