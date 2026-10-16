"""Run Chase's real cases RC01/RC02 through the GD official method (branch only).

Read-only on a copy of the live DB. Real xAI calls (XAI_API_KEY from env).
Writes transcripts + a JSONL usage log under --out. Nothing touches live or R2.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_llm  # noqa: E402
import gd_official as go  # noqa: E402

RC = {
    "RC01": {
        "category": "Leveling",
        "model": "Lippert OneControl Ground Control GC 3.0 Advantage 4pt fifth wheel PN 803280",
        "pre": "Auto Level initializes but raises passenger side higher than driver side and fails to complete.",
        "turns": [
            "Auto Level initializes but raises passenger side higher than driver side and fails to complete.",
            "not checked",
            "Plugs checked, controller, jack and touch pad plugs all seated. No change.",
            "Touch pad shows a motor fault on the passenger side jack circuit. Jacks are all retracted now.",
            "Zero point calibration done, the panel said calibration complete.",
            "Ran Auto Level 3 times, it completes and levels every time.",
        ],
    },
    "RC02": {
        "category": "Slide-Outs",
        "model": "Lippert OneControl Unity X270D",
        "pre": "",
        "turns": [
            "Complaint (INFERRED, exact wording not given): both slide outs will not extend or retract.",
            "About 14.4 VDC at the X270D power inputs. Touch panel comm OK, relays click on extend and retract. X270 30A and 15A fuses in the 12V panel are good.",
            "No voltage at the X270D slide output terminals during commands. Output is open/floating and collapses under command instead of switching polarity. Both slide circuits are the same.",
            "Replaced the Unity X270D, transferred wiring, programmed and resynced OneControl.",
            "Slides and awning all work now.",
        ],
    },
}


class PlantedLibrary:
    """Adds one wrong-brand document that names the same model. It must never be pinned."""

    def __init__(self, base, model_words):
        self.base = base
        self.fake = {"id": -999, "title": f"Dometic {model_words} Troubleshooting and Service Manual",
                     "brand": "Dometic", "models": model_words, "product_line": "", "clean_title": "",
                     "doc_number": model_words, "keywords": f"{model_words} troubleshooting fault code", "revision_date": ""}

    def documents(self):
        return self.base.documents() + [self.fake]

    def chunks(self, doc_id):
        if doc_id == -999:
            return [{"page": 1, "text": "Troubleshooting. Fault code E9: replace Dometic board 3316. " * 40}]
        return self.base.chunks(doc_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/workspace/techtrack-validation/live-data-copy/out-2026-10-13/rv_techtrack_v4.db")
    ap.add_argument("--out", required=True)
    ap.add_argument("--case", choices=sorted(RC), required=True)
    ap.add_argument("--variant", choices=["library", "planted", "withheld"], default="library")
    ap.add_argument("--identify-first", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    db = os.path.join(a.out, f"db-copy-{a.case}-{a.variant}.sqlite")
    if not os.path.exists(db):
        shutil.copyfile(a.db, db)
    case = RC[a.case]
    lib = go.SqliteLibrary(db)
    exclude = ()
    if a.variant == "planted":
        lib = PlantedLibrary(lib, "X270D" if a.case == "RC02" else "Ground Control GC 3.0 803280")
    if a.variant == "withheld":
        toks = go.identify_unit([], "", "", case["model"])["tokens"]
        exclude = tuple(d["id"] for d in lib.documents() if go.score_document(go.identify_unit([], "", "", case["model"]), d)[0] > 0)
    key = os.environ.get("XAI_API_KEY", "")

    def chat_fn(messages, max_tokens, effort):
        return gd_llm.complete_chat(messages, temperature=0.2, max_tokens=max_tokens,
                                    secret_fn=os.environ.get, reasoning_effort=effort,
                                    providers=[gd_llm.PROVIDER_XAI])

    web_fn = (lambda unit: go.fetch_official_manual(unit, key)) if a.variant == "withheld" else (lambda unit: {})
    tag = f"{a.case}-{a.variant}" + ("-identify" if a.identify_first else "")
    log = os.path.join(a.out, f"{tag}.usage.jsonl")
    open(log, "w").close()
    store, history, lines = {}, [], [f"# {tag}  ({time.strftime('%Y-%m-%d %H:%M %Z')})", f"Model field: {case['model']}", ""]
    turns = list(case["turns"])
    model_seq = [case["model"]] * len(turns)
    if a.identify_first:
        turns = [case["turns"][0]] + turns
        model_seq = [""] + model_seq
    for i, (msg, model) in enumerate(zip(turns, model_seq)):
        r = go.official_turn(msg, case["category"], model, history, library=lib, chat_fn=chat_fn,
                             pin_store=store, usage_fn=gd_llm.last_usage, web_fetch_fn=web_fn,
                             log_path=log, exclude_doc_ids=exclude)
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": r["reply"]}]
        u = r.get("usage") or {}
        lines += [f"## Turn {i+1}", f"**Tech:** {msg}", "", "**GD:**", r["reply"], "",
                  f"_mode={r['mode']} tokens in={u.get('prompt_tokens')} cached={u.get('cached_tokens')} out={u.get('completion_tokens')} "
                  f"reasoning={u.get('reasoning_tokens')} cost=${r.get('cost_usd')} latency={r['seconds']}s_", ""]
        if r["mode"] == "no_manual":
            break
    pin = store.get("gd_pin") or {}
    lines += ["## Pin", "```", json.dumps({k: pin.get(k) for k in ("doc_id", "doc_title", "url", "mode", "pages", "web", "checked")}, indent=1, default=str), "```"]
    path = os.path.join(a.out, f"{tag}.md")
    open(path, "w").write("\n".join(lines))
    print(path)


if __name__ == "__main__":
    main()
