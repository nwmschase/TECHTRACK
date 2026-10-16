"""Neutral notes (clear tangent / for review) for saved RC sim transcripts. No pass/fail."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_llm
from scripts.gd_rc_sim import JUDGE_SYS, RC_DIR, chat
OUT = sys.argv[1]
rows = []
for case, path in [a.split("=") for a in sys.argv[2:]]:
    t = open(path).read().split("## Judge")[0]
    case_text = open([os.path.join(RC_DIR, f) for f in os.listdir(RC_DIR) if f.startswith(case + "-") and f.endswith(".md")][0]).read()
    r = chat([{"role": "system", "content": JUDGE_SYS}, {"role": "user", "content": f"CASE FILE (guidance only):\n{case_text}\n\nTRANSCRIPT:\n{t}"}], 500, "low")
    v = json.loads(re.search(r"\{.*\}", r, re.S).group(0))
    old = json.load(open(path.replace(".md", ".verdict.json")))
    log = path.replace(".md", ".usage.jsonl")
    recs = [json.loads(l) for l in open(log) if l.strip()]
    cost = round(sum(x.get("cost_usd") or 0 for x in recs), 4)
    secs = [x["seconds"] for x in recs if x.get("stage") == "walk"]
    v.update(case=case, transcript=path, steps=old.get("gd_turns"), web_calls=old.get("web_calls"), doc=old.get("doc"), cost_usd=cost,
             max_turn_s=max(secs) if secs else None)
    rows.append(v); print(json.dumps(v))
json.dump(rows, open(os.path.join(OUT, "notes.json"), "w"), indent=1)
