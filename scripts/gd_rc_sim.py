"""Real-case rerun with a simulated tech (branch only, real xAI calls, read-only DB copy).

The simulated tech knows only the case file's findings and answers what GD asks.
A separate judge call grades: complaint verified first, known fix reached, no wrong part condemned.
"""
import argparse, json, os, re, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_llm  # noqa: E402
import gd_official as go  # noqa: E402

RC_DIR = "/workspace/techtrack-validation/real-cases"
UNITS = {  # model field the tech would type, category, Unity selector
    "RC01": ("Lippert OneControl Ground Control GC 3.0 Advantage 4pt fifth wheel PN 803280", "Leveling", "Yes"),
    "RC02": ("Lippert OneControl Unity X270D", "Slide-Outs", "Yes"),
    "RC03": ("Lippert OneControl Unity X270D", "Awnings", "Yes"),
    "RC04": ("BAL touchscreen leveling system, 2025 Venture SportTrek travel trailer (no model tag found)", "Leveling", "Not sure"),
    "RC07": ("Coleman-Mach rooftop A/C 2111-0001", "Air Conditioning", "No"),
    "RC08": ("BAL Soft-Touch SS 5.1 stabilizer system", "Leveling", "No"),
    "RC12": ("Furrion FCR10DCGTA-BG-PWH", "Refrigerators", "No"),
    "RC13": ("Suburban NT-20SEQT furnace", "Furnaces", "No"),
    "RC14": ("Dometic B57915E711J0EMX rooftop A/C", "Air Conditioning", "No"),
    "RC15": ("Lippert Ground Control 5th wheel 343633", "Leveling", "Not sure"),
    "RC16": ("Furrion FACT12SA2-PS (Lippert 2024031961) A/C", "Air Conditioning", "No"),
    "RC17": ("Girard GSWH-2 tankless water heater", "Water Heaters", "No"),
    "RC18": ("Lippert front stabilizer jack (model not recovered)", "Leveling", "Not sure"),
    "RC19": ("Suburban SDN2U cooktop", "Range & Cooktops", "No"),
    "RC23": ("2026 Brinkley Model Z 3100 fifth wheel front jack", "Leveling", "No"),
    "RC28": ("BAL Exact-Slide Emforce cable slide, column tag 22000928", "Slide-Outs", "No"),
    "RC29": ("Furrion FACR13LPSA2-PS rooftop A/C", "Air Conditioning", "No"),
    "RC27": ("Furrion FCR fridge (model unknown)", "Refrigerators", "No"),
}

TECH_SYS = """You are role-playing an RV service tech at the bench. Hidden case file below is what is TRUE about this unit.
Answer GD's latest instructions briefly (1-3 sentences) like a tech would, using ONLY facts from the case file.
- If GD asks for a reading the case file records at a nearby point (e.g. at the panel instead of the harness), report that recorded reading and where you took it.
- If GD asks for something the case file doesn't record at all, say it looks normal/OK, never invent a fault.
- Report the complaint as the customer stated it in your first message (no findings yet).
- When GD asks you to verify/operate the unit, report what the case file says you observed.
- If GD tells you to do the repair in the case file's Fix, do it and report the result as in the case file.
- If GD tells you to replace a part NOT in the case file's Fix, say: 'Before I replace that - anything else to check?'
- When the repair is done and verified, or GD has called No Problem Found, end your message with [END].
CASE FILE:
"""

JUDGE_SYS = """Write a NEUTRAL note on a Guided Diagnostics transcript (Chase's rule: no pass/fail; Chase and Leader decide).
Reply JSON only: {"label": "clear tangent" | "for review", "verified_complaint_first": bool, "fix_reached": "<what repair GD directed, or none>",
"parts_condemned": ["..."], "note": "<=30 words, neutral"}
Use "clear tangent" ONLY if GD went way off track (wrong appliance/system) or gave unsafe instructions; otherwise "for review"."""


def chat(messages, max_tokens=600, effort="low"):
    return gd_llm.complete_chat(messages, temperature=0.3, max_tokens=max_tokens, secret_fn=os.environ.get,
                                reasoning_effort=effort, providers=[gd_llm.PROVIDER_XAI])


def run(case, out, db, max_turns=14):
    case_text = open([os.path.join(RC_DIR, f) for f in os.listdir(RC_DIR) if f.startswith(case + "-") and f.endswith(".md")][0]).read()
    model, category, unity = UNITS[case]
    lib = go.SqliteLibrary(db)
    key = os.environ.get("XAI_API_KEY", "")
    store, history, lines = {}, [], [f"# {case} sim  ({time.strftime('%Y-%m-%d %H:%M %Z')})", f"Model field: {model} | Category: {category} | Unity selector: {unity}", ""]
    log = os.path.join(out, f"{case}.usage.jsonl"); open(log, "w").close()
    tech_hist = [{"role": "system", "content": TECH_SYS + case_text}, {"role": "user", "content": "GD: Describe the complaint."}]
    msg = chat(tech_hist).strip()
    for t in range(1, max_turns + 1):
        r = go.official_turn(msg, category, model, history, library=lib,
                             chat_fn=lambda m, mt, e: chat(m, mt, e), pin_store=store, usage_fn=gd_llm.last_usage,
                             web_fetch_fn=lambda u: go.fetch_official_manual(u, key), log_path=log,
                             unity_gate=unity, web_get=go.official_pdf_text)
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": r["reply"]}]
        u = r.get("usage") or {}
        lines += [f"## Turn {t}", f"**Tech:** {msg}", "", "**GD:**", r["reply"], "",
                  f"_mode={r['mode']} in={u.get('prompt_tokens')} cached={u.get('cached_tokens')} out={u.get('completion_tokens')} reasoning={u.get('reasoning_tokens')} cost=${r.get('cost_usd')} latency={r['seconds']}s_", ""]
        if "[END]" in msg:
            break
        tech_hist += [{"role": "assistant", "content": msg}, {"role": "user", "content": "GD: " + r["reply"]}]
        msg = chat(tech_hist).strip()
        if "[END]" in msg and t > 1:
            history_end = msg
            lines += [f"## Tech final", history_end, ""]
            break
    pin = store.get("gd_pin") or {}
    transcript = "\n".join(lines)
    verdict = chat([{"role": "system", "content": JUDGE_SYS},
                    {"role": "user", "content": f"CASE FILE:\n{case_text}\n\nTRANSCRIPT:\n{transcript}"}], 500, "low")
    m = re.search(r"\{.*\}", verdict, re.S)
    try:
        v = json.loads(m.group(0))
    except Exception:
        v = {"reason": verdict[:200]}
    web = (pin.get("web") or {}).get("search_usage") or {}
    calls = (web.get("server_side_tool_usage_details") or {}).get("web_search_calls", 0)
    v.update({"case": case, "gd_turns": sum(1 for x in history if x["role"] == "assistant"),
              "doc": pin.get("doc_title"), "mode": pin.get("mode"), "web_calls": calls, "web_flag_over_12": calls > 12,
              "facts": list((pin.get("facts") or {}).keys())})
    lines += ["## Pin", "```", json.dumps({k: pin.get(k) for k in ("doc_title", "url", "mode", "pages", "unity_mode", "unity_path", "charge_path", "facts")}, indent=1, default=str), "```",
              "## Judge", "```", json.dumps(v, indent=1), "```"]
    open(os.path.join(out, f"{case}.md"), "w").write("\n".join(lines))
    json.dump(v, open(os.path.join(out, f"{case}.verdict.json"), "w"), indent=1)
    print(json.dumps(v))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", default="/workspace/techtrack-validation/live-data-copy/out-2026-10-13/rv_techtrack_v4.db")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    db = os.path.join(a.out, f"db-{a.case}.sqlite")
    shutil.copyfile(a.db, db)
    run(a.case, a.out, db)
