"""Free offline check (no model call): the library tools Grok calls return the right Suburban / Furrion / Atwood pages for
six follow-ups (F08 F09 F15 F27 F31 F35 from runs/priority-2026-10-22/harness/fq.py) when called with sensible arguments,
and the size in characters of what each tool hands back.

    APPDB=/tmp/fq2/app.db ../offline.sh python3 scripts/grok_tool_check.py [--json out.json]
"""
import argparse
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gd_pages  # noqa: E402
import gd_tools  # noqa: E402

# id, unit (category, model as typed), the follow-up, gold docs, hit regex (fq.py), the arguments Grok would send
ROWS = [
    ("F08", "Furnaces", "Suburban NT-20SEQT", "TCO", {"L120"}, r"limit switch|\bTCO\b|high limit",
     dict(brand="Suburban", model="NT-20SEQT", unit_type="Furnaces"), dict(words="TCO", brand="Suburban", unit_type="Furnaces")),
    ("F09", "Furnaces", "Suburban NT-20SEQT", "blower motor amp draw", {"L120"}, r"amp",
     dict(brand="Suburban", model="NT-20SEQT", unit_type="Furnaces"), dict(words="blower motor amp draw", brand="Suburban", unit_type="Furnaces")),
    ("F15", "Air Conditioning", "Furrion FACT12SA2-PS", "coil sensor resistance", {"L201", "L202", "L159", "L158", "L203", "L205", "L206"},
     r"sensor.{0,300}(ohm|Ω|resistance)|(ohm|Ω|resistance).{0,300}sensor",
     dict(brand="Furrion", model="FACT12SA2-PS", unit_type="Air Conditioning"), dict(words="coil sensor resistance", brand="Furrion", unit_type="Air Conditioning")),
    ("F27", "Refrigerators", "Furrion FCR08DCGTA", "inline fuse location", {"L186"}, r"fuse",
     dict(brand="Furrion", model="FCR08DCGTA", unit_type="Refrigerators"), dict(words="inline fuse location", brand="Furrion", unit_type="Refrigerators")),
    ("F31", "Refrigerators", "Furrion FCR08DCGTA", "thermistor resistance chart", {"L186"},
     r"thermistor|sensor.{0,300}(ohm|Ω|resistance)|(ohm|Ω|resistance).{0,300}sensor",
     dict(brand="Furrion", model="FCR08DCGTA", unit_type="Refrigerators"), dict(words="thermistor resistance chart", brand="Furrion", unit_type="Refrigerators")),
    ("F35", "Water Heaters", "Atwood GC10A-4E", "DSI board", {"L892", "L893", "L894"}, r"\bDSI\b",
     dict(brand="Atwood", model="GC10A-4E", unit_type="Water Heaters"), dict(words="DSI board", brand="Atwood", unit_type="Water Heaters")),
]


def run(tools, rows=ROWS):
    lib = tools.lib
    out, sizes = [], {n: [] for n in ("find_documents", "table_of_contents", "search_pages", "read_pages")}
    for rid, cat, model, ask, gold, rx, fd_args, sp_args in rows:
        fd = tools.find_documents(**fd_args)
        sizes["find_documents"].append(len(json.dumps(fd)))
        doc_ids = [d["doc_id"] for d in fd["documents"]]
        toc = tools.table_of_contents(doc_ids[0]) if doc_ids else {}
        sizes["table_of_contents"].append(len(json.dumps(toc)))
        sp = tools.search_pages(**sp_args)
        sizes["search_pages"].append(len(json.dumps(sp)))
        hits = sp["hits"]
        top = hits[0] if hits else {}
        # the page Grok opens: the best hit in a gold doc (or the top hit)
        pick = next((h for h in hits if h["doc_id"] in gold), top)
        rp, pages = tools.read_pages(pick["doc_id"], pages=[pick["page"]]) if pick else ({}, [])
        sizes["read_pages"].append(len(json.dumps(rp)))
        txt = " ".join(p.text + " " + p.topics for p in pages)
        # the same search narrowed to the documents find_documents listed (what Grok does once it has picked them)
        sp2 = tools.search_pages(words=sp_args["words"], doc_ids=doc_ids) if doc_ids else {"hits": []}
        def rx_ok(h):
            _, pg = tools.read_pages(h["doc_id"], pages=[h["page"]])
            return bool(re.search(rx, " ".join(x.text + " " + x.topics for x in pg), re.I))
        brands = sorted({h["brand"] for h in hits})
        out.append({"id": rid, "unit": f"{cat} | {model}", "ask": ask, "find_documents": doc_ids,
                    "find_ok": bool(set(doc_ids) & gold), "search_hits": [f"{h['doc_id']} p{h['page']}" for h in hits],
                    "hit_brands": brands, "top_hit": f"{top.get('doc_id')} p{top.get('page')}" if top else "",
                    "top_in_gold": top.get("doc_id") in gold, "gold_in_hits": sum(h["doc_id"] in gold for h in hits),
                    "read": f"{pick.get('doc_id')} p{pick.get('page')}" if pick else "", "read_matches": bool(re.search(rx, txt, re.I)),
                    "gold_hits_matching_rx": sum(1 for h in hits if h["doc_id"] in gold and rx_ok(h)),
                    "narrowed_hits": [f"{h['doc_id']} p{h['page']}" for h in sp2["hits"]],
                    "narrowed_matching_rx": sum(1 for h in sp2["hits"] if rx_ok(h)),
                    "sizes": {k: v[-1] for k, v in sizes.items()}})
    summary = {k: {"median": int(statistics.median(v)), "min": min(v), "max": max(v)} for k, v in sizes.items()}
    return out, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    f = gd_pages.LibraryPageFinder(app_db=os.environ.get("APPDB", ""), meaning=os.environ.get("MEANING", "off") == "on")
    rows, summary = run(gd_tools.LibraryTools.for_finder(f))
    for r in rows:
        print(f"{r['id']} {r['unit']} | {r['ask']}\n   find_documents -> {r['find_documents']} (gold found: {r['find_ok']})"
              f"\n   search_pages -> {r['search_hits']}\n   brands {r['hit_brands']}; top in gold: {r['top_in_gold']}; gold hits {r['gold_in_hits']}/{len(r['search_hits'])}"
              f"\n   gold hits whose page matches the follow-up: {r['gold_hits_matching_rx']}"
              f"\n   search_pages(doc_ids=find_documents) -> {r['narrowed_hits']} ({r['narrowed_matching_rx']} match)"
              f"\n   read_pages {r['read']} matches the follow-up: {r['read_matches']}\n   chars {r['sizes']}")
    print("chars returned per tool:", json.dumps(summary))
    if a.json:
        json.dump({"rows": rows, "sizes": summary}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
