"""Warranty story from the stored case state (branch fresh-core).

Pure assembly: every line comes from a field the brain stored (with the tech's own words as quotes) or from the
tech's first message. No regex picks lines out of the chat, and nothing is cut short.
"""
from __future__ import annotations


def warranty_story(case: dict, history: list = None, model_text: str = "") -> str:
    case = case or {}
    st = case.get("state") or {}
    if (st.get("story") or "").strip():
        return st["story"].strip()
    first_user = next(((m.get("content") or "").strip() for m in (history or []) if m.get("role") == "user"
                       and (m.get("content") or "").strip()), "") or case.get("complaint", "")
    if not first_user and not st:
        return "No session recorded."
    unit = (case.get("unit") or {}).get("model_text") or model_text or "not recorded"
    facts = st.get("facts") or []
    tests = "\n".join(f"- {f['item']}: {f.get('value', '')}" + (f' (tech: "{f["quote"]}")' if f.get("quote") else "")
                      for f in facts) or "None recorded."
    rep = st.get("repair") or {}
    if rep.get("done"):
        corr = (rep.get("what") or "Repair recorded") + (f' (tech: "{rep["quote"]}")' if rep.get("quote") else "") + \
               (" - verified working." if rep.get("verified") else " - not yet verified.")
    else:
        corr = "OPEN - no correction recorded in this session."
    return "\n".join([
        f"UNIT: {unit}", "",
        "1. CUSTOMER COMPLAINT", first_user or "Not recorded.", "",
        "2. TESTS AND READINGS (as the tech reported them)", tests, "",
        "3. CAUSE", st.get("cause") or "Not determined in this session.", "",
        "4. CORRECTION", corr,
    ])
