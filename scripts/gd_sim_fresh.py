"""Simulated-tech harness for the fresh GD core. NOT RUN on this branch: it makes live LLM calls.

Running it live needs Chase's OK, --chase-ok, and a dollar cap (--max-usd). With neither, it refuses.

What changed from the old harness (scripts/gd_rc_sim.py, deleted; see FIX-PLAN.md section 6):
  * The sim tech never sees the answer. split_case() gives it only the unit, the complaint and the recorded
    findings/readings. Cause, fix, outcome, pass/fail notes and old GD runs go to the answer key only.
  * Anything the case file does not record, the sim tech answers "not measured" / "don't know". Never a fake "looks OK".
  * Whether a repair GD directs actually fixes the unit is decided by a separate referee call that sees the answer key
    and GD's reply and returns JSON; the harness then tells the sim tech the result. The tech never learns the fix.
  * The judge returns a fixed JSON record (ending type, fix reached vs the case fix, parts condemned, verify asked once,
    every step cited). A run that hits the turn cap is "capped", never a pass.
  * A deterministic check lists every part number / phone number GD wrote that is not on a page it was shown.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_turn  # noqa: E402

RC_DIR = "/workspace/techtrack-validation/real-cases"
PRICE_PER_M = {"input": 2.00, "cached": 0.50, "output": 6.00}  # grok-4.6 list price, 2026-10-16
TECH_FIELDS = ("unit", "brand/model", "complaint", "found on arrival", "findings", "tech readings")
UNITS = {  # what the tech would type in the app's two fields (category, model). No Unity selector any more.
    "RC01": ("Leveling", "Lippert OneControl Ground Control GC 3.0 Advantage 4pt fifth wheel PN 803280"),
    "RC04": ("Leveling", "BAL touchscreen leveling system, 2025 Venture SportTrek travel trailer (no model tag found)"),
    "RC12": ("Refrigerators", "Furrion FCR10DCGTA-BG-PWH"),
    "RC13": ("Furnaces", "Suburban NT-20SEQT furnace"),
    "RC16": ("Air Conditioning", "Furrion FACT12SA2-PS (Lippert 2024031961) A/C"),
    "RC18": ("Leveling", "Lippert front stabilizer jack (model not recovered)"),
    "RC22": ("Water Heaters", "Suburban SW6DE water heater"),
    "RC27": ("Refrigerators", "Furrion FCR fridge (model unknown)"),
}

TECH_SYS = """You are an RV service tech at the bench, talking to Guided Diagnostics (GD). Below are your own notes on this unit.
Answer GD's latest message briefly (1-3 sentences), like a tech would.
- Your first message is the customer's complaint only, as the customer said it.
- Report only what your notes record. If GD asks for something your notes do not record, say "not measured" or "I don't know".
  Never say a part "looks normal" or "OK" unless your notes say so.
- If GD asks whether you have seen the complaint, answer from your notes.
- If GD tells you to do a repair, say you did it; the bench will tell you what happened after, report exactly that.
- You do not know the cause or the fix. Do not guess them.
YOUR NOTES:
"""

REFEREE_SYS = """You referee a simulated repair. You see the case answer key and GD's latest reply.
Reply JSON only: {"repair_directed": bool, "what": "<the repair GD told the tech to do, or empty>", "matches_fix": bool}
repair_directed = GD told the tech to do a repair now (replace, adjust, calibrate, reset, re-seat...), not just a test.
matches_fix = that repair is the case's fix (same component or same adjustment, any wording)."""

JUDGE_SYS = """Grade a Guided Diagnostics transcript against the case answer key. Reply JSON only:
{"ending": "closed" | "escalated" | "open", "fix_reached": bool, "fix_directed": "<repair GD directed, or none>",
 "parts_condemned": ["..."], "wrong_parts": ["parts condemned that are not the fix"], "verify_asked_once": bool,
 "steps_cited": "all" | "most" | "few", "unsafe": "<quote of any unsafe instruction, or empty>", "note": "<=30 words"}"""


def split_case(text: str):
    """(tech_notes, answer_key). Only 'Field: value' lines whose field is in TECH_FIELDS reach the tech; everything else
    (cause, fix, outcome, pass/fail, status, sources, old GD runs, free text) goes to the answer key."""
    tech, key = [], []
    for line in (text or "").splitlines():
        m = re.match(r"\s*([A-Za-z/ ]+?)(?:\s*\([^)]*\))?\s*:\s*(.+)$", line)
        if m and m.group(1).strip().lower() in TECH_FIELDS:
            tech.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
        elif line.strip():
            key.append(line)
    return "\n".join(tech), "\n".join(key)


def invented_numbers(replies, shown_text):
    """Part numbers / phone numbers in GD's replies that appear on none of the pages GD was shown."""
    pat = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|\b[A-Z]{0,4}-?\d{5,}[A-Z0-9-]*\b")
    seen = re.sub(r"\s+", " ", shown_text or "")
    return sorted({n for r in replies for n in pat.findall(r or "") if n not in seen})


def cost(usage):
    u = usage or {}
    cached = u.get("cached_tokens", 0) or 0
    return ((u.get("prompt_tokens", 0) - cached) * PRICE_PER_M["input"] + cached * PRICE_PER_M["cached"]
            + (u.get("completion_tokens", 0) + (u.get("reasoning_tokens", 0) or 0)) * PRICE_PER_M["output"]) / 1e6
    # reasoning tokens added on top on purpose: if the provider already counts them in completion_tokens this
    # over-estimates, which is the safe side for a dollar cap.


def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


def run_case(case_text, category, model, *, finder, gd_chat, tech_chat, referee_chat, judge_chat,
             max_turns=14, max_usd=1.0, usage_fn=None, spent_fn=None):
    """One simulated session. All four chat functions are injected (fakes in tests).
    spent_fn() -> dollars spent so far on ALL calls (GD + tech + referee + judge); without it only GD cost is counted."""
    notes, key = split_case(case_text)
    store, history, spent, gd_replies, shown = {}, [], 0.0, [], []
    tech_hist = [{"role": "system", "content": TECH_SYS + notes}, {"role": "user", "content": "GD: Describe the complaint."}]
    msg = tech_chat(tech_hist).strip()
    ending = "capped"
    for _ in range(max_turns):
        r = gd_turn.run_turn(msg, category, model, history, finder=finder, chat_fn=gd_chat, store=store, usage_fn=usage_fn)
        spent = spent_fn() if spent_fn else spent + cost(r.get("usage"))
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": r["reply"]}]
        gd_replies.append(r["reply"])
        shown.append(json.dumps(store["gd_case"].get("picked") or {}) + json.dumps(store["gd_case"].get("part_pages") or {}))
        if r["mode"] == "closed":
            ending = "closed"
            break
        if spent >= max_usd * 0.8:  # stop early: tech + referee + judge calls still to come
            ending = "budget"
            break
        ref = _json(referee_chat([{"role": "system", "content": REFEREE_SYS},
                                  {"role": "user", "content": f"ANSWER KEY:\n{key}\n\nGD REPLY:\n{r['reply']}"}])) or {}
        bench = ""
        if ref.get("repair_directed"):
            bench = ("\n(Bench: you did that repair. Result: the complaint is gone, the unit works.)" if ref.get("matches_fix")
                     else "\n(Bench: you did that repair. Result: the complaint is still there, same as before.)")
        tech_hist += [{"role": "assistant", "content": msg}, {"role": "user", "content": "GD: " + r["reply"] + bench}]
        msg = tech_chat(tech_hist).strip()
    transcript = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    verdict = _json(judge_chat([{"role": "system", "content": JUDGE_SYS},
                                {"role": "user", "content": f"ANSWER KEY:\n{key}\n\nTRANSCRIPT:\n{transcript}"}])) or {"judge_error": True}
    if spent_fn:
        spent = spent_fn()
    verdict.update({"harness_ending": ending, "gd_turns": len(gd_replies), "usd": round(spent, 4),
                    "invented_numbers": invented_numbers(gd_replies, "\n".join(shown)),
                    "pass_eligible": ending == "closed"})
    return verdict, history, store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-usd", type=float, required=True, help="hard stop for this case")
    ap.add_argument("--chase-ok", action="store_true", help="Chase approved this live run")
    a = ap.parse_args()
    if not a.chase_ok:
        sys.exit("Refusing: live LLM run needs Chase's OK (--chase-ok) and a dollar cap (--max-usd).")
    import gd_llm
    import gd_pages

    total = {"usd": 0.0}

    def chat(messages, max_tokens=600, effort="low"):
        out = gd_llm.complete_chat(messages, temperature=0.3, max_tokens=max_tokens, secret_fn=os.environ.get,
                                   reasoning_effort=effort, providers=[gd_llm.PROVIDER_XAI])
        total["usd"] += cost(gd_llm.last_usage())
        return out
    case_text = open([os.path.join(RC_DIR, f) for f in os.listdir(RC_DIR) if f.startswith(a.case + "-") and f.endswith(".md")][0]).read()
    category, model = UNITS[a.case]
    verdict, history, store = run_case(case_text, category, model, finder=gd_pages.LibraryPageFinder(),
                                       gd_chat=chat, tech_chat=chat, referee_chat=chat, judge_chat=chat,
                                       max_usd=a.max_usd, usage_fn=gd_llm.last_usage, spent_fn=lambda: total["usd"])
    os.makedirs(a.out, exist_ok=True)
    json.dump({"verdict": verdict, "history": history, "state": store["gd_case"]["state"]},
              open(os.path.join(a.out, f"{a.case}.json"), "w"), indent=1, default=str)
    print(json.dumps(verdict))


if __name__ == "__main__":
    main()
