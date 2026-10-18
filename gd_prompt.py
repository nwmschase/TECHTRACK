"""Prompt for Guided Diagnostics (branch fresh-core).

Only Chase's two approved rules, the plain guidance he kept, and the state-block format.
No other rule is written here; anything else is PROPOSED in FIX-PLAN.md and needs Chase's OK first.

Message order each turn (stable text first, so the provider can cache it):
  1. system: rules + guidance + state format             (same every turn)
  2. system: the unit as typed, the picked manual(s), table of contents, the selected pages,
             the pages not shown (labels only), the case state so far, the running summary
  3. the last HISTORY_TURNS exchanges verbatim
  4. the tech's new message
"""
from __future__ import annotations

import json

HISTORY_TURNS = 6  # exchanges (tech + GD) kept word for word; older ones live in the brain's running summary

RULES = """You are TechTrack Guided Diagnostics. You help an RV service tech find and fix a fault, one step at a time.

RULE 1 - Library docs first, relevant pages only.
Work from the manual pages given to you below. When the next step needs a part's pages you do not have, name that part in
next_part_to_fetch and its pages will be fetched. If the library has nothing for this unit, say so; you may ask for a web
lookup with web_lookup. If neither the docs nor the web cover it, say you don't know. You never invent specs, readings,
part numbers, page numbers or phone numbers: you look them up or say you don't know.

RULE 2 - Verify the complaint with one quick question at the start.
On your first reply, ask once whether the tech has seen the complaint happen. Accept their answer as given: "yes", or
"no, it's actually X" (then X is the complaint). Record it and move on. Do not ask again and do not question their answer."""

GUIDANCE = """How to work (guidance):
- Don't re-ask a reading or result the tech already gave; it is listed under CASE STATE.
- Put the doc and page on every step, like [Furrion FCR10 Troubleshooting, p.25]. A step that comes from general
  trade knowledge instead of a page says [General trade knowledge].
- For an OEM call, give the phone number printed in the manual pages you have. If no page shows one, say so.
- Spell out physical steps in order, e.g. "power off, unplug X and Y, join them, insulate, power on".
- When the tech reports the fix (a replaced part, or an adjustment, calibration, realign or reset that cleared it), ask
  them to run the unit once to confirm; when they confirm it works, close the job in one short line."""

STATE_FORMAT = """After your reply to the tech, end with exactly one state block:
<state>{"complaint_verified": "yes|no|not_asked", "complaint_quote": "", "complaint_actual": "",
"facts": [{"item": "", "value": "", "quote": ""}], "fault_code": "", "pending_test": "", "part_working": "",
"next_part_to_fetch": "", "web_lookup": "", "cause": "", "repair": {"done": false, "verified": false, "what": "", "quote": ""},
"cited": [{"doc_id": "", "page": ""}], "summary": "", "closed": false}</state>
Only include fields that changed this turn (always include summary and cited). Quotes are the tech's exact words.
The tech never sees the state block."""

SYSTEM = "\n\n".join([RULES, GUIDANCE, STATE_FORMAT])


def _pages_block(title, pages):
    if not pages:
        return ""
    parts = [f"=== {title} ==="]
    for p in pages:
        parts.append(f"--- [{p.label()}] ({p.kind}{'; ' + p.reason if p.reason else ''}) ---\n{p.text.strip()}")
    return "\n".join(parts)


def context_block(*, category, model_text, picked, toc, pages, not_shown, state, notes=()):
    lines = [f"UNIT (as the tech typed it): category={category or '-'}; model={model_text or '-'}"]
    if picked is not None and picked.found:
        lines.append("MANUALS PICKED FROM THE SHOP LIBRARY: " + "; ".join(f"{m['title']} ({m['doc_id']})" for m in picked.manuals))
    else:
        lines.append("MANUALS PICKED FROM THE SHOP LIBRARY: none found for this unit.")
    for n in notes:
        lines.append(n)
    body = "\n".join(lines)
    blocks = [body, _pages_block("TABLE OF CONTENTS", toc), _pages_block("SELECTED PAGES", pages)]
    if not_shown:
        blocks.append("PAGES FOUND BUT NOT SHOWN (page budget; name one in next_part_to_fetch to see it): "
                      + "; ".join(p.label() for p in not_shown))
    st = {k: v for k, v in (state or {}).items() if k != "summary"}
    blocks.append("CASE STATE SO FAR (from your earlier state blocks):\n" + json.dumps(st, ensure_ascii=False, sort_keys=True))
    if (state or {}).get("summary"):
        blocks.append("RUNNING SUMMARY OF EARLIER TURNS:\n" + state["summary"])
    return "\n\n".join(b for b in blocks if b)


def recent_history(history, turns=HISTORY_TURNS):
    msgs = [m for m in (history or []) if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()]
    return msgs[-2 * turns:] if turns else []


def build_messages(*, user_msg, history, category, model_text, picked, toc, pages, not_shown, state, notes=()):
    return ([{"role": "system", "content": SYSTEM},
             {"role": "system", "content": context_block(category=category, model_text=model_text, picked=picked, toc=toc,
                                                         pages=pages, not_shown=not_shown, state=state, notes=notes)}]
            + [{"role": m["role"], "content": m["content"]} for m in recent_history(history)]
            + [{"role": "user", "content": user_msg or ""}])
